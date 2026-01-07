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

"""Исключения для работы с картами и локациями."""


class MaxBBoxLimitExceeded(Exception):
    """Превышен лимит сохранённых bbox для аккаунта."""
    
    def __init__(self, message: str = "MAX_GAME_LOCATIONS_REACHED"):
        self.message = message
        super().__init__(self.message)


class LocationNotFoundException(Exception):
    """Локация не найдена."""
    
    def __init__(self, location_id: int):
        self.location_id = location_id
        self.message = f"Location with id={location_id} not found"
        super().__init__(self.message)


class OverpassAPIException(Exception):
    """Ошибка при запросе к Overpass API."""
    
    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

