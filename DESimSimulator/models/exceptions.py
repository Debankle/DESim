class AppError(Exception):
    pass


class RateLimitExceeded(AppError):
    pass


class InvalidParameter(AppError):
    pass


class CognitoError(AppError):
    pass


class UserAlreadyExists(CognitoError):
    pass


class UserNotFound(CognitoError):
    pass


class InvalidPassword(CognitoError):
    pass


class DBError(AppError):
    pass


class DBReturnedNoneError(DBError):
    pass


class DBFailed(DBError):
    pass


class InvalidData(DBError):
    pass


class DuplicateEntry(DBError):
    pass


class S3Error(AppError):
    pass


class SQSError(AppError):
    pass
