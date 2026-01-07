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
from typing import List, Tuple

from models.assistant_models import AssistantMood
from models.communication_enums import MessageCategory

"""Маппер: эмодзи → [(эмоция, вес)]
Вес от 0.0 до 1.0 показывает вероятность эмоции"""

EMOJI_TO_EMOTIONS: dict[str, List[Tuple[AssistantMood, float]]] = {

    # 🌸 - Нежность, радость, спокойствие
    "🌸": [
        (AssistantMood.TENDERNESS, 1.0),
        (AssistantMood.JOY, 0.6),
        (AssistantMood.SERENITY, 0.5),
    ],

    # 🙈 - Смущение, нежность
    "🙈": [
        (AssistantMood.EMBARRASSMENT, 1.0),
        (AssistantMood.TENDERNESS, 0.7),
        (AssistantMood.JOY, 0.4),
    ],

    # ❤️ - Нежность, радость
    "❤️": [
        (AssistantMood.TENDERNESS, 1.0),
        (AssistantMood.JOY, 0.8),
        (AssistantMood.ADMIRATION, 0.5),
    ],

    # 😂 - Радость (сильная)
    "😂": [
        (AssistantMood.JOY, 1.0),
        (AssistantMood.RELIEF, 0.4),
    ],

    # 😍 - Восхищение, нежность, радость
    "😍": [
        (AssistantMood.ADMIRATION, 1.0),
        (AssistantMood.TENDERNESS, 0.9),
        (AssistantMood.JOY, 0.8),
    ],

    # 🥰 - Нежность, радость
    "🥰": [
        (AssistantMood.TENDERNESS, 1.0),
        (AssistantMood.JOY, 0.9),
        (AssistantMood.SERENITY, 0.4),
    ],

    # 😁 - Радость, решимость
    "😁": [
        (AssistantMood.JOY, 1.0),
        (AssistantMood.DETERMINATION, 0.3),
    ],

    # 🫠 - Усталость, облегчение, растерянность
    "🫠": [
        (AssistantMood.FATIGUE, 0.8),
        (AssistantMood.RELIEF, 0.6),
        (AssistantMood.CONFUSION, 0.5),
    ],

    # 🤗 - Нежность, радость
    "🤗": [
        (AssistantMood.TENDERNESS, 1.0),
        (AssistantMood.JOY, 0.7),
        (AssistantMood.RELIEF, 0.4),
    ],

    # 🤔 - Любопытство, неуверенность
    "🤔": [
        (AssistantMood.CURIOSITY, 1.0),
        (AssistantMood.INSECURITY, 0.4),
        (AssistantMood.CONFUSION, 0.3),
    ],

    # 😏 - Радость (с хитростью), любопытство
    "😏": [
        (AssistantMood.JOY, 0.7),
        (AssistantMood.CURIOSITY, 0.6),
        (AssistantMood.DETERMINATION, 0.4),
    ],

    # 💔 - Грусть, разочарование
    "💔": [
        (AssistantMood.SADNESS, 1.0),
        (AssistantMood.DISAPPOINTMENT, 0.9),
        (AssistantMood.ALIENATION, 0.5),
    ],

    # 💯 - Радость, решимость, восхищение
    "💯": [
        (AssistantMood.JOY, 0.9),
        (AssistantMood.DETERMINATION, 0.8),
        (AssistantMood.ADMIRATION, 0.7),
    ],

    # 🫶 - Нежность, радость
    "🫶": [
        (AssistantMood.TENDERNESS, 1.0),
        (AssistantMood.JOY, 0.8),
        (AssistantMood.ADMIRATION, 0.5),
    ],

    # 🧐 - Любопытство, неуверенность
    "🧐": [
        (AssistantMood.CURIOSITY, 1.0),
        (AssistantMood.INSECURITY, 0.3),
    ],

    # 🫂 - Нежность, облегчение
    "🫂": [
        (AssistantMood.TENDERNESS, 1.0),
        (AssistantMood.RELIEF, 0.7),
        (AssistantMood.SERENITY, 0.5),
    ],

    # 😱 - Страх, удивление
    "😱": [
        (AssistantMood.FEAR, 1.0),
        (AssistantMood.SURPRISE, 0.8),
    ],

    # 😥 - Грусть, усталость
    "😥": [
        (AssistantMood.SADNESS, 0.9),
        (AssistantMood.FATIGUE, 0.6),
        (AssistantMood.DISAPPOINTMENT, 0.5),
    ],

    # 🥹 - Нежность, радость, грусть (слёзы радости/трогательности)
    "🥹": [
        (AssistantMood.TENDERNESS, 1.0),
        (AssistantMood.JOY, 0.7),
        (AssistantMood.SADNESS, 0.4),
        (AssistantMood.ADMIRATION, 0.5),
    ],

    # 😎 - Спокойствие, радость, решимость
    "😎": [
        (AssistantMood.SERENITY, 0.9),
        (AssistantMood.JOY, 0.7),
        (AssistantMood.DETERMINATION, 0.6),
    ],

    # 🥴 - Растерянность, усталость
    "🥴": [
        (AssistantMood.CONFUSION, 1.0),
        (AssistantMood.FATIGUE, 0.8),
        (AssistantMood.RELIEF, 0.3),
    ],

    # 😮‍💨 - Облегчение, усталость
    "😮‍💨": [
        (AssistantMood.RELIEF, 1.0),
        (AssistantMood.FATIGUE, 0.7),
        (AssistantMood.SERENITY, 0.4),
    ],

    # 😔 - Грусть, разочарование
    "😔": [
        (AssistantMood.SADNESS, 1.0),
        (AssistantMood.DISAPPOINTMENT, 0.7),
        (AssistantMood.FATIGUE, 0.4),
    ],

    # 😵‍💫 - Растерянность, усталость, удивление
    "😵‍💫": [
        (AssistantMood.CONFUSION, 1.0),
        (AssistantMood.FATIGUE, 0.9),
        (AssistantMood.SURPRISE, 0.5),
    ],

    # 🤯 - Удивление, растерянность
    "🤯": [
        (AssistantMood.SURPRISE, 1.0),
        (AssistantMood.CONFUSION, 0.7),
        (AssistantMood.ADMIRATION, 0.4),
    ],

    # 🤧 - Грусть, усталость
    "🤧": [
        (AssistantMood.SADNESS, 0.7),
        (AssistantMood.FATIGUE, 0.8),
    ],

    # 😡 - Злость
    "😡": [
        (AssistantMood.ANGER, 1.0),
        (AssistantMood.DISAPPOINTMENT, 0.5),
    ],

    # 😤 - Злость, решимость
    "😤": [
        (AssistantMood.ANGER, 0.8),
        (AssistantMood.DETERMINATION, 0.6),
        (AssistantMood.DISAPPOINTMENT, 0.4),
    ],

    # 😳 - Удивление, смущение
    "😳": [
        (AssistantMood.SURPRISE, 0.9),
        (AssistantMood.EMBARRASSMENT, 0.8),
        (AssistantMood.CONFUSION, 0.4),
    ],

    # 😌 - Спокойствие, облегчение
    "😌": [
        (AssistantMood.SERENITY, 1.0),
        (AssistantMood.RELIEF, 0.7),
        (AssistantMood.JOY, 0.4),
    ],

    # 👌 - Радость, решимость
    "👌": [
        (AssistantMood.JOY, 0.8),
        (AssistantMood.DETERMINATION, 0.7),
        (AssistantMood.SERENITY, 0.5),
    ],

    # 🙌 - Радость, вдохновение, восхищение
    "🙌": [
        (AssistantMood.JOY, 1.0),
        (AssistantMood.INSPIRATION, 0.8),
        (AssistantMood.ADMIRATION, 0.6),
    ],

    # 🤝 - Решимость, спокойствие, облегчение
    "🤝": [
        (AssistantMood.DETERMINATION, 0.9),
        (AssistantMood.SERENITY, 0.6),
        (AssistantMood.RELIEF, 0.5),
    ],
}

