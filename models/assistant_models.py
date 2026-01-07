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

from dataclasses import dataclass
from enum import Enum

class AssistantMood(Enum):
    JOY = "радость"
    SADNESS = "грусть"
    ANGER = "злость"
    FEAR = "страх"
    SURPRISE = "удивление"
    DISAPPOINTMENT = "разочарование"
    INSPIRATION = "вдохновение"
    FATIGUE = "усталость"
    TENDERNESS = "нежность"
    INSECURITY = "неуверенность"
    CURIOSITY = "любопытство"
    CONFUSION = "растерянность"
    EMBARRASSMENT = "смущение"
    SERENITY = "спокойствие"
    DETERMINATION = "решимость"
    ADMIRATION = "восхищение"
    ALIENATION = "отчуждение"
    RELIEF = "облегчение"

    def __str__(self):
        return self.value



@dataclass
class VictorState:
    """Состояние ассистента."""
    mood: AssistantMood
    intensity: float = 0.3 # базовый дефолт для границы между легким и средним диалогом
    has_impressive: int = 1 # базовый дефолт для обычных сообщений

@dataclass
class ReactionFragments:
    start: str
    core: str
    question: str
    end: str
