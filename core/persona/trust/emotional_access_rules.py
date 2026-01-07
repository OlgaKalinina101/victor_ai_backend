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
