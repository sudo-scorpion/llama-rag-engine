# api/routers/document.py
from fastapi import APIRouter, File, UploadFile, HTTPException
from typing import Dict, List
import tempfile
import os
from core.document_processor.pdf_processor import PDFProcessor

router = APIRouter(prefix="/documents", tags=["documents"])
processor = PDFProcessor()

@router.post("/analyze")
async def analyze_document(file: UploadFile = File(...)) -> Dict:
    """Analyze a document for tables and content structure."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
        
        try:
            analysis = processor.analyze_document(tmp_path)
            return analysis
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            os.unlink(tmp_path)

@router.post("/process")
async def process_document(file: UploadFile = File(...)) -> Dict[str, List]:
    """Process a document and return chunks."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
        
        try:
            chunks = processor.process_document(tmp_path)
            return {"chunks": chunks}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            os.unlink(tmp_path)