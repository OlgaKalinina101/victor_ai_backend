def parse_key_info(key_info: str) -> tuple[str, str]:
    """
    Парсит строку [Подкатегория:Факт] на отдельные "Подкатегория" и "Факт"
    """
    category = ""
    fact = ""
    if isinstance(key_info, str):
        parts = key_info.split(":", 1)
        if len(parts) == 2:
            category, fact = map(str.strip, parts)

    return category, fact