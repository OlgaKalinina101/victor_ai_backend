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

from fastapi import APIRouter, HTTPException, Query, Depends

from api.dependencies.runtime import get_db
from infrastructure.database.session import Database
from tools.maps.repositories import AchievementRepository
from infrastructure.logging.logger import setup_logger

router = APIRouter(prefix="/api/achievements", tags=["achievements"])
logger = setup_logger("achievements_api")


@router.get("/")
def get_all(account_id: str = Query(..., min_length=1), db: Database = Depends(get_db)):
    """
    Получает полный список достижений системы "Места". Каждое достижение содержит информацию
    о его типе, иконке и описании условий получения.

    Args:
        account_id: Идентификатор пользователя

    Returns:
        Список объектов достижений в формате JSON, каждый из которых содержит:
        - id: Уникальный идентификатор достижения в системе
        - name: Название достижения
        - description: Подробное описание условий получения достижения
        - type: Тип достижения (например, 'bronze', 'silver', 'gold' или категория)
        - icon: Ссылка или путь к иконке достижения
        - unlocked_at: Дата и время разблокировки достижения (null, если ещё не получено)

    Raises:
        HTTPException 500: При внутренней ошибке базы данных или проблемах с подключением.

    Notes:
        - Эндпоинт возвращает все достижения независимо от статуса разблокировки
        - Поле `unlocked_at` может быть null для ещё не полученных достижений
        - Список отсортирован в порядке, определённом базой данных (обычно по id)
    """
    with db.get_session() as session:
        try:
            repo = AchievementRepository(session)
            achievements = repo.get_all(account_id)

            logger.info(f"[achievements] Получено {len(achievements)} достижений для {account_id}")
            
            return [
                {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "type": a.type,
                    "icon": a.icon,
                    "unlocked_at": a.unlocked_at
                }
                for a in achievements
            ]
            
        except Exception as e:
            logger.error(f"[achievements] Ошибка при получении достижений: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении достижений: {e}")
