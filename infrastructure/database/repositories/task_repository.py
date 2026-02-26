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

"""Репозиторий для внутренних задач Victor (victor_tasks)."""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from infrastructure.database.models import VictorTask, VictorTaskTrigger, VictorTaskStatus
from infrastructure.logging.logger import setup_logger

logger = setup_logger("task_repository")


class TaskRepository:
    def __init__(self, db_session: Session):
        self.session = db_session

    def create(
        self,
        account_id: str,
        text: str,
        trigger_type: VictorTaskTrigger = VictorTaskTrigger.MANUAL,
        trigger_value: Optional[str] = None,
        source: str = "reflection",
    ) -> VictorTask:
        """Создаёт новую задачу."""
        task = VictorTask(
            account_id=account_id,
            text=text,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            source=source,
        )
        self.session.add(task)
        self.session.commit()
        logger.info(f"[TASK] Создана задача #{task.id}: {text[:60]}...")
        return task

    def get_pending(self, account_id: str) -> list[VictorTask]:
        """Возвращает все pending задачи для аккаунта."""
        return (
            self.session.query(VictorTask)
            .filter(
                VictorTask.account_id == account_id,
                VictorTask.status == VictorTaskStatus.PENDING,
            )
            .order_by(VictorTask.created_at)
            .all()
        )

    def get_pending_by_trigger(
        self,
        account_id: str,
        trigger_type: VictorTaskTrigger,
    ) -> list[VictorTask]:
        """Возвращает pending задачи определённого типа триггера."""
        return (
            self.session.query(VictorTask)
            .filter(
                VictorTask.account_id == account_id,
                VictorTask.status == VictorTaskStatus.PENDING,
                VictorTask.trigger_type == trigger_type,
            )
            .order_by(VictorTask.created_at)
            .all()
        )

    def mark_done(self, task_id: int) -> None:
        """Помечает задачу как выполненную."""
        task = self.session.query(VictorTask).get(task_id)
        if task:
            task.status = VictorTaskStatus.DONE
            self.session.commit()
            logger.info(f"[TASK] Задача #{task_id} помечена как done")

    def mark_cancelled(self, task_id: int) -> None:
        """Отменяет задачу."""
        task = self.session.query(VictorTask).get(task_id)
        if task:
            task.status = VictorTaskStatus.CANCELLED
            self.session.commit()
            logger.info(f"[TASK] Задача #{task_id} отменена")
