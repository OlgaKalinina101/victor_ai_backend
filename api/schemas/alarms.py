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

"""
Схемы для эндпоинта /alarms.

Содержит модели для работы с будильниками пользователя,
включая настройки повторений и выбор музыкальных треков.
"""

from typing import Optional, List
from pydantic import BaseModel


class AlarmItemDto(BaseModel):
    """
    Отдельный будильник пользователя.
    
    Содержит время, режим повторения и статус активности будильника.
    """
    time: Optional[str] = None
    repeatMode: Optional[str] = None
    enabled: bool = True


class AlarmUpdateDto(BaseModel):
    """
    Запрос на обновление полного списка будильников пользователя.
    
    Содержит все будильники пользователя и выбранный трек
    для воспроизведения при срабатывании.
    """
    account_id: str
    alarms: List[AlarmItemDto]
    selected_track_id: Optional[int] = None

