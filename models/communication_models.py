# Victor AI Project
# Copyright (c) 2025 Olga Kalinina
# All rights reserved.
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from models.communication_enums import MessageCategory, MessageType, KeyInfoCategory
from models.user_enums import Mood, UserMoodLevel


@dataclass
class MessageMetadata:
    """Метаданные сообщения пользователя."""
    text: Optional[str] = ""
    message_history: [str] = field(default_factory=list),
    mood: Optional[Mood] = field(default=None)
    mood_level: Optional[UserMoodLevel] = field(default=None)
    dialog_weight: Optional[int] = field(default=None)
    message_category: MessageCategory = MessageCategory.PHATIC
    emotional_anchor: Dict[str, Any] = None
    focus_phrases: Dict[str, Any] = field(default_factory=list)
    has_first_disclosure: bool = False #first_disclosure
    memories: Optional[str] = ""

    @staticmethod
    def empty() -> "MessageMetadata":
        return MessageMetadata()


@dataclass
class KeyInformation:
    """Ключевая информация из сообщения."""
    content: Optional[str] = None
    category: Optional[KeyInfoCategory] = None
    subcategory: Optional[str] = None
    victor_impressive: int = 1
    is_critical: bool = False

    @staticmethod
    def empty() -> "KeyInformation":
        return KeyInformation()