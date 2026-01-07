# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from infrastructure.database.models import UserAlarms, Reminder
from infrastructure.database.session import Database
from infrastructure.firebase.tokens import get_user_tokens
from infrastructure.logging.logger import setup_logger
from infrastructure.pushi.push_notifications import send_pushy_notification

logger = setup_logger("reminders_sender")


def check_and_send_reminders_pushi():
    """
    Проверяет напоминалки и будильники.
    Использует singleton Database для избежания утечки соединений.
    """
    now = datetime.now()
    db = Database.get_instance()
    session = db.get_session()

    try:
        fixed_weekly = reset_done_weekly_reminders(session, now)
        processed_reminders = process_due_reminders(session, now)
        processed_alarms = process_alarms(session, now)

        logger.debug(
            f"check_and_send_reminders_pushi: завершено. "
            f"Напоминаний: {processed_reminders}, "
            f"weekly-rescheduled: {fixed_weekly}, "
            f"будильников: {processed_alarms}"
        )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в чекере будильников/напоминаний: {e}", exc_info=True)
    finally:
        session.close()


def _normalize_now_for_dt(now: datetime, dt: datetime) -> datetime:
    """
    Приводит now к tz-aware/naive формату dt, чтобы корректно сравнивать в Python.
    (В базе сравнение и так работает, но для расчёта next_datetime нужно в Python.)
    """
    if dt is None:
        return now

    if (dt.tzinfo is not None) and (now.tzinfo is None):
        return now.replace(tzinfo=dt.tzinfo)

    if (dt.tzinfo is None) and (now.tzinfo is not None):
        return now.replace(tzinfo=None)

    return now


def _next_weekly_datetime(current_dt: datetime, now: datetime) -> datetime:
    """
    Возвращает ближайшую дату в будущем (строго > now), двигая current_dt шагами по 7 дней.
    """
    if current_dt is None:
        # Фолбэк: если по какой-то причине datetime отсутствует (не должно быть по модели)
        return now + timedelta(days=7)

    now_norm = _normalize_now_for_dt(now, current_dt)

    next_dt = current_dt + timedelta(days=7)
    # Если пропустили много недель — докручиваем до ближайшей будущей даты
    while next_dt <= now_norm:
        next_dt = next_dt + timedelta(days=7)
    return next_dt


def reset_done_weekly_reminders(session, now: datetime) -> int:
    """
    Safety-net: weekly-напоминания не должны оставаться done=True.
    Если нашли такие — переносим их на ближайшую будущую неделю и делаем done=False.
    """
    reminders = session.scalars(
        select(Reminder).where(
            and_(
                Reminder.repeat_weekly.is_(True),
                Reminder.done.is_(True),
            )
        )
    ).all()

    if not reminders:
        return 0

    processed = 0
    for r in reminders:
        r.datetime = _next_weekly_datetime(r.datetime, now)
        r.done = False
        session.add(r)
        processed += 1

    session.commit()
    logger.info(f"[reminders] weekly: восстановили (done->active) и перенесли: {processed} шт.")
    return processed

def process_due_reminders(session, now: datetime) -> int:
    """
    Находит и отправляет все просроченные/текущие напоминания.
    Возвращает количество обработанных напоминаний.
    """
    reminders = session.scalars(
        select(Reminder).where(
            and_(
                Reminder.done.is_(False),
                Reminder.datetime <= now
            )
        )
    ).all()

    logger.debug(f"Найдено активных напоминаний для срабатывания: {len(reminders)}")

    processed = 0

    for r in reminders:
        account_id = r.account_id
        tokens = get_user_tokens(account_id)

        if not tokens:
            logger.debug(f"Нет токенов у {account_id}, пропускаем напоминалку id={r.id}")
            continue

        logger.info(f" СРАБОТАЛО напоминание! → {account_id} | {r.title}")

        _send_reminder_pushes(r, tokens)

        # Для weekly-напоминаний: не "done", а перенос на следующую неделю
        if r.repeat_weekly:
            r.datetime = _next_weekly_datetime(r.datetime, now)
            r.done = False
        else:
            # Обычные: помечаем как выполненное
            r.done = True
        session.add(r)
        processed += 1

    if processed:
        session.commit()
        logger.info(f"[reminders] Отметили выполненными: {processed} шт.")

    return processed


