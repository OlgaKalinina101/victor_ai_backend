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

"""Тестовый скрипт для проверки сохранения user-сообщений в carebank_tool"""

import asyncio
from pathlib import Path

from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from settings import settings
from tools.carebank.carebank_tool import run_care_bank_chain

logger = setup_logger("test_carebank")


async def t_carebank_with_context_save():
    """Тестирует сохранение user-сообщения в контекст"""
    
    account_id = "test_user"
    test_message = "Закажи нам пожалуйста шоколадное эскимо, чипсы с лисичками, капучино и гречневую шоколадку"
    
    logger.info("=" * 60)
    logger.info("ТЕСТ: Сохранение user-сообщения в контекст")
    logger.info("=" * 60)
    
    # Шаг 1: Проверяем контекст ДО вызова
    db = Database()
    db_session = db.get_session()
    
    try:
        context_store = SessionContextStore(storage_path=settings.SESSION_CONTEXT_DIR)
        context_before = context_store.load(account_id, db_session)
        
        logger.info(f"\n📋 Контекст ДО вызова:")
        logger.info(f"   Количество сообщений: {len(context_before.message_history)}")
        if context_before.message_history:
            logger.info(f"   Последние 3 сообщения:")
            for msg in context_before.message_history[-3:]:
                logger.info(f"      - {msg[:80]}...")
        
    finally:
        db_session.close()
    
    # Шаг 2: Вызываем carebank_tool
    logger.info(f"\n🚀 Вызываем run_care_bank_chain...")
    response, result = await run_care_bank_chain(
        account_id=account_id,
        text=test_message
    )
    
    logger.info(f"\n📤 Ответ: {response}")
    logger.info(f"📦 Результат парсинга: {result}")
    
    # Шаг 3: Проверяем контекст ПОСЛЕ вызова
    db_session = db.get_session()
    
    try:
        context_after = context_store.load(account_id, db_session)
        
        logger.info(f"\n📋 Контекст ПОСЛЕ вызова:")
        logger.info(f"   Количество сообщений: {len(context_after.message_history)}")
        logger.info(f"   Последние 3 сообщения:")
        for msg in context_after.message_history[-3:]:
            logger.info(f"      - {msg[:80]}...")
        
        # Проверяем, что наше сообщение добавилось
        last_message = context_after.message_history[-1] if context_after.message_history else ""
        
        if test_message in last_message:
            logger.info(f"\n✅ SUCCESS: User-сообщение успешно сохранено в контекст!")
        else:
            logger.warning(f"\n⚠️ WARNING: User-сообщение не найдено в последнем сообщении контекста")
            logger.warning(f"   Ожидалось: {test_message[:50]}...")
            logger.warning(f"   Получено: {last_message[:50]}...")
        
    finally:
        db_session.close()
    
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(t_carebank_with_context_save())

