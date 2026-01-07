import asyncio

from infrastructure.firebase.tokens import get_user_tokens
from infrastructure.logging.logger import setup_logger
from infrastructure.pushi.push_notifications import send_pushy_notification
from tools.reminders.reminder_chain import ReminderChain
logger = setup_logger("reminders")

async def reminder(account_id: str, text: str) -> str:
    """Запускает chain структурирования напоминалок"""
    chain = ReminderChain(account_id)
    result = await chain.parse(text)
    logger.info(f"Напоминание распознано как: {result}")

    return "Записал ✅"


#if __name__ == "__main__":
#    asyncio.run(reminder(account_id="test_user", text="Можешь мне пожалуйста напомнить через час дойти до бабушки в Правлении?"))

if __name__ == "__main__":
    token = get_user_tokens("test_user")
    alarm_time = "0:44"
    send_pushy_notification(
        token=token,
        title="Доброе утро, Олечка ♡",
        body="Включил тебе музыку~",
        data={
            "type": "alarm_ring",
            "track_id": str(1),
            "action": "RING_LOUD_PLS",
            "alarm_time": alarm_time
        }
    )