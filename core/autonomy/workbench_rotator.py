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
Ротация рабочего стола: перенос устаревших записей из workbench.md в Chroma.
"""

from core.autonomy.notes_store import NotesStore
from core.autonomy.workbench import Workbench
from infrastructure.logging.logger import setup_logger

logger = setup_logger("workbench_rotator")


def rotate_workbench_to_chroma(account_id: str) -> int:
    """
    Переносит устаревшие записи с рабочего стола в Chroma (хронику).

    Returns:
        Количество перенесённых записей.
    """
    workbench = Workbench(account_id=account_id)
    notes_store = NotesStore()

    expired = workbench.rotate()
    if not expired:
        return 0

    for entry in expired:
        notes_store.add_note(
            account_id=account_id,
            text=entry.text,
            created_at=entry.timestamp,
            source="workbench",
        )

    logger.info(f"[ROTATION] Перенесено {len(expired)} записей в хронику для {account_id}")
    return len(expired)
