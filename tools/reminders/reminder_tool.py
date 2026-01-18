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