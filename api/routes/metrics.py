from fastapi import APIRouter, Depends, HTTPException
from core.rag.rag_engine import RAGEngine
from api.dependencies import get_rag_system, verify_auth
from core.models.metrics_response import MetricsResponse
from loguru import logger

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("", response_model=MetricsResponse)
async def get_metrics(
    rag_engine: RAGEngine = Depends(get_rag_system),
    authenticated: bool = Depends(verify_auth)
):
    if not authenticated:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        return rag_engine.get_performance_metrics()
    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))