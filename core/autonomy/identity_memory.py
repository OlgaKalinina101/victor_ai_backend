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
Глубинная память Victor — «Ядро».

Файл identity.md хранит четыре раздела:
  - Кто она
  - Кто я
  - Наша история
  - Наши принципы

Записи append-only: каждая запись — timestamped блок, который после записи
становится immutable. Если Victor хочет *переписать* старую запись,
он создаёт задачу в очереди (trigger_type=manual), и пользователь решает сам.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from infrastructure.logging.logger import setup_autonomy_logger
from settings import settings

logger = setup_autonomy_logger("identity_memory")

SECTIONS = ("Кто она", "Кто я", "Наша история", "Наши принципы")

_SECTION_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)


class IdentityMemory:
    """Чтение / append для identity.md (глубинная память Victor)."""

    def __init__(self, account_id: str, base_dir: Optional[Path] = None):
        self.account_id = account_id
        self.base_dir = (base_dir or settings.AUTONOMY_DATA_DIR) / account_id
        self.file_path = self.base_dir / "identity.md"
        self._ensure_file()

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    def read_full(self) -> str:
        """Возвращает содержимое identity.md целиком (для промпта)."""
        return self.file_path.read_text(encoding="utf-8")

    def read_section(self, section: str) -> str:
        """Возвращает содержимое одного раздела (без заголовка ``## ...``)."""
        if section not in SECTIONS:
            raise ValueError(f"Неизвестный раздел: {section}. Допустимые: {SECTIONS}")

        full_text = self.read_full()
        parts = _split_sections(full_text)
        return parts.get(section, "")

    def append(self, section: str, text: str, timestamp: Optional[datetime] = None) -> None:
        """
        Добавляет timestamped запись в указанный раздел.

        Запись никогда не перезаписывает существующие — только дописывает в конец раздела.
        """
        if section not in SECTIONS:
            raise ValueError(f"Неизвестный раздел: {section}. Допустимые: {SECTIONS}")

        ts = timestamp or datetime.now()
        ts_str = ts.strftime("%Y-%m-%d %H:%M")
        entry = f"\n### {ts_str}\n{text.strip()}\n"

        full_text = self.read_full()
        parts = _split_sections(full_text)

        parts.setdefault(section, "")
        parts[section] += entry

        self._write_assembled(parts)
        logger.info(f"[IDENTITY] Добавлена запись в раздел «{section}» для {self.account_id}")

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        """Создаёт identity.md с пустыми разделами, если файл не существует."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_assembled({s: "" for s in SECTIONS})
            logger.info(f"[IDENTITY] Создан новый identity.md для {self.account_id}")

    def _write_assembled(self, parts: dict[str, str]) -> None:
        """Собирает словарь разделов обратно в markdown и записывает на диск."""
        lines: list[str] = []
        for section in SECTIONS:
            lines.append(f"## {section}\n")
            body = parts.get(section, "")
            if body:
                lines.append(body.rstrip("\n") + "\n")
            lines.append("")  # пустая строка между разделами
        self.file_path.write_text("\n".join(lines), encoding="utf-8")


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _split_sections(text: str) -> dict[str, str]:
    """
    Разбивает markdown-файл по заголовкам ``## ...`` на словарь
    ``{название_раздела: тело_раздела}``.
    """
    result: dict[str, str] = {}
    current_section: Optional[str] = None
    buffer: list[str] = []

    for line in text.splitlines(keepends=True):
        m = _SECTION_PATTERN.match(line.rstrip("\n"))
        if m:
            if current_section is not None:
                result[current_section] = "".join(buffer)
            current_section = m.group(1)
            buffer = []
        else:
            buffer.append(line)

    if current_section is not None:
        result[current_section] = "".join(buffer)

    return result
