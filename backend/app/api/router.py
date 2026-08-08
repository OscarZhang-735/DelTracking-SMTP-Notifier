from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.recipients import router as recipients_router
from app.api.runs import router as runs_router
from app.api.settings import router as settings_router
from app.api.trackings import router as trackings_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(trackings_router)
api_router.include_router(recipients_router)
api_router.include_router(settings_router)
api_router.include_router(runs_router)
