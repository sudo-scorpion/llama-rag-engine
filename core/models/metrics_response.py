from pydantic import BaseModel
from typing import List, Dict, Optional

class MetricsResponse(BaseModel):
    avg_response_time: float
    avg_relevance_score: float
    current_temperature: float
    temperature_history: List[float]