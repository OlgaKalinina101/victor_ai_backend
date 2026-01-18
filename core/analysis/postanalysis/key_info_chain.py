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

import asyncio
import uuid
from datetime import datetime, timezone

from core.analysis.postanalysis.helpers import parse_key_info
from core.analysis.postanalysis.prompts import KEY_INFO_PROMPTS, IMPRESSIVE_RATING_PROMPT, get_key_info_prompt
from core.analysis.preanalysis.preanalysis import analyze_dialogue
from core.persona.trust.service import TrustService
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database import Database
from infrastructure.database.repositories import KeyInfoRepository
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from models.communication_models import MessageMetadata
from models.user_enums import Gender, RelationshipLevel
from infrastructure.context_store.session_context_schema import SessionContext
from settings import settings

from typing import Optional

class KeyInfoPostAnalyzer:
    def __init__(
        self,
        account_id: str,
        llm_client: Optional["LLMClient"] = None,
        pipeline: Optional["PersonaEmbeddingPipeline"] = None,
        db: Optional["Database"] = None,
        logger=None,
    ) -> None:
        self.account_id = account_id
        self.pipeline = pipeline or PersonaEmbeddingPipeline()
        self.logger = logger or setup_logger("postanalysis")
        self.llm_client = llm_client or LLMClient(account_id=account_id, mode="foundation")
        self.db = db or Database.get_instance()
        self.trust_service = TrustService(llm_client=self.llm_client, logger=self.logger)


    async def process(
        self,
        account_id: str,
        user_message: str,
        metadata: MessageMetadata,
        gender: Gender = None,
        session_context: Optional[SessionContext] = None,
    ) -> None:
        """
        Обрабатывает сообщение пользователя, извлекает ключевую информацию и сохраняет её.

        Args:
            account_id: ID аккаунта пользователя.
            user_message: Сообщение пользователя.
            metadata: Мета-данные сообщения.
            gender: Пол пользователя (для адаптации промпта).
            session_context: Контекст сессии (если передан — можем обновлять trust/relationship в YAML/DB).
        """
        self.logger.info(f"[INFO] Начало обработки сообщения для account_id: {account_id}, gender: {gender}")

        try:
            key_info = await self._analyze_dialogue(user_message, gender)
            if not self._is_valid_key_info(key_info):
                self.logger.info("[INFO] Нет ключевой информации в сообщении пользователя.")
                return

            category, memory = self._parse_key_info(key_info)
            if not memory or not category:
                self.logger.warning("[WARNING] Недостаточно данных для сохранения key_info.")
                return

            impressive = await self._rate_impressiveness(memory)
            await self._save_to_pipeline(account_id, category, memory, impressive, metadata)
            self._save_to_database(account_id, category, memory, impressive, metadata)

            # ===== BONUS TRUST: FRIEND + impressive=4 =====
            await self._maybe_bonus_trust(account_id, session_context, impressive)

            self.logger.info("[INFO] ✅ Обработка key info завершена успешно.")

        except Exception as e:
            self.logger.exception(f"[ERROR] ❌ Ошибка при обработке key info: {e}")
            raise  # или можно убрать raise, если не нужно пробрасывать ошибку дальше

    async def _maybe_bonus_trust(
        self,
        account_id: str,
        session_context: Optional[SessionContext],
        impressive: int,
    ) -> None:
        """BONUS TRUST вынесен в `TrustService` (здесь только оркестрация сохранений)."""
        if not session_context:
            return

        # Ограничение по RelationshipLevel (как общий принцип гейтинга доверия):
        # бонус применим только для FRIEND и выше.
        relationship_level = getattr(session_context, "relationship_level", None)
        if relationship_level not in {
            RelationshipLevel.FRIEND,
            RelationshipLevel.CLOSE_FRIEND,
            RelationshipLevel.BEST_FRIEND,
        }:
            return

        # Safety: для пользователей без creator мы никогда не должны превысить 79
        is_creator = bool(getattr(session_context, "is_creator", False))
        current_trust = int(getattr(session_context, "trust_level", 0) or 0)
        if not is_creator and current_trust >= 79:
            return

        try:
            bonus_result = self.trust_service.apply_impressive_bonus(
                session_context=session_context,
                impressive=impressive,
                bonus=2,
            )
            if not bonus_result:
                return

            old_trust, new_trust = bonus_result

            # Defense-in-depth: даже если внутренняя логика изменится, не даём не-creator выйти за 79.
            if not is_creator and new_trust > 79:
                self.logger.warning(
                    f"[TRUST][BONUS] Попытка превысить лимит для non-creator: {old_trust} -> {new_trust}, clamped to 79"
                )
                new_trust = 79
                session_context.trust_level = 79

            self.logger.info(
                f"[TRUST][BONUS] {relationship_level.value} + impressive=4 → trust_level {old_trust} -> {new_trust}"
            )

            # 1) YAML: пересохраняем SessionContext
            try:
                store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, store.save, session_context)
            except Exception as e:
                self.logger.warning(
                    f"[TRUST][BONUS] Не удалось сохранить SessionContext в YAML: {e}"
                )

            # 2) DB: обновляем ChatMeta.trust_level
            try:
                with self.db.get_session() as session:
                    self.trust_service.persist_trust_level_only(
                        account_id=account_id, trust_level=new_trust, db_session=session
                    )
            except Exception as e:
                self.logger.warning(
                    f"[TRUST][BONUS] Не удалось обновить trust_level в ChatMeta: {e}"
                )

        except Exception as e:
            # Никогда не валим postanalysis из-за бонусного trust
            self.logger.warning(f"[TRUST][BONUS] Ошибка начисления бонуса: {e}")

    async def _analyze_dialogue(self, user_message: str, gender: Gender = None) -> str:
        """Анализирует диалог и возвращает ключевую информацию."""
        try:
            # Получаем промпт с учетом пола пользователя
            if gender:
                prompt_template = get_key_info_prompt(gender.value)
            else:
                # Fallback на стандартный промпт, если gender не указан
                prompt_template = KEY_INFO_PROMPTS
                
            return await analyze_dialogue(
                llm_client=self.llm_client,
                prompt_template=prompt_template,
                user_message=user_message,
                return_json=False,
            )
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при анализе диалога: {e}")
            raise

    def _is_valid_key_info(self, key_info: str) -> bool:
        """Проверяет, содержит ли ключная информация валидные данные."""
        return key_info.lower() not in {"null", "none", "", "нет ключевой информации"}

    def _parse_key_info(self, key_info: str) -> tuple[Optional[str], Optional[str]]:
        """Парсит ключевую информацию и возвращает категорию и память."""
        try:
            category, memory = parse_key_info(key_info)
            return category, memory
        except Exception as e:
            self.logger.warning(f"[WARNING] Ошибка при парсинге key_info: {e}")
            return None, None

    async def _rate_impressiveness(self, memory: str) -> int:
        """Оценивает значимость памяти."""
        try:
            result = await analyze_dialogue(
                llm_client=self.llm_client,
                prompt_template=IMPRESSIVE_RATING_PROMPT,
                memories=memory,
                return_json=False,
            )
            rating = int(result.strip().replace('"', ''))
            if rating not in {1, 2, 3, 4}:
                raise ValueError(f"Недопустимая оценка: {rating}")
            self.logger.debug(f"[DEBUG] Оценка значимости: {rating}")
            return rating
        except Exception as e:
            self.logger.warning(f"[WARNING] Не удалось определить значимость: {e}, default=1")
            return 1

    async def _save_to_pipeline(self, account_id: str, category: str, memory: str, impressive: int, metadata: MessageMetadata) -> None:
        """Сохраняет данные в pipeline."""
        try:
            self.pipeline.add_entry(
                account_id=account_id,
                memory=memory,
                mood=metadata.mood,
                mood_level=metadata.mood_level,
                category=category,
                impressive=impressive,
                frequency=0,
                last_used=datetime.now(timezone.utc),
                external_id=str(uuid.uuid4()),
            )
            self.logger.info("[DEBUG] ✅ Key info успешно сохранено в Chroma.")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при сохранении в pipeline: {e}")
            raise

    def _save_to_database(self, account_id: str, category: str, memory: str, impressive: int,
                          metadata: MessageMetadata) -> None:
        """Сохраняет данные в базу данных."""
        try:
            with self.db.get_session() as session:
                repo = KeyInfoRepository(session)
                repo.create_from_memory(account_id, category, memory, impressive, metadata)
                self.logger.info("[DEBUG] ✅ Key info успешно сохранено в database.")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при сохранении в базу данных: {e}")
            raise
