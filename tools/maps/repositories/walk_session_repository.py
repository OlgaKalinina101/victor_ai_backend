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

"""Репозиторий для работы с сессиями прогулок."""

from typing import List, Optional
from sqlalchemy.orm import Session

from tools.maps.models import WalkSession, POIVisit, StepPoint
from infrastructure.logging.logger import setup_logger

logger = setup_logger("walk_session_repository")


class WalkSessionRepository:
    """Репозиторий для работы с прогулками пользователя."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_walk(
        self,
        account_id: str,
        start_time,
        end_time,
        distance_m: int,
        steps: int,
        mode: Optional[str] = None,
        notes: Optional[str] = None
    ) -> WalkSession:
        """
        Создаёт новую прогулку.
        
        Args:
            account_id: ID пользователя
            start_time: Время начала
            end_time: Время окончания
            distance_m: Расстояние в метрах
            steps: Количество шагов
            mode: Режим активности (walk/run/hike/bike)
            notes: Заметки пользователя
            
        Returns:
            Созданная прогулка (с ID после flush())
        """
        walk = WalkSession(
            account_id=account_id,
            start_time=start_time,
            end_time=end_time,
            distance_m=distance_m,
            steps=steps,
            mode=mode,
            notes=notes
        )
        self.session.add(walk)
        self.session.flush()  # Получаем ID без коммита
        
        logger.info(f"Создана прогулка: id={walk.id}, account_id={account_id}, distance={distance_m}m")
        return walk
    
    def add_poi_visit(
        self,
        session_id: int,
        poi_id: str,
        poi_name: str,
        distance_from_start: int,
        found_at,
        emotion_emoji: Optional[str] = None,
        emotion_label: Optional[str] = None,
        emotion_color: Optional[str] = None
    ) -> POIVisit:
        """
        Добавляет посещение точки интереса к прогулке.
        
        Args:
            session_id: ID сессии прогулки
            poi_id: ID точки интереса
            poi_name: Название POI
            distance_from_start: Дистанция от старта (метры)
            found_at: Время обнаружения
            emotion_emoji: Эмодзи эмоции (опционально)
            emotion_label: Текст эмоции (опционально)
            emotion_color: Цвет эмоции (опционально)
            
        Returns:
            Созданная запись POIVisit
        """
        visit = POIVisit(
            session_id=session_id,
            poi_id=poi_id,
            poi_name=poi_name,
            distance_from_start=distance_from_start,
            found_at=found_at,
            emotion_emoji=emotion_emoji,
            emotion_label=emotion_label,
            emotion_color=emotion_color
        )
        self.session.add(visit)
        logger.debug(f"Добавлен POI visit: session={session_id}, poi={poi_name}")
        return visit
    
    def add_step_point(
        self,
        session_id: int,
        lat: float,
        lon: float,
        timestamp
    ) -> StepPoint:
        """
        Добавляет геоточку маршрута к прогулке.
        
        Args:
            session_id: ID сессии прогулки
            lat: Широта
            lon: Долгота
            timestamp: Время фиксации точки
            
        Returns:
            Созданная запись StepPoint
        """
        point = StepPoint(
            session_id=session_id,
            lat=lat,
            lon=lon,
            timestamp=timestamp
        )
        self.session.add(point)
        return point
    
    def get_by_id(self, session_id: int) -> Optional[WalkSession]:
        """Получает прогулку по ID."""
        return self.session.query(WalkSession).filter_by(id=session_id).first()
    
    def get_all(self, account_id: str) -> List[WalkSession]:
        """Получает все прогулки пользователя."""
        return (
            self.session.query(WalkSession)
            .filter(WalkSession.account_id == account_id)
            .order_by(WalkSession.start_time.desc())
            .all()
        )
    
    def get_poi_visits(self, session_id: int) -> List[POIVisit]:
        """Получает все посещенные POI для прогулки."""
        return (
            self.session.query(POIVisit)
            .filter(POIVisit.session_id == session_id)
            .order_by(POIVisit.distance_from_start)
            .all()
        )
    
    def get_step_points(self, session_id: int) -> List[StepPoint]:
        """Получает все точки маршрута для прогулки."""
        return (
            self.session.query(StepPoint)
            .filter(StepPoint.session_id == session_id)
            .order_by(StepPoint.timestamp)
            .all()
        )

