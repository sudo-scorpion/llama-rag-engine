# api/routes/health.py
from fastapi import APIRouter, Depends
from core.rag.rag_engine import RAGEngine
from api.dependencies import get_rag_system

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
async def health_check(
    rag_engine: RAGEngine = Depends(get_rag_system)
):
    return {
        "status": "healthy",
        "rag_engine": "initialized"
    }