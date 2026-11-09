from fastapi import APIRouter

from app.api.routes import analytics, health, predict, transactions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(predict.router, tags=["predict"])
api_router.include_router(transactions.router, tags=["transactions"])
api_router.include_router(analytics.router, tags=["analytics"])
