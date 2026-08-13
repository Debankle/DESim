from db.db import DBService
from simulate.queue import DLQHandler
from utils import (CognitoService, ParameterService, S3Service, SecretsService,
                   SQSService, register_service)

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

    dlq = SQSService(parameters.dlq_queue_url)

    register_service("dlq", dlq)

    cognito = CognitoService(
        parameters.cognito_user_pool_id,
        parameters.cognito_client_id,
        secrets.cognito_client_secret,
    )

    register_service("cognito", cognito)

    dlq_handler = DLQHandler()
    dlq_handler.run()

    register_service("dlq_handler", dlq_handler)
