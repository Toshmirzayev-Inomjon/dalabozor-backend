"""v1 API — barcha routerlarni yig'adi."""
from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, collector, farmer, payment, restaurant

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(ai.router)
api_router.include_router(farmer.router)
api_router.include_router(restaurant.router)
api_router.include_router(collector.router)
api_router.include_router(payment.router)
api_router.include_router(admin.router)
