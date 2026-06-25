from pydantic import BaseModel
from typing import Dict, List

class EmbeddingRequest(BaseModel):
    model: str
    task: str
    dimensions: int
    input: int

class EmbeddingData(BaseModel):
    object: str
    index: int
    embedding: List[float]
    
class EmbeddingResponse(BaseModel):
    model: str
    object: str 
    usage: Dict[str, int]
    data: List[EmbeddingData]
    