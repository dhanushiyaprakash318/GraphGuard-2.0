from fastapi import APIRouter

from app.api.routes import analytics, fabric_ops, health, predict, transactions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(predict.router, tags=["predict"])
api_router.include_router(transactions.router, tags=["transactions"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(fabric_ops.router)
