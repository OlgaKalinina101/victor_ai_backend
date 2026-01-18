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

"""
Схемы для эндпоинта /reminders.

Содержит модели для работы с напоминаниями пользователя,
включая откладывание, повторение и управление напоминаниями.
"""

from typing import Literal
from pydantic import BaseModel, Field


class ReminderRequest(BaseModel):
    """
    Базовый запрос для операций над напоминанием.
    
    Используется в операциях, требующих только ID напоминания,
    например при пометке напоминания как выполненного или
    при удалении напоминания.
    
    Attributes:
        reminder_id: Уникальный идентификатор напоминания.
    """
    reminder_id: str = Field(..., description="Уникальный ID напоминания")


class ReminderDelayRequest(BaseModel):
    """
    Запрос на откладывание напоминания.
    
    Позволяет сдвинуть время срабатывания напоминания на заданный
    интервал в будущее. Новое время рассчитывается на сервере
    относительно текущего времени срабатывания.
    
    Attributes:
        reminder_id: ID напоминания для откладывания.
        value: Величина сдвига (положительное число, >= 1).
        unit: Единицы измерения времени сдвига:
            - "minute" - минуты
            - "hour" - часы (по умолчанию)
            - "day" - дни
    
    Examples:
        Отложить на 30 минут: value=30, unit="minute"
        Отложить на 2 часа: value=2, unit="hour"
        Отложить на 1 день: value=1, unit="day"
    """
    reminder_id: str = Field(..., description="ID напоминания")
    value: int = Field(
        1,
        ge=1,
        description="Величина сдвига (> 0)",
    )
    unit: Literal["minute", "hour", "day"] = Field(
        "hour",
        description='Единицы измерения: "minute", "hour" или "day"',
    )


class ReminderRepeatWeeklyRequest(BaseModel):
    """
    Запрос на включение/выключение еженедельного повторения.
    
    Управляет режимом повторения напоминания каждую неделю
    в тот же день недели и время. При включении повторения
    напоминание автоматически переносится на следующую неделю
    после каждого срабатывания.
    
    Attributes:
        reminder_id: ID напоминания для настройки повторения.
        repeat_weekly: Флаг еженедельного повторения:
            - True: напоминание будет повторяться каждую неделю
            - False: отключить повторение (разовое напоминание)
    """
    reminder_id: str = Field(..., description="ID напоминания")
    repeat_weekly: bool = Field(
        False,
        description="Включить еженедельное повторение",
    )
