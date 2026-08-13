import json

import boto3
from botocore.exceptions import ClientError


class SecretsService:
    def __init__(self):
        self.region_name = "ap-southeast-2"
        self.client = boto3.client(
            service_name="secretsmanager", region_name=self.region_name
        )

        self.db_credentials = json.loads(
            self.get_secret("nXXXXXXXX/desim-db-credentials")
        )
        self.cognito_client_secret = self.get_secret(
            "nXXXXXXXX/desim-cognito-client-secret"
        )

    def get_secret(self, secret_name):
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret = response.get("SecretString")
            return secret
        except ClientError as e:
            raise e
