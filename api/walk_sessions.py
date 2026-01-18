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
from api.schemas.walk_sessions import WalkSessionCreate
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from tools.maps.repositories import WalkSessionRepository
from tools.maps.achievements.walks import check_walk_achievements

router = APIRouter(prefix="/api/walk_sessions", tags=["walks"])
logger = setup_logger("walk_sessions_api")

@router.post("/")
def create_walk_session(payload: WalkSessionCreate, db: Database = Depends(get_db)):
    """
    Создаёт новую сессию прогулки с полной детализацией активности.

    Принимает детальную информацию о завершённой прогулке пользователя,
    сохраняет геоданные, посещённые точки интереса (POI) и шаги,
    а также вычисляет и присваивает достижения за активность.
    Эндпоинт является центральным для трекинга физической активности.

    Args:
        payload: Объект WalkSessionCreate с полями:
            - account_id: Идентификатор пользователя (обязательный)
            - start_time: Время начала прогулки (обязательный, ISO 8601)
            - end_time: Время окончания прогулки (обязательный, ISO 8601)
            - distance_m: Пройденное расстояние в метрах (обязательный)
            - steps: Количество сделанных шагов (обязательный)
            - mode: Режим активности ('walk', 'run', 'hike', 'bike') (опционально)
            - notes: Пользовательские заметки о прогулке (опционально)
            - poi_visits: Список посещённых точек интереса:
                - poi_id: Уникальный идентификатор POI
                - poi_name: Название точки интереса
                - distance_from_start: Дистанция от старта до POI (в метрах)
                - found_at: Время обнаружения POI (ISO 8601)
                - emotion_emoji: Эмодзи эмоции при посещении (опционально)
                - emotion_label: Текстовая метка эмоции (опционально)
                - emotion_color: Цвет эмоции в HEX (опционально)
            - step_points: Список геоточек маршрута:
                - lat: Широта точки (обязательный, float)
                - lon: Долгота точки (обязательный, float)
                - timestamp: Время фиксации точки (обязательный, ISO 8601)

    Returns:
        Dict[str, Any] с результатом операции:
            - status: "ok" при успешном создании
            - session_id: Уникальный идентификатор созданной сессии
            - unlocked_achievements: Список разблокированных достижений:
                - name: Название достижения
                - type: Тип достижения ('distance', 'streak', 'poi', 'special')
                - description: Описание условий получения

    Raises:
        HTTPException 500: При ошибках базы данных или внутренней логики.

    Notes:
        - Все временные метки должны быть в UTC или содержать информацию о часовом поясе
        - POI могут дублироваться в системе - каждая запись сохраняется отдельно
        - Шаги сохраняются в хронологическом порядке
        - Достижения проверяются автоматически на основе пройденной дистанции, времени, POI
        - Эмоции при посещении POI помогают персонализировать рекомендации
        - При ошибке в любом шаге выполняется полный rollback транзакции

    Пример успешного ответа:
    ```json
    {
        "status": "ok",
        "session_id": 12345,
        "unlocked_achievements": [
            {
                "name": "Первые 5 км",
                "type": "distance",
                "description": "Пройдите 5 километров за одну прогулку"
            },
            {
                "name": "Исследователь",
                "type": "poi",
                "description": "Посетите 3 разные точки интереса"
            }
        ]
    }
    ```

    Business Logic:
        1. Создание записи о прогулке в таблице WalkSession
        2. Сохранение всех посещённых POI в таблицу POIVisit
        3. Сохранение геоточек маршрута в таблицу StepPoint
        4. Автоматическая проверка и присвоение достижений
        5. Атомарный коммит всех изменений или полный откат при ошибке
    """
    with db.get_session() as db_session:
        try:
            repo = WalkSessionRepository(db_session)
            
            # 1️⃣ Создаём саму прогулку
            new_walk = repo.create_walk(
                account_id=payload.account_id,
                start_time=payload.start_time,
                end_time=payload.end_time,
                distance_m=payload.distance_m,
                steps=payload.steps,
                mode=payload.mode,
                notes=payload.notes
            )
            
            # 2️⃣ Сохраняем посещённые POI
            for poi in payload.poi_visits:
                repo.add_poi_visit(
                    session_id=new_walk.id,
                    poi_id=poi.poi_id,
                    poi_name=poi.poi_name,
                    distance_from_start=poi.distance_from_start,
                    found_at=poi.found_at,
                    emotion_emoji=poi.emotion_emoji,
                    emotion_label=poi.emotion_label,
                    emotion_color=poi.emotion_color
                )
            
            # 3️⃣ Сохраняем геоточки маршрута
            for step in payload.step_points:
                repo.add_step_point(
                    session_id=new_walk.id,
                    lat=step.lat,
                    lon=step.lon,
                    timestamp=step.timestamp
                )
            
            # 🔥 Вычисляем достижения
            unlocked = check_walk_achievements(
                session=db_session,
                account_id=payload.account_id,
                walk=new_walk,
                payload=payload
            )
            
            # 4️⃣ Фиксируем всё в базе
            db_session.commit()
            
            logger.info(
                f"[walk_sessions] Создана прогулка id={new_walk.id} для {payload.account_id}: "
                f"distance={payload.distance_m}m, steps={payload.steps}, "
                f"POIs={len(payload.poi_visits)}, unlocked={len(unlocked)} achievements"
            )
            
            return {
                "status": "ok",
                "session_id": new_walk.id,
                "unlocked_achievements": [
                    {"name": a.name, "type": a.type, "description": a.description}
                    for a in unlocked
                ],
            }

        except Exception as e:
            db_session.rollback()
            logger.error(f"[walk_sessions] Ошибка при создании прогулки: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при создании прогулки: {e}")
