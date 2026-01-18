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

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from logging import Logger
from pathlib import Path
from typing import List, Optional, Any, Dict

from fastapi import HTTPException

from api.schemas.common import Message
from core.persona.emotional.emotional_map import EMOJI_TO_EMOTIONS
from infrastructure.context_store.session_context_schema import to_serializable, SessionContext
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.database_enums import EnergyDescription, TemperatureDescription
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load
from models.assistant_models import AssistantMood
from settings import settings

# Настройка логгера для текущего модуля
logger = setup_logger("assistant")

def convert_message_history(raw_history: List[str]) -> List[Message]:
    """
    Преобразует сырую историю сообщений в список объектов [Message].

    Ожидает строки формата:
    - "user: текст сообщения"
    - "assistant: текст сообщения"

    Для каждой строки создаётся [Message] с полями:
    - text: очищенный текст без префикса "user: " / "assistant: "
    - is_user: True, если сообщение от пользователя, иначе False
    - timestamp: текущий timestamp на момент конвертации

    Сообщения с неизвестным префиксом логируются как warning и пропускаются.

    Args:
        raw_history: Список строковой истории сообщений.

    Returns:
        Список объектов [Message] в том порядке, в котором они были в raw_history.
    """
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
    Загружает SessionContext для указанного пользователя и приводит его к сериализуемому виду.

    Читает контекст из хранилища [SessionContextStore], при необходимости
    используя базу данных для восстановления состояния, а затем преобразует
    контекст к структуре, пригодной для JSON-сериализации.

    Args:
        account_id: Идентификатор пользователя, для которого нужно загрузить контекст.

    Returns:
        Словарь с сериализованным SessionContext, готовый к возврату через API.
    """
    db = Database.get_instance()
    db_session = db.get_session()

    session_context_store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
    session_context = session_context_store.load(
        account_id=account_id, db_session=db_session
    )

    return to_serializable(session_context)


def get_provider_by_model(model, model_settings_file, logger):
    """
    Определяет провайдера по имени модели на основе YAML-настроек.

    Читает YAML-файл с настройками моделей, находит секцию,
    где поле "model" совпадает с переданным [model],
    и возвращает значение поля "provider".

    Args:
        model: Имя модели (например, "gpt-4.1" или "grok-2").
        model_settings_file: Путь или файловый объект с YAML-настройками.
        logger: Логгер для логирования ошибок.

    Returns:
        Строка с именем провайдера (например, "openai", "xai") или None,
        если модель не найдена в конфиге.
    """
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
    """
    Ищет значение перечисления [EnergyDescription] по его русскому текстовому значению.

    Args:
        value: Русское описание энергии трека
            (например, "спокойный", "энергичный" и т.п.).

    Returns:
        Соответствующий элемент [EnergyDescription], если найден,
        иначе None.
    """
    for item in EnergyDescription:
        if item.value == value:
            return item
    return None

def get_temperature_by_value(value: str) -> Optional[TemperatureDescription]:
    """
    Ищет значение перечисления [TemperatureDescription] по его русскому текстовому значению.

    Args:
        value: Русское описание "температуры" трека

    Returns:
        Соответствующий элемент [TemperatureDescription], если найден,
        иначе None.
    """
    for item in TemperatureDescription:
        if item.value == value:
            return item
    return None


def clean_message_text(text: str, role: str) -> str:
    """
    Очищает текст сообщения от префиксов вида "user: " или "assistant: ".

    В зависимости от роли:
    - если role == "user" и текст начинается с "user: ", префикс обрезается
    - если role == "assistant" и текст начинается с "assistant: ", префикс обрезается
    - в остальных случаях текст возвращается без изменений

    Args:
        text: Исходный текст сообщения.
        role: Роль отправителя ("user" или "assistant").

    Returns:
        Очищенный текст без технических префиксов.
    """
    if not text:
        return text

    # Убираем префиксы в зависимости от роли
    if role == "user" and text.startswith("user: "):
        return text[6:]  # убираем "user: "
    elif role == "assistant" and text.startswith("assistant: "):
        return text[11:]  # убираем "assistant: "

    return text


def _map_emoji_to_mood(emoji_char: str) -> tuple[Optional[AssistantMood], float]:
    """
    Маппит один emoji на доминирующую эмоцию с весом.

    Args:
        emoji_char: Эмодзи символ

    Returns:
        Кортеж (доминирующая_эмоция, суммарный_вес) или (None, 0.0)
    """
    if emoji_char not in EMOJI_TO_EMOTIONS:
        return None, 0.0

    mood_weights = defaultdict(float)
    for mood, weight in EMOJI_TO_EMOTIONS[emoji_char]:
        mood_weights[mood] += weight

    if not mood_weights:
        return None, 0.0

    # Выбираем доминирующую эмоцию
    dominant_mood = max(mood_weights.items(), key=lambda x: x[1])
    return dominant_mood[0], dominant_mood[1]


def update_victor_state_from_emoji(session_context: SessionContext, emoji_char: str) -> None:
    """
    Обновляет victor_mood и victor_intensity на основе emoji.

    Args:
        session_context: Контекст сессии для обновления
        emoji_char: Эмодзи символ
    """
    # Получаем предыдущие значения
    prev_intensity = session_context.get_last_victor_intensity(fallback=0.0)

    # Маппим emoji на эмоцию
    mood, weight = _map_emoji_to_mood(emoji_char)

    if mood is None:
        logger.debug(f"[UPDATE_VICTOR_STATE] Emoji '{emoji_char}' не найден в маппинге")
        return

    # Обновляем intensity (добавляем вес emoji, умноженный на коэффициент)
    # Коэффициент 0.5 чтобы emoji не слишком сильно влияли
    new_intensity = prev_intensity + (weight * 0.5)

    # Проверяем на переполнение (> 12)
    if new_intensity > 12.0:
        logger.info(f"[UPDATE_VICTOR_STATE] Intensity переполнен: {new_intensity:.2f} > 12, переход на другую эмоцию")
        # При переполнении: сбрасываем intensity и можем сменить настроение
        # Упрощенная логика: просто вычитаем 12
        new_intensity = new_intensity - 12.0

    # Ограничиваем в пределах [0, 12]
    new_intensity = max(0.0, min(new_intensity, 12.0))

    # Обновляем историю
    session_context.victor_mood_history.append(mood.value)
    session_context.victor_intensity_history.append(round(new_intensity, 2))

    logger.info(
        f"[UPDATE_VICTOR_STATE] Обновлено: mood={mood.value}, intensity={new_intensity:.2f}, emoji='{emoji_char}'")


def safe_json_loads(s: Optional[str]) -> Any:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in 'geo': {e}")


def add_user_message_to_context(account_id: str, text: str, db, context_store, logger: Logger) -> None:
    """
    Добавляет user-сообщение в контекст и сохраняет.

    НЕ обновляет last_update, чтобы не сбросить таймер staleness.
    Время обновится позже в MessageAnalyzer после проверки staleness.
    """
    db_session = db.get_session()
    try:
        session_context = context_store.load(account_id, db_session)
        session_context.add_user_message(text)
        context_store.save(session_context, update_timestamp=False)
        logger.info(f"[WEB_DEMO] User-сообщение добавлено в контекст: {text[:50]}...")
    finally:
        db_session.close()


def normalize_demo_key(demo_key: str) -> str:
    key = (demo_key or "").strip()
    if len(key) < 4:
        raise HTTPException(status_code=400, detail="demo_key is too short")
    return key


def validate_demo_key_from_file(demo_key: str) -> None:
    path = settings.DEMO_KEYS_DIR
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="demo_keys.json not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"demo_keys.json invalid: {e}")

    allowed = set(data.get("demo_keys", []))
    if demo_key not in allowed:
        raise HTTPException(status_code=401, detail="Invalid demo key")


def normalize_account_id(account_id: str) -> str:
    acc = (account_id or "").strip()
    if not acc:
        raise HTTPException(status_code=400, detail="account_id is empty")
    return acc


def create_access_token(account_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=24)
    payload = {"sub": account_id, "scope": "web_demo", "exp": int(exp.timestamp())}
    # return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return f"DEMO_TOKEN_FOR_{account_id}"


def build_initial_state(chat_meta=None) -> Dict[str, Any]:
    return {
        "connection": True,
        "trust_level": getattr(chat_meta, "trust_level", None) if chat_meta else None,
        "relationship_level": getattr(chat_meta, "relationship_level", None) if chat_meta else None,
        "gender": getattr(chat_meta, "gender", None) if chat_meta else None,
        "is_creator": getattr(chat_meta, "is_creator", None) if chat_meta else None,
        "model": getattr(chat_meta, "model", None) if chat_meta else None,
    }



