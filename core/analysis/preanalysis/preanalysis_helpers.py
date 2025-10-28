import json
import ast
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union

def is_more_than_6_hours_passed(last_message_time: datetime) -> bool:
    """Проверяет, прошло ли больше 6 часов с момента последнего сообщения"""
    return datetime.now() - last_message_time > timedelta(hours=6)

#TODO: расширенный вариант этой функции, который умеет сам себя чинить через LLM, если парсинг не удался
def parse_llm_json(
    raw: str,
    expected_keys: Optional[List[str]] = None,
    default_to_value: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Универсальный парсер JSON-ответов от LLM.
    Поддерживает OpenAI, X.AI.

    Args:
        raw: Строка от модели (может содержать json, markdown-блоки, просто ключ:значение и т.д.)
        expected_keys: Если переданы, будет проверять наличие хотя бы одного ключа из списка.
        default_to_value: Если True, то при неудачном парсинге вернет {"value": raw}.

    Returns:
        dict | None
    """
    if not raw or not isinstance(raw, str):
        return None

    # 1. Удаляем markdown-блоки ```json ... ```
    raw = re.sub(r"```json\s*(.*?)\s*```", r"\1", raw, flags=re.DOTALL).strip()
    raw = re.sub(r"```(.*?)```", r"\1", raw, flags=re.DOTALL).strip()

    # 2. Попытки парсинга JSON
    attempts = [
        lambda x: json.loads(x),                    # нормальный JSON
        lambda x: json.loads(x.replace("'", '"')),  # с одинарными кавычками
        lambda x: ast.literal_eval(x),              # Python-подобные ответы
    ]

    for attempt in attempts:
        try:
            result = attempt(raw)
            if isinstance(result, dict):
                # Проверяем expected_keys, если они есть
                if expected_keys and not any(k in result for k in expected_keys):
                    continue
                return result
            elif isinstance(result, str):
                return {"value": result}
        except Exception:
            continue

    # 3. Обрабатываем простые строки "key: value"
    if ":" in raw and not raw.strip().startswith("{"):
        try:
            key, value = raw.split(":", 1)
            return {key.strip().strip('"\''): value.strip().strip('"\'')}
        except Exception:
            pass

    # 4. Строка в кавычках → {"value": "..."}
    if raw.startswith(('"', "'")) and raw.endswith(('"', "'")):
        return {"value": raw[1:-1]}

    # 5. Фоллбэк
    if default_to_value:
        return {"value": raw}

    return None


from datetime import datetime, timezone, timedelta


def humanize_timestamp(created_at_iso: Optional[str]) -> str:
    """
    Преобразует ISO timestamp в человекочитаемый формат:
    - До недели: "2 дня назад", "5 дней назад"
    - До месяца: "2 недели назад", "3 недели назад"
    - Больше месяца: "давно"
    """
    if not created_at_iso:
        return "давно"

    try:
        created_at = datetime.fromisoformat(created_at_iso)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = now - created_at

        days = delta.days

        # До недели
        if days == 0:
            return "сегодня"
        elif days == 1:
            return "вчера"
        elif days < 7:
            return f"{days} дня назад" if days in [2, 3, 4] else f"{days} дней назад"

        # До месяца
        elif days < 30:
            weeks = days // 7
            if weeks == 1:
                return "неделю назад"
            elif weeks in [2, 3, 4]:
                return f"{weeks} недели назад"
            else:
                return f"{weeks} недель назад"

        # Больше месяца
        else:
            months = days // 30
            if months == 1:
                return "месяц назад"
            else:
                return "давно"

    except Exception:
        return "давно"



