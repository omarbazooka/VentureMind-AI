from fastapi import APIRouter

from app.api.v1.analysis import router as analysis_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.ideas import router as ideas_router
from app.api.v1.profile import router as profile_router


api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(ideas_router)
api_router.include_router(chat_router)
api_router.include_router(profile_router)
api_router.include_router(analysis_router)
