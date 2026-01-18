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

"""Репозиторий для работы с GameLocation в БД."""

from typing import List, Optional
from sqlalchemy.orm import Session

from infrastructure.logging.logger import setup_logger
from tools.maps.models import GameLocation

logger = setup_logger("game_location_repository")


class GameLocationRepository:
    """Репозиторий для работы с игровыми локациями."""

    def __init__(self, session: Session):
        self.session = session

    def get_active_locations_by_account(self, account_id: str) -> List[GameLocation]:
        """Получает все активные локации для аккаунта."""
        locations = (
            self.session.query(GameLocation)
            .filter(
                GameLocation.account_id == account_id,
                GameLocation.is_active.is_(True),
            )
            .all()
        )
        logger.debug(
            "Найдено %d активных локаций для account_id=%s",
            len(locations),
            account_id,
        )
        return locations

    def get_by_id(self, location_id: int) -> Optional[GameLocation]:
        """Получает локацию по ID."""
        return self.session.get(GameLocation, location_id)

    def create(
        self,
        account_id: str,
        name: str,
        bbox_south: float,
        bbox_west: float,
        bbox_north: float,
        bbox_east: float,
        description: Optional[str] = None,
        difficulty: Optional[str] = None,
        location_type: Optional[str] = None,
    ) -> GameLocation:
        """Создаёт новую локацию."""
        location = GameLocation(
            account_id=account_id,
            name=name,
            description=description,
            bbox_south=bbox_south,
            bbox_west=bbox_west,
            bbox_north=bbox_north,
            bbox_east=bbox_east,
            is_active=True,
            difficulty=difficulty,
            location_type=location_type,
        )
        self.session.add(location)
        self.session.flush()  # Получаем ID сразу
        
        logger.info(
            "Создана новая локация id=%s для account_id=%s, bbox=(%f,%f,%f,%f)",
            location.id,
            account_id,
            bbox_south,
            bbox_west,
            bbox_north,
            bbox_east,
        )
        return location

    def count_by_account(self, account_id: str) -> int:
        """Считает количество локаций для аккаунта."""
        count = (
            self.session.query(GameLocation)
            .filter(GameLocation.account_id == account_id)
            .count()
        )
        logger.debug("Аккаунт %s имеет %d локаций", account_id, count)
        return count

    def deactivate(self, location_id: int) -> bool:
        """Деактивирует локацию."""
        location = self.get_by_id(location_id)
        if location:
            location.is_active = False
            logger.info("Локация id=%s деактивирована", location_id)
            return True
        return False

    def update(
        self,
        location_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        difficulty: Optional[str] = None,
        location_type: Optional[str] = None,
    ) -> Optional[GameLocation]:
        """Обновляет поля локации."""
        location = self.get_by_id(location_id)
        if not location:
            return None

        if name is not None:
            location.name = name
        if description is not None:
            location.description = description
        if difficulty is not None:
            location.difficulty = difficulty
        if location_type is not None:
            location.location_type = location_type

        self.session.flush()
        logger.info("Локация id=%s обновлена", location_id)
        return location

