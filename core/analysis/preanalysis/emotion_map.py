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

from models.user_enums import Mood

EMOTION_BONUS_RU = {
    "joy": 0.05,
    "no_emotion": 0.1,
    "sadness": 0.15,
    "fear": 0.15,
    "anger": 0.1,
    "surprise": 0.0
}
EMOTION_BONUS_ENG = {
    "joy": 0.05,
    "love": 0.1,
    "sadness": 0.15,
    "fear": 0.15,
    "anger": 0.1,
    "surprise": 0.0
}

MOOD_RULES = {
    Mood.TENDER: {
        "joy": 0.6,
        "sadness": 0.2,
        "__condition__": lambda s: s.get("joy", 0) > s.get("sadness", 0)
    },
    Mood.JOY: {
        "joy": 0.7,
        "sadness": {"max": 0.03},
        "surprise": {"max": 0.3}
    },
    Mood.CALM: {"no_emotion": 0.6},
    Mood.SURPRISE: {"surprise": 0.6},
    Mood.SADNESS: {"sadness": 0.7},
    Mood.TIRED: {"sadness": 0.4, "no_emotion": 0.3},
    Mood.DISAPPOINTMENT: {"sadness": 0.5, "anger": 0.2},
    Mood.ANGER: {"anger": 0.6},
    Mood.INSECURITY: {"fear": 0.4, "sadness": 0.3},
    Mood.SHAME: {"sadness": 0.5, "fear": 0.3}
}