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

"""Сервис для работы с Overpass API (только внешние запросы)."""

import math
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import requests
import yaml

from infrastructure.logging.logger import setup_logger
from tools.maps.exceptions import OverpassAPIException

logger = setup_logger("osm_api_service")


class OSMAPIService:
    """Сервис для работы с Overpass API."""

    def __init__(
        self,
        overpass_url: Optional[str] = None,
        timeout: Optional[int] = None,
        query_type: str = "full",
        config_path: Optional[Path] = None,
        max_retries: Optional[int] = None,
        retry_backoff_factor: Optional[float] = None,
        retry_initial_delay: Optional[int] = None,
    ) -> None:
        """
        Инициализация сервиса OSM API.
        
        Args:
            overpass_url: URL Overpass API (если None - берётся из конфига)
            timeout: Таймаут запроса (если None - берётся из конфига)
            query_type: Тип запроса (full, amenities_only, nature_only и т.д.)
            config_path: Путь к конфигу (если None - используется дефолтный)
            max_retries: Максимальное количество повторных попыток
            retry_backoff_factor: Множитель для экспоненциальной задержки
            retry_initial_delay: Начальная задержка при retry в секундах
        """
        # Загружаем конфиг
        self.config = self._load_config(config_path)
        
        # Используем параметры или дефолты из конфига
        defaults = self.config.get("defaults", {})
        self.overpass_url = overpass_url or defaults.get(
            "overpass_url", "https://overpass-api.de/api/interpreter"
        )
        self.timeout = timeout or defaults.get("timeout", 180)
        self.query_type = query_type
        
        # Настройки retry логики
        self.max_retries = max_retries or defaults.get("max_retries", 3)
        self.retry_backoff_factor = retry_backoff_factor or defaults.get(
            "retry_backoff_factor", 2.0
        )
        self.retry_initial_delay = retry_initial_delay or defaults.get(
            "retry_initial_delay", 5
        )
        self.retry_on_status_codes = defaults.get(
            "retry_on_status_codes", [504, 503, 429]
        )
        
        logger.debug(
            "OSMAPIService инициализирован: url=%s, timeout=%d, query_type=%s, "
            "max_retries=%d, backoff_factor=%.1f",
            self.overpass_url,
            self.timeout,
            self.query_type,
            self.max_retries,
            self.retry_backoff_factor,
        )

    @staticmethod
    def _load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Загружает конфигурацию из YAML файла.
        
        Args:
            config_path: Путь к конфигу (если None - используется дефолтный)
            
        Returns:
            Словарь с конфигурацией
        """
        if config_path is None:
            # Дефолтный путь: tools/maps/config/overpass_queries.yaml
            current_file = Path(__file__)
            config_path = current_file.parent.parent / "config" / "overpass_queries.yaml"

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.debug("Конфиг загружен из %s", config_path)
                return config
        except FileNotFoundError:
            logger.warning(
                "Конфиг не найден: %s, используем дефолтную конфигурацию",
                config_path,
            )
            return {"queries": {}, "defaults": {}}
        except yaml.YAMLError as exc:
            logger.error("Ошибка парсинга YAML конфига: %s", exc)
            return {"queries": {}, "defaults": {}}

    def get_query_template(self, query_type: Optional[str] = None) -> str:
        """
        Получает шаблон запроса из конфига.
        
        Args:
            query_type: Тип запроса (если None - используется self.query_type)
            
        Returns:
            Строка с шаблоном запроса
            
        Raises:
            OverpassAPIException: если тип запроса не найден
        """
        qtype = query_type or self.query_type
        queries = self.config.get("queries", {})
        
        if qtype not in queries:
            available = ", ".join(queries.keys())
            raise OverpassAPIException(
                f"Тип запроса '{qtype}' не найден в конфиге. "
                f"Доступные: {available}"
            )
        
        query_config = queries[qtype]
        template = query_config.get("query", "")
        
        logger.debug(
            "Получен шаблон запроса '%s': %s",
            qtype,
            query_config.get("description", "без описания"),
        )
        
        return template

    def get_available_query_types(self) -> Dict[str, str]:
        """
        Возвращает список доступных типов запросов с описаниями.
        
        Returns:
            Словарь {query_type: description}
        """
        queries = self.config.get("queries", {})
        return {
            qtype: qconfig.get("description", "Без описания")
            for qtype, qconfig in queries.items()
        }

    def calculate_bounding_box(
        self,
        lat: float,
        lon: float,
        radius_km: float,
    ) -> Tuple[float, float, float, float]:
        """
        Рассчитывает прямоугольник вокруг точки для заданного радиуса.
        
        Returns:
            Tuple[south, west, north, east]
        """
        km_per_degree_lat = 111.0
        km_per_degree_lon = 111.0 * math.cos(math.radians(lat))

        delta_lat = radius_km / km_per_degree_lat
        delta_lon = radius_km / km_per_degree_lon

        south = lat - delta_lat
        north = lat + delta_lat
        west = lon - delta_lon
        east = lon + delta_lon

        logger.debug(
            "Рассчитан bbox для точки (%f, %f) радиус=%f: (%f,%f,%f,%f)",
            lat,
            lon,
            radius_km,
            south,
            west,
            north,
            east,
        )

        return south, west, north, east

    def fetch_osm_data(
        self,
        bbox: str,
        query_type: Optional[str] = None,
    ) -> List[dict]:
        """
        Запрашивает сырые данные OSM из Overpass по bbox с retry логикой.
        
        Args:
            bbox: строка формата "south,west,north,east"
            query_type: тип запроса (если None - используется self.query_type)
            
        Returns:
            Список элементов из Overpass API
            
        Raises:
            OverpassAPIException: если запрос не удался после всех попыток
        """
        try:
            south, west, north, east = map(float, bbox.split(","))
        except (ValueError, AttributeError) as exc:
            raise OverpassAPIException(
                f"Невалидный формат bbox: {bbox}", exc
            ) from exc

        south_str = f"{south:.6f}"
        west_str = f"{west:.6f}"
        north_str = f"{north:.6f}"
        east_str = f"{east:.6f}"
        bbox_str = f"{south_str},{west_str},{north_str},{east_str}"

        # Получаем шаблон запроса из конфига
        query_template = self.get_query_template(query_type)
        
        # Подставляем параметры в шаблон
        overpass_query = query_template.format(
            timeout=self.timeout,
            bbox=bbox_str,
        )

        logger.info(
            "Запрос к Overpass для bbox=%s, query_type=%s",
            bbox,
            query_type or self.query_type,
        )
        
        # Логируем первые строки запроса для отладки
        query_preview = "\n".join(overpass_query.split("\n")[:10])
        logger.debug("Первые строки запроса:\n%s\n...", query_preview)

        # Retry логика
        last_exception = None
        for attempt in range(self.max_retries + 1):  # +1 для первой попытки
            try:
                if attempt > 0:
                    # Экспоненциальная задержка перед повторной попыткой
                    delay = self.retry_initial_delay * (self.retry_backoff_factor ** (attempt - 1))
                    logger.warning(
                        "🔄 Повторная попытка %d/%d после задержки %.1f сек...",
                        attempt,
                        self.max_retries,
                        delay,
                    )
                    time.sleep(delay)
                
                response = requests.post(
                    self.overpass_url,
                    data={"data": overpass_query},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                
                # Успешный запрос - выходим из цикла
                break
                
            except requests.RequestException as exc:
                last_exception = exc
                
                # Проверяем, нужно ли делать retry
                should_retry = False
                if hasattr(exc, 'response') and exc.response is not None:
                    status_code = exc.response.status_code
                    
                    # Логируем ошибку
                    if status_code == 400:
                        logger.error("❌ BAD REQUEST (400) - синтаксическая ошибка в запросе!")
                        logger.error("Полный запрос:\n%s", overpass_query)
                        try:
                            error_detail = exc.response.text
                            logger.error("Ответ Overpass: %s", error_detail[:500])
                        except:
                            pass
                    
                    # Проверяем, нужен ли retry для этого кода
                    should_retry = (
                        status_code in self.retry_on_status_codes 
                        and attempt < self.max_retries
                    )
                    
                    if should_retry:
                        logger.warning(
                            "⚠️ Получена ошибка %d (попытка %d/%d): %s",
                            status_code,
                            attempt + 1,
                            self.max_retries + 1,
                            exc,
                        )
                    else:
                        logger.error("❌ Ошибка запроса к Overpass: %s", exc)
                else:
                    # Ошибка сети (timeout, connection error и т.д.)
                    should_retry = attempt < self.max_retries
                    if should_retry:
                        logger.warning(
                            "⚠️ Ошибка сети (попытка %d/%d): %s",
                            attempt + 1,
                            self.max_retries + 1,
                            exc,
                        )
                    else:
                        logger.error("❌ Ошибка запроса к Overpass: %s", exc)
                
                # Если не нужен retry - выбрасываем исключение
                if not should_retry:
                    raise OverpassAPIException(
                        f"Не удалось выполнить запрос к Overpass API: {exc}",
                        exc,
                    ) from exc
        else:
            # Все попытки исчерпаны
            logger.error(
                "❌ Все %d попыток исчерпаны. Последняя ошибка: %s",
                self.max_retries + 1,
                last_exception,
            )
            raise OverpassAPIException(
                f"Не удалось выполнить запрос к Overpass API после {self.max_retries + 1} попыток: {last_exception}",
                last_exception,
            ) from last_exception

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Не получилось распарсить JSON-ответ от Overpass")
            raise OverpassAPIException(
                "Невалидный JSON-ответ от Overpass API", exc
            ) from exc

        elements = data.get("elements", [])
        logger.info("✅ Overpass вернул %d элементов", len(elements))

        if not elements:
            logger.debug("Пустой ответ Overpass: %s", data)

        return elements

    def convert_osm_geometry(self, osm_item: dict) -> Optional[str]:
        """
        Конвертирует геометрию Overpass в WKT (Well-Known Text).
        
        Args:
            osm_item: Элемент из Overpass API (с geometry после 'out geom')
            
        Returns:
            WKT строка (POINT, LINESTRING, POLYGON, MULTIPOLYGON) или None
        """
        osm_type = osm_item.get("type")
        tags = osm_item.get("tags", {})

        # --- NODE (точка) ---
        if osm_type == "node":
            if "lon" in osm_item and "lat" in osm_item:
                lon = osm_item["lon"]
                lat = osm_item["lat"]
                return f"POINT({lon} {lat})"
            return None

        # --- WAY (линия или полигон) ---
        if osm_type == "way":
            if "geometry" not in osm_item:
                return None
            
            coords = osm_item["geometry"]
            if not coords:
                return None
            
            # Строим список точек для WKT
            points = [f"{p['lon']} {p['lat']}" for p in coords]
            
            if not points:
                return None
            
            # Проверяем, замкнутый ли way
            is_closed = (coords[0]["lon"] == coords[-1]["lon"] and 
                        coords[0]["lat"] == coords[-1]["lat"])
            
            # Решаем: полигон или линия
            is_area = self._is_area(tags)
            
            if is_area and is_closed:
                # Полигон (уже замкнутый)
                points_str = ", ".join(points)
                return f"POLYGON(({points_str}))"
            elif is_area and not is_closed:
                # Полигон (нужно замкнуть)
                points.append(points[0])
                points_str = ", ".join(points)
                return f"POLYGON(({points_str}))"
            else:
                # Линия (дорога, граница и т.д.)
                points_str = ", ".join(points)
                return f"LINESTRING({points_str})"

        # --- RELATION (мультиполигон, маршрут и т.д.) ---
        if osm_type == "relation":
            # Для relation с 'out geom' можем получить:
            # 1. center - центральная точка
            # 2. members с геометрией
            
            if "center" in osm_item:
                lon = osm_item["center"]["lon"]
                lat = osm_item["center"]["lat"]
                return f"POINT({lon} {lat})"
            
            # Пытаемся построить мультиполигон из members
            if "members" in osm_item:
                polygons = self._build_multipolygon_from_members(osm_item["members"])
                if polygons:
                    if len(polygons) == 1:
                        return polygons[0]
                    else:
                        # MULTIPOLYGON
                        polygons_str = ", ".join([
                            p.replace("POLYGON", "").strip() 
                            for p in polygons
                        ])
                        return f"MULTIPOLYGON({polygons_str})"
            
            return None

        return None

    @staticmethod
    def _is_area(tags: dict) -> bool:
        """
        Определяет, является ли way площадным объектом (полигоном).
        
        По OSM правилам:
        - building, landuse, leisure, natural, amenity и т.д. = полигон
        - highway, railway, waterway = линия
        """
        # Явные площадные теги
        area_tags = {
            "building", "landuse", "leisure", "natural", "amenity",
            "shop", "tourism", "historic", "place", "man_made",
        }
        
        # Явно НЕ площадные теги
        linear_tags = {"highway", "railway", "waterway", "barrier"}
        
        # Проверяем наличие тегов
        has_area_tag = any(tag in tags for tag in area_tags)
        has_linear_tag = any(tag in tags for tag in linear_tags)
        
        # Явный тег area=yes/no
        if "area" in tags:
            return tags["area"] in ("yes", "true", "1")
        
        # Если есть area тег и нет linear - это полигон
        if has_area_tag and not has_linear_tag:
            return True
        
        # Если есть только linear тег - это линия
        if has_linear_tag and not has_area_tag:
            return False
        
        # По умолчанию: замкнутый way без явных тегов = полигон
        return True

    @staticmethod
    def _build_multipolygon_from_members(members: List[dict]) -> List[str]:
        """
        Строит список полигонов из members relation'а.
        
        Args:
            members: Список member'ов из relation
            
        Returns:
            Список WKT POLYGON строк
        """
        polygons = []
        
        for member in members:
            # Пропускаем member'ы без геометрии
            if "geometry" not in member or member.get("type") != "way":
                continue
            
            role = member.get("role", "")
            geometry = member["geometry"]
            
            if not geometry:
                continue
            
            # Строим полигон из member'а
            points = [f"{p['lon']} {p['lat']}" for p in geometry]
            
            if len(points) < 3:  # Полигон должен иметь минимум 3 точки
                continue
            
            # Замыкаем если нужно
            if points[0] != points[-1]:
                points.append(points[0])
            
            points_str = ", ".join(points)
            
            # outer = внешний контур, inner = дырка
            if role == "outer":
                polygons.append(f"POLYGON(({points_str}))")
        
        return polygons

    @staticmethod
    def is_point_in_bbox(
        point_lat: float,
        point_lon: float,
        bbox_south: float,
        bbox_west: float,
        bbox_north: float,
        bbox_east: float,
    ) -> bool:
        """Проверяет, находится ли точка внутри прямоугольника."""
        return (
            bbox_south <= point_lat <= bbox_north
            and bbox_west <= point_lon <= bbox_east
        )

