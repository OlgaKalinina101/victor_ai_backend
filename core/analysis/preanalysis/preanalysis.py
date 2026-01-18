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

from typing import Dict, Any, Union
from collections import UserDict

from core.analysis.preanalysis.preanalysis_helpers import parse_llm_json
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger


class SafeDict(UserDict):
    def __missing__(self, key):
        return ""  # подставляем пустую строку, если чего-то нет

async def analyze_dialogue(
    llm_client: LLMClient,
    prompt_template: str,
    *,
    user_message: str = "",
    message_history: str = "",
    memories: str = "",
    return_json: bool = True,
    system_prompt: str = "Ты — аналитик смысла."
) -> Union[Dict[str, Any], str]:
    """
    Универсальный раннер промптов.

    Args:
        llm_client: Экземпляр LLMClient для вызова модели.
        prompt_template: Шаблон промпта с плейсхолдерами.
        user_message: Сообщение пользователя.
        message_history: История сообщений.
        memories: Воспоминания в виде строки.
        return_json: Возвращать ли результат как JSON.
        system_prompt: Системный промпт.

    Returns:
        Union[Dict[str, Any], str]: Результат анализа (JSON или строка).
    """
    from datetime import datetime
    
    logger = setup_logger("analyze_dialogue")
    try:
        # Добавляем timestamp для ломания DeepSeek кеша
        now = datetime.now()
        time_str = now.strftime('%I:%M %p')  # Формат: "02:30 PM"
        timestamp_prefix = f"Сейчас: {time_str}\n\n"
        
        fields = SafeDict(
            text=user_message,
            message_history=message_history,
            memories=memories,
        )
        prompt = timestamp_prefix + prompt_template.format_map(fields)

        raw = await llm_client.get_response(
            system_prompt=system_prompt,
            context_prompt=prompt,
            message_history=[],
            new_message="",
            temperature=0.5
        )

        if return_json:
            result = parse_llm_json(raw)
            logger.debug(f"[DEBUG] Парсированный JSON: {result}")
            return result
        return raw.strip()

    except Exception as e:
        logger.error(f"[ERROR] Ошибка при анализе диалога: {e}")
        raise
