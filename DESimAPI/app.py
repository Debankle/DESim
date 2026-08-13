# From week 3 tutorial https://canvas.qut.edu.au/courses/20367/pages/practical-rest-api-with-multi-container-service-architecture-python?module_item_id=2065855

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, status

from db.db import DBService
from routes.v1 import v1_router
from utils import (
    register_service,
    ParameterService,
    SecretsService,
    S3Service,
    SQSService,
    CognitoService
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    parameters = ParameterService()
    secrets = SecretsService()
    s3 = S3Service(parameters.sim_bucket)

    register_service("parameters", parameters)
    register_service("secrets", secrets)
    register_service("s3", s3)

    db = DBService(
        parameters.db_host,
        parameters.db_name,
        parameters.db_port,
        secrets.db_credentials["username"],
        secrets.db_credentials["password"],
    )

    register_service("db", db)

    sqs = SQSService(parameters.sqs_queue_url)

    register_service("sqs", sqs)

    cognito = CognitoService(
        parameters.cognito_user_pool_id,
        parameters.cognito_client_id,
        secrets.cognito_client_secret,
    )

    register_service("cognito", cognito)

    yield
    pass


app = FastAPI(
    title="Differential Equation Simulator",
    description="API for modelling differential equations",
    version="0.0.1",
    lifespan=lifespan,
)

app.include_router(v1_router, prefix="/v1")


@app.get("/", status_code=status.HTTP_200_OK)
async def serve_index():
    return


if __name__ == "__main__":
    parameters = ParameterService()
    secrets = SecretsService()
    s3 = S3Service(parameters.sim_bucket)

    register_service("parameters", parameters)
    register_service("secrets", secrets)
    register_service("s3", s3)

    db = DBService(
        parameters.db_host,
        parameters.db_name,
        parameters.db_port,
        secrets.db_credentials["username"],
        secrets.db_credentials["password"],
    )

    register_service("db", db)

    sqs = SQSService(parameters.sqs_queue_url)

    register_service("sqs", sqs)

    cognito = CognitoService(
        parameters.cognito_user_pool_id,
        parameters.cognito_client_id,
        secrets.cognito_client_secret,
    )

    register_service("cognito", cognito)

    uvicorn.run(app, host="0.0.0.0", port=3000)
