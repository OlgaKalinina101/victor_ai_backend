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
Рабочий стол Victor — оперативная память.

Файл workbench.md хранит мысли за последние 24-48 часов.
Каждая запись — timestamped блок:

    ### 2026-02-26 02:00
    Текст мысли...

При ротации записи старше WORKBENCH_RETENTION_HOURS (default 48)
переносятся в Chroma (коллекция victor_notes) и удаляются из файла.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from infrastructure.logging.logger import setup_logger
from settings import settings

logger = setup_logger("workbench")

_ENTRY_HEADER = re.compile(r"^### (\d{4}-\d{2}-\d{2} \d{2}:\d{2})$", re.MULTILINE)
_TS_FORMAT = "%Y-%m-%d %H:%M"


@dataclass
class WorkbenchEntry:
    """Одна запись с рабочего стола."""
    timestamp: datetime
    text: str

    @property
    def header(self) -> str:
        return f"### {self.timestamp.strftime(_TS_FORMAT)}"


class Workbench:
    """Чтение / append / ротация для workbench.md."""

    def __init__(self, account_id: str, base_dir: Optional[Path] = None):
        self.account_id = account_id
        self.base_dir = (base_dir or settings.AUTONOMY_DATA_DIR) / account_id
        self.file_path = self.base_dir / "workbench.md"
        self._ensure_file()

    # ------------------------------------------------------------------
    # public: чтение
    # ------------------------------------------------------------------

    def read_full(self) -> str:
        """Возвращает содержимое workbench.md целиком (для промпта рефлексии)."""
        return self.file_path.read_text(encoding="utf-8")

    def read_entries(self) -> list[WorkbenchEntry]:
        """Парсит workbench.md и возвращает список записей."""
        text = self.read_full()
        return _parse_entries(text)

    def read_recent(self, hours: int = 24) -> list[WorkbenchEntry]:
        """Возвращает записи не старше ``hours`` часов."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [e for e in self.read_entries() if e.timestamp >= cutoff]

    # ------------------------------------------------------------------
    # public: запись
    # ------------------------------------------------------------------

    def append(self, text: str, timestamp: Optional[datetime] = None) -> WorkbenchEntry:
        """Добавляет новую запись в конец workbench.md."""
        ts = timestamp or datetime.now()
        entry = WorkbenchEntry(timestamp=ts, text=text.strip())

        content = self.read_full().rstrip("\n")
        block = f"\n\n{entry.header}\n{entry.text}\n"

        self.file_path.write_text(content + block, encoding="utf-8")
        logger.info(f"[WORKBENCH] Добавлена запись {ts.strftime(_TS_FORMAT)} для {self.account_id}")
        return entry

    # ------------------------------------------------------------------
    # public: ротация
    # ------------------------------------------------------------------

    def rotate(self, retention_hours: Optional[int] = None) -> list[WorkbenchEntry]:
        """
        Удаляет из файла записи старше ``retention_hours`` и возвращает их.

        Вызывающий код должен переместить возвращённые записи в Chroma.

        Returns:
            Список удалённых (устаревших) записей.
        """
        hours = retention_hours if retention_hours is not None else settings.WORKBENCH_RETENTION_HOURS
        cutoff = datetime.now() - timedelta(hours=hours)

        entries = self.read_entries()
        keep: list[WorkbenchEntry] = []
        expired: list[WorkbenchEntry] = []

        for entry in entries:
            if entry.timestamp >= cutoff:
                keep.append(entry)
            else:
                expired.append(entry)

        if not expired:
            return []

        self._write_entries(keep)
        logger.info(
            f"[WORKBENCH] Ротация для {self.account_id}: "
            f"удалено {len(expired)}, осталось {len(keep)}"
        )
        return expired

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        """Создаёт пустой workbench.md, если его нет."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("# Рабочий стол\n", encoding="utf-8")
            logger.info(f"[WORKBENCH] Создан новый workbench.md для {self.account_id}")

    def _write_entries(self, entries: list[WorkbenchEntry]) -> None:
        """Перезаписывает файл из списка записей (используется при ротации)."""
        lines = ["# Рабочий стол\n"]
        for entry in entries:
            lines.append(f"\n{entry.header}\n{entry.text}\n")
        self.file_path.write_text("\n".join(lines), encoding="utf-8")


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _parse_entries(text: str) -> list[WorkbenchEntry]:
    """Парсит markdown-файл и возвращает список WorkbenchEntry."""
    entries: list[WorkbenchEntry] = []
    parts = _ENTRY_HEADER.split(text)

    # parts: [преамбула, ts1, body1, ts2, body2, ...]
    # Нечётные индексы — timestamps, чётные (после первого) — тела
    i = 1
    while i < len(parts) - 1:
        ts_str = parts[i].strip()
        body = parts[i + 1].strip()
        try:
            ts = datetime.strptime(ts_str, _TS_FORMAT)
            if body:
                entries.append(WorkbenchEntry(timestamp=ts, text=body))
        except ValueError:
            logger.warning(f"[WORKBENCH] Не удалось распарсить timestamp: {ts_str}")
        i += 2

    return entries
