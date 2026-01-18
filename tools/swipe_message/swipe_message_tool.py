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

import yaml
from typing import Optional, Tuple

from infrastructure.logging.logger import setup_logger
from core.analysis.preanalysis.preanalysis_helpers import humanize_timestamp
from infrastructure.database.models import DialogueHistory
from models.user_enums import Gender


class SwipeMessageContextBuilder:
    def __init__(self, prompt_path: str = "tools/swipe_message/swipe_message_prompt.yaml"):
        self.logger = setup_logger("swipe_message_tool")
        self.prompt_path = prompt_path
        self.context_template = self._load_prompt_template()

    def _load_prompt_template(self) -> dict:
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.error(f"Ошибка загрузки {self.prompt_path}: {e}")
            return {}

    @staticmethod
    def _gender_phrase_and_verb(gender: Gender) -> Tuple[str, str, str]:
        if gender == Gender.MALE:
            return "Он", "свайпнул", "вернулся"
        if gender == Gender.FEMALE:
            return "Она", "свайпнула", "вернулась"
        return "Пользователь", "свайпнул(а)", "вернул(ась)"

    def build(
        self,
        *,
        db_session,
        account_id: str,
        message_id: int,
        user_gender: Gender = Gender.OTHER,
    ) -> str:
        """
        Формирует контекст для события "свайп старого сообщения".

        Возвращает пустую строку, если сообщение не найдено или произошла ошибка.
        """
        try:
            if not message_id:
                return ""

            record: Optional[DialogueHistory] = (
                db_session.query(DialogueHistory)
                .filter(DialogueHistory.account_id == account_id, DialogueHistory.id == message_id)
                .first()
            )

            if not record:
                self.logger.info(f"[SWIPE] Message not found: account_id={account_id}, id={message_id}")
                return ""

            created_iso = record.created_at.isoformat() if getattr(record, "created_at", None) else None
            humanized_time = humanize_timestamp(created_iso)

            role = (record.role or "").strip() or "unknown"
            message_text = (record.text or "").strip()
            if not message_text:
                message_text = "<пусто>"

            # Без переносов строк (чтобы не ломать форматирование промпта)
            message_text = " ".join(message_text.split())

            user_phrase, swiped_verb, returned_verb = self._gender_phrase_and_verb(user_gender)

            prompt_template = self.context_template.get("swipe_message_prompt", "")
            if not prompt_template:
                return ""

            return prompt_template.format(
                user_phrase=user_phrase,
                swiped_verb=swiped_verb,
                returned_verb=returned_verb,
                humanized_time=humanized_time,
                role=role,
                message_text=message_text,
            ).strip()

        except Exception as e:
            self.logger.error(f"[SWIPE] Ошибка при формировании swipe_context: {e}")
            return ""


