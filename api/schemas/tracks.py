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
Схемы для эндпоинта /tracks.

Содержит модели для работы с музыкальными треками,
включая пользовательские описания энергии и температуры.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TrackDescriptionUpdate(BaseModel):
    """
    Запрос на обновление пользовательских описаний трека.
    
    Используется для сохранения субъективных характеристик трека,
    определённых пользователем. Оба описания опциональны - можно
    обновить только одно поле, оставив второе без изменений.
    
    Attributes:
        track_id: ID трека в базе данных.
        energy_description: Словесное описание энергетики трека
            (например, "спокойный", "энергичный", "взрывной").
        temperature_description: Словесное описание "температуры" трека
            (например, "холодный", "теплый", "жаркий").
    """
    track_id: int
    energy_description: Optional[str] = None
    temperature_description: Optional[str] = None


class MusicTrackOut(BaseModel):
    """Публичная схема трека (все колонки из `MusicTrack`)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_path: str

    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    duration: Optional[float] = None
    track_number: Optional[int] = None
    bitrate: Optional[int] = None
    file_size: Optional[int] = None


class PlaylistMomentOut(BaseModel):
    """Публичная схема `PlaylistMoment` (stage1/2/3 + вложенный трек)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: Optional[str] = None
    created_at: datetime

    stage1_text: Optional[str] = None
    stage2_text: Optional[str] = None
    stage3_text: Optional[str] = None

    track_id: Optional[int] = None
    track: Optional[MusicTrackOut] = None
