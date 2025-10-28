import datetime
from typing import Literal, Dict, Any, Optional

from pydantic import BaseModel

class AssistantResponse(BaseModel):
    answer: str
    status: str

class Message(BaseModel):
    text: str
    is_user: bool
    timestamp: int

class Usage(BaseModel):
    account_id: str
    model_name: str
    provider: str
    input_tokens_used: int
    output_tokens_used: int
    input_token_price: float
    output_token_price: float
    account_balance: float

class AssistantState(BaseModel):
    state: str

class AssistantMind(BaseModel):
    mind: str
    type: Literal["anchor", "focus"]

class AssistantProvider(BaseModel):
    provider: str

# Модель для ответа
class MemoryResponse(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any]

class TrackDescriptionUpdate(BaseModel):
    account_id: str
    track_id: int
    energy_description: Optional[str] = None
    temperature_description: Optional[str] = None