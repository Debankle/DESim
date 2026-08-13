# https://canvas.qut.edu.au/courses/20367/pages/practical-s3-blob-storage-service-python?module_item_id=2063601
import os

import boto3


class S3Service:
    def __init__(self, sim_bucket: str):
        self.sim_bucket = sim_bucket
        self.region_name = "ap-southeast-2"

        self.client = boto3.client("s3", region_name=self.region_name)

    def upload_sim(self, uuid: str):
        file_path = f"/tmp/{uuid}.h5"
        object_key = f"{uuid}.h5"
        with open(file_path, "rb") as f:
            response = self.client.put_object(
                Bucket=self.sim_bucket, Key=object_key, Body=f
            )
        os.remove(file_path)
        return response

    def presigned_url(self, uuid: str) -> str:
        object_key = f"{uuid}.h5"
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.sim_bucket, "Key": object_key},
            ExpiresIn=3600,
        )

    def delete_sim(self, uuid: str):
        return self.client.delete_object(Bucket=self.sim_bucket, Key=f"{uuid}.h5")
