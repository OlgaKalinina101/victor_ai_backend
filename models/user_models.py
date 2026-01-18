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

from dataclasses import dataclass

from models.user_enums import Gender, RelationshipLevel


@dataclass
class UserProfile:
    """Профиль пользователя."""
    account_id: str | None = None
    gender: Gender = Gender.OTHER
    relationship: RelationshipLevel = RelationshipLevel.STRANGER
    trust_level: int = 0
    model: str = "gpt-4o"

