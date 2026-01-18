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

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends, Query
from starlette import status

from api.dependencies.runtime import get_db

from api.schemas.location import (
    GameLocationDeleteResponse,
    GameLocationListItem,
    GameLocationResponse,
    UpdateLocationRequest,
)
from api.schemas.place_caption import PlaceCaptionRequest, PlaceCaptionResponse
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from tools.maps import GameLocationService, MaxBBoxLimitExceeded, PlaceCaptionService
from tools.maps.models import GameLocation

logger = setup_logger("places")

router = APIRouter(prefix="/places", tags=["Places"])

@router.get("")
def get_places(
        account_id: str,
        latitude: float,
        longitude: float,
        radius_km: float = 2.0,
        limit: int = 15000,
        offset: int = 0,
) -> Dict[str, Any]:
    """
    Получает OSM (OpenStreetMap) объекты для заданных географических координат.

    Интеллектуальный поиск игровой локации по точке на карте:
    1. Проверяет существующие локации пользователя, попадает ли точка в их радиус
    2. Если подходящая локация не найдена:
       - Создаёт новую игровую локацию с центром в указанной точке
       - Загружает OSM данные через Overpass API для заданного радиуса
       - Сохраняет объекты в базу данных для быстрого доступа

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        latitude: Географическая широта в градусах (от -90 до 90).
        longitude: Географическая долгота в градусах (от -180 до 180).
        radius_km: Радиус поиска объектов в километрах.
                  Определяет размер игровой зоны. По умолчанию 2.0 км.
        limit: Максимальное количество возвращаемых OSM объектов.
               По умолчанию 15000 (оптимально для большинства сценариев).
        offset: Смещение для пагинации (сколько объектов пропустить).
                По умолчанию 0.

    Returns:
        Словарь с результатами поиска:
        - location: Название найденной/созданной локации
        - items: Список OSM объектов с метаданными
        - count: Общее количество найденных объектов
        - limit: Использованное значение limit
        - offset: Использованное значение offset

    Raises:
        HTTPException 400: MAX_GAME_LOCATIONS_REACHED - достигнут лимит локаций пользователя.
        HTTPException 500: Внутренняя ошибка сервера при обработке запроса.

    Note:
        При первом обращении к новым координатам может занять несколько секунд
        из-за загрузки данных из Overpass API.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            # Создаём сервис
            service = GameLocationService(session)

            # Находим или создаём локацию
            location = service.get_or_create_location_for_point(
                account_id=account_id,
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
            )

            # Получаем элементы для локации
            result = service.get_osm_elements_for_location(
                location=location,
                limit=limit,
                offset=offset,
            )

            logger.info(f"[places] Получено {result['count']} объектов для {account_id}, location={location.name}")
            
            return {
                "location": location.name,
                "items": result["items"],
                "count": result["count"],
                "limit": result["limit"],
                "offset": result["offset"],
            }

        except MaxBBoxLimitExceeded:
            logger.warning(f"[places] Достигнут лимит локаций для {account_id}")
            raise HTTPException(status_code=400, detail="MAX_GAME_LOCATIONS_REACHED")
            
        except Exception as exc:
            logger.error(f"[places] Ошибка при получении мест для {account_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {exc}")


@router.post("/caption", response_model=PlaceCaptionResponse)
async def generate_place_caption(request: PlaceCaptionRequest) -> PlaceCaptionResponse:
    """
    Генерирует одну короткую "живую" подпись к месту по OSM-тегам.

    Внутри берёт модель из ChatMeta (по account_id) и вызывает LLM через infrastructure/llm/client.py.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            service = PlaceCaptionService(db_session=session)
            caption = await service.generate_caption(
                account_id=request.account_id,
                poi_osm_id=request.poi_osm_id,
                poi_osm_type=request.poi_osm_type,
                tags=request.tags,
            )
            return PlaceCaptionResponse(caption=caption)
        except Exception as exc:
            logger.error(
                "[places.caption] Ошибка генерации подписи для %s: %s",
                request.account_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Внутренняя ошибка сервера: {exc}",
            )


