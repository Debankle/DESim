from typing import Any, NoReturn
from uuid import UUID

from botocore.exceptions import ClientError

from models.exceptions import (CognitoError, InvalidParameter, InvalidPassword,
                               RateLimitExceeded, UserAlreadyExists,
                               UserNotFound)
from routes.v1.schemas import User
from utils import CognitoService, get_service


def _map_cognito_error(e: ClientError) -> NoReturn:
    code = e.response.get("Error", {}).get("Code", "")
    message = e.response.get("Error", {}).get("Message", "")
    if code in ("UsernameExistsException"):
        raise UserAlreadyExists(message)
    elif code in ("InvalidPasswordException"):
        raise InvalidPassword(message)
    elif code in ("TooManyRequestsException", "LimitExceededException"):
        raise RateLimitExceeded(message)
    elif code in (
        "InvalidParameterException",
        "ExpiredCodeException",
        "CodeMismatchException",
    ):
        raise InvalidParameter(message)
    elif code in ("UserNotFoundException"):
        raise UserNotFound(message)

    raise CognitoError(message)


def _cognito_user_to_model(cognito_user: dict) -> User:
    attrs = {a["Name"]: a["Value"] for a in cognito_user.get("Attributes", [])}
    return User(
        id=UUID(attrs.get("sub")),
        username=cognito_user["Username"],
        email=attrs.get("email"),
        isadmin=(
            any(g["GroupName"] == "admin" for g in cognito_user.get("Groups", []))
            if "Groups" in cognito_user
            else False
        ),
    )


def register_user(username, password, email):
    cognito = get_service("cognito", CognitoService)
    try:
        return cognito.signup(username, password, email)
    except ClientError as e:
        _map_cognito_error(e)


def confirm_user(username, code):
    cognito = get_service("cognito", CognitoService)
    try:
        return cognito.confirm(username, code)
    except ClientError as e:
        _map_cognito_error(e)


def authenticate_user(username, password) -> dict[str, Any]:
    cognito = get_service("cognito", CognitoService)
    try:
        return cognito.authenticate(username, password)
    except ClientError as e:
        _map_cognito_error(e)


def get_user_by_sub(user_sub: str):
    cognito = get_service("cognito", CognitoService)
    try:
        user_dict = cognito.get_user_by_sub(str(user_sub))
        return _cognito_user_to_model(user_dict)
    except KeyError:
        raise UserNotFound(user_sub)
    except ClientError as e:
        _map_cognito_error(e)


def update_user(
    access_token: str, email=None, current_password=None, new_password=None
):
    cognito = get_service("cognito", CognitoService)
    if email:
        try:
            cognito.update_email(access_token, email)
        except ClientError as e:
            _map_cognito_error(e)
    if new_password and current_password:
        try:
            cognito.update_password(access_token, current_password, new_password)
        except ClientError as e:
            _map_cognito_error(e)


def get_all_users():
    cognito = get_service("cognito", CognitoService)
    try:
        user_dicts = cognito.list_all_users()
        return [_cognito_user_to_model(u) for u in user_dicts]
    except ClientError as e:
        _map_cognito_error(e)


def delete_user(access_token):
    cognito = get_service("cognito", CognitoService)
    try:
        cognito.delete_user(access_token)
    except ClientError as e:
        _map_cognito_error(e)


def mfa_setup(access_token):
    cognito = get_service("cognito", CognitoService)
    try:
        return cognito.associate_software_token(access_token)
    except ClientError as e:
        _map_cognito_error(e)


def mfa_verify(access_token, user_code):
    cognito = get_service("cognito", CognitoService)
    try:
        res = cognito.verify_software_token(access_token, user_code)
        if res.get("Status") == "SUCCESS":
            return cognito.enable_mfa(access_token)
        raise CognitoError(str(res))
    except ClientError as e:
        _map_cognito_error(e)


def mfa_challenge_response(username, session, challenge_response):
    cognito = get_service("cognito", CognitoService)
    try:
        return cognito.respond_to_auth_challenge(username, session, challenge_response)
    except ClientError as e:
        _map_cognito_error(e)
