from typing import List, Dict

from core.analysis.preanalysis import emotion_map
from infrastructure.logging.logger import setup_logger
from models.user_enums import Mood, UserMoodLevel

# TODO: Перейти на эмбеддинги эмоций вместо скорингов (например, GoEmotions
# , sentence-transformers + классификатор по топ-эмоциям).
# Разделить "эмоциональный тон" и "эмоциональное намерение" — это разные штуки, и тебе скорее нужно второе.
# Ввести механику эмоционального "следа": не от одного сообщения, а как кривая за последние n

logger = setup_logger("emotion_analyzer")

class EmotionInterpreter:
    EMOTION_BONUS_RU = emotion_map.EMOTION_BONUS_RU
    MOOD_RULES = emotion_map.MOOD_RULES

    def __init__(self, emotions: List[Dict]):
        self.emotions = self._normalize(emotions)
        self.scores = {e["label"]: e["score"] for e in self.emotions}

    @staticmethod
    def _normalize(emotions: List[Dict]) -> List[Dict]:
        """Убирает вложенность, если [[...]] вместо [...]."""
        if isinstance(emotions, list):
            if len(emotions) == 1 and isinstance(emotions[0], list):
                return emotions[0]
            elif all(isinstance(item, dict) for item in emotions):
                return emotions
        raise ValueError("Unexpected format of emotion recognition result.")

    def get_mood(self) -> Mood:
        """Маппит набор эмоций на основное настроение (Mood enum)."""
        best_mood = None
        best_score = -1

        for mood, rule in self.MOOD_RULES.items():
            score_sum = 0
            valid = True

            for label, threshold in rule.items():
                if label == "__condition__":
                    if not threshold(self.scores):
                        valid = False
                        break
                elif isinstance(threshold, dict) and "max" in threshold:
                    if self.scores.get(label, 0) > threshold["max"]:
                        valid = False
                        break
                else:
                    if self.scores.get(label, 0) < threshold:
                        valid = False
                        break
                    score_sum += self.scores.get(label, 0)

            if valid and score_sum > best_score:
                best_mood = mood
                best_score = score_sum

        return best_mood if best_mood else Mood.CALM

    def get_mood_level(self) -> UserMoodLevel:
        """Оценивает уровень силы эмоции."""
        logger.info(f"emotions {self.emotions}")
        top = self.emotions[0]
        logger.info(f"top emotions {self.emotions[0]}")
        label = top["label"]
        score = top["score"]

        score += self.EMOTION_BONUS_RU.get(label, 0.0)

        if score >= 0.85:
            return UserMoodLevel.HIGH
        elif score >= 0.65:
            return UserMoodLevel.MEDIUM
        else:
            return UserMoodLevel.LIGHT

