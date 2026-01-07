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

from enum import Enum

class Gender(str, Enum):
    """Пол пользователя."""
    MALE = "мужчина"
    FEMALE = "девушка"
    OTHER = "другое"

    @classmethod
    def from_str(cls, gender_str: str) -> "Gender":
        """
        Преобразует строку в значение enum Gender.

        Args:
            gender_str (str): Строка, соответствующая значению enum.

        Returns:
            MessageCategory: Соответствующее значение enum.

        Raises:
            ValueError: Если строка не соответствует ни одному значению enum.
        """
        try:
            return cls(gender_str)
        except ValueError:
            raise ValueError(f"Неизвестный тип gender: {gender_str}")

    @classmethod
    def default(cls):
        return Gender.OTHER


class RelationshipLevel(str, Enum):
    """Уровень близости с пользователем. BEST_FRIEND — уникальный уровень для одного человека."""
    STRANGER = "незнакомец"
    ACQUAINTANCE = "знакомый"
    FRIEND = "друг"
    CLOSE_FRIEND = "близкий друг"
    BEST_FRIEND = "самый близкий"

    @classmethod
    def from_str(cls, relationship_str: str) -> "RelationshipLevel":
        """
        Преобразует строку в значение enum Gender.

        Args:
            relationship_str (str): Строка, соответствующая значению enum.

        Returns:
            MessageCategory: Соответствующее значение enum.

        Raises:
            ValueError: Если строка не соответствует ни одному значению enum.
        """
        try:
            return cls(relationship_str)
        except ValueError:
            raise ValueError(f"Неизвестный тип gender: {relationship_str}")

    @classmethod
    def default(cls):
        return RelationshipLevel.STRANGER


class EventType(str, Enum):
    """Тип ивента для таблицы в базе с фиксацией первых предупреждений"""
    WEATHER = "weather"

# Core эмоции
class Mood(Enum):
    JOY = "Радость"
    TENDER = "Нежность"
    CALM = "Спокойствие"
    SURPRISE = "Удивление"
    SADNESS = "Огорчение"
    TIRED = "Усталость"
    DISAPPOINTMENT = "Разочарование"
    ANGER = "Гнев"
    INSECURITY = "Неуверенность"
    SHAME = "Стыд"
    DOMINANT = "Доминирующее чувство"

    @classmethod
    def from_str(cls, mood_str: str) -> "Mood":
        """
        Преобразует строку в значение enum Mood.

        Args:
            mood_str (str): Строка, соответствующая значению enum.

        Returns:
            Mood: Соответствующее значение enum.

        Raises:
            ValueError: Если строка не соответствует ни одному значению enum.
        """
        try:
            return cls(mood_str)
        except ValueError:
            raise ValueError(f"Неизвестный тип Mood: {mood_str}")


class UserMoodLevel(Enum):
    """Уровень настроения в сообщении"""
    LIGHT = 1
    MEDIUM = 2
    HIGH = 3


