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

import requests

from infrastructure.logging.logger import setup_logger
from settings import settings
logger = setup_logger("send_reminders")


def send_pushy_notification(token: str, title: str, body: str, data: dict):
    """Отправка уведомлений на андроид с помощью сервиса pushi"""
    url = "https://api.pushy.me/push?api_key=" + settings.PUSHY_SECRET_KEY


    logger.info(f"[DEBUG] Отправляю через Pushy API token={token[:12]}...")
    payload = {
        "to": token,  # Device token от Android
        "notification": {
            "title": title,
            "body": body
        },
        "data": data  # Дополнительные данные
    }

    response = requests.post(url, json=payload)
    return response.json()