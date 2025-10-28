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

