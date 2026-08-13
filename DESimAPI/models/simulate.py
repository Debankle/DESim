import datetime
from typing import List, NoReturn

import psycopg
from botocore.exceptions import ClientError
from psycopg.types.json import Json

from db.db import DBService
from models.exceptions import (DBError, DBFailed, DBReturnedNoneError,
                               DuplicateEntry, InvalidData, S3Error, SQSError)
from routes.v1.schemas import Simulation
from utils import S3Service, SQSService, get_service


def _map_psycopg_error(e: psycopg.Error) -> NoReturn:
    if isinstance(e, (psycopg.OperationalError, psycopg.InterfaceError)):
        raise DBFailed(str(e))

    if isinstance(e, psycopg.IntegrityError):
        cause = getattr(e, "__cause__", None)

        if isinstance(cause, psycopg.errors.UniqueViolation):
            raise DuplicateEntry(str(e)) from e
        elif isinstance(
            cause, (psycopg.errors.NotNullViolation, psycopg.errors.CheckViolation)
        ):
            raise InvalidData(str(e)) from e
        else:
            raise DBError(str(e)) from e

    if isinstance(e, psycopg.DataError):
        raise InvalidData(str(e)) from e

    raise DBError(str(e)) from e


def add_job(username, equation, theta, params, private):
    db = get_service("db", DBService)
    sqs = get_service("sqs", SQSService)
    try:
        res = db.fetchone(
            """
            insert into simulations
            (username, equation, theta, params, status, submit_time, private)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning simulation_id
            """,
            (
                username,
                equation,
                theta,
                Json(params.dict()),
                "queued",
                datetime.datetime.now(),
                private,
            ),
        )
        if res is None:
            raise DBReturnedNoneError
        sim_id = str(res["simulation_id"])
        size = params.estimate_size()
        sqs.upload_simulation(sim_id, size)
    except psycopg.Error as e:
        _map_psycopg_error(e)
    except ClientError as e:
        raise SQSError(str(e))

    return sim_id


def get_all_user_simulation_jobs(username) -> List[Simulation]:
    db = get_service("db", DBService)
    try:
        res = db.fetchall("select * from simulations where username=%s", (username,))
        sims = [Simulation(**row) for row in res]
        return sims
    except psycopg.Error as e:
        _map_psycopg_error(e)


def get_all_simulations() -> List[Simulation]:
    db = get_service("db", DBService)
    try:
        res = db.fetchall("select * from simulations")
        sims = [Simulation(**row) for row in res]
        return sims
    except psycopg.Error as e:
        _map_psycopg_error(e)


def get_public_simulations() -> List[Simulation]:
    db = get_service("db", DBService)
    try:
        res = db.fetchall("select * from simulations where private=%s", (False,))
        print(res)
        sims = [Simulation(**row) for row in res]
        return sims
    except psycopg.Error as e:
        _map_psycopg_error(e)


def get_simulation(sim_id) -> Simulation:
    db = get_service("db", DBService)
    try:
        res = db.fetchone("select * from simulations where simulation_id=%s", (sim_id,))
        if res is not None:
            return Simulation(**res)
        raise DBReturnedNoneError
    except psycopg.Error as e:
        _map_psycopg_error(e)


def delete_simulation(sim_id):
    db = get_service("db", DBService)
    try:
        db.execute("delete from simulations where simulation_id=%s", (sim_id,))
    except psycopg.Error as e:
        _map_psycopg_error(e)


def fetch_presigned_url(sim_id):
    s3 = get_service("s3", S3Service)
    try:
        return s3.presigned_url(sim_id)
    except ClientError as e:
        raise S3Error(str(e))


def update_simulation_status(sim_id, status):
    db = get_service("db", DBService)
    try:
        db.execute(
            "update simulations set status=%s where simulation_id=%s", (status, sim_id)
        )
    except psycopg.Error as e:
        _map_psycopg_error(e)
