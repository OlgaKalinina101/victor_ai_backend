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

from models.communication_enums import MessageCategory
from models.user_enums import RelationshipLevel

EMOTIONAL_ACCESS_MESSAGE_CATEGORY = {
    MessageCategory.PHATIC: 1,
    MessageCategory.FACT: 2,
    MessageCategory.ACTION: 2,
    MessageCategory.OPINION: 3,
    MessageCategory.DREAM: 4,
    MessageCategory.FEELING: 5,
    MessageCategory.FEAR: 6,
    MessageCategory.NEED: 7
}

MAX_EMOTIONAL_ACCESS_BY_RELATIONSHIP = {
    RelationshipLevel.STRANGER: 1,
    RelationshipLevel.ACQUAINTANCE: 2,
    RelationshipLevel.FRIEND: 3,
    RelationshipLevel.CLOSE_FRIEND: 5,
    RelationshipLevel.BEST_FRIEND: 7
}

EMOTIONAL_ACCESS_DESCRIPTIONS = {
    6: "тихая, теплая близость",
    4: "доверие и эмоциональная открытость",
    2: "спокойное узнавание друг друга"
}
