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

"""Тестовый скрипт для проверки ItemSelector"""

import asyncio
from pathlib import Path

from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from .item_selector import ItemSelector

logger = setup_logger("test_selector")


async def t_item_selector():
    """Тестирует выбор позиции из скриншота"""

    # Путь к тестовому скриншоту
    test_screenshot_path = Path(__file__).parent.parent / "test_user_1764111859497.webp"

    if not test_screenshot_path.exists():
        logger.error(f"Тестовый скриншот не найден: {test_screenshot_path}")
        return

    # Читаем скриншот
    with open(test_screenshot_path, "rb") as f:
        screenshot_bytes = f.read()

    logger.info(f"Загружен тестовый скриншот: {len(screenshot_bytes)} bytes")

    # Инициализируем селектор
    account_id = "test_user"
    selector = ItemSelector(account_id=account_id, logger=logger)

    # Получаем сессию БД
    db = Database()
    db_session = db.get_session()

    try:
        # Вызываем выбор позиции
        result = await selector.select_item(
            screenshot_bytes=screenshot_bytes,
            search_query="блинчики с творогом",
            mime_type="image/webp",
            db_session=db_session,
        )

        logger.info("=" * 60)
        logger.info("РЕЗУЛЬТАТ ВЫБОРА:")
        logger.info(f"  ID: {result['id']}")
        logger.info(f"  Позиция: {result['selected_item']}")
        logger.info(f"  Тип совпадения: {result['match_type']}")
        logger.info(f"  Сообщение: {result['user_message']}")
        logger.info("=" * 60)

    finally:
        db_session.close()


if __name__ == "__main__":
    asyncio.run(t_item_selector())