def _send_reminder_pushes(r: Reminder, tokens: list[str]) -> None:
    """Отправляет пуши по одному напоминанию всем токенам."""
    for token in tokens:
        try:
            send_pushy_notification(
                token=token,
                title=r.title or "Напоминание",
                body=r.text or "Пора действовать~",
                data={
                    "reminder_id": str(r.id),
                    "account_id": r.account_id,
                    "title": "Напоминалка ♡",
                    "text": r.text or "",
                    "repeat_weekly": r.repeat_weekly,
                },
            )
            logger.info(f" Отправлено напоминание → {token[:12]}…")
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания {r.account_id}: {e}")

def process_alarms(session, now: datetime) -> int:
    """
    Проверяет и отправляет будильники на текущее время.
    Возвращает количество сработавших будильников (по всем пользователям).
    """
    current_time = now.strftime("%H:%M")  # например "06:00"
    weekday_today = now.weekday()  # 0=понедельник ... 6=воскресенье

    logger.debug(
        f"Проверяем будильники для времени: {current_time}, день недели: {weekday_today}"
    )

    users = session.query(UserAlarms).all()
    logger.debug(f"Найдено пользователей с будильниками: {len(users)}")

    processed = 0

    for user in users:
        account_id = user.account_id
        selected_track_id = user.selected_track_id
        logger.debug(
            f"Проверяем будильники для {account_id}, кол-во: {len(user.alarms)}"
        )

        for alarm in user.alarms:
            if not alarm.get("enabled", True):
                logger.debug(f"  Будильник отключен: {alarm}")
                continue

            alarm_time = alarm.get("time")
            logger.debug(
                f"  Будильник: time={alarm_time}, текущее время: {current_time}"
            )

            if alarm_time != current_time:
                continue

            repeat_mode = alarm.get("repeatMode")
            logger.debug(
                f"  Время совпало! repeat_mode={repeat_mode}, weekday={weekday_today}"
            )

            if not _should_trigger_alarm_today(repeat_mode, weekday_today):
                continue

            _trigger_alarm_for_user(
                account_id=account_id,
                selected_track_id=selected_track_id,
                alarm_time=alarm_time,
            )
            processed += 1

    return processed


def _should_trigger_alarm_today(repeat_mode: str | None, weekday_today: int) -> bool:
    """Решает, должен ли будильник с данным режимом сработать сегодня."""
    # "Будни" — только пн–пт
    if repeat_mode == "Будни" and weekday_today >= 5:  # суббота-воскресенье
        logger.debug("  Пропускаем: будни, а сегодня выходной")
        return False

    # "Выходные" — только сб–вс
    if repeat_mode == "Выходные" and weekday_today < 5:  # понедельник-пятница
        logger.debug("  Пропускаем: выходные, а сегодня будний день")
        return False

    # "Один раз", "Каждый день", None — срабатывают всегда
    return True


def _trigger_alarm_for_user(account_id: str, selected_track_id: int | None, alarm_time: str) -> None:
    """Отправляет пуши будильника конкретному пользователю."""
    logger.info(f"🔔🔔🔔 БУДИЛЬНИК СРАБОТАЛ ДЛЯ {account_id}! Время: {alarm_time}")

    track_id_to_play = selected_track_id or 1  # дефолтный трек
    logger.info(f"  Трек для воспроизведения: {track_id_to_play}")

    tokens = get_user_tokens(account_id)
    logger.info(f"  Токены пользователя: {tokens}")

    for token in tokens:
        try:
            msg_id = send_pushy_notification(
                token=token,
                title="Доброе утро ♡",
                body="Включил тебе музыку~",
                data={
                    "track_id": str(track_id_to_play),
                    "alarm_time": alarm_time,
                },
            )
            logger.info(
                f"✅ Будильник отправлен {account_id} → track {track_id_to_play} → "
                f"{token[:12]}… msg_id={msg_id}"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки будильника {account_id}: {e}", exc_info=True)
