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
Схемы для эндпоинта /chat.

Содержит модели для работы с историей диалога, включая
пагинацию, поиск и обновление истории сообщений.
"""

from typing import List, Optional
from pydantic import BaseModel

from api.schemas.common import Message


class UpdateHistoryRequest(BaseModel):
    """
    Запрос на обновление истории диалога после редактирования сообщения.
    
    Содержит последние 6 сообщений (3 пары user-assistant) и информацию
    об отредактированном сообщении.
    """
    messages: List[Message]  # Последние 6 сообщений для SessionContext
    edited_message_id: int  # ID отредактированного сообщения
    edited_message_text: str  # Новый текст отредактированного сообщения


class UpdateHistoryResponse(BaseModel):
    """
    Ответ на запрос обновления истории диалога.
    
    Содержит информацию о результате операции обновления.
    """
    success: bool
    message: str
    session_updated: bool  # Обновлён ли SessionContext
    db_updated: bool  # Обновлено ли сообщение в БД


class ChatHistoryResponse(BaseModel):
    """
    Ответ для GET /chat/history с пагинацией.
    
    Содержит порцию сообщений и метаданные для
    реализации бесконечного скролла истории.
    """
    messages: List[Message]
    has_more: bool  # Есть ли еще старые сообщения
    oldest_id: Optional[int]  # ID самого старого сообщения в выборке
    newest_id: Optional[int]  # ID самого нового сообщения
    total_count: Optional[int] = None  # Общее количество (опционально)


class SearchResult(BaseModel):
    """
    Результат поиска в истории диалога.
    
    Содержит найденное сообщение с контекстом вокруг него
    и метаданные для навигации по результатам поиска.
    """
    messages: List[Message]  # Контекст вокруг найденного
    matched_message_id: Optional[int]  # ID найденного сообщения
    total_matches: int  # Всего найдено совпадений
    current_match_index: int  # Индекс текущего результата
    has_next: bool  # Есть ли следующий результат
    has_prev: bool  # Есть ли предыдущий результат


class UpdateEmojiRequest(BaseModel):
    """
    Запрос на обновление emoji у сообщения.
    
    Используется для установки или изменения emoji-реакции
    на конкретное сообщение в истории диалога.
    """
    account_id: str
    backend_id: int  # ID сообщения в базе данных
    emoji: Optional[str] = None  # Emoji для установки (None для удаления)
