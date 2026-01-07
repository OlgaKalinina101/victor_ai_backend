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

from typing import AsyncGenerator, Any

from core.chain.communication import CommunicationPipeline
from infrastructure.logging.logger import setup_logger

logger = setup_logger("tracebook")

async def run_communication(
    account_id: str,
    text: str,
    function_call: str,
    geo: Any,
    extra_context: str = None,
    llm_client=None,
    db=None,
    session_context_store=None,
    embedding_pipeline=None,
    image_bytes: bytes = None,  # 🖼️ Байты изображения
    mime_type: str = "image/png",  # 🖼️ MIME-тип изображения
    swipe_message_id: int | None = None,  # 👆 свайп старого сообщения (id из dialogue_history)
) -> AsyncGenerator[str | dict, None]:
    """Вызывает диалог с поддержкой изображений"""

    pipeline = CommunicationPipeline(
        account_id=account_id,
        user_message=text,
        llm_client=llm_client,
        db=db,
        session_context_store=session_context_store,
        embedding_pipeline=embedding_pipeline,
        function_call=function_call,
        geo=geo,
        extra_context=extra_context,
        image_bytes=image_bytes,  # 🖼️ Пробрасываем изображение
        mime_type=mime_type,  # 🖼️ Пробрасываем MIME-тип
        swipe_message_id=swipe_message_id,
    )
    async for chunk in pipeline.process():
        yield chunk
