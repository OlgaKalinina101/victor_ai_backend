"""
Схемы API для Victor AI Core.

Организованы по доменам для удобства навигации и поддержки.
Каждый модуль соответствует одному или группе связанных эндпоинтов.

Структура:
- common: Общие схемы, используемые в нескольких эндпоинтах
- assistant: Схемы для работы с ассистентом
- chat: Схемы для истории диалога
- chat_meta: Схемы для метаданных чата
- alarms: Схемы для будильников
- care_bank: Схемы для Care Bank
- journal: Схемы для дневника
- reminders: Схемы для напоминаний
- tracks: Схемы для музыкальных треков
- walk_sessions: Схемы для прогулок
- firebase_models: Схемы для Firebase интеграции
- location_models: Схемы для работы с геолокацией
"""

# Common
from api.schemas.common import (
    GeoLocation,
    ImageContent,
    Message,
    Usage,
)

# Assistant
from api.schemas.assistant import (
    AssistantRequest,
    AssistantResponse,
    AssistantState,
    AssistantMind,
    AssistantProvider,
    MemoryResponse,
    DeleteRequest,
    UpdateMemoryRequest,
)

# Chat
from api.schemas.chat import (
    UpdateHistoryRequest,
    ChatHistoryResponse,
    SearchResult,
)

# Chat Meta
from api.schemas.chat_meta import (
    ChatMetaBase,
    ChatMetaUpdateRequest,
)

# Alarms
from api.schemas.alarms import (
    AlarmItemDto,
    AlarmUpdateDto,
)

# Care Bank
from api.schemas.care_bank import (
    CareBankEntryCreate,
    CareBankEntryRead,
    CareBestResponse,
    ItemSelectionResponse,
    TaxiClass,
    CareBankSettingsUpdate,
    CareBankSettingsRead,
)

# Journal
from api.schemas.journal import (
    JournalEntryIn,
    JournalEntryOut,
)

# Reminders
from api.schemas.reminders import (
    ReminderRequest,
    ReminderDelayRequest,
    ReminderRepeatWeeklyRequest,
)

# Tracks
from api.schemas.tracks import (
    TrackDescriptionUpdate,
)

# Walk Sessions
from api.schemas.walk_sessions import (
    WalkSessionCreate,
    POIVisitIn,
    StepPointIn,
)

# Firebase
from api.schemas.token import (
    TokenRequest,
)

# Location
from api.schemas.location import (
    GameLocationResponse,
    GameLocationListItem,
    UpdateLocationRequest,
    GameLocationDeleteResponse,
)

# Places Caption
from api.schemas.place_caption import (
    PlaceCaptionRequest,
    PlaceCaptionResponse,
)

__all__ = [
    # Common
    "GeoLocation",
    "ImageContent",
    "Message",
    "Usage",
    # Assistant
    "AssistantRequest",
    "AssistantResponse",
    "AssistantState",
    "AssistantMind",
    "AssistantProvider",
    "MemoryResponse",
    "DeleteRequest",
    "UpdateMemoryRequest",
    # Chat
    "UpdateHistoryRequest",
    "ChatHistoryResponse",
    "SearchResult",
    # Chat Meta
    "ChatMetaBase",
    "ChatMetaUpdateRequest",
    # Alarms
    "AlarmItemDto",
    "AlarmUpdateDto",
    # Care Bank
    "CareBankEntryCreate",
    "CareBankEntryRead",
    "CareBestResponse",
    "ItemSelectionResponse",
    "TaxiClass",
    "CareBankSettingsUpdate",
    "CareBankSettingsRead",
    # Journal
    "JournalEntryIn",
    "JournalEntryOut",
    # Reminders
    "ReminderRequest",
    "ReminderDelayRequest",
    "ReminderRepeatWeeklyRequest",
    # Tracks
    "TrackDescriptionUpdate",
    # Walk Sessions
    "WalkSessionCreate",
    "POIVisitIn",
    "StepPointIn",
    # Firebase
    "TokenRequest",
    # Location
    "GameLocationResponse",
    "GameLocationListItem",
    "UpdateLocationRequest",
    "GameLocationDeleteResponse",
    # Places Caption
    "PlaceCaptionRequest",
    "PlaceCaptionResponse",
]

