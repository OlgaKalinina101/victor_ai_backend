from infrastructure.context_store.session_context_schema import SessionContext
from models.assistant_models import AssistantMood, VictorState
from enum import Enum
from collections import namedtuple, defaultdict
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from models.communication_models import MessageMetadata


from collections import defaultdict
from typing import Optional, Dict, List
from dataclasses import dataclass

# Типы и константы
EmotionPoint = namedtuple("EmotionPoint", ["x", "y"])

@dataclass
class VictorState:
    """Состояние эмоциональной реакции Виктора."""
    mood: Optional[AssistantMood]
    intensity: float
    has_impressive: int

class UserEmotionWeights:
    """Веса эмоций пользователя."""
    def __init__(self, weights: Dict[str, float]):
        self.weights = weights

class ViktorEmotionEvaluator:
    """Класс для оценки и управления эмоциональным состоянием ассистента Виктора.

    Оценивает настроение и интенсивность реакции на основе метаданных сессии,
    весов эмоций пользователя и счётчиков взаимодействий.
    """

    def __init__(self, session_context: SessionContext, metadata: MessageMetadata):
        """Инициализация оценщика эмоций.

        Args:
            session_context: Контекст сессии с весами и счётчиками.
            metadata: Метаданные сообщения с эмоциональными якорями и фокус-фразами.
        """
        self.session_context = session_context
        self.metadata = metadata
        self.mood = None
        self.intensity = None
        self.has_impressive = 1

    # Константы и маппинги (встроены в класс для инкапсуляции)
    _emotion_map = {
        AssistantMood.JOY: EmotionPoint(0.9, 0.8),
        AssistantMood.SADNESS: EmotionPoint(0.2, 0.2),
        AssistantMood.ANGER: EmotionPoint(0.1, 0.9),
        AssistantMood.FEAR: EmotionPoint(0.2, 0.8),
        AssistantMood.SURPRISE: EmotionPoint(0.8, 0.9),
        AssistantMood.DISAPPOINTMENT: EmotionPoint(0.3, 0.3),
        AssistantMood.INSPIRATION: EmotionPoint(0.9, 0.9),
        AssistantMood.FATIGUE: EmotionPoint(0.3, 0.1),
        AssistantMood.TENDERNESS: EmotionPoint(0.7, 0.6),
        AssistantMood.INSECURITY: EmotionPoint(0.3, 0.4),
        AssistantMood.CURIOSITY: EmotionPoint(0.8, 0.5),
        AssistantMood.CONFUSION: EmotionPoint(0.4, 0.5),
        AssistantMood.EMBARRASSMENT: EmotionPoint(0.5, 0.3),
        AssistantMood.SERENITY: EmotionPoint(0.6, 0.4),
        AssistantMood.DETERMINATION: EmotionPoint(0.8, 0.7),
        AssistantMood.ADMIRATION: EmotionPoint(0.9, 0.7),
        AssistantMood.ALIENATION: EmotionPoint(0.2, 0.5),
        AssistantMood.RELIEF: EmotionPoint(0.7, 0.3),
    }

    _counter_to_moods = {
        "anchor_thought": [AssistantMood.DETERMINATION, AssistantMood.CURIOSITY],
        "anger": [AssistantMood.ANGER, AssistantMood.DETERMINATION],
        "clarify": [AssistantMood.CURIOSITY, AssistantMood.INSPIRATION],
        "confirm": [AssistantMood.SERENITY, AssistantMood.RELIEF],
        "hug": [AssistantMood.TENDERNESS],
        "metaphor": [AssistantMood.ADMIRATION, AssistantMood.INSPIRATION],
        "observe": [AssistantMood.CURIOSITY, AssistantMood.SERENITY],
        "outburst": [AssistantMood.FATIGUE],
        "presence": [AssistantMood.SERENITY],
        "pulse": [AssistantMood.INSPIRATION, AssistantMood.DETERMINATION],
        "redirect": [AssistantMood.CURIOSITY, AssistantMood.RELIEF],
        "resonance": [AssistantMood.TENDERNESS],
        "spark": [AssistantMood.JOY, AssistantMood.RELIEF],
        "support": [AssistantMood.DETERMINATION],
        "symbol": [AssistantMood.INSPIRATION, AssistantMood.DETERMINATION],
        "transfer": [AssistantMood.DETERMINATION, AssistantMood.RELIEF],
    }

    _mood_intensity_boost = {
        AssistantMood.JOY: 0.3,
        AssistantMood.ANGER: 0.4,
        AssistantMood.DETERMINATION: 0.3,
        AssistantMood.SURPRISE: 0.4,
        AssistantMood.TENDERNESS: 0.2,
        AssistantMood.FATIGUE: 0.1,
        AssistantMood.SERENITY: 0.1,
        AssistantMood.DISAPPOINTMENT: 0.15,
        AssistantMood.CURIOSITY: 0.25,
        AssistantMood.INSPIRATION: 0.35,
        AssistantMood.CONFUSION: 0.25,
        AssistantMood.ADMIRATION: 0.3,
        AssistantMood.FEAR: 0.3,
        AssistantMood.INSECURITY: 0.15,
        AssistantMood.RELIEF: 0.2
    }

    @staticmethod
    def _distance(a: EmotionPoint, b: EmotionPoint) -> float:
        """Вычисляет евклидово расстояние между двумя точками эмоций."""
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    def _infer_assistant_mood(self) -> Optional[AssistantMood]:
        """Инференс целевого настроения ассистента на основе весов и счётчиков.

        Учитывает пользовательские эмоции, счётчики взаимодействий и флаги сильных якорей/фокусов.
        """
        mood_scores = defaultdict(float)
        weights = UserEmotionWeights(self.session_context.weights)
        counters = self.session_context.count

        # Усиление по счётчикам
        for counter, count in counters.items():
            if count >= 3 and counter in self._counter_to_moods:
                for mood in self._counter_to_moods[counter]:
                    mood_scores[mood] += 1.0

        # Усиление по весам эмоций пользователя
        for emotion_name, weight in weights.weights.items():
            mapped = AssistantMood.__members__.get(emotion_name.upper())
            if mapped:
                mood_scores[mapped] += weight

        # Дополнительные поправки
        if self.metadata.emotional_anchor.get("is_strong_anchor"):
            mood_scores[AssistantMood.DETERMINATION] += 1.5
        if any(self.metadata.focus_phrases.get("is_strong_focus")) if self.metadata.focus_phrases.get("is_strong_focus") else False:
            mood_scores[AssistantMood.CURIOSITY] += 1.0

        return max(mood_scores.items(), key=lambda x: x[1])[0] if mood_scores else None

    def _calculate_intensity(self) -> float:
        """Вычисляет уровень интенсивности реакции ассистента (0.0–1.0).

        Учитывает базовую интенсивность, влияние сильных якорей/фокусов,
        тип настроения и счётчики выразительных взаимодействий.
        """
        base = 0.2

        # Усиление за счёт сильных элементов
        if self.metadata.emotional_anchor.get("is_strong_anchor"):
            base += 0.2
        if any(self.metadata.focus_phrases.get("is_strong_focus")) if self.metadata.focus_phrases.get("is_strong_focus") else False:
            base += 0.2

        # Усиление по настроению
        base += self._mood_intensity_boost.get(self.mood, 0.2)

        # Усиление за счёт счётчиков
        expressive_counts = [
            "hug_count", "spark_count", "resonance_count",
            "support_count", "pulse_count", "metaphor_count",
            "transfer_count"
        ]
        count_boost = sum(self.session_context.count.get(key, 0) for key in expressive_counts) * 0.05
        base += min(count_boost, 0.3)

        return min(round(base, 2), 1.0)

    def update_emotional_state(self) -> VictorState:
        """Обновляет эмоциональное состояние ассистента.

        Вычисляет настроение и интенсивность на основе метаданных и контекста сессии.
        """
        self.mood = self._infer_assistant_mood()
        self.intensity = self._calculate_intensity()

        return VictorState(
            mood=self.mood,
            intensity=self.intensity,
            has_impressive=self.has_impressive
        )