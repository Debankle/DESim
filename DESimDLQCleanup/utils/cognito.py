import base64
import hashlib
import hmac
import urllib.parse
from typing import Any, List

import boto3
import jwt
import requests
from jwt import PyJWKClient


class CognitoService:
    # NOTE: This is not seucre. Not using access tokens and not authenticating users with password for stuff
    # If ID token is stolen most of this can be run. Oh well lmao

    def __init__(self, user_pool_id, client_id, client_secret):
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.region_name = "ap-southeast-2"

        self.jwks_url = f"https://cognito-idp.{self.region_name}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        self.jwk_client = PyJWKClient(self.jwks_url)

        self.client = boto3.client("cognito-idp", region_name=self.region_name)

    def _secret_hash(self, username):
        message = bytes(username + self.client_id, "utf-8")
        key = bytes(self.client_secret, "utf-8")
        return base64.b64encode(
            hmac.new(key, message, digestmod=hashlib.sha256).digest()
        ).decode()

    def verify_jwt(self, token):
        signing_key = self.jwk_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token, signing_key.key, algorithms=["RS256"], audience=self.client_id
        )
        if decoded.get("aud") != self.client_id:
            raise jwt.InvalidTokenError("Invalid token audience for id_token")
        return decoded

    def signup(self, username, password, email):
        return self.client.sign_up(
            ClientId=self.client_id,
            Username=username,
            Password=password,
            SecretHash=self._secret_hash(username),
            UserAttributes=[{"Name": "email", "Value": email}],
        )

    def confirm(self, username, confirmation_code):
        return self.client.confirm_sign_up(
            ClientId=self.client_id,
            Username=username,
            ConfirmationCode=confirmation_code,
            SecretHash=self._secret_hash(username),
        )

    def authenticate(self, username, password) -> dict[str, Any]:
        response = self.client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
                "SECRET_HASH": self._secret_hash(username),
            },
            ClientId=self.client_id,
        )
        return response

    def get_user_by_sub(self, sub: str) -> dict:
        resp = self.client.list_users(
            UserPoolId=self.user_pool_id, Filter=f'sub = "{sub}"', Limit=1
        )
        users = resp.get("Users", [])
        if not users:
            raise KeyError("user_not_found")
        return users[0]

    def list_all_users(self) -> List[dict]:
        paginator = self.client.get_paginator("list_users")
        users = []
        for page in paginator.paginate(UserPoolId=self.user_pool_id):
            users.extend(page.get("Users", []))
        return users

    def update_email(self, access_token: str, new_email: str):
        self.client.update_user_attributes(
            UserAttributes=[{"Name": "email", "Value": new_email}],
            AccessToken=access_token,
        )

    def update_password(self, access_token, current_password, new_password):
        self.client.change_password(
            AccessToken=access_token,
            PreviousPassword=current_password,
            ProposedPassword=new_password,
        )

    def delete_user(self, access_token: str):
        self.client.delete_user(AccessToken=access_token)

    def respond_to_auth_challenge(
        self,
        username: str,
        session: str,
        challenge_response: str,
    ):
        return self.client.respond_to_auth_challenge(
            ClientId=self.client_id,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=session,
            ChallengeResponses={
                "USERNAME": username,
                "SECRET_HASH": self._secret_hash(username),
                "SOFTWARE_TOKEN_MFA_CODE": challenge_response,
            },
        )

    def associate_software_token(self, access_token):
        return self.client.associate_software_token(AccessToken=access_token)

    def verify_software_token(self, access_token, user_code):
        return self.client.verify_software_token(
            AccessToken=access_token, UserCode=user_code
        )

    def enable_mfa(self, access_token):
        return self.client.set_user_mfa_preference(
            SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
            AccessToken=access_token,
        )

    def make_authorize_url(self, redirect_uri, state):
        base = f"https://desim-login.auth.ap-southeast-2.amazoncognito.com/oauth2/authorize"
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "identity_provider": "Google",
        }
        return base + "?" + urllib.parse.urlencode(params)

    def exchange_code_for_tokens(self, code, redirect_uri):
        token_url = (
            "https://desim-login.auth.ap-southeast-2.amazoncognito.com/oauth2/token"
        )
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        resp = requests.post(
            token_url,
            data=data,
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()
