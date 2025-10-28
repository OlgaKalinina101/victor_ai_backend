import asyncio

from infrastructure.logging.logger import setup_logger
from tools.reminders.reminder_chain import ReminderChain
logger = setup_logger("reminders")

async def reminder(account_id: str, text: str) -> str:
    """Запускает chain структурирования напоминалок"""
    chain = ReminderChain(account_id)
    result = await chain.parse(text)
    logger.info(f"Напоминание распознано как: {result}")

    return "Записал ✅"

if __name__ == "__main__":
    asyncio.run(reminder(account_id="test_user", text="Можешь мне пожалуйста напомнить через час дойти до бабушки в Правлении?"))