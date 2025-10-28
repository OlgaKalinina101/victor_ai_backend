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