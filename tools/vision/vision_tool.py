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
Запускает пайплайн обработки изображений.
"""

from infrastructure.logging.logger import setup_logger
from tools.vision.vision_builder import VisionBuilder

logger = setup_logger("vision")


async def run_vision_chain(
        account_id: str,
        text: str,
        image_bytes: bytes = None,
        mime_type: str = "image/png",
) -> str:
    """
    Запускает chain распознавания скриншотов.

    Args:
        account_id: ID аккаунта пользователя для трекинга usage
        text: Текст сообщения пользователя
        image_bytes: Байты изображения
        mime_type: MIME-тип изображения (image/png, image/jpeg, и т.д.)

    Returns:
        str: vision extra context для добавления в промпт
    """
    builder = VisionBuilder(
        account_id=account_id,
    )
    result = await builder.analyze_screenshot(
        text=text,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )
    return result

