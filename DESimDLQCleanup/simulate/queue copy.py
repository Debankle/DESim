import threading
import time

import h5py
import psutil
from botocore.exceptions import ClientError

from models import simulate
from models.exceptions import DBError, DBFailed, S3Error, SQSError
from simulate.equations import DiffusionAdvection, Heat2D, Wave2D
from simulate.theta_solver import ThetaMethod
from utils import S3Service, SQSService, get_service


class SimJobNotFound(Exception):
    pass


class SimJobFailed(Exception):
    pass


class ServiceFailed(Exception):
    pass


class ResourceManager:
    def __init__(self, total_units):
        self.total = total_units
        self.available = total_units
        self.cond = threading.Condition()

    def reserve(self, units, timeout=None):
        with self.cond:
            end = None if timeout is None else time.time() + timeout
            while self.available < units:
                if timeout is None:
                    self.cond.wait()
                else:
                    if end is not None:
                        rem = end - time.time()
                        if rem <= 0:
                            return False
                        self.cond.wait(rem)
            self.available -= units
            return True

    def release(self, units):
        with self.cond:
            self.available = min(self.total, self.available + units)
            self.cond.notify_all()

    def get_available(self):
        with self.cond:
            return self.available


class SimulationQueue:
    def __init__(self):
        self.dlq = get_service("dlq", SQSService)
        self.s3 = get_service("s3", S3Service)
        self.total_units = psutil.virtual_memory().total / (1024**2) * 0.95
        self.resource_mgr = ResourceManager(self.total_units)
        self.stop = False

        self.dispatcher_thread = threading.Thread(target=self.dispatcher)
        self.dispatcher_thread.start()

    def dispatcher(self):
        while not self.stop:
            with self.resource_mgr.cond:
                while self.resource_mgr.available < 1:
                    self.resource_mgr.cond.wait()

            try:
                receipt, job = self.dlq.receive_job()
            except ClientError:
                continue

            if not job:
                continue
            uuid = job["uuid"]
            size = int(job["size"])

            if size > self.resource_mgr.total:
                self.dlq.release_job(receipt)
                continue

            ok = self.resource_mgr.reserve(size, timeout=0)
            if not ok:
                try:
                    self.dlq.release_job(receipt)
                except ClientError:
                    continue
                continue

            t = threading.Thread(
                target=self.simulation, args=(receipt, uuid, size), daemon=True
            )
            t.start()

    def _heartbeat(self, receipt, hb_stop):
        while not hb_stop.wait(30):
            try:
                self.dlq.extend_visibility(receipt)
            except ClientError:
                break

    def simulation(self, receipt, uuid, size):
        hb_stop = None
        hb_thread = None

        try:
            job = simulate.get_simulation(uuid)
            if job is None:
                raise SimJobNotFound
            if job.status in ("complete", "failed"):
                self.dlq.delete_job(receipt)
        except DBFailed:
            self.dlq.release_job(receipt)
            self.resource_mgr.release(size)
            return
        except DBError:
            self.dlq.delete_job(receipt)
            self.resource_mgr.release(size)
            return
        except SimJobNotFound:
            self.dlq.delete_job(receipt)
            self.resource_mgr.release(size)
            return
        except Exception:
            self.resource_mgr.release(size)
            return

        try:
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

            try:
                simulate.update_simulation_status(uuid, "running")
            except DBFailed:
                raise ServiceFailed

            try:
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
                    destination = f.create_dataset(
                        f"{uuid}",
                        shape=(steps + 1, components, nx, ny),
                        maxshape=(steps + 1, components, nx, ny),
                        dtype="float64",
                        chunks=True,
                        compression="gzip",
                    )

                    destination[0] = u

                    for step in range(1, int(params["steps"]) + 1):
                        u = solver.step(u)
                        destination[step] = u
            except Exception:
                raise SimJobFailed

            try:
                self.s3.upload_sim(uuid)
            except S3Error:
                simulate.update_simulation_status(uuid, "queued")
                self.dlq.release_job(receipt)
                raise ServiceFailed

            try:
                simulate.update_simulation_status(uuid, "complete")
            except DBFailed:
                raise ServiceFailed
            except DBError:
                self.dlq.release_job(receipt)
                raise ServiceFailed

            try:
                self.dlq.delete_job(receipt)
            except SQSError:
                raise ServiceFailed

        except ServiceFailed:
            pass
        except SimJobFailed:
            simulate.update_simulation_status(uuid, "failed")
            self.dlq.delete_job(receipt)
        except Exception:
            simulate.update_simulation_status(uuid, "queued")
            self.dlq.release_job(receipt)
        finally:
            if hb_stop is not None:
                hb_stop.set()
            if hb_thread is not None:
                hb_thread.join()
            self.resource_mgr.release(size)
