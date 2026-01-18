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

def parse_key_info(key_info: str) -> tuple[str, str]:
    """
    Парсит строку [Подкатегория:Факт] на отдельные "Подкатегория" и "Факт"
    """
    category = ""
    fact = ""
    if isinstance(key_info, str):
        parts = key_info.split(":", 1)
        if len(parts) == 2:
            category, fact = map(str.strip, parts)

    return category, fact