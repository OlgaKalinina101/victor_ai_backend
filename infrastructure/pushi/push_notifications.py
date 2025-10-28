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