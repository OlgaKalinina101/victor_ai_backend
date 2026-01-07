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