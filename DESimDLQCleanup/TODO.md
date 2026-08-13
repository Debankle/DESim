# DLQ cleanup and error handler microservice

1. Modify queue to handle DLQ options
2. Run through once and handle errors
3. Either submit like normal or update RDB if an actual error
4. Implement cleanup process to make sure RDB, SQS and S3 are in sync