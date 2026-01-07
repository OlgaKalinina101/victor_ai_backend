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

from infrastructure.context_store.session_context_schema import SessionContext
from models.assistant_models import AssistantMood, VictorState
from collections import namedtuple

from models.communication_models import MessageMetadata
from models.user_enums import RelationshipLevel

from collections import defaultdict
from typing import Optional, Dict, List
from dataclasses import dataclass
import re
import emoji

from core.persona.emotional.emotional_map import (
    EMOJI_TO_EMOTIONS,
    CATEGORY_ENERGY_COST,
    COUNTERS_ENERGY_COST
)

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

    def __init__(self, session_context: SessionContext, metadata: MessageMetadata, active_counters: Optional[List[str]] = None):
        """Инициализация оценщика эмоций.

        Args:
            session_context: Контекст сессии с весами и счётчиками.
            metadata: Метаданные сообщения с эмоциональными якорями и фокус-фразами.
            active_counters: Список активных счетчиков из текущей реакции (опционально)
        """
        self.session_context = session_context
        self.metadata = metadata
        self.active_counters = active_counters or []
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

    # Ограничения по уровню отношений (trust-gate).
    # Примечание: "нейтрально" (🤖) трактуем как спокойствие (SERENITY),
    # потому что в AssistantMood нет отдельной NEUTRAL эмоции.
    _ALLOWED_MOODS_BY_RELATIONSHIP: Dict[RelationshipLevel, set[AssistantMood]] = {
        RelationshipLevel.STRANGER: {
            AssistantMood.CURIOSITY,      # 🧐
            AssistantMood.SURPRISE,       # 😮
            AssistantMood.CONFUSION,      # 😕
            AssistantMood.SERENITY,       # 🌿 (и как "нейтрально")
        },
        RelationshipLevel.ACQUAINTANCE: {
            AssistantMood.CURIOSITY,
            AssistantMood.SURPRISE,
            AssistantMood.CONFUSION,
            AssistantMood.SERENITY,
            AssistantMood.JOY,            # 😊
            AssistantMood.DISAPPOINTMENT, # 😞
            AssistantMood.FATIGUE,        # 🥱
            AssistantMood.INSECURITY,     # 😟
            AssistantMood.EMBARRASSMENT,  # 😳
            AssistantMood.DETERMINATION,  # 💪
        },
        RelationshipLevel.FRIEND: {
            AssistantMood.CURIOSITY,
            AssistantMood.SURPRISE,
            AssistantMood.CONFUSION,
            AssistantMood.SERENITY,
            AssistantMood.JOY,
            AssistantMood.DISAPPOINTMENT,
            AssistantMood.FATIGUE,
            AssistantMood.INSECURITY,
            AssistantMood.EMBARRASSMENT,
            AssistantMood.DETERMINATION,
            AssistantMood.SADNESS,        # 😔
            AssistantMood.INSPIRATION,    # 🌟
            AssistantMood.RELIEF,         # 😌
            AssistantMood.ADMIRATION,     # 🤩
        },
        RelationshipLevel.CLOSE_FRIEND: {
            AssistantMood.CURIOSITY,
            AssistantMood.SURPRISE,
            AssistantMood.CONFUSION,
            AssistantMood.SERENITY,
            AssistantMood.JOY,
            AssistantMood.DISAPPOINTMENT,
            AssistantMood.FATIGUE,
            AssistantMood.INSECURITY,
            AssistantMood.EMBARRASSMENT,
            AssistantMood.DETERMINATION,
            AssistantMood.SADNESS,
            AssistantMood.INSPIRATION,
            AssistantMood.RELIEF,
            AssistantMood.ADMIRATION,
            AssistantMood.ANGER,          # 😠
            AssistantMood.FEAR,           # 😨
            AssistantMood.TENDERNESS,     # 💗
        },
        # BEST_FRIEND: доступны все эмоции (включая ALIENATION)
        # - задаём как "all allowed" через None-логику в коде ниже
    }

    @classmethod
    def _get_allowed_moods(cls, relationship_level: Optional[RelationshipLevel]) -> Optional[set[AssistantMood]]:
        """
        Возвращает множество разрешённых эмоций для уровня отношений.
        Если уровень BEST_FRIEND (или неизвестен) — не ограничиваем (None).
        """
        if relationship_level is None:
            return None
        try:
            # На всякий случай нормализуем (если прилетела строка)
            if not isinstance(relationship_level, RelationshipLevel):
                relationship_level = RelationshipLevel.from_str(str(relationship_level))
        except Exception:
            return None

        if relationship_level == RelationshipLevel.BEST_FRIEND:
            return None

        return cls._ALLOWED_MOODS_BY_RELATIONSHIP.get(relationship_level)

    def _filter_mood_scores_by_trust(self, mood_scores: Dict[AssistantMood, float]) -> Dict[AssistantMood, float]:
        """Фильтрует кандидатные эмоции по relationship_level (trust gate)."""
        allowed = self._get_allowed_moods(getattr(self.session_context, "relationship_level", None))
        if not allowed:
            return dict(mood_scores)
        return {m: s for m, s in mood_scores.items() if m in allowed}

    def _coerce_mood_to_allowed(self, mood: Optional[AssistantMood]) -> Optional[AssistantMood]:
        """
        Если mood запрещён текущим уровнем отношений — заменяем на ближайший разрешённый.
        Фолбэк: SERENITY (если разрешён) иначе любой разрешённый.
        """
        if mood is None:
            return None

        allowed = self._get_allowed_moods(getattr(self.session_context, "relationship_level", None))
        if not allowed:
            return mood
        if mood in allowed:
            return mood

        # Предпочтение "нейтральности"
        if AssistantMood.SERENITY in allowed:
            return AssistantMood.SERENITY

        # Если есть координаты — выберем ближайшую по карте эмоций
        if mood in self._emotion_map:
            mood_point = self._emotion_map[mood]
            candidates = [m for m in allowed if m in self._emotion_map]
            if candidates:
                return min(candidates, key=lambda m: self._distance(mood_point, self._emotion_map[m]))

        return next(iter(allowed))

    @staticmethod
    def _distance(a: EmotionPoint, b: EmotionPoint) -> float:
        """Вычисляет евклидово расстояние между двумя точками эмоций."""
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    @staticmethod
    def _convert_text_smiles_to_emoji(text: str) -> str:
        """Конвертирует текстовые смайлы в эмодзи.
        
        Args:
            text: Текст с текстовыми смайлами
            
        Returns:
            Текст с конвертированными эмодзи
        """
        # Конвертация скобочек в эмодзи
        # )))) или больше → 😂 (сильная радость)
        text = re.sub(r'\){4,}', '😂', text)
        # ))) или )) → 😊 (радость)
        text = re.sub(r'\){2,3}', '😊', text)
        # ) → 🙂 (легкая радость)
        text = re.sub(r'(?<!\))\)(?!\))', '🙂', text)
        
        # (((( или больше → 😥 (сильная грусть)
        text = re.sub(r'\({4,}', '😥', text)
        # ((( или (( → 😔 (грусть)
        text = re.sub(r'\({2,3}', '😔', text)
        # ( → 😔 (легкая грусть)
        text = re.sub(r'(?<!\()\((?!\()', '😔', text)
        
        return text

    @staticmethod
    def _extract_emojis(text: str) -> List[str]:
        """Извлекает все эмодзи из текста.
        
        Args:
            text: Текст для поиска эмодзи
            
        Returns:
            Список найденных эмодзи
        """
        # Используем emoji.emoji_list() для более надежного определения
        emoji_list = emoji.emoji_list(text)
        return [item['emoji'] for item in emoji_list]

    def _map_emojis_to_moods(self, emojis: List[str]) -> Dict[AssistantMood, float]:
        """Маппит эмодзи на эмоции с весами.
        
        Args:
            emojis: Список эмодзи для маппинга
            
        Returns:
            Словарь {AssistantMood: суммарный_вес}
        """
        mood_weights = defaultdict(float)
        
        for emoji_char in emojis:
            if emoji_char in EMOJI_TO_EMOTIONS:
                for mood, weight in EMOJI_TO_EMOTIONS[emoji_char]:
                    mood_weights[mood] += weight
        
        return dict(mood_weights)

    def _find_transition_mood(self, current_mood: AssistantMood) -> AssistantMood:
        """Находит ближайшую эмоцию для перехода при переполнении intensity.
        
        Args:
            current_mood: Текущее настроение
            
        Returns:
            Новое настроение после перехода
        """
        if current_mood not in self._emotion_map:
            return current_mood
        
        current_point = self._emotion_map[current_mood]
        
        # Находим ближайшую эмоцию по расстоянию (исключая текущую)
        closest_mood = current_mood
        min_distance = float('inf')
        
        for mood, point in self._emotion_map.items():
            if mood != current_mood:
                dist = self._distance(current_point, point)
                if dist < min_distance:
                    min_distance = dist
                    closest_mood = mood
        
        return closest_mood

    def _infer_assistant_mood(self) -> Optional[AssistantMood]:
        """Инференс целевого настроения ассистента на основе весов и счётчиков.

        Учитывает:
        - Эмодзи из сообщения пользователя
        - Активные счетчики (counters) из текущей реакции
        - Пользовательские эмоции
        - Флаги сильных якорей/фокусов
        """
        mood_scores = defaultdict(float)
        
        # 1. Получаем и обрабатываем сообщение пользователя
        user_message = self.session_context.get_last_user_message()
        if user_message:
            # Конвертируем текстовые смайлы в эмодзи
            converted_message = self._convert_text_smiles_to_emoji(user_message)
            
            # Извлекаем эмодзи
            emojis = self._extract_emojis(converted_message)
            
            # Маппим эмодзи на эмоции с весами
            emoji_moods = self._map_emojis_to_moods(emojis)
            for mood, weight in emoji_moods.items():
                mood_scores[mood] += weight
        
        # 2. Добавляем эмоции из активных счетчиков текущей реакции
        for counter in self.active_counters:
            # Убираем суффикс "_count" для поиска в маппинге
            counter_key = counter.replace("_count", "")
            if counter_key in self._counter_to_moods:
                for mood in self._counter_to_moods[counter_key]:
                    mood_scores[mood] += 1.5  # Вес для активных counters
        
        # 3. Усиление по накопленным счётчикам (старая логика)
        counters = self.session_context.count
        for counter, count in counters.items():
            counter_key = counter.replace("_count", "")
            if count >= 3 and counter_key in self._counter_to_moods:
                for mood in self._counter_to_moods[counter_key]:
                    mood_scores[mood] += 1.0

        # 4. Усиление по весам эмоций пользователя
        weights = UserEmotionWeights(self.session_context.weights)
        for emotion_name, weight in weights.weights.items():
            mapped = AssistantMood.__members__.get(emotion_name.upper())
            if mapped:
                mood_scores[mapped] += weight

        # 5. Дополнительные поправки
        if self.metadata.emotional_anchor.get("is_strong_anchor"):
            mood_scores[AssistantMood.DETERMINATION] += 1.5
        strong_flags = self.metadata.focus_phrases.get("is_strong_focus")
        has_strong_focus = False
        if isinstance(strong_flags, bool):
            has_strong_focus = strong_flags
        elif isinstance(strong_flags, (list, tuple)):
            has_strong_focus = any(bool(x) for x in strong_flags)
        if has_strong_focus:
            mood_scores[AssistantMood.CURIOSITY] += 1.0

        # 6. Trust-gate: ограничиваем список эмоций по relationship_level
        filtered_scores = self._filter_mood_scores_by_trust(mood_scores)
        if not filtered_scores:
            # Если всё вырезали — мягкий фолбэк в "спокойствие/нейтральность"
            return self._coerce_mood_to_allowed(AssistantMood.SERENITY)

        return max(filtered_scores.items(), key=lambda x: x[1])[0]

    def _calculate_intensity(self) -> tuple[float, Optional[AssistantMood]]:
        """Вычисляет уровень интенсивности реакции ассистента (0.0–12.0).

        Накопительная система:
        - Берет предыдущий intensity из истории
        - Добавляет затраты по категории сообщения (CATEGORY_ENERGY_COST)
        - Добавляет затраты по активным счетчикам (COUNTERS_ENERGY_COST)
        - При превышении 12 → переход на другую эмоцию
        
        Returns:
            Кортеж (новый_intensity, новое_настроение_если_был_переход)
        """
        # 1. Получаем предыдущий intensity
        prev_intensity = self.session_context.get_last_victor_intensity(fallback=0.0)
        
        # 2. Добавляем затраты по категории сообщения
        new_intensity = prev_intensity
        if self.metadata.message_category and self.metadata.message_category in CATEGORY_ENERGY_COST:
            new_intensity += CATEGORY_ENERGY_COST[self.metadata.message_category]
        
        # 3. Добавляем затраты по активным счетчикам
        for counter in self.active_counters:
            if counter in COUNTERS_ENERGY_COST:
                new_intensity += COUNTERS_ENERGY_COST[counter]
        
        # 4. Проверяем на переполнение
        transition_mood = None
        if new_intensity > 12.0:
            # Находим новую эмоцию для перехода
            if self.mood:
                transition_mood = self._find_transition_mood(self.mood)
                # Остаток после перехода
                new_intensity = new_intensity - 12.0
        
        # Ограничиваем intensity в пределах [0, 12]
        new_intensity = max(0.0, min(new_intensity, 12.0))
        
        return round(new_intensity, 2), transition_mood

    def update_emotional_state(self) -> VictorState:
        """Обновляет эмоциональное состояние ассистента.

        Вычисляет настроение и интенсивность на основе:
        - Эмодзи из сообщения пользователя
        - Активных счетчиков реакции
        - Метаданных и контекста сессии
        - Накопительного intensity с переходами при переполнении
        """
        # 1. Определяем настроение
        self.mood = self._infer_assistant_mood()
        self.mood = self._coerce_mood_to_allowed(self.mood)
        
        # 2. Вычисляем intensity (может вернуть новое настроение при переходе)
        self.intensity, transition_mood = self._calculate_intensity()
        
        # 3. Если был переход (intensity > 12), меняем настроение
        if transition_mood:
            self.mood = self._coerce_mood_to_allowed(transition_mood)

        return VictorState(
            mood=self.mood,
            intensity=self.intensity,
            has_impressive=self.has_impressive
        )