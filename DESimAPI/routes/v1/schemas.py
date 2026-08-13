import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class User(BaseModel):
    id: UUID
    username: Optional[str] = None
    email: Optional[str] = None
    isadmin: bool = False


class UpdateUser(BaseModel):
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    access_token: str


class Register(BaseModel):
    username: str
    password: str
    email: str


class Login(BaseModel):
    username: str
    password: str


class Confirm(BaseModel):
    username: str
    confirmation_code: str


class Simulation(BaseModel):
    simulation_id: UUID
    username: str
    equation: str
    theta: float
    params: dict
    status: str
    submit_time: datetime.datetime
    complete_time: Optional[datetime.datetime] = None
    private: bool
    message: Optional[str] = None


class ChallengeResponse(BaseModel):
    username: str
    session: str
    challenge_response: str


class MFASetup(BaseModel):
    access_token: str


class MFAVerify(BaseModel):
    access_token: str
    user_code: str


class Delete(BaseModel):
    access_token: str
