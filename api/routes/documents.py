from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from core.rag.rag_engine import RAGEngine
from ..dependencies import get_rag_system, verify_auth
import os
from loguru import logger

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),
    rag_engine: RAGEngine = Depends(get_rag_system),
    authenticated: bool = Depends(verify_auth)
):
    if not authenticated:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    temp_path = None
    try:
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        num_chunks = await rag_engine.process_document(temp_path)
        return {
            "message": "Document processed successfully",
            "chunks_processed": num_chunks
        }
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)