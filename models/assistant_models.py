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
