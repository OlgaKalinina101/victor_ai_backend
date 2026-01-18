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

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from uuid import UUID

from sqlalchemy import select

from infrastructure.database.models import Reminder
from infrastructure.database.session import Database


class ReminderStore:
    def __init__(self, account_id: str, db: Optional[Database] = None):
        self.account_id = account_id
        self.db = db or Database.get_instance()

    # --- helpers ---
    @staticmethod
    def _short_title(text: str, max_len: int = 50) -> str:
        t = (text or "").strip()
        if not t:
            return "Напоминание"
        return t if len(t) <= max_len else t[:max_len - 1] + "…"

    @staticmethod
    def _normalize_dt(dt_str: str) -> datetime:
        """
        Принимает 'YYYY-MM-DD HH:MM' или ISO, возвращает datetime объект
        """
        if not dt_str:
            # если времени нет — ставим через 5 минут
            return datetime.now() + timedelta(minutes=5)
        try:
            # ISO-путь
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                # старый формат без 'T'
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            except ValueError:
                # если не получилось — через 5 минут
                return datetime.now() + timedelta(minutes=5)

    @staticmethod
    def _reminder_to_dict(reminder: Reminder) -> Dict:
        """Конвертирует модель Reminder в словарь для совместимости со старым API"""
        return {
            "id": str(reminder.id),
            "user_id": reminder.account_id,
            "title": reminder.title,
            "text": reminder.text,
            "datetime": reminder.datetime.isoformat(),
            "created_at": reminder.created_at.isoformat(),
            "repeat_weekly": reminder.repeat_weekly,
            "done": reminder.done,
        }

    # --- public API ---
    def save(self, reminder: Dict) -> Dict:
        """
        Принимает минимум: {"datetime": "...", "text": "..."}.
        Остальные поля достраивает сама.
        """
        session = self.db.get_session()
        try:
            text = reminder.get("text", "")
            dt = self._normalize_dt(reminder.get("datetime"))

            new_reminder = Reminder(
                account_id=self.account_id,
                title=reminder.get("title") or self._short_title(text, max_len=50),
                text=text,
                datetime=dt,
                repeat_weekly=reminder.get("repeat_weekly", False),
                done=bool(reminder.get("done", False)),
            )

            session.add(new_reminder)
            session.commit()
            session.refresh(new_reminder)

            return self._reminder_to_dict(new_reminder)
        finally:
            session.close()

    def get_due_reminders(self, now: Optional[datetime] = None) -> List[Dict]:
        """Получает все невыполненные напоминания, время которых наступило"""
        now = now or datetime.now()
        session = self.db.get_session()
        try:
            stmt = select(Reminder).where(
                Reminder.account_id == self.account_id,
                Reminder.done == False,
                Reminder.datetime <= now
            ).order_by(Reminder.datetime)
            
            reminders = session.execute(stmt).scalars().all()
            return [self._reminder_to_dict(r) for r in reminders]
        finally:
            session.close()

    def mark_done(self, reminder_id: str) -> bool:
        """
        Помечает напоминание как выполненное.
        
        Для постоянных напоминаний (repeat_weekly=True) НЕ ставит done=True,
        а переносит дату на неделю вперёд и оставляет done=False.
        
        Returns: True если напоминание найдено и обновлено, False иначе
        """
        session = self.db.get_session()
        try:
            stmt = select(Reminder).where(
                Reminder.id == UUID(reminder_id),
                Reminder.account_id == self.account_id
            )
            reminder = session.execute(stmt).scalar_one_or_none()
            
            if not reminder:
                return False
            
            if reminder.repeat_weekly:
                # weekly не может быть "done" — переносим на неделю и активируем снова
                reminder.datetime = reminder.datetime + timedelta(days=7)
                reminder.done = False
            else:
                reminder.done = True
            session.commit()
            return True
        finally:
            session.close()

    def delay_one_hour(self, reminder_id: str) -> bool:
        """
        Откладывает напоминание на 1 час.
        Deprecated: лучше использовать delay(reminder_id, delta).
        """
        return self.delay(reminder_id, timedelta(hours=1))

    def delay(self, reminder_id: str, delta: timedelta) -> bool:
        """
        Откладывает напоминание на произвольный интервал времени (delta).
        Returns: True если напоминание найдено и обновлено, False иначе
        """
        session = self.db.get_session()
        try:
            stmt = select(Reminder).where(
                Reminder.id == UUID(reminder_id),
                Reminder.account_id == self.account_id
            )
            reminder = session.execute(stmt).scalar_one_or_none()

            if not reminder:
                return False

            # На всякий случай, если datetime вдруг None — можно решить, как себя вести.
            # Сейчас просто предполагаем, что значение есть.
            reminder.datetime = reminder.datetime + delta
            reminder.done = False  # раз отложили — считаем "активным" снова
            session.commit()
            return True
        finally:
            session.close()

    def get_all(self) -> List[Dict]:
        """Получает все напоминания пользователя (включая выполненные)"""
        session = self.db.get_session()
        try:
            stmt = select(Reminder).where(
                Reminder.account_id == self.account_id
            ).order_by(Reminder.datetime)
            
            reminders = session.execute(stmt).scalars().all()
            return [self._reminder_to_dict(r) for r in reminders]
        finally:
            session.close()

    def set_repeat_weekly(self, reminder_id: str, repeat: bool) -> bool:
        """
        Включает или выключает weekly-повтор для напоминания.
        repeat=True  -> repeat_weekly = True
        repeat=False -> repeat_weekly = False (и дополнительно done=True, чтобы напоминание больше не срабатывало)
        Returns: True если напоминание найдено и обновлено, False иначе
        """
        session = self.db.get_session()
        try:
            stmt = select(Reminder).where(
                Reminder.id == UUID(reminder_id),
                Reminder.account_id == self.account_id
            )
            reminder = session.execute(stmt).scalar_one_or_none()

            if not reminder:
                return False

            reminder.repeat_weekly = repeat

            # Если выключаем повтор ("больше не надо") — гасим напоминание полностью
            if not repeat:
                reminder.done = True
            else:
                # Если включаем weekly — напоминание должно быть активным
                reminder.done = False
            session.commit()
            return True
        finally:
            session.close()


