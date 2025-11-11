from datetime import datetime, date
from typing import Literal, Dict, Any, Optional, List

from pydantic import BaseModel, Field


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

class ChatMetaBase(BaseModel):
    account_id: str = Field(..., description="Уникальный ID пользователя")
    model: str = Field(default="deepseek-chat")
    trust_level: int = 0
    raw_trust_score: Optional[int] = None
    gender: str = "другое"
    relationship_level: Optional[str] = "незнакомец"
    is_creator: bool = False
    trust_established: bool = False
    trust_test_completed: bool = False
    trust_test_timestamp: Optional[str] = None
    last_updated: Optional[str] = None

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
    account_id: str  # ← добавили
    poi_id: str
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
    account_id: str  # ← добавили
    session_id: Optional[int] = None
    text: str
    photo_path: Optional[str] = None
    poi_id: Optional[str] = None  # ← исправили на str
    poi_name: Optional[str] = None


class JournalEntryOut(BaseModel):
    id: int
    account_id: str  # ← добавили
    date: date
    session_id: int
    text: str
    photo_path: Optional[str]
    poi_name: Optional[str]

    class Config:
        orm_mode = True