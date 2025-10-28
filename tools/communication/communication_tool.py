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
) -> AsyncGenerator[str, None]:
    """Вызывает диалог"""

    pipeline = CommunicationPipeline(
        account_id=account_id,
        user_message=text,
        llm_client=llm_client,
        db=db,
        session_context_store=session_context_store,
        embedding_pipeline=embedding_pipeline,
        function_call=function_call,
        geo=geo,
        extra_context=extra_context
    )
    async for chunk in pipeline.process():
        yield chunk
