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
Схемы для эндпоинта /journal.

Содержит модели для работы с дневником пользователя,
включая создание и чтение записей о прогулках и местах.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel


class JournalEntryIn(BaseModel):
    """
    Запрос на создание записи в дневнике.
    
    Содержит текст записи, дату, привязку к сессии прогулки
    и опциональную фотографию и место.
    """
    date: date
    account_id: str
    session_id: Optional[int] = None
    text: str
    photo_path: Optional[str] = None
    poi_id: Optional[str] = None
    poi_name: Optional[str] = None


class JournalEntryOut(BaseModel):
    """
    Запись дневника для возврата клиенту.
    
    Содержит все данные записи, включая ID из базы данных.
    """
    id: int
    account_id: str
    date: date
    session_id: int
    text: str
    photo_path: Optional[str]
    poi_name: Optional[str]

    class Config:
        from_attributes = True

