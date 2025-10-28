import json
from datetime import datetime
from typing import List, Optional

from api.response_models import Message
from infrastructure.context_store.session_context_schema import to_serializable
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.database_enums import EnergyDescription, TemperatureDescription
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load
from settings import settings

# Настройка логгера для текущего модуля
logger = setup_logger("assistant")

def convert_message_history(raw_history: List[str]) -> List[Message]:
    messages = []
    for raw in raw_history:
        if raw.startswith("user: "):
            text = raw[len("user: "):].strip()
            messages.append(Message(
                text=text,
                is_user=True,
                timestamp=round(datetime.now().timestamp())  # Можно улучшить (см. ниже)
            ))
        elif raw.startswith("assistant: "):
            text = raw[len("assistant: "):].strip()
            messages.append(Message(
                text=text,
                is_user=False,
                timestamp=round(datetime.now().timestamp())
            ))
        else:
            logger.warning(f"[history] Неизвестный формат сообщения: {raw}")
    logger.info(json.dumps([m.__dict__ for m in messages], indent=2))
    return messages

def load_serialized_session_context(account_id: str) -> dict:
    """
    Загружает и сериализует SessionContext по account_id.
    """
    db = Database()
    db_session = db.get_session()

    session_context_store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
    session_context = session_context_store.load(
        account_id=account_id, db_session=db_session
    )

    return to_serializable(session_context)


def get_provider_by_model(model, model_settings_file, logger):
    # Загружаем настройки из YAML
    model_settings = yaml_safe_load(model_settings_file, logger)

    # Проходим по всем секциям в model_settings
    for section, settings in model_settings.items():
        if settings.get("model") == model:
            return settings.get("provider")

    # Если модель не найдена, логируем и возвращаем None или вызываем исключение
    logger.error(f"Модель {model} не найдена в настройках")
    return None

def get_energy_by_value(value: str) -> Optional[EnergyDescription]:
    """Получает enum по русскому значению."""
    for item in EnergyDescription:
        if item.value == value:
            return item
    return None

def get_temperature_by_value(value: str) -> Optional[TemperatureDescription]:
    """Получает enum по русскому значению."""
    for item in TemperatureDescription:
        if item.value == value:
            return item
    return None


