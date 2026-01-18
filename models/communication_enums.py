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

from enum import Enum
from typing import Optional


class MessageCategory(str, Enum):
    """Категория сообщения, определяющая его содержание для механики доверия."""
    FACT = "факт"
    OPINION = "мнение"
    ACTION = "действие"
    DREAM = "мечты и надежды"
    FEELING = "чувства"
    FEAR = "страхи"
    NEED = "эмоциональные потребности"
    PHATIC = "диалог"

    @classmethod
    def from_str(cls, message_category_str: str, default: Optional["MessageCategory"] = None) -> "MessageCategory":
        """
        Преобразует строку в значение enum MessageCategory. Если не удаётся, возвращает default (если задан).

        Args:
            message_category_str (str): Строка, соответствующая значению enum.
            default (MessageCategory, optional): Значение по умолчанию, если строка не распознана.

        Returns:
            MessageCategory: Соответствующее значение enum или default.

        Raises:
            ValueError: Если строка не соответствует и default не задан.
        """
        if not isinstance(message_category_str, str):
            return default if default else cls.PHATIC

        normalized = message_category_str.strip().lower()

        # Создадим map на случай ошибок и синонимов
        translation_map = {
            "факт": cls.FACT,
            "мнение": cls.OPINION,
            "действие": cls.ACTION,
            "мечты и надежды": cls.DREAM,
            "чувства": cls.FEELING,
            "страхи": cls.FEAR,
            "эмоциональные потребности": cls.NEED,
            "диалог": cls.PHATIC,
        }

        if normalized in translation_map:
            return translation_map[normalized]

        if default is not None:
            return default

        raise ValueError(f"Неизвестный тип message_category: {message_category_str}")


class MessageType(str, Enum):
    """Тип сообщения, определяющий его назначение для переключения веток кода."""
    EVENT = "Свидание"
    OPINION = "Мнение о тебе"
    WEATHER = "Погода"
    DIALOG = "Диалог"
    REMINDER = "Напоминание"
    NEWS = "Новости"
    RESTAURANT = "Рестораны"

class KeyInfoCategory(str, Enum):
    """Категории ключевой информации в сообщении, по умолчанию topic."""
    PERSONAL = "Личное"
    RELATIONSHIPS = "Отношения"
    FAMILY = "Семья"
    FRIENDS = "Друзья"
    ACQUAINTANCES = "Знакомые"
    WORK = "Работа"
    EDUCATION = "Учёба"
    LEISURE = "Досуг"
    HEALTH = "Здоровье"
    VALUES = "Ценности"
    STRESS = "Стресс"
    TRAVEL = "Путешествия"
    CONFLICTS = "Противоречия"

    @classmethod
    def from_str(cls, category_str: str) -> 'KeyInfoCategory':
        """Преобразует строку категории в элемент KeyInfoCategory."""
        try:
            return cls(category_str)
        except ValueError:
            raise ValueError(f"Неизвестный тип message_category: {category_str}")