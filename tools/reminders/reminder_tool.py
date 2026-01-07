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