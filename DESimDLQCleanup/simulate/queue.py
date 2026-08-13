import threading
import time

import h5py
import psutil
from botocore.exceptions import ClientError

from models import simulate
from models.exceptions import SQSError
from simulate.equations import DiffusionAdvection, Heat2D, Wave2D
from simulate.theta_solver import ThetaMethod
from utils import S3Service, SQSService, get_service


class SimJobNotFound(Exception):
    pass


class SimJobFailed(Exception):
    pass


class ServiceFailed(Exception):
    pass


class DLQHandler:
    def __init__(self):
        self.dlq = get_service("dlq", SQSService)
        self.s3 = get_service("s3", S3Service)
        self.total_units = psutil.virtual_memory().total / (1024**2) * 0.95
        self.stop = False

    def _heartbeat(self, receipt, hb_stop):
        while not hb_stop.wait(30):
            try:
                self.dlq.extend_visibility(receipt)
            except ClientError:
                break

    def run(self):
        while not self.stop:
            try:
                receipt, job = self.dlq.receive_job()
            except ClientError:
                continue

            if not job:
                time.sleep(5)
                continue

            uuid = job["uuid"]
            size = int(job["size"])

            if size > self.total_units:
                simulate.update_simulation_status(uuid, "failed", message="too big")
                try:
                    self.dlq.delete_job(receipt)
                except SQSError:
                    pass
                continue

            try:
                self.simulation(receipt, uuid)
            except Exception as e:
                print(f"Error running {uuid}: {e}")

    def simulation(self, receipt, uuid):
        hb_stop = None

        try:
            job = simulate.get_simulation(uuid)
            if job is None:
                raise SimJobNotFound
            if job.status in ("complete", "failed"):
                self.dlq.delete_job(receipt)
                return

            hb_stop = threading.Event()
            hb_thread = threading.Thread(
                target=self._heartbeat, args=(receipt, hb_stop), daemon=True
            )
            hb_thread.start()

            params = job.params

            match job.equation:
                case "heat":
                    equation = Heat2D(
                        params["nx"],
                        params["ny"],
                        params["dx"],
                        params["dy"],
                        params["alpha"],
                        params["ic"],
                        params["bc"],
                    )
                case "wave":
                    equation = Wave2D(
                        params["nx"],
                        params["ny"],
                        params["dx"],
                        params["dy"],
                        params["c"],
                        params["ic"],
                        params["bc"],
                        params["ic_v"],
                    )
                case "diffusionadvection":
                    equation = DiffusionAdvection(
                        params["nx"],
                        params["ny"],
                        params["dx"],
                        params["dy"],
                        params["D"],
                        params["v"],
                        params["ic"],
                        params["bc"],
                    )
                case _:
                    raise SimJobFailed

            simulate.update_simulation_status(uuid, "running")

            solver = ThetaMethod(
                equation,
                params["theta"],
                params["dt"],
                params["tol"],
                params["maxiters"],
                params["linesearching"],
            )

            u = equation.initial_condition()
            components, nx, ny = u.shape
            steps = int(params["steps"])

            with h5py.File(f"/tmp/{uuid}.h5", "w") as f:
                dest = f.create_dataset(
                    f"{uuid}",
                    shape=(steps + 1, components, nx, ny),
                    maxshape=(steps + 1, components, nx, ny),
                    dtype="float64",
                    chunks=True,
                    compression="gzip",
                )
                dest[0] = u

                for step in range(1, steps + 1):
                    u = solver.step(u)
                    dest[step] = u

            self.s3.upload_sim(uuid)
            simulate.complete_simulation(uuid)

        except SimJobFailed:
            simulate.update_simulation_status(uuid, "failed")
        except Exception as e:
            simulate.update_simulation_status(uuid, "failed", message=str(e))
        finally:
            self.dlq.delete_job(receipt)
            if hb_stop:
                hb_stop.set()
