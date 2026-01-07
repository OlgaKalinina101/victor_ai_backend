"""
Репозитории для работы с общими моделями базы данных.

Этот пакет содержит репозитории для моделей, которые используются 
across different features (ChatMeta, DialogueHistory, Diary, etc).

Domain-specific репозитории должны находиться в соответствующих tools:
- tools/carebank/repository.py
- tools/maps/repositories/
- tools/playlist/repository.py
- etc.
"""

from .chat_meta_repository import ChatMetaRepository
from .alarms_repository import AlarmsRepository
from .dialogue_repository import DialogueRepository
from .diary_repository import DiaryRepository
from .model_usage_repository import ModelUsageRepository
from .key_info_repository import KeyInfoRepository

__all__ = [
    "ChatMetaRepository",
    "AlarmsRepository",
    "DialogueRepository",
    "DiaryRepository",
    "ModelUsageRepository",
    "KeyInfoRepository",
]