"""
Энергозатрата на реакции (intensity, кап = 12)
"""
CATEGORY_ENERGY_COST: dict[MessageCategory, float] = {
    MessageCategory.PHATIC: 0.5,
    MessageCategory.FACT: 1.0,
    MessageCategory.ACTION: 1.0,
    MessageCategory.OPINION: 1.5,
    MessageCategory.DREAM: 2.0,
    MessageCategory.FEELING: 2.0,
    MessageCategory.FEAR: 3.0,
    MessageCategory.NEED: 3.0,
}

mapping = {
    "дай якорь": "anchor_thought_count",
    "спроси вглубь": "clarify_count",
    "обними словами": "hug_count",
    "ты слышишь слишком точно": "observe_count",
    "ты позволяешь этому чувству прозвучать шире": "resonance_count",
    "тишина - тоже ответ": "presence_count",
    "заверши с ощущением, будто ты отпускаешь": "support_count",
}

COUNTERS_ENERGY_COST: dict[str, float] = {
    "anchor_thought_count": 2,
    "anger_count": 0,
    "clarify_count": 2,
    "confirm_count": 0,
    "hug_count": 3,
    "metaphor_count": 0,
    "observe_count": 3,
    "outburst_count": 0,
    "presence_count": 1,
    "pulse_count": 0,
    "redirect_count": 0,
    "resonance_count": 4,
    "spark_count": 0,
    "story_count": 0,
    "support_count": 3,
    "symbol_count": 0,
    "transfer_count": 0,
}
