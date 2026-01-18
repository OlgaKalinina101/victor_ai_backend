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

from fastapi import APIRouter, HTTPException, Depends

from api.dependencies.runtime import get_db
from api.schemas.journal import JournalEntryIn
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from tools.maps.repositories import JournalRepository

logger = setup_logger("journal")
router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("/")
def list_entries(account_id: str, db: Database = Depends(get_db)):
    """
    Возвращает все записи журнала прогулок пользователя.

    Журнал используется для сохранения «моментов» из совместных прогулок:
    посещённые поинты (например, ресторанчики), заметки пользователя,
    опциональный путь к фотографии и связанный session_id. Эндпоинт
    возвращает все записи для указанного пользователя без пагинации.

    Args:
        account_id: Идентификатор пользователя, для которого нужно получить
            журнал (query-параметр, обязательный).

    Returns:
        List[dict]: Список словарей с полями:
            - id: Уникальный идентификатор записи журнала.
            - date: Дата/время события (как сохранено в базе).
            - text: Текст заметки пользователя.
            - photo_path: Путь к привязанной фотографии (если есть).
            - poi_name: Название поинта/места (например, ресторана).
            - session_id: Идентификатор сессии прогулки/маршрута.

    Raises:
        HTTPException 500: Любая внутренняя ошибка при работе с базой данных
        или репозиторием журнала.

    Notes:
        - Эндпоинт не применяет фильтры по дате или по месту — возвращает весь журнал.
        - Порядок записей определяется реализацией JournalRepository.get_all()
          (обычно по дате создания или посещения).
        - Может возвращать пустой список, если для пользователя ещё нет записей.
    """
    with db.get_session() as session:
        try:
            repo = JournalRepository(session)
            entries = repo.get_all(account_id)
            
            logger.info(f"[journal] Получено {len(entries)} записей для {account_id}")
            
            return [
                {
                    "id": e.id,
                    "date": e.date,
                    "text": e.text,
                    "photo_path": e.photo_path,
                    "poi_name": e.poi_name,
                    "session_id": e.session_id,
                }
                for e in entries
            ]
            
        except Exception as e:
            logger.error(f"[journal] Ошибка при получении записей: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении дневника: {e}")


@router.post("/")
def create_entry(payload: JournalEntryIn, db: Database = Depends(get_db)):
    """
    Создаёт новую запись в журнале прогулок пользователя.

    Используется для сохранения момента из прогулки: текстового описания,
    связанного поинта (ресторан, место на карте), а также опциональной
    фотографии и session_id маршрута. Запись сразу сохраняется в базу
    и становится доступна в list_entries().

    Args:
        payload: JournalEntryIn — тело запроса с данными записи, включая:
            - account_id: Идентификатор пользователя, владельца дневника.
            - date: Дата/время события (в формате, ожидаемом моделью).
            - text: Текст заметки/комментария пользователя.
            - photo_path: Путь/идентификатор фотографии (если есть).
            - poi_name: Название поинта/места, с которым связана запись.
            - session_id: Идентификатор сессии прогулки/маршрута (если используется).

    Returns:
        dict: Короткий ответ со статусом и идентификатором созданной записи:
            - status: Строка, обычно "ok" при успешном создании.
            - entry_id: ID созданной записи журнала.

    Raises:
        HTTPException 500: Любая внутренняя ошибка при создании записи или
        работе с базой данных.

    Notes:
        - Все поля проходят валидацию на уровне Pydantic-модели JournalEntryIn.
        - В логах фиксируется полный payload (для отладки) и id созданной записи.
        - Эндпоинт не возвращает всю запись целиком, только служебный ответ —
          для получения полного объекта используйте list_entries().
    """
    logger.info(f"[journal] Создание записи: {payload}")
    with db.get_session() as session:
        try:
            repo = JournalRepository(session)
            entry = repo.create(**payload.dict())
            
            logger.info(f"[journal] Создана запись id={entry.id} для {payload.account_id}")
            return {"status": "ok", "entry_id": entry.id}
            
        except Exception as e:
            logger.error(f"[journal] Ошибка при создании записи: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при создании записи: {e}")
