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

"""Репозиторий для работы с OSMElement в БД."""

import json
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from infrastructure.logging.logger import setup_logger
from tools.maps.models import OSMElement, GameLocation, GameLocationOSMElement

logger = setup_logger("osm_repository")


class OSMRepository:
    """Репозиторий для работы с OSM элементами."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, osm_id: int) -> OSMElement | None:
        """Получает OSM элемент по ID."""
        return self.session.get(OSMElement, osm_id)

    def get_by_ids(self, osm_ids: List[int]) -> List[OSMElement]:
        """Получает несколько OSM элементов по ID."""
        return (
            self.session.query(OSMElement)
            .filter(OSMElement.id.in_(osm_ids))
            .all()
        )

    def create(
        self,
        osm_id: int,
        osm_type: str,
        tags: Dict[str, Any],
        geometry,
    ) -> OSMElement:
        """Создаёт новый OSM элемент."""
        element = OSMElement(
            id=osm_id,
            type=osm_type,
            tags=tags,
            geometry=geometry,
        )
        self.session.add(element)
        logger.debug(
            "Создан OSMElement id=%s type=%s, tags=%s",
            osm_id,
            osm_type,
            tags,
        )
        return element

    def link_to_location(
        self,
        osm_element: OSMElement,
        location: GameLocation,
    ) -> None:
        """Привязывает OSM элемент к локации."""
        if osm_element not in location.osm_elements:
            location.osm_elements.append(osm_element)
            logger.debug(
                "OSMElement id=%s привязан к location_id=%s",
                osm_element.id,
                location.id,
            )

    def get_elements_for_location(
        self,
        location_id: int,
        bbox_south: float,
        bbox_west: float,
        bbox_north: float,
        bbox_east: float,
        limit: int = 500,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Получает OSM элементы для локации с фильтрацией по bbox.
        
        Returns:
            Tuple[элементы, общее_количество_связей]
        """
        # Проверяем количество связей
        total_links = (
            self.session.query(GameLocationOSMElement)
            .filter(GameLocationOSMElement.game_location_id == location_id)
            .count()
        )
        logger.debug(
            "Всего связей для location_id=%s: %d",
            location_id,
            total_links,
        )

        # Запрос элементов
        query = (
            self.session.query(
                OSMElement.id,
                OSMElement.type,
                OSMElement.tags,
                func.ST_AsGeoJSON(OSMElement.geometry).label("geojson"),
            )
            .join(
                GameLocationOSMElement,
                GameLocationOSMElement.osm_element_id == OSMElement.id,
            )
            .filter(GameLocationOSMElement.game_location_id == location_id)
        )

        # Фильтр по bbox
        bbox_geom = func.ST_MakeEnvelope(
            bbox_west,
            bbox_south,
            bbox_east,
            bbox_north,
            4326,
        )
        query = query.filter(func.ST_Intersects(OSMElement.geometry, bbox_geom))

        # Считаем и грузим
        count_after_bbox = query.count()
        logger.debug(
            "Элементов после фильтра ST_Intersects для location_id=%s: %d",
            location_id,
            count_after_bbox,
        )

        elements = query.limit(limit).offset(offset).all()
        logger.debug(
            "Загружено %d элементов (limit=%d, offset=%d)",
            len(elements),
            limit,
            offset,
        )

        # Преобразуем в словари
        items: List[Dict[str, Any]] = []
        for el in elements:
            geom = json.loads(el.geojson)
            geom_type = geom["type"]
            coords = geom["coordinates"]

            # Важно:
            # - `el.tags` (OSM tags) могут содержать ключ `type` (особенно у relation),
            #   поэтому нельзя делать простое `{"type": el.type, **tags}` — иначе теги
            #   перезатрут системные поля.
            # - Для совместимости оставляем "плоские" поля тегов на верхнем уровне,
            #   но дополнительно всегда возвращаем вложенный объект `tags`.
            tags: Dict[str, Any] = el.tags or {}
            item: Dict[str, Any] = {
                "id": el.id,
                "type": el.type,   # OSM element type: node/way/relation
                "tags": tags,      # raw OSM tags (сюда попадёт cuisine, opening_hours и т.д.)
            }

            # Backward compatible: поднимаем теги на верхний уровень, но не даём им
            # перетирать служебные ключи/геометрию/сам объект tags.
            reserved_keys = {"id", "type", "tags", "point", "points", "rings"}
            for k, v in tags.items():
                if k in reserved_keys:
                    continue
                item[k] = v

            # --- NODE (точка) ---
            if el.type == "node":
                if geom_type == "Point":
                    item["point"] = coords
                else:
                    logger.warning(f"Unexpected geom type '{geom_type}' for node {el.id}")

            # --- WAY (линия или полигон) ---
            elif el.type == "way":
                if geom_type == "LineString":
                    item["points"] = coords  # [[lon, lat], ...]
                elif geom_type == "Polygon":
                    # ✅ ИСПРАВЛЕНИЕ: для way-полигона берем ТОЛЬКО внешний контур
                    item["points"] = coords[0]  # Первое кольцо (внешний контур)
                else:
                    logger.warning(f"Unexpected geom type '{geom_type}' for way {el.id}")

            # --- RELATION (мультиполигон, relation и т.д.) ---
            elif el.type == "relation":
                if geom_type == "Point":
                    item["point"] = coords  # Центр relation
                elif geom_type == "Polygon":
                    item["rings"] = coords  # [[[lon, lat], ...]]
                elif geom_type == "MultiPolygon":
                    # Можно взять все полигоны или только первый
                    item["rings"] = coords[0]  # Берем первый полигон
                else:
                    logger.warning(f"Unexpected geom type '{geom_type}' for relation {el.id}")

            items.append(item)

        return items, total_links

    def exists(self, osm_id: int) -> bool:
        """Проверяет существование OSM элемента."""
        return self.session.query(
            self.session.query(OSMElement)
            .filter(OSMElement.id == osm_id)
            .exists()
        ).scalar()

    def count_for_location(self, location_id: int) -> int:
        """Считает количество элементов для локации."""
        return (
            self.session.query(GameLocationOSMElement)
            .filter(GameLocationOSMElement.game_location_id == location_id)
            .count()
        )

