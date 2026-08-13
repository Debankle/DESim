import boto3
from botocore.exceptions import ClientError


class ParameterService:
    def __init__(self):
        self.region_name = "ap-southeast-2"
        self.client = boto3.client("ssm", region_name=self.region_name)

        self.db_host = self.get_parameter("/nXXXXXXXX/desim-db-host")
        self.db_port = self.get_parameter("/nXXXXXXXX/desim-db-port")
        self.db_name = self.get_parameter("/nXXXXXXXX/desim-db-name")
        self.sim_bucket = self.get_parameter("/nXXXXXXXX/desim-sims")
        self.cognito_client_id = self.get_parameter(
            "/nXXXXXXXX/desim-cognito-client-id"
        )
        self.cognito_user_pool_id = self.get_parameter(
            "/nXXXXXXXX/desim-cognito-user-pool-id"
        )
        self.sqs_queue_url = self.get_parameter("/nXXXXXXXX/desim-sqs-queue-url")
        self.dlq_queue_url = self.get_parameter("/nXXXXXXXX/desim-dlq-queue-url")

    def get_parameter(self, parameter_name) -> str:
        try:
            response = self.client.get_parameter(Name=parameter_name)
            parameter = response["Parameter"]["Value"]
            return parameter
        except ClientError as e:
            raise e
