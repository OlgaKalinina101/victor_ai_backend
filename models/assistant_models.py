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
