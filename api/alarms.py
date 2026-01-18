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

from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Body, Depends

from api.dependencies.runtime import get_db
from api.schemas.alarms import AlarmUpdateDto
from infrastructure.database.repositories import AlarmsRepository
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from tools.playlist.playlist_tool import run_playlist_chain

logger = setup_logger("alarms")

router = APIRouter(prefix="/alarms", tags=["Alarms"])


@router.post("")
async def update_alarms(payload: AlarmUpdateDto, db: Database = Depends(get_db)) -> dict[str, str]:
    """
    Сохраняет или обновляет список будильников для пользователя.

    Принимает полный список будильников пользователя и сохраняет его в базу данных.
    Использует операцию `merge`, которая обновляет существующую запись или создаёт новую,
    если запись для данного пользователя отсутствует.

    Args:
        payload: Объект AlarmUpdateDto

    Returns:
        Словарь с результатом операции:
        - status: "ok" при успешном сохранении
        - message: Описательное сообщение

    Raises:
        HTTPException 400: Если данные будильников невалидны.
        HTTPException 500: При ошибке сохранения в базу данных.

    Note:
        Этот метод полностью заменяет существующий список будильников.
        Для частичного обновления используйте другие эндпоинты.
    """
    with db.get_session() as session:
        try:
            repo = AlarmsRepository(session)
            repo.upsert(
                account_id=payload.account_id,
                alarms=[alarm.dict() for alarm in payload.alarms],
                selected_track_id=payload.selected_track_id
            )
            
            logger.info(f"[alarms] Сохранены будильники для {payload.account_id}: {len(payload.alarms)} записей, track_id={payload.selected_track_id}")
            return {
                "status": "ok",
                "message": "Будильники сохранены в БД"
            }
            
        except Exception as e:
            logger.error(f"[alarms] Ошибка сохранения будильников: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{account_id}")
async def get_alarms(account_id: str, db: Database = Depends(get_db)) -> dict:
    """
    Получает полную конфигурацию будильников пользователя.

    Возвращает как список настроенных будильников, так и выбранный трек для воспроизведения.
    Если пользователь ещё не настраивал будильники, возвращает пустой список.

    Args:
        account_id: Идентификатор пользователя (из пути URL).

    Returns:
        Словарь с конфигурацией будильников:
        - alarms: Массив объектов будильников со всеми настройками
        - selected_track_id: ID музыкального трека для будильника.
                            Может быть None, если трек не выбран.

    Raises:
        HTTPException 500: При ошибке чтения из базы данных.

    Examples:
        Используется при запуске приложения для загрузки сохранённых настроек.
    """
    with db.get_session() as session:
        try:
            repo = AlarmsRepository(session)
            result = repo.get_by_account_id(account_id)
            
            if not result:
                logger.info(f"[alarms] Будильники не найдены для {account_id}, возвращаем пустой список")
                return {
                    "alarms": [],
                    "selected_track_id": None
                }

            logger.info(f"[alarms] Получены будильники для {account_id}: {len(result.alarms)} записей")
            return {
                "alarms": result.alarms,
                "selected_track_id": result.selected_track_id
            }
            
        except Exception as e:
            logger.error(f"[alarms] Ошибка получения будильников: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/select_track")
async def select_track(
        db: Database = Depends(get_db),
        account_id: str = Body(..., embed=True),
        track_id: Optional[int] = Body(None, embed=True)
) -> dict[str, Any]:
    """
    Устанавливает или сбрасывает выбранный музыкальный трек для всех будильников пользователя.

    Позволяет пользователю выбрать конкретный трек, который будет воспроизводиться
    при срабатывании любого из его будильников. Если передать `track_id = None`,
    система будет автоматически выбирать трек для каждого срабатывания.

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        track_id: ID музыкального трека для установки.
                 Если None - включается режим автоматического выбора.

    Returns:
        Словарь с результатом операции:
        - status: "ok" при успешном выполнении
        - selected_track_id: Установленный ID трека (или None)
        - message: Пользовательское сообщение о результате

    Raises:
        HTTPException 400: Если передан невалидный track_id.
        HTTPException 404: Если трек с указанным ID не существует.
        HTTPException 500: При ошибке сохранения в базу данных.

    Note:
        При установке конкретного трека, он будет использоваться для всех будильников
        до тех пор, пока пользователь не изменит выбор или не сбросит его.
    """

    with db.get_session() as session:
        try:
            repo = AlarmsRepository(session)
            
            # Пытаемся получить существующую запись
            user_alarms = repo.get_by_account_id(account_id)
            
            if not user_alarms:
                # Создаём новую запись если не существует
                user_alarms = repo.upsert(account_id=account_id, alarms=[], selected_track_id=track_id)
            else:
                # Обновляем только трек
                user_alarms = repo.update_selected_track(account_id, track_id)

            logger.info(f"[alarms] Трек выбран для {account_id}: {track_id}")

            return {
                "status": "ok",
                "selected_track_id": track_id,
                "message": "Трек успешно выбран ♡" if track_id is not None else "Теперь я буду выбирать сам каждый раз~"
            }
            
        except Exception as e:
            logger.error(f"[alarms] Ошибка выбора трека: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/select_track_for_yourself")
async def select_track_for_yourself(
        db: Database = Depends(get_db),
        account_id: str = None,
        payload: Optional[dict] = None,  # можно передать extra_context
):
    """ Кнопка «Разбуди меня сам...»
        Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        payload: Дополнительные параметры для уточнения выбора (опционально):
            - extra_context: Текстовый контекст (например, "для пробуждения", "медленный")

    Returns:
        Словарь с результатом операции:
        - status: "ok" при успешном выполнении
        - selected_track_id: ID подобранного трека (или None если ИИ решил оставить авто-выбор)
        - message: Креативное сообщение о результате выбора

    Raises:
        HTTPException 500: При ошибке алгоритма подбора или базы данных.

    Note:
        Этот эндпоинт реализует кнопку "Разбуди меня сам..." в интерфейсе.
        ИИ может сознательно вернуть None, чтобы сохранить элемент неожиданности.
    """
    extra_context = payload.get("extra_context") if payload else None

    try:
        # Запускаем цепочку выбора трека
        track_data, _ = await run_playlist_chain(
            account_id=account_id,
            extra_context=extra_context
        )

        chosen_track_id: Optional[int] = track_data.get("track_id")

        # Сохраняем выбранный трек
        with db.get_session() as session:
            repo = AlarmsRepository(session)
            
            user_alarms = repo.get_by_account_id(account_id)
            
            if not user_alarms:
                # Создаём новую запись
                repo.upsert(account_id=account_id, alarms=[], selected_track_id=chosen_track_id)
            else:
                # Обновляем трек
                repo.update_selected_track(account_id, chosen_track_id)

        logger.info(f"[alarms] AI выбрал track_id={chosen_track_id} для {account_id}")

        return {
            "status": "ok",
            "selected_track_id": chosen_track_id,
            "message": "Выбрал ♡" if chosen_track_id else "Я буду каждый раз выбирать сам, сюрприз! ♡"
        }

    except Exception as e:
        logger.error(f"[alarms] Критическая ошибка в auto-select-track: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Задумался слишком сильно… Давай retry?")
