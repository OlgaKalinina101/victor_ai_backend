# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

"""
Схемы для эндпоинта /walk_sessions.

Содержит модели для работы с прогулками пользователя,
включая запись треков, посещение мест и статистику шагов.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class StepPointIn(BaseModel):
    """
    Точка трека прогулки с координатами и временем.
    
    Используется для записи детального маршрута прогулки
    с временными метками для каждой точки.
    """
    lat: float
    lon: float
    timestamp: datetime


class POIVisitIn(BaseModel):
    """
    Посещение точки интереса (POI) во время прогулки.
    
    Содержит информацию о месте, времени обнаружения,
    расстоянии от начала маршрута и эмоциональной реакции.
    """
    account_id: str
    poi_id: str
    poi_name: str
    distance_from_start: float
    found_at: datetime
    emotion_emoji: Optional[str] = None
    emotion_label: Optional[str] = None
    emotion_color: Optional[str] = None


class WalkSessionCreate(BaseModel):
    """
    Запрос на создание сессии прогулки.
    
    Содержит полную информацию о прогулке: время, расстояние,
    шаги, посещённые места и детальный трек маршрута.
    """
    account_id: str
    start_time: datetime
    end_time: datetime
    distance_m: float
    steps: int
    mode: Optional[str] = None
    notes: Optional[str] = None
    poi_visits: List[POIVisitIn] = []
    step_points: List[StepPointIn] = []

