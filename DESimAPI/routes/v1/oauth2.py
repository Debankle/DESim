from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from utils import CognitoService, get_service

oauth2_router = APIRouter()


@oauth2_router.get("/login/google")
def login_google():
    cognito = get_service("cognito", CognitoService)
    redirect_uri = "https://desim.cab432.com/callback"
    # redirect_uri = "https://desim.cab432.com/v1/oauth2/callback"
    url = cognito.make_authorize_url(
        redirect_uri=redirect_uri, state="googoogaagaa")
    return RedirectResponse(url)


@oauth2_router.get("/callback")
def oauth2_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    cognito = get_service("cognito", CognitoService)
    redirect_uri = "https://desim.cab432.com/callback"

    tokens = cognito.exchange_code_for_tokens(code, redirect_uri)

    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")

    if not id_token:
        raise HTTPException(status_code=400, detail="Missing ID token")

    user_id = cognito.verify_jwt(id_token)
    print("Verified user:", user_id)

    return {
        "id_token": id_token,
        "access_token": access_token,
        "user": user_id,
    }