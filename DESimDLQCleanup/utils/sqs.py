import json

import boto3


class SQSService:
    def __init__(self, queue_url):
        self.queue_url = queue_url
        self.region_name = "ap-southeast-2"

        self.client = boto3.client("sqs", region_name=self.region_name)

    def receive_job(self):
        receive_response = self.client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            MessageAttributeNames=["All"],
        )
        messages = receive_response.get("Messages", [])
        if not messages:
            return None, None
        message = messages[0]
        body = json.loads(message["Body"])
        return message["ReceiptHandle"], body

    def delete_job(self, receipt_handle):
        self.client.delete_message(
            QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
        )

    def release_job(self, receipt_handle):
        self.client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=10,
        )

    def extend_visibility(self, receipt_handle):
        self.client.change_message_visibility(
            QueueUrl=self.queue_url, ReceiptHandle=receipt_handle, VisibilityTimeout=60
        )

    def upload_simulation(self, simulation_uuid, sim_size):
        self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps({"uuid": simulation_uuid, "size": sim_size}),
        )
