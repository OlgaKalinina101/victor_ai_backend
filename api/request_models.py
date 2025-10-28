from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from api.response_models import Message


class GeoLocation(BaseModel):
    lat: float
    lon: float

class AssistantRequest(BaseModel):
    session_id: str
    text: str
    geo: Optional[GeoLocation] = None

class UpdateHistoryRequest(BaseModel):
    messages: List[Message]

class DeleteRequest(BaseModel):
    record_ids: List[str]

class UpdateMemoryRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None