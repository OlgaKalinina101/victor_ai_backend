import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tools.reminders.reminder_chain import ReminderChain


@pytest.mark.asyncio
async def test_reminder_chain_parse():
    # arrange
    mock_response = MagicMock()
    mock_response.content = """
    {
      "datetime": "2025-09-19 16:00",
      "text": "Заказать пиццу"
    }
    """

    reminder = ReminderChain(account_id="test_user")  # Явно передаём для теста

    # Мокаем chain.ainvoke у уже созданного объекта
    reminder.chain = MagicMock()
    reminder.chain.ainvoke = AsyncMock(return_value=mock_response)

    # Мокаем store.save, чтобы не писать в хранилище
    reminder.store = MagicMock()

    # act
    result = await reminder.parse("напомни в пятницу заказать пиццу")

    # assert
    assert result["datetime"] == "2025-09-19 16:00"
    assert result["text"] == "Заказать пиццу"
    reminder.store.save.assert_called_once()
