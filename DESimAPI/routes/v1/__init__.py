from fastapi import APIRouter

from .oauth2 import oauth2_router
from .simulate import simulate_router
from .users import user_router

v1_router = APIRouter()
v1_router.include_router(user_router, prefix="/users")
v1_router.include_router(simulate_router, prefix="/simulations")
v1_router.include_router(oauth2_router, prefix="/oauth2")
