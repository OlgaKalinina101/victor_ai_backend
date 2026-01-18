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

"""Сервис для работы с игровыми локациями (бизнес-логика)."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from geoalchemy2 import WKTElement

from infrastructure.logging.logger import setup_logger
from tools.maps.models import GameLocation
from tools.maps.repositories import GameLocationRepository, OSMRepository
from tools.maps.services.osm_api_service import OSMAPIService
from tools.maps.exceptions import MaxBBoxLimitExceeded

logger = setup_logger("game_location_service")


class GameLocationService:
    """Сервис для управления игровыми локациями."""

    # Константы
    MAX_LOCATIONS_PER_ACCOUNT = 100
    DEFAULT_RADIUS_KM = 2.0

    def __init__(
        self,
        session: Session,
        osm_api_service: Optional[OSMAPIService] = None,
    ):
        """
        Инициализация сервиса.
        
        Args:
            session: SQLAlchemy сессия
            osm_api_service: Сервис для работы с Overpass API (опционально)
        """
        self.session = session
        self.location_repo = GameLocationRepository(session)
        self.osm_repo = OSMRepository(session)
        self.osm_api = osm_api_service or OSMAPIService()

    def get_or_create_location_for_point(
        self,
        account_id: str,
        latitude: float,
        longitude: float,
        radius_km: float = DEFAULT_RADIUS_KM,
    ) -> GameLocation:
        """
        Находит существующую локацию для точки или создаёт новую.
        
        Логика:
        1. Ищем все активные локации аккаунта
        2. Проверяем, попадает ли точка в какую-то из них
        3. Если нет — создаём новую (с проверкой лимита)
        4. Если создаём новую — загружаем OSM данные из Overpass
        
        Args:
            account_id: ID аккаунта
            latitude: Широта точки
            longitude: Долгота точки
            radius_km: Радиус для создания новой локации
            
        Returns:
            GameLocation (существующая или новая)
            
        Raises:
            MaxBBoxLimitExceeded: если достигнут лимит локаций
        """
        logger.info(
            "Поиск/создание локации для account_id=%s, точка=(%f,%f), radius=%f",
            account_id,
            latitude,
            longitude,
            radius_km,
        )

        # 1. Получаем все активные локации аккаунта
        locations = self.location_repo.get_active_locations_by_account(account_id)
        logger.debug("Найдено %d активных локаций для аккаунта", len(locations))

        # 2. Проверяем, попадает ли точка в существующую локацию
        for location in locations:
            if self.osm_api.is_point_in_bbox(
                point_lat=latitude,
                point_lon=longitude,
                bbox_south=location.bbox_south,
                bbox_west=location.bbox_west,
                bbox_north=location.bbox_north,
                bbox_east=location.bbox_east,
            ):
                logger.info(
                    "Точка попадает в существующую локацию id=%s",
                    location.id,
                )
                return location

        # 3. Точка не попала ни в одну локацию — нужно создать новую
        logger.info("Точка не попадает ни в одну локацию, создаём новую")

        # 3.1. Проверяем лимит
        if len(locations) >= self.MAX_LOCATIONS_PER_ACCOUNT:
            logger.warning(
                "Достигнут лимит локаций (%d) для account_id=%s",
                self.MAX_LOCATIONS_PER_ACCOUNT,
                account_id,
            )
            raise MaxBBoxLimitExceeded()

        # 3.2. Создаём bbox
        south, west, north, east = self.osm_api.calculate_bounding_box(
            latitude, longitude, radius_km
        )

        # 3.3. Создаём локацию в БД
        new_location = self.location_repo.create(
            account_id=account_id,
            name="Автолокация",
            bbox_south=south,
            bbox_west=west,
            bbox_north=north,
            bbox_east=east,
        )

        logger.info("Создана новая локация id=%s", new_location.id)

        # 3.4. Загружаем OSM данные из Overpass и сохраняем
        try:
            self._load_and_save_osm_data(new_location, south, west, north, east)
        except Exception as exc:
            logger.error(
                "Ошибка при загрузке OSM данных для location_id=%s: %s",
                new_location.id,
                exc,
                exc_info=True,
            )
            # Не фейлим весь запрос, просто логируем

        # 3.5. Коммитим всё
        self.session.commit()
        logger.info(
            "✅ Локация id=%s успешно создана и заполнена данными",
            new_location.id,
        )

        return new_location

    def get_osm_elements_for_location(
        self,
        location: GameLocation,
        limit: int = 500,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Получает OSM элементы для локации из БД.
        
        Args:
            location: Игровая локация
            limit: Максимум элементов
            offset: Смещение для пагинации
            
        Returns:
            Словарь с элементами и метаданными
        """
        logger.info(
            "Загрузка OSM элементов для location_id=%s (limit=%d, offset=%d)",
            location.id,
            limit,
            offset,
        )

        items, total_links = self.osm_repo.get_elements_for_location(
            location_id=location.id,
            bbox_south=location.bbox_south,
            bbox_west=location.bbox_west,
            bbox_north=location.bbox_north,
            bbox_east=location.bbox_east,
            limit=limit,
            offset=offset,
        )

        logger.info(
            "Загружено %d элементов из %d связей",
            len(items),
            total_links,
        )

        return {
            "items": items,
            "count": len(items),
            "total_links": total_links,
            "limit": limit,
            "offset": offset,
            "location_id": location.id,
        }

    def _load_and_save_osm_data(
        self,
        location: GameLocation,
        south: float,
        west: float,
        north: float,
        east: float,
    ) -> None:
        """
        Загружает данные из Overpass и сохраняет в БД.
        
        Args:
            location: Локация для привязки элементов
            south, west, north, east: Координаты bbox
        """
        bbox_str = f"{south},{west},{north},{east}"
        logger.info("Запрос данных из Overpass для bbox=%s", bbox_str)

        # Загружаем из Overpass
        overpass_data = self.osm_api.fetch_osm_data(bbox_str)
        logger.info("Overpass вернул %d элементов", len(overpass_data))

        if not overpass_data:
            logger.warning("Overpass не вернул данных для bbox=%s", bbox_str)
            return

        # Создаём элементы в БД
        created_count = 0
        existing_count = 0
        linked_count = 0
        skipped_no_geometry = 0
        skipped_by_type = {}  # Статистика пропущенных по типам

        logger.info("Обработка %d элементов из Overpass", len(overpass_data))

        for item in overpass_data:
            osm_id = item["id"]
            osm_type = item["type"]

            # Проверяем, существует ли элемент
            osm_element = self.osm_repo.get_by_id(osm_id)

            if osm_element is None:
                # Конвертируем геометрию в WKT
                wkt_geometry = self.osm_api.convert_osm_geometry(item)

                if not wkt_geometry:
                    # Детальное логирование пропущенных объектов
                    tags = item.get("tags", {})
                    name = tags.get("name", "без названия")
                    object_type = (
                        tags.get("amenity") or 
                        tags.get("leisure") or 
                        tags.get("natural") or 
                        tags.get("highway") or 
                        tags.get("building") or 
                        tags.get("landuse") or
                        "unknown"
                    )
                    
                    logger.warning(
                        "Пропуск элемента id=%s type=%s (%s: '%s') - нет геометрии. "
                        "Has geometry field: %s",
                        osm_id,
                        osm_type,
                        object_type,
                        name,
                        "geometry" in item,
                    )
                    skipped_no_geometry += 1
                    
                    # Собираем статистику
                    skipped_by_type[object_type] = skipped_by_type.get(object_type, 0) + 1
                    
                    continue

                # Создаём новый элемент с WKT геометрией
                osm_element = self.osm_repo.create(
                    osm_id=osm_id,
                    osm_type=osm_type,
                    tags=item.get("tags", {}),
                    geometry=WKTElement(wkt_geometry, srid=4326),
                )
                created_count += 1
                logger.debug(
                    "Создан OSMElement id=%s type=%s, геометрия: %s",
                    osm_id,
                    osm_type,
                    wkt_geometry[:50] + "..." if len(wkt_geometry) > 50 else wkt_geometry,
                )
            else:
                existing_count += 1
                logger.debug("Найден существующий OSMElement id=%s", osm_id)

        # 🔥 Важно: делаем flush, чтобы все новые элементы получили ID
        if created_count > 0:
            logger.info("Сохраняем %d новых OSMElement в БД...", created_count)
            self.session.flush()
            logger.info("✅ Flush выполнен, элементы получили ID")

        # Привязываем все элементы к локации (после flush!)
        for item in overpass_data:
            osm_id = item["id"]
            osm_element = self.osm_repo.get_by_id(osm_id)

            if osm_element:
                self.osm_repo.link_to_location(osm_element, location)
                linked_count += 1

        logger.info(
            "Итого: создано=%d, найдено=%d, привязано=%d, пропущено=%d",
            created_count,
            existing_count,
            linked_count,
            skipped_no_geometry,
        )
        
        # Логируем статистику пропущенных по типам
        if skipped_by_type:
            logger.info("Статистика пропущенных объектов по типам:")
            for obj_type, count in sorted(skipped_by_type.items(), key=lambda x: -x[1]):
                logger.info("  - %s: %d шт.", obj_type, count)

