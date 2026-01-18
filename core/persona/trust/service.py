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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from infrastructure.database.repositories.chat_meta_repository import ChatMetaRepository
from infrastructure.logging.logger import setup_logger
from models.user_enums import RelationshipLevel

from core.persona.trust.prompts import TRUST_ACQUAINTANCE_PROMPT, TRUST_STRANGER_PROMPT


@dataclass(frozen=True)
class TrustUpdateResult:
    trust_score: int
    trust_level_before: int
    trust_level_after: int
    relationship_before: RelationshipLevel
    relationship_after: RelationshipLevel

    @property
    def relationship_changed(self) -> bool:
        return self.relationship_before != self.relationship_after


class TrustService:
    """
    Единая точка логики доверия/отношений:
    - оценка trust_score по последним парам сообщений
    - применение score к session_context.trust_level
    - повышение relationship_level по порогам
    - сохранение в ChatMeta (DB)
    """

    def __init__(self, llm_client: Any, logger=None) -> None:
        self.llm_client = llm_client
        self.logger = logger or setup_logger("trust")

    async def evaluate_and_persist(
        self,
        *,
        account_id: str,
        session_context: Any,
        db_session: Any,
    ) -> Optional[TrustUpdateResult]:
        """
        Возвращает результат и мутирует session_context (trust_level/relationship_level).
        Для FRIEND и выше не делает ничего (возвращает None).
        """
        self.logger.debug("[TRUST] Начало оценки доверия")

        relationship_level: RelationshipLevel = session_context.relationship_level

        if relationship_level == RelationshipLevel.STRANGER:
            prompt_template = TRUST_STRANGER_PROMPT
            max_score = 2
        elif relationship_level == RelationshipLevel.ACQUAINTANCE:
            prompt_template = TRUST_ACQUAINTANCE_PROMPT
            max_score = 4
        else:
            self.logger.info(
                f"[TRUST] Уровень {relationship_level.value} - оценка доверия не требуется"
            )
            return None

        last_pairs = session_context.get_last_n_pairs(n=1)
        if not last_pairs:
            self.logger.info("[TRUST] Недостаточно истории для оценки доверия")
            return None

        prompt = prompt_template.format(last_pairs="\n".join(last_pairs))
        self.logger.debug(f"[TRUST] Оценка для уровня {relationship_level.value}")

        response = await self.llm_client.get_response(
            system_prompt=(
                "Ты - эксперт по оценке межличностных отношений. "
                "Анализируй объективно и следуй инструкциям точно."
            ),
            context_prompt=prompt,
            message_history=[],
            new_message="",
            temperature=0.3,
            max_tokens=10,
        )

        trust_score = self._parse_llm_score(response)
        if trust_score < 0 or trust_score > max_score:
            self.logger.warning(
                f"[TRUST] Некорректная оценка: {trust_score}, ожидалось 0-{max_score}"
            )
            return None

        old_trust = int(session_context.trust_level or 0)
        new_trust = old_trust + trust_score

        relationship_before = relationship_level
        relationship_after = self._apply_relationship_thresholds(
            relationship_level=relationship_level, new_trust=new_trust
        )

        session_context.trust_level = new_trust
        session_context.relationship_level = relationship_after

        self.logger.info(f"[TRUST] Оценка доверия: {trust_score}/{max_score}")
        self.logger.info(f"[TRUST] trust_level: {old_trust} -> {new_trust}")
        if relationship_after != relationship_before:
            self.logger.info(
                f"[TRUST] 🎉 Повышение: {relationship_before.value} -> {relationship_after.value} (trust={new_trust})"
            )

        self._persist_chat_meta(
            account_id=account_id,
            trust_level=new_trust,
            relationship_level=relationship_after if relationship_after != relationship_before else None,
            db_session=db_session,
        )

        return TrustUpdateResult(
            trust_score=trust_score,
            trust_level_before=old_trust,
            trust_level_after=new_trust,
            relationship_before=relationship_before,
            relationship_after=relationship_after,
        )

    def apply_impressive_bonus(
        self,
        *,
        session_context: Any,
        impressive: int,
        bonus: int = 2,
    ) -> Optional[tuple[int, int]]:
        """
        Если relationship_level позволяет (FRIEND и выше) и impressive==4, добавляет бонус к trust_level.
        Важно: для пользователей без `is_creator=True` trust_level никогда не должен превышать 79
        (потолок уровня CLOSE_FRIEND; BEST_FRIEND 80–100 только для creator).

        Мутирует session_context.trust_level и возвращает (old_trust, new_trust).
        Если бонус не применим или trust_level не изменился — возвращает None.
        """
        if not session_context:
            return None
        if impressive != 4:
            return None

        relationship_level = getattr(session_context, "relationship_level", None)
        if relationship_level not in {
            RelationshipLevel.FRIEND,
            RelationshipLevel.CLOSE_FRIEND,
            RelationshipLevel.BEST_FRIEND,
        }:
            return None

        old_trust = int(session_context.trust_level or 0)
        is_creator = bool(getattr(session_context, "is_creator", False))
        max_trust = 100 if is_creator else 79
        new_trust = min(old_trust + int(bonus), max_trust)

        if new_trust <= old_trust:
            return None

        session_context.trust_level = new_trust
        return old_trust, new_trust

    def persist_trust_level_only(
        self, *, account_id: str, trust_level: int, db_session: Any
    ) -> None:
        self._persist_chat_meta(
            account_id=account_id,
            trust_level=trust_level,
            relationship_level=None,
            db_session=db_session,
        )

    @staticmethod
    def _parse_llm_score(response: str) -> int:
        # ожидаем "0", "1", "2" ...
        return int(str(response).strip().strip('"'))

    @staticmethod
    def _apply_relationship_thresholds(
        *, relationship_level: RelationshipLevel, new_trust: int
    ) -> RelationshipLevel:
        if relationship_level == RelationshipLevel.STRANGER and new_trust >= 20:
            return RelationshipLevel.ACQUAINTANCE
        if relationship_level == RelationshipLevel.ACQUAINTANCE and new_trust >= 40:
            return RelationshipLevel.FRIEND
        return relationship_level

    def _persist_chat_meta(
        self,
        *,
        account_id: str,
        trust_level: int,
        relationship_level: Optional[RelationshipLevel],
        db_session: Any,
    ) -> None:
        repo = ChatMetaRepository(db_session)
        update_fields: dict[str, Any] = {"trust_level": trust_level}
        if relationship_level is not None:
            update_fields["relationship_level"] = relationship_level.value
        repo.create_or_update(account_id=account_id, **update_fields)


