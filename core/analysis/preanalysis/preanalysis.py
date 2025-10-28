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
    logger = setup_logger("analyze_dialogue")
    try:
        fields = SafeDict(
            text=user_message,
            message_history=message_history,
            memories=memories,
        )
        prompt = prompt_template.format_map(fields)

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
