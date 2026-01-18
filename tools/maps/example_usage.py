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

"""Примеры использования нового Maps API."""

from infrastructure.database.session import Database
from tools.maps.services import GameLocationService, OSMAPIService
from tools.maps.repositories import GameLocationRepository, OSMRepository
from tools.maps.exceptions import MaxBBoxLimitExceeded


def example_1_get_places_for_point():
    """Пример 1: Получение мест для точки (основной use case)."""
    db = Database()
    session = db.get_session()

    try:
        # Создаём сервис
        service = GameLocationService(session)

        # Находим или создаём локацию для точки
        location = service.get_or_create_location_for_point(
            account_id="test_user",
            latitude=55.7558,  # Москва, Красная площадь
            longitude=37.6173,
            radius_km=2.0,
        )

        print(f"Используется локация: {location.id} - {location.name}")
        print(f"Bbox: ({location.bbox_south}, {location.bbox_west}, "
              f"{location.bbox_north}, {location.bbox_east})")

        # Получаем элементы для локации
        result = service.get_osm_elements_for_location(
            location=location,
            limit=10,
            offset=0,
        )

        print(f"\nНайдено {result['count']} элементов:")
        for item in result["items"][:5]:  # Показываем первые 5
            name = item.get("name", "Без названия")
            amenity = item.get("amenity", item.get("leisure", "unknown"))
            print(f"  - {name} ({amenity})")

        session.commit()

    except MaxBBoxLimitExceeded:
        print("❌ Достигнут лимит локаций для аккаунта")
    except Exception as exc:
        print(f"❌ Ошибка: {exc}")
        session.rollback()
    finally:
        session.close()


def example_2_work_with_repositories():
    """Пример 2: Прямая работа с репозиториями."""
    db = Database()
    session = db.get_session()

    try:
        # Репозиторий локаций
        location_repo = GameLocationRepository(session)

        # Получаем все локации аккаунта
        locations = location_repo.get_active_locations_by_account("test_user")
        print(f"Локаций для test_user: {len(locations)}")

        for loc in locations:
            # Репозиторий OSM элементов
            osm_repo = OSMRepository(session)
            
            # Считаем элементы в каждой локации
            count = osm_repo.count_for_location(loc.id)
            print(f"  - {loc.name} (id={loc.id}): {count} элементов")

    except Exception as exc:
        print(f"❌ Ошибка: {exc}")
    finally:
        session.close()


def example_3_only_overpass_api():
    """Пример 3: Только работа с Overpass API (без БД)."""
    osm_api = OSMAPIService()

    # Показываем доступные типы запросов
    print("Доступные типы запросов:")
    for qtype, description in osm_api.get_available_query_types().items():
        print(f"  - {qtype}: {description}")

    # Рассчитать bbox
    south, west, north, east = osm_api.calculate_bounding_box(
        lat=55.7558,
        lon=37.6173,
        radius_km=1.0,
    )

    print(f"\nРассчитан bbox: ({south}, {west}, {north}, {east})")

    # Проверить, попадает ли точка в bbox
    is_inside = osm_api.is_point_in_bbox(
        point_lat=55.76,
        point_lon=37.62,
        bbox_south=south,
        bbox_west=west,
        bbox_north=north,
        bbox_east=east,
    )

    print(f"Точка (55.76, 37.62) внутри bbox: {is_inside}")

    # Можно использовать разные типы запросов:
    # osm_api_cafes = OSMAPIService(query_type="amenities_only")
    # osm_api_nature = OSMAPIService(query_type="nature_only")
    
    # Загрузить данные из Overpass (реальный HTTP запрос!)
    # bbox_str = f"{south},{west},{north},{east}"
    # elements = osm_api.fetch_osm_data(bbox_str)
    # print(f"Overpass вернул {len(elements)} элементов")
    
    # Или с конкретным типом запроса:
    # elements = osm_api.fetch_osm_data(bbox_str, query_type="minimal")


def example_4_create_custom_location():
    """Пример 4: Создание кастомной локации с конкретным bbox."""
    db = Database()
    session = db.get_session()

    try:
        location_repo = GameLocationRepository(session)

        # Создаём кастомную локацию
        location = location_repo.create(
            account_id="test_user",
            name="Парк Горького",
            description="Моя любимая зона для прогулок",
            bbox_south=55.7250,
            bbox_west=37.5950,
            bbox_north=55.7350,
            bbox_east=37.6050,
            difficulty="easy",
            location_type="park",
        )

        print(f"Создана локация: {location.id} - {location.name}")

        # Обновим её
        location_repo.update(
            location_id=location.id,
            description="Парк с классной набережной",
            difficulty="medium",
        )

        print(f"Локация обновлена!")

        session.commit()

    except Exception as exc:
        print(f"❌ Ошибка: {exc}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Пример 1: Основной use case")
    print("=" * 60)
    example_1_get_places_for_point()

    print("\n" + "=" * 60)
    print("Пример 2: Работа с репозиториями")
    print("=" * 60)
    example_2_work_with_repositories()

    print("\n" + "=" * 60)
    print("Пример 3: Только Overpass API")
    print("=" * 60)
    example_3_only_overpass_api()

    print("\n" + "=" * 60)
    print("Пример 4: Создание кастомной локации")
    print("=" * 60)
    example_4_create_custom_location()

