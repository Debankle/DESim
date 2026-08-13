import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from routes.v1.schemas import User
from utils import CognitoService, get_service

security = HTTPBearer(auto_error=False)


def authenticate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme",
        )

    access_token = credentials.credentials
    cognito = get_service("cognito", CognitoService)
    try:
        user_id = cognito.verify_jwt(access_token)
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}"
        )


def get_current_user(user_id: dict = Depends(authenticate_token)) -> User:
    sub = user_id.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing sub claim"
        )

    try:
        user = User(
            id=sub,
            username=user_id.get("cognito:username"),
            email=user_id.get("email"),
            isadmin="admin" in user_id.get("cognito:groups", []),
        )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User Details Not Found"
        )


def require_admin(user=Depends(get_current_user)) -> User:
    if not user.isadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user
