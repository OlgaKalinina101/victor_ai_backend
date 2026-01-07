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

