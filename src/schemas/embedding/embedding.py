from pydantic import BaseModel
from typing import Dict, List

class EmbeddingRequest(BaseModel):
    model: str
    task: str
    dimensions: int
    input: int
    
class EmbeddingResponse(BaseModel):
    model: str
    object: str 
    usage: Dict[str, int]
    data: List[Dict]
    