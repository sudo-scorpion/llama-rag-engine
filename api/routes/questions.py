from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.models.question_response import QuestionResponse
from core.models.question_request import QuestionRequest
from core.rag.rag_engine import RAGEngine
from api.dependencies import get_rag_system, verify_auth
from loguru import logger

router = APIRouter(prefix="/questions", tags=["questions"])

@router.post("/ask", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    rag_engine: RAGEngine = Depends(get_rag_system),
    authenticated: bool = Depends(verify_auth)
):
    if not authenticated:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        return await rag_engine.answer_question(request.question)
    except Exception as e:
        logger.error(f"Error answering question: {e}")
        raise HTTPException(status_code=500, detail=str(e))