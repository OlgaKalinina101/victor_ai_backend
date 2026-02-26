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

"""
Web search через DuckDuckGo — для рефлексии Victor.

Используется внутри reflection engine, когда Victor решает
поискать что-то в интернете ([WEB_SEARCH: запрос]).

Использует библиотеку duckduckgo-search (pip install duckduckgo-search).
API ключ не требуется.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from infrastructure.logging.logger import setup_logger

logger = setup_logger("web_search")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


async def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    """
    Выполняет поиск через DuckDuckGo.

    Args:
        query: Поисковый запрос.
        max_results: Максимальное количество результатов.

    Returns:
        Список SearchResult.
    """
    try:
        from duckduckgo_search import DDGS

        loop = asyncio.get_running_loop()
        raw_results = await loop.run_in_executor(
            None,
            lambda: DDGS().text(query, max_results=max_results),
        )

        results: list[SearchResult] = []
        for item in raw_results:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", ""),
            ))

        logger.info(f"[WEB_SEARCH] '{query}': найдено {len(results)} результатов")
        return results

    except ImportError:
        logger.error(
            "[WEB_SEARCH] Библиотека duckduckgo-search не установлена. "
            "Установите: pip install duckduckgo-search"
        )
        return []
    except Exception as e:
        logger.error(f"[WEB_SEARCH] Ошибка при поиске: {e}")
        return []


def format_search_results(results: list[SearchResult]) -> str:
    """Форматирует результаты поиска в читаемую строку для промпта."""
    if not results:
        return "Ничего не найдено."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title}")
        if r.snippet:
            lines.append(f"   {r.snippet[:200]}")
        if r.url:
            lines.append(f"   URL: {r.url}")
    return "\n".join(lines)
