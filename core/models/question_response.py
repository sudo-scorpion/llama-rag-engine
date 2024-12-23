from pydantic import BaseModel
from typing import List, Dict, Optional

class QuestionResponse(BaseModel):
    question: str
    answer: str
    relevance_score: Optional[float] = None
    confidence_score: Optional[float] = None
    contexts: Optional[list] = None
    response_time: Optional[float] = None
    error: Optional[str] = None