from datetime import datetime, date
from typing import Literal, Dict, Any, Optional, List

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

class StepPointIn(BaseModel):
    lat: float
    lon: float
    timestamp: datetime

class POIVisitIn(BaseModel):
    poi_id: int
    poi_name: str
    distance_from_start: float
    found_at: datetime
    emotion_emoji: Optional[str] = None
    emotion_label: Optional[str] = None
    emotion_color: Optional[str] = None

class WalkSessionCreate(BaseModel):
    account_id: str
    start_time: datetime
    end_time: datetime
    distance_m: float
    steps: int
    mode: Optional[str] = None
    notes: Optional[str] = None
    poi_visits: List[POIVisitIn] = []
    step_points: List[StepPointIn] = []

class JournalEntryIn(BaseModel):
    date: date
    session_id: int
    text: str
    photo_path: Optional[str] = None
    poi_id: Optional[int] = None
    poi_name: Optional[str] = None


class JournalEntryOut(BaseModel):
    id: int
    date: date
    session_id: int
    text: str
    photo_path: Optional[str]
    poi_name: Optional[str]

    class Config:
        orm_mode = True