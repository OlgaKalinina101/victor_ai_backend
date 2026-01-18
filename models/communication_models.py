# Victor AI - Personal AI Companion for Android
# Copyright (C) 2025-2026 Olga Kalinina

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from models.communication_enums import MessageCategory, MessageType, KeyInfoCategory
from models.user_enums import Mood, UserMoodLevel


@dataclass
class MessageMetadata:
    """Метаданные сообщения пользователя."""
    text: str = ""
    # История сообщений хранится как единая строка и дальше разбивается через splitlines().
    message_history: str = ""
    mood: Optional[Mood] = field(default=None)
    mood_level: Optional[UserMoodLevel] = field(default=None)
    dialog_weight: Optional[int] = field(default=None)
    message_category: MessageCategory = MessageCategory.PHATIC
    emotional_anchor: Dict[str, Any] = field(default_factory=dict)
    focus_phrases: Dict[str, Any] = field(default_factory=dict)
    has_first_disclosure: bool = False #first_disclosure
    memories: Optional[str] = ""

    def __post_init__(self) -> None:
        """
        Делает поля, приходящие из анализа, None-safe.

        В анализе некоторые блоки могут легитимно отсутствовать (None) — тогда считаем,
        что данных нет и используем безопасные дефолты.
        """
        if self.message_history is None:
            self.message_history = ""
        # Иногда извне могут прилететь не-словари (или None) — нормализуем.
        if not isinstance(self.emotional_anchor, dict):
            self.emotional_anchor = {}
        if not isinstance(self.focus_phrases, dict):
            self.focus_phrases = {}

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