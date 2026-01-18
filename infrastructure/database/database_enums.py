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


class EnergyDescription(Enum):
    LIGHT_RHYTHMIC = "Светлая-ритмичная"
    WARM_HEARTED = "Тёплая-сердечная"
    CALM_GROUNDING = "Тихая-заземляющая"
    REFLECTIVE_OBSERVING = "Отражающее-наблюдение"
    COMPLEX_REFLECTIVE = "Сложно-рефлексивные"

    @classmethod
    def from_value(cls, value: str) -> str:
        """Из значения → в имя enum"""
        for member in cls:
            if member.value == value:
                return member.name
        raise ValueError(f"Неизвестное значение: {value}")


class TemperatureDescription(Enum):
    WARM = "Тёплая"
    MODERATE = "Умеренная"
    HOT = "Горячая"
    COLD = "Холодная"
    ICY = "Ледяная"

    @classmethod
    def from_value(cls, value: str) -> str:
        for member in cls:
            if member.value == value:
                return member.name
        raise ValueError(f"Неизвестное значение: {value}")