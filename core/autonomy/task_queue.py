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

"""
Очередь внутренних задач Victor.

Тонкая обёртка над TaskRepository для использования из ReflectionEngine
и AutonomyPostAnalyzer.
"""

import re
from typing import Optional

from infrastructure.database.models import VictorTask, VictorTaskTrigger
from infrastructure.database.repositories.task_repository import TaskRepository
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_autonomy_logger

logger = setup_autonomy_logger("task_queue")


class TaskQueue:
    def __init__(self, account_id: str, db: Optional[Database] = None):
        self.account_id = account_id
        self.db = db or Database.get_instance()

    def create_from_payload(self, payload: str, source: str = "reflection") -> Optional[VictorTask]:
        """
        Парсит payload из команды [CREATE_TASK: текст | trigger]
        и создаёт задачу в БД.

        Примеры payload:
          "Напомнить ей про годовщину | time:2026-03-01 09:00"
          "Спросить про кино | next_session"
          "Переписать запись в Кто я | manual"
          "Просто мысль без триггера"
        """
        parts = payload.rsplit("|", maxsplit=1)
        text = parts[0].strip()
        trigger_raw = parts[1].strip() if len(parts) > 1 else "manual"

        trigger_type, trigger_value = _parse_trigger(trigger_raw)

        with self.db.get_session() as session:
            repo = TaskRepository(session)
            if trigger_type == VictorTaskTrigger.TIME and trigger_value:
                pending_same_time = repo.get_pending_time_by_value(self.account_id, trigger_value)
                exact_duplicate = next(
                    (t for t in pending_same_time if t.text.strip() == text),
                    None,
                )
                if exact_duplicate:
                    logger.info(
                        f"[TASK] Пропуск exact duplicate: #{exact_duplicate.id} "
                        f"на {trigger_value} уже существует"
                    )
                    return exact_duplicate

                if pending_same_time:
                    repo.cancel_tasks([t.id for t in pending_same_time])
                    logger.info(
                        f"[TASK] Отменены предыдущие TIME-задачи на {trigger_value} "
                        f"перед созданием новой"
                    )

            return repo.create(
                account_id=self.account_id,
                text=text,
                trigger_type=trigger_type,
                trigger_value=trigger_value,
                source=source,
            )

    def get_pending(self) -> list[VictorTask]:
        """Возвращает все pending задачи."""
        with self.db.get_session() as session:
            repo = TaskRepository(session)
            return repo.get_pending(self.account_id)

    def get_pending_for_session(self) -> list[VictorTask]:
        """Возвращает задачи с trigger_type=next_session."""
        with self.db.get_session() as session:
            repo = TaskRepository(session)
            return repo.get_pending_by_trigger(
                self.account_id,
                VictorTaskTrigger.NEXT_SESSION,
            )

    def mark_done(self, task_id: int) -> None:
        with self.db.get_session() as session:
            repo = TaskRepository(session)
            repo.mark_done(task_id)

    def cancel_duplicate_time_task(self, trigger_value: str, source: str | None = None) -> int:
        """Отменяет все pending TIME-задачи на то же время. source оставлен для совместимости."""
        with self.db.get_session() as session:
            repo = TaskRepository(session)
            duplicates = repo.get_pending_time_by_value(self.account_id, trigger_value.strip())
            cancelled = repo.cancel_tasks([t.id for t in duplicates])
            if cancelled:
                logger.info(
                    f"[TASK] Отменено {cancelled} дублей на {trigger_value} "
                    f"(source={source}, ignored)"
                )
            return cancelled

    def format_for_prompt(self, tasks: list[VictorTask]) -> str:
        """Форматирует список задач для промпта рефлексии."""
        if not tasks:
            return ""
        lines = []
        for t in tasks:
            trigger_info = f" ({t.trigger_type.value}"
            if t.trigger_value:
                trigger_info += f": {t.trigger_value}"
            trigger_info += ")"
            lines.append(f"- [{t.id}] {t.text}{trigger_info}")
        return "\n".join(lines)


def _parse_trigger(raw: str) -> tuple[VictorTaskTrigger, Optional[str]]:
    """Парсит строку триггера."""
    raw_lower = raw.lower().strip()

    if raw_lower == "next_session":
        return VictorTaskTrigger.NEXT_SESSION, None

    if raw_lower == "manual":
        return VictorTaskTrigger.MANUAL, None

    time_match = re.match(r"^time:\s*(.+)$", raw, re.IGNORECASE)
    if time_match:
        return VictorTaskTrigger.TIME, time_match.group(1).strip()

    return VictorTaskTrigger.MANUAL, None
