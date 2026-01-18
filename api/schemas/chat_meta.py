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

"""
Схемы для эндпоинта /chat_meta.

Содержит модели для работы с метаданными чата пользователя,
включая настройки модели, уровень доверия и персональные параметры.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ChatMetaBase(BaseModel):
    """
    Базовая модель метаданных чата пользователя.
    
    Содержит все настройки и параметры, связанные с сессией пользователя,
    включая выбор модели, уровень доверия и персональные характеристики.
    """
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


class ChatMetaUpdateRequest(BaseModel):
    """
    Запрос на частичное обновление метаданных чата.
    
    Все поля опциональны - обновляются только переданные значения.
    Поддерживает PATCH-семантику для гибкого изменения настроек.
    """
    model: str | None = None
    trust_level: int | None = None
    raw_trust_score: int | None = None
    gender: str | None = None
    relationship_level: str | None = None
    is_creator: bool | None = None
    trust_established: bool | None = None
    trust_test_completed: bool | None = None