@router.get("/locations", response_model=List[GameLocationListItem])
def get_locations(account_id: str) -> List[GameLocationListItem]:
    """
    Возвращает список всех активных игровых локаций пользователя.

    Получает краткую информацию о всех сохранённых локациях пользователя,
    включая их базовые характеристики (название, тип, сложность).
    Используется для отображения списка локаций в интерфейсе приложения.

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).

    Returns:
        Список объектов GameLocationListItem, содержащих:
        - id: Уникальный идентификатор локации
        - name: Название локации (автогенерируемое или пользовательское)
        - description: Описание локации
        - is_active: Флаг активности локации
        - difficulty: Уровень сложности (easy, medium, hard)
        - location_type: Тип локации (city, park, rural, etc.)

    Raises:
        HTTPException 500: Внутренняя ошибка сервера при получении данных.

    Examples:
        Используется для загрузки списка локаций в меню выбора игровых зон.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            service = GameLocationService(session)
            location_repo = service.location_repo

            # Получаем все активные локации
            locations = location_repo.get_active_locations_by_account(account_id)

            # Преобразуем в Pydantic модели
            result = [
                GameLocationListItem(
                    id=loc.id,
                    name=loc.name,
                    description=loc.description,
                    is_active=loc.is_active,
                    difficulty=loc.difficulty,
                    location_type=loc.location_type,
                )
                for loc in locations
            ]

            logger.info(f"[places] Возвращено {len(result)} локаций для {account_id}")
            return result

        except Exception as exc:
            logger.error(f"[places] Ошибка при получении локаций для {account_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {exc}")


@router.get("/locations/{location_id}", response_model=GameLocationResponse)
def get_location(location_id: int, account_id: str) -> GameLocationResponse:
    """
    Получает полную детальную информацию о конкретной игровой локации.

    Возвращает все метаданные локации, включая географические параметры,
    статистику объектов и пользовательские настройки. Требует проверки
    прав доступа - локация должна принадлежать указанному пользователю.

    Args:
        location_id: ID локации (из пути URL).
        account_id: Идентификатор пользователя для проверки прав доступа.

    Returns:
        Полный объект GameLocationResponse с детальной информацией:
        - Все базовые поля (id, name, description, etc.)
        - Географические параметры (center_lat, center_lon, radius_km)
        - Статистика (total_osm_elements, created_at, updated_at)
        - Настройки игры (difficulty, location_type, is_active)

    Raises:
        HTTPException 403: Access denied - локация принадлежит другому пользователю.
        HTTPException 404: Location not found - локация с указанным ID не существует.
        HTTPException 500: Внутренняя ошибка сервера.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            service = GameLocationService(session)
            location_repo = service.location_repo

            # Получаем локацию
            location = location_repo.get_by_id(location_id)

            if not location:
                raise HTTPException(status_code=404, detail=f"Location with id={location_id} not found")

            # Проверяем доступ
            if location.account_id != account_id:
                raise HTTPException(status_code=403, detail="Access denied to this location")

            logger.info(f"[places] Получена локация id={location_id} для {account_id}")
            return GameLocationResponse.model_validate(location)

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[places] Ошибка при получении локации id={location_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {exc}")


@router.get("/locations/{location_id}/places")
def get_places_by_location_id(
        location_id: int,
        account_id: str,
        limit: int = 15000,
        offset: int = 0,
) -> Dict[str, Any]:
    """
    Получает OSM объекты для существующей сохранённой локации.

    Альтернатива основному эндпоинту `/places`, но работает с уже
    существующей локацией по её ID. Используется для быстрой загрузки
    объектов локации без повторного поиска по координатам.

    Args:
        location_id: ID существующей локации.
        account_id: Идентификатор пользователя для проверки прав доступа.
        limit: Максимальное количество возвращаемых OSM объектов.
               По умолчанию 15000.
        offset: Смещение для пагинации. По умолчанию 0.

    Returns:
        Словарь с результатами в том же формате, что и `/places`:
        - location: Название локации
        - items: Список OSM объектов
        - count: Общее количество объектов
        - limit, offset: Использованные значения

    Raises:
        HTTPException 403: Access denied - локация принадлежит другому пользователю.
        HTTPException 404: Location not found - локация не существует.
        HTTPException 500: Внутренняя ошибка сервера.

    Note:
        Этот эндпоинт работает быстрее чем `/places`, так как не требует
        геопоиска и загрузки данных из Overpass API.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            service = GameLocationService(session)
            location_repo = service.location_repo

            # Получаем локацию
            location = location_repo.get_by_id(location_id)

            if not location:
                raise HTTPException(status_code=404, detail=f"Location with id={location_id} not found")

            # Проверяем доступ
            if location.account_id != account_id:
                raise HTTPException(status_code=403, detail="Access denied to this location")

            # Получаем элементы
            result = service.get_osm_elements_for_location(
                location=location,
                limit=limit,
                offset=offset,
            )

            logger.info(f"[places] Получено {result['count']} элементов для location_id={location_id}")

            return {
                "location": location.name,
                "items": result["items"],
                "count": result["count"],
                "limit": result["limit"],
                "offset": result["offset"],
            }

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[places] Ошибка при получении элементов для location_id={location_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {exc}")

#ПОКА НЕ ИСПОЛЬЗУЕТСЯ!!!
@router.patch("/locations/{location_id}", response_model=GameLocationResponse)
def update_location(
        location_id: int,
        account_id: str,
        update_data: UpdateLocationRequest,
) -> GameLocationResponse:
    """
    Обновляет пользовательские метаданные существующей игровой локации.

    Позволяет пользователю модифицировать название, описание, сложность
    и тип локации. Не изменяет географические параметры (координаты, радиус)
    и OSM объекты. Обновляются только те поля, которые переданы в запросе.

    Args:
        location_id: ID локации для обновления.
        account_id: Идентификатор пользователя (должен быть владельцем локации).
        update_data: Данные для обновления (PATCH-стиль, только изменяемые поля):
            - name: Новое название локации (опционально)
            - description: Новое описание (опционально)
            - difficulty: Новая сложность (опционально)
            - location_type: Новый тип локации (опционально)

    Returns:
        Обновлённый объект GameLocationResponse с актуальными данными.

    Raises:
        HTTPException 403: Access denied - локация принадлежит другому пользователю.
        HTTPException 404: Location not found - локация не существует.
        HTTPException 500: Внутренняя ошибка сервера при обновлении.

    Note:
        Для изменения географических параметров используйте основной эндпоинт `/places`.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            service = GameLocationService(session)
            location_repo = service.location_repo

            # Получаем локацию
            location = location_repo.get_by_id(location_id)

            if not location:
                raise HTTPException(status_code=404, detail=f"Location with id={location_id} not found")

            # Проверяем доступ
            if location.account_id != account_id:
                raise HTTPException(status_code=403, detail="Access denied to this location")

            # Обновляем только переданные поля
            updated_location = location_repo.update(
                location_id=location_id,
                name=update_data.name,
                description=update_data.description,
                difficulty=update_data.difficulty,
                location_type=update_data.location_type,
            )

            # Коммит произойдет автоматически при выходе из контекстного менеджера
            logger.info(f"[places] Локация id={location_id} обновлена для {account_id}")
            return GameLocationResponse.model_validate(updated_location)

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[places] Ошибка при обновлении локации id={location_id}: {exc}", exc_info=True)
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {exc}")


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_200_OK,
    response_model=GameLocationDeleteResponse,  # или просто {"detail": "Локация удалена"}
    summary="Удалить свою игровую локацию (soft delete)"
)
async def delete_game_location(
        location_id: int,
        account_id: str,
):
    """
    Выполняет мягкое удаление (soft delete) игровой локации.

    Устанавливает флаг `is_active = False` для указанной локации, что
    делает её недоступной для игровых сессий. OSM объекты и связи
    удаляются автоматически благодаря каскадному удалению в базе данных.

    Только владелец локации (тот же account_id) может её удалить.
    Удалённые локации могут быть восстановлены через админ-панель.

    Args:
        location_id: ID локации для удаления.
        account_id: Идентификатор пользователя (должен быть владельцем).

    Returns:
        Объект подтверждения удаления:
        - detail: Текстовое сообщение об успешном удалении
        - location_id: ID удалённой локации
        - name: Название удалённой локации

    Raises:
        HTTPException 400: Локация уже удалена (is_active уже False).
        HTTPException 403: Access denied - локация принадлежит другому пользователю.
        HTTPException 404: Локация не найдена или не принадлежит пользователю.
        HTTPException 500: Внутренняя ошибка сервера.

    Note:
        Это мягкое удаление (soft delete). Данные остаются в базе
        и могут быть восстановлены администратором.
    """
    db = Database.get_instance()
    with db.get_session() as session:
        try:
            service = GameLocationService(session)
            location_repo = service.location_repo

            location = location_repo.get_by_id(location_id)

            if not location or location.account_id != account_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Локация не найдена или не принадлежит вам"
                )

            if not location.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Локация уже удалена"
                )

            # Soft delete через репозиторий
            location_repo.deactivate(location_id)
            
            logger.info(f"[places] Удалена локация id={location_id} для {account_id}")
            
            return {
                "detail": "Локация успешно удалена",
                "location_id": location.id,
                "name": location.name
            }
            
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[places] Ошибка удаления локации id={location_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {exc}")