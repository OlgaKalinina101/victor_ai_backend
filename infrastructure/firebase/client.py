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

from pathlib import Path
import firebase_admin
from firebase_admin import credentials, messaging

# Инициализация (один раз на процесс)
_key_path = Path(__file__).resolve().parent / "victoraiproject-a706f0bbcb99.json"
print(_key_path)
if not firebase_admin._apps:
    cred = credentials.Certificate(str(_key_path))
    firebase_admin.initialize_app(cred)

def send_push(token: str, title: str, body: str, data: dict | None = None):
    """
    HTTP v1 через firebase-admin.
    Аналог send_firebase_push, но современный и рабочий при отключённом Legacy.
    """
    payload_data = {"title": title, "text": body}
    if data:
        payload_data.update(data)

    message = messaging.Message(
        token=token,
        data=payload_data,
        android=messaging.AndroidConfig(
            priority="high",  # важно для фоновой доставки
        ),
    )
    return messaging.send(message)

