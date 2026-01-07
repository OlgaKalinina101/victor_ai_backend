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
Схемы для Pushi интеграции.

Содержит модели для работы с Pushi,
включая регистрацию device tokens для push-уведомлений.
"""

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """
    Запрос на регистрацию device token.
    
    Используется для привязки FCM токена устройства к пользователю
    для последующей отправки push-уведомлений о напоминаниях,
    будильниках и других событиях.
    
    Attributes:
        user_id: Уникальный идентификатор пользователя.
        token: токен устройства,
            полученный на клиенте.
    
    Notes:
        - Токен привязывается к конкретному устройству
        - При переустановке приложения токен может измениться
        - Один пользователь может иметь несколько токенов (разные устройства)
    """
    user_id: str = Field(..., description="ID пользователя")
    token: str = Field(..., description="FCM device token")
