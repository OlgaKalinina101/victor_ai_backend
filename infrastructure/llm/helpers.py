from logging import Logger
from typing import Optional, Tuple

def extract_usage_info(logger: Logger, response: dict) -> Optional[Tuple[int, int]]:
    """Хелпер для подсчета токенов"""
    try:
        logger.info(f"response: {response}")
        usage_data = response.get("usage")
        if not usage_data:
            return None

        # Ключи зависят от API — у OpenAI это prompt_tokens и completion_tokens
        input_tokens = usage_data.get("input_tokens") or usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("output_tokens") or usage_data.get("completion_tokens", 0)

        return input_tokens, output_tokens
    except Exception as e:
        logger.warning(f"[extract_usage_info] Ошибка: {e}")
        return None
