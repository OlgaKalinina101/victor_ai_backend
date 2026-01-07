# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

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

