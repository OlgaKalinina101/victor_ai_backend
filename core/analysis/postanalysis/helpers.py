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