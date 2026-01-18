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

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, HTTPException, Query

from api.schemas.reminders import (
    ReminderDelayRequest,
    ReminderRepeatWeeklyRequest, ReminderRequest,
)
from infrastructure.logging.logger import setup_logger
from infrastructure.pushi.reminders_sender import check_and_send_reminders_pushi
from tools.reminders.reminder_store import ReminderStore

logger = setup_logger("reminders")

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.get("", tags=["Reminders"])
async def get_reminders(
        account_id: str = Query(..., min_length=1, description="User account id")
):
    """
    Получает все напоминания для указанного пользователя.

    Возвращает список всех активных напоминаний (разовых и периодических),
    принадлежащих пользователю с указанным `account_id`.

    Args:
        account_id: Идентификатор пользователя.

    Returns:
        Словарь, где ключи — категории напоминаний, значения — списки объектов напоминаний.

    Raises:
        HTTPException: 400, если `account_id` пустой.
    """
    if not account_id or not account_id.strip():
        raise HTTPException(status_code=400, detail="account_id is required")

    store = ReminderStore(account_id=account_id)
    all_reminders = store.get_all()

    grouped: Dict[str, list] = defaultdict(list)

    for r in all_reminders:
        repeat = r.get("repeat_weekly", False)
        dt_str = r.get("datetime")

        if not dt_str:
            continue

        try:
            dt = datetime.fromisoformat(dt_str)
        except ValueError:
            # кривую дату просто пропускаем
            continue

        if repeat:
            key = dt.strftime("%A").upper()
            grouped[key].append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "datetime": dt.isoformat(),
                    "repeat_weekly": True,
                    "dayOfWeek": key,  # Пример: "FRIDAY"
                }
            )
        else:
            key = dt.date().isoformat()
            grouped[key].append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "datetime": dt.isoformat(),
                    "repeat_weekly": False,
                    "dayOfWeek": None,
                }
            )

    logger.info(f"Grouped reminders for {account_id}: {grouped}")

    return grouped or {}


@router.post("/done", tags=["Reminders"])
async def reminders_done(
        account_id: str = Query(..., min_length=1),
        req: ReminderRequest = ...,
):
    """
    Помечает напоминание как выполненное.

    Для разовых напоминаний (repeat_weekly=False) — помечает как done=True.
    Для постоянных напоминаний (repeat_weekly=True) — НЕ ставит done=True,
    а переносит дату на неделю вперёд и оставляет done=False (weekly никогда не “выполнено”).

    Args:
        account_id: Идентификатор пользователя.
        req: Словарь с обязательным полем "reminder_id" — ID напоминания.

    Returns:
        {"status": "ok"} при успешном выполнении.

    Raises:
        HTTPException: 400, если `reminder_id` отсутствует.
        HTTPException: 404, если напоминание не найдено или недоступно.
    """
    reminder_id = req.get("reminder_id")
    if not reminder_id:
        raise HTTPException(status_code=400, detail="reminder_id is required")

    store = ReminderStore(account_id)
    success = store.mark_done(reminder_id)

    if not success:
        logger.warning(
            f"⚠️ Напоминание {reminder_id} не найдено для пользователя {account_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="Reminder not found or access denied",
        )

    return {"status": "ok"}


@router.post("/delay", tags=["Reminders"])
async def reminders_delay(
        account_id: str = Query(..., min_length=1),
        req: ReminderDelayRequest = ...,
):
    """
    Откладывает выполнение напоминания на указанный интервал.

    Работает одинаково для разовых и постоянных напоминаний — просто откладывает 
    время срабатывания на указанное количество минут/часов/дней.
    
    Для постоянных напоминаний (repeat_weekly=True) не влияет на логику 
    еженедельного повторения — перенос weekly происходит в эндпоинте /done и/или в пуш-джобе.

    Args:
        account_id: Идентификатор пользователя.
        req: Объект запроса с данными для откладывания напоминания.

    Returns:
        {"status": "ok"} при успешном обновлении.

    Raises:
        HTTPException: 400, если unit/value невалидны.
        HTTPException: 404, если напоминание с указанным ID не найдено.
    """
    if req.value <= 0:
        raise HTTPException(
            status_code=400,
            detail="value must be greater than 0",
        )

    reminder_id = req.reminder_id

    if req.unit == "minute":
        delta = timedelta(minutes=req.value)
    elif req.unit == "hour":
        delta = timedelta(hours=req.value)
    elif req.unit == "day":
        delta = timedelta(days=req.value)
    else:
        raise HTTPException(
            status_code=400,
            detail="unit must be one of: minute, hour, day",
        )

    store = ReminderStore(account_id)
    success = store.delay(reminder_id, delta)

    if not success:
        logger.warning(
            f"⚠️ Напоминание {reminder_id} не найдено для пользователя {account_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="Reminder not found or access denied",
        )

    return {"status": "ok"}


@router.post("/repeat-weekly", tags=["Reminders"])
async def set_reminder_repeat_weekly(
        account_id: str = Query(..., min_length=1),
        req: ReminderRepeatWeeklyRequest = ...,
):
    """
    Включает или выключает еженедельное повторение для напоминания.
    
    Используется для кнопки "Больше не надо" на фронте — отключает repeat_weekly, 
    и напоминание перестаёт повторяться. Дополнительно при repeat_weekly=False
    напоминание помечается done=True, чтобы больше не срабатывало.

    Args:
        account_id: Идентификатор пользователя.
        req: Объект запроса с данными для настройки повторения.

    Returns:
        {"status": "ok"} при успешном обновлении.

    Raises:
        HTTPException: 404, если напоминание не найдено или недоступно.
    """

    store = ReminderStore(account_id)
    success = store.set_repeat_weekly(req.reminder_id, req.repeat_weekly)

    if not success:
        logger.warning(
            f"⚠️ Напоминание {req.reminder_id} не найдено для пользователя {account_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="Reminder not found or access denied",
        )

    return {"status": "ok"}


@router.post("/run_reminders")
def debug_run():
    """
    Запускает отладочную проверку напоминаний и будильников.

    **ВНИМАНИЕ:** Этот эндпоинт предназначен только для отладки!
    Вручную запускает процесс проверки всех активных напоминаний
    и отправки уведомлений, если время наступило.

    Returns:
        Статистика выполненной проверки.
    """
    check_and_send_reminders_pushi()
    return {"status": "ran"}