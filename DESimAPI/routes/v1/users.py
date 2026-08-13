from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from models import users
from models.exceptions import (
    CognitoError,
    InvalidParameter,
    InvalidPassword,
    RateLimitExceeded,
    UserAlreadyExists,
    UserNotFound,
)
from routes.v1.api_helpers import (
    PaginationParams,
    SortParams,
    UserFilterParams,
    apply_query_features,
    get_admin_pagination_params,
    get_user_filter_params,
    get_user_sort_params,
)
from routes.v1.schemas import (
    ChallengeResponse,
    Confirm,
    Delete,
    Login,
    MFASetup,
    MFAVerify,
    Register,
    UpdateUser,
    User,
)
from utils.security import get_current_user, require_admin

user_router = APIRouter()

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdminUser = Annotated[User, Depends(require_admin)]


@user_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: Register):
    try:
        result = users.register_user(req.username, req.password, req.email)
        return {
            "message": "Registered. Check email for confirmation.",
            "cognito": result,
        }
    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists"
        )
    except InvalidPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password does not meet policy",
        )
    except InvalidParameter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parameter"
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.post("/confirm", status_code=status.HTTP_200_OK)
async def confirm(req: Confirm):
    try:
        users.confirm_user(req.username, req.confirmation_code)
        return {"message": "User confirmed successfully!"}
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except InvalidParameter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad parameters"
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.post("/login", status_code=status.HTTP_200_OK)
async def login(req: Login):
    try:
        res = users.authenticate_user(req.username, req.password)
        if "ChallengeName" in res:
            print(res)
            return {
                "challenge_name": res["ChallengeName"],
                "session": res.get("Session"),
                "challenge_parameters": res.get("ChallengeParameters", {}),
            }
        return {
            "ID Token": res["AuthenticationResult"]["IdToken"],
            "Access Token": res["AuthenticationResult"]["AccessToken"],
        }
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except InvalidPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password"
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.post("/challenge-response", status_code=status.HTTP_200_OK)
async def challenge_response(req: ChallengeResponse):
    try:
        res = users.mfa_challenge_response(
            req.username, req.session, req.challenge_response
        )
        if "AuthenticationResult" in res:
            return {
                "ID Token": res["AuthenticationResult"]["IdToken"],
                "Access Token": res["AuthenticationResult"]["AccessToken"],
            }
        return {
            "challenge_name": res.get("ChallengeName"),
            "session": res.get("Session"),
            "challenge_parameters": res.get("ChallengeParameters", {}),
        }
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.post("/mfa/setup", status_code=status.HTTP_200_OK)
async def setup_mfa(req: MFASetup, _: CurrentUser):
    try:
        res = users.mfa_setup(req.access_token)
        return res
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.post("/mfa/verify", status_code=status.HTTP_200_OK)
async def mfa_confirm(req: MFAVerify, _: CurrentUser):
    try:
        res = users.mfa_verify(req.access_token, req.user_code)
        return res
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.get("/me", status_code=status.HTTP_200_OK)
async def get_logged_in_user(current_user: CurrentUser):
    return current_user


@user_router.get("", status_code=status.HTTP_200_OK, response_model=List[User])
async def get_all(
    _: CurrentAdminUser,
    response: Response,
    pagination: PaginationParams = Depends(get_admin_pagination_params),
    user_sort: SortParams = Depends(get_user_sort_params),
    user_filter: UserFilterParams = Depends(get_user_filter_params),
):
    try:
        all_users = users.get_all_users()
        if all_users is None:
            raise CognitoError
        if len(all_users) > 0:
            result = apply_query_features(
                all_users,
                user_filter,
                user_sort.sort_by,
                user_sort.sort_order,
                pagination.page,
                pagination.per_page,
            )
            response.headers["X-Total-Count"] = str(result["total_items"])
            response.headers["X-Page"] = str(result["page"])
            response.headers["X-Per-Page"] = str(result["per_page"])
            response.headers["X-Total-Pages"] = str(result["total_pages"])
            return result["items"]
        return []
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.patch("/me", status_code=status.HTTP_200_OK)
async def update_user(req: UpdateUser, _: CurrentUser):
    try:
        users.update_user(
            access_token=req.access_token,
            email=req.email,
            current_password=req.current_password,
            new_password=req.new_password,
        )
        return {"message": "User updated successfully"}
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already in use"
        )
    except InvalidPassword as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid password: {e}"
        ) from e
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(req: Delete, _: CurrentUser):
    try:
        users.delete_user(req.access_token)
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.get("/username/{username}", status_code=status.HTTP_200_OK)
async def get_user_by_username(username: str):
    try:
        user = users.get_user_by_username(username)
        return user
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User sub not found"
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@user_router.get("/{user_sub}", status_code=status.HTTP_200_OK)
async def get_user_by_sub(user_sub: UUID):
    try:
        user = users.get_user_by_sub(str(user_sub))
        return user
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User sub not found"
        )
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    except CognitoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cognito error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e
