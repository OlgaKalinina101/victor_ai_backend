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

