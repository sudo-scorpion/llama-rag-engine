from pydantic import BaseModel
from typing import List, Dict, Optional

class QuestionRequest(BaseModel):
    question: str
    
    def to_dict(self) -> Dict:
        return self.model_dump()