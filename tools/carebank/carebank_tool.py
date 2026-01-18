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

import asyncio

from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from settings import settings
from tools.carebank.carebank_chain import CareBankChain
from tools.carebank.models import FoodOrder

logger = setup_logger("care_bank")

async def run_care_bank_chain(
    account_id: str,
    text: str,
    db: "Database" = None
) -> tuple[str, dict]:
    """
    Запускает chain структурирования заказов
    
    Args:
        account_id: ID аккаунта пользователя
        text: Текст сообщения с заказом
        db: Инстанс Database (опционально, для тестов)
        session_context_store: Инстанс SessionContextStore (опционально, для тестов)
        
    Returns:
        tuple: (response_text, parsed_result)
    """
    # Fallback для тестов
    db = db or Database.get_instance()
    
    db_session = db.get_session()

    try:
        # 1. Парсим заказ через chain
        chain = CareBankChain(account_id)
        result = await chain.parse(text)
        logger.info(f"[CARE_BANK] Список распарсен как: {result}")

        # 2. Сохраняем заказ в food_orders с emoji = "☕"
        try:
            food_order = FoodOrder(
                account_id=account_id,
                emoji="☕",
                order_data=result,  # dict → JSONB
            )
            db_session.add(food_order)
            db_session.commit()
            logger.info(f"[CARE_BANK] Заказ сохранён в food_orders для {account_id}")
        except Exception as e:
            db_session.rollback()
            logger.error(f"[CARE_BANK] Ошибка при сохранении заказа в food_orders: {e}")

        # 3. Возвращаем ответ для чата и распарсенный результат для сценария
        return "Смотрю... 👀", result

    finally:
        db_session.close()

if __name__ == "__main__":
    # Example usage - требует явный account_id
    import sys
    account_id = sys.argv[1] if len(sys.argv) > 1 else "test_user"
    asyncio.run(run_care_bank_chain(
        account_id=account_id,
        text="Закажи нам пожалуйста шоколадное эскимо, чипсы с лисичками, капучино и гречневую шоколадку"
    ))