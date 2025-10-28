import asyncio
from pathlib import Path
from typing import Any, Coroutine

from core.chain.communication import CommunicationPipeline
from infrastructure.embeddings.runner import preload_models
from infrastructure.logging.logger import setup_logger

logger = setup_logger("tracebook")

async def run_communication(
    account_id: str,
    text: str,
) -> int:
    """Вызывает диалог"""
    preload_models()
    pipline = CommunicationPipeline(
        account_id=account_id,
        user_message=text,
        system_prompt_path=Path("C:/Users/Alien/PycharmProjects/Victor_AI_Core/core/persona/prompts/system.yaml"),
        context_prompt_path=Path("C:/Users/Alien/PycharmProjects/Victor_AI_Core/core/dialog/templates/context.yaml")
    )
    # Этап 1: Анализ сообщения
    user_profile, metadata, reaction_data, session_context = await pipline._analyze_message()
    logger.info(f"[DEBUG] Категория сообщения: {metadata.message_category}")

    # Этап 2: Оценка эмоционального состояния
    victor_profile = await pipline._evaluate_emotional_state(session_context, metadata)
    logger.info(f"[DEBUG] victor_profile: {victor_profile}")

    # Этап 3: Оценка глубины коммуникации
    emotional_access = pipline._calculate_emotional_access(user_profile, victor_profile, metadata)
    logger.info(f"[DEBUG] Эмоциональный доступ: {emotional_access}")

    # Этап 4: Построение промптов
    system_prompt, context_prompt = await pipline._build_prompts(user_profile, victor_profile, metadata,
                                                              reaction_data, emotional_access, session_context)
    logger.info(f"[DEBUG] Системный промпт: {str(system_prompt)}")
    logger.info(f"[DEBUG] Контекстный промпт: {str(context_prompt)}")

    return emotional_access

if __name__ == "__main__":
    asyncio.run(run_communication(account_id="test_user", text="C другой стороны новоиспеченная Португальская сеньорина все еще забывает писать await перед вызовом асинхронной функции"))