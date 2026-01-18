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

from infrastructure.firebase.client import send_push
from infrastructure.firebase.tokens import get_user_tokens

def send_reminder(user_id: str, title: str, body: str, reminder_id: str):
    tokens = get_user_tokens(user_id)
    for token in tokens:
        send_push(
            token=token,
            title=title,
            body=body,
            data={"reminder_id": reminder_id}
        )
