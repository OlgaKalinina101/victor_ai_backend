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
