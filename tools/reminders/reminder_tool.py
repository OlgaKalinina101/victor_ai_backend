import logging

from infrastructure.logging.logger import setup_logger
from tools.reminders.reminder_chain import ReminderChain

# Настройка логгера для текущего модуля
logger = setup_logger("reminders")

async def run_reminder_chain(account_id: str, text: str) -> str:
    """Запускает chain структурирования напоминалок"""
    chain = ReminderChain(account_id)
    result = await chain.parse(text)
    logger.info(f"Напоминание распознано как: {result}")

    return "Записал ✅"