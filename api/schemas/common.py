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
Общие схемы, используемые в нескольких эндпоинтах.

Содержит базовые модели данных, которые переиспользуются
в различных частях API для обеспечения консистентности.
"""

from typing import List, Optional
from pydantic import BaseModel


class GeoLocation(BaseModel):
    """
    Географические координаты.
    
    Используется для передачи местоположения пользователя
    в запросах к ассистенту, при создании записей о прогулках
    и в других геозависимых операциях.
    """
    lat: float
    lon: float


class ImageContent(BaseModel):
    """
    Изображение в формате base64 для мультимодальных запросов.
    
    Используется при отправке изображений в запросах к ассистенту.
    Base64-строка должна быть чистой, без префикса data:image/...
    """
    type: str = "base64"
    media_type: str = "image/png"
    data: str  # base64 строка


class Message(BaseModel):
    """
    Сообщение в истории диалога.
    
    Универсальный формат сообщения, используемый для обмена
    историей диалога между сервером и клиентом.
    """
    text: str
    is_user: bool
    timestamp: int
    id: Optional[int] = None  # ID из БД (null для SessionContext сообщений)
    vision_context: Optional[str] = None  # Контекст изображения (если было отправлено)
    emoji: Optional[str] = None  # Эмодзи-реакция пользователя (если установлена)
    # Swipe meta: к какому старому сообщению пользователь вернулся свайпом (если было)
    swiped_message_id: Optional[int] = None
    swiped_message_text: Optional[str] = None


class Usage(BaseModel):
    """
    Статистика использования языковых моделей.
    
    Содержит информацию о потреблении токенов и стоимости
    для конкретного провайдера и модели.
    """
    account_id: str
    model_name: str
    provider: str
    input_tokens_used: int
    output_tokens_used: int
    input_token_price: float
    output_token_price: float
    account_balance: float

