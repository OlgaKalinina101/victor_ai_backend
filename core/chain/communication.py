import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.analysis.postanalysis.key_info_chain import KeyInfoPostAnalyzer
from core.analysis.preanalysis.message_analyzer import MessageAnalyzer
from core.dialog.context_builder import ContextBuilder
from core.persona.emotional.engine import ViktorEmotionEvaluator
from core.persona.system_prompt_builder import SystemPromptBuilder
from core.persona.trust.emotional_access_rules import MAX_EMOTIONAL_ACCESS_BY_RELATIONSHIP
from core.persona.trust.helpers import estimate_communication_depth
from infrastructure.context_store.session_context_schema import update_session_context_from_victor_state, SessionContext
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.session import Database
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from infrastructure.utils.threading_tools import run_in_executor
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from models.assistant_models import ReactionFragments, VictorState
from models.communication_models import MessageMetadata
from models.user_models import UserProfile
from settings import settings

from typing import List, Tuple, Optional, AsyncGenerator, Any

from tools.places.places_tool import PlacesContextBuilder
from tools.playlist.playlist_tool import run_playlist_chain
from tools.weather.weather_tool import WeatherContextBuilder


class CommunicationPipeline:
    """Оркестрирует полный цикл коммуникации: анализ, эмоции, генерация ответа и пост-обработка."""

    def __init__(
        self,
        account_id: str,
        user_message: str,
        llm_client: Optional["LLMClient"] = None,
        db: Optional["Database"] = None,
        session_context_store: Optional["SessionContextStore"] = None,
        embedding_pipeline: Optional["PersonaEmbeddingPipeline"] = None,
        extra_context: str = None,
        function_call: str = None,
        geo: Any = None,
        track_data: Optional[dict] = None,
        message_analyzer: Optional["MessageAnalyzer"] = None,
        key_info_analyzer: Optional["KeyInfoPostAnalyzer"] = None,
        logger=None,
        system_prompt_path: Path = settings.SYSTEM_PROMPT_PATH,
        context_prompt_path: Path = settings.CONTEXT_PROMPT_PATH,
    ):
        self.account_id = account_id
        self.user_message = user_message
        self.extra_context = extra_context
        self.function_call = function_call
        self.geo = geo
        self.track_data = track_data
        self.system_prompt_path = system_prompt_path
        self.context_prompt_path = context_prompt_path

        self.logger = logger or setup_logger("communication")
        self.db = db or Database()
        self.session_context_store = session_context_store or SessionContextStore(settings.SESSION_CONTEXT_DIR)
        self.embedding_pipeline = embedding_pipeline or PersonaEmbeddingPipeline()
        self.llm_client = llm_client or LLMClient(mode="foundation")
        self.message_analyzer = message_analyzer or MessageAnalyzer(
            user_message=user_message,
            account_id=account_id,
            llm_client_advanced=self.llm_client,
            db=self.db,
            session_context_store=self.session_context_store,
            embedding_pipeline=self.embedding_pipeline,
        )
        self.key_info_analyzer = key_info_analyzer or KeyInfoPostAnalyzer(llm_client=self.llm_client)


    async def process(self) ->  AsyncGenerator[str | dict, None]:
        """
        Запускает пайплайн коммуникации.

        Returns:
            str: Ответ ассистента.
        """
        self.logger.info(f"[INFO] Запуск пайплайна коммуникации для account_id: {self.account_id}")

        try:
            # Этап 1: Анализ сообщения
            # === ПАРАЛЛЕЛЬНЫЙ ЗАПУСК: анализ + extra_context ===
            analysis_task = asyncio.create_task(self._analyze_message())
            extra_context_task = asyncio.create_task(self._build_extra_context())

            # Ждём ВСЕ задачи
            user_profile, metadata, reaction_data, session_context = await analysis_task
            extra_context_result = await extra_context_task

            # Устанавливаем extra_context (если не было — оставляем как есть)
            if extra_context_result is not None:
                self.extra_context = extra_context_result

            self.logger.info(f"[DEBUG] Категория сообщения: {metadata.message_category}")
            if self.extra_context:
                self.logger.info(f"[DEBUG] extra_context сформирован: {self.extra_context[:100]}...")

            # Этап 2: Оценка эмоционального состояния
            victor_profile = await self._evaluate_emotional_state(session_context, metadata)
            self._update_session_context(session_context, victor_profile)

            # Этап 3: Оценка глубины коммуникации
            emotional_access = self._calculate_emotional_access(user_profile, victor_profile, metadata)
            self.logger.info(f"[DEBUG] Эмоциональный доступ: {emotional_access}")

            # Этап 4: Построение промптов
            system_prompt, context_prompt = await self._build_prompts(user_profile, victor_profile, metadata,
                                                                      reaction_data, emotional_access, session_context)
            self.logger.info(f"[DEBUG] Системный промпт: {str(system_prompt)[:100]}...")
            self.logger.info(f"[DEBUG] Контекстный промпт: {str(context_prompt)[:100]}...")

            # Этап 5: Стрим ответа
            message_history = self._extract_message_history(metadata)
            chunks = []
            text_chunks = []  # ← только строки
            async for chunk in self._generate_response(system_prompt, context_prompt, message_history):
                chunks.append(chunk)
                if isinstance(chunk, str):
                    text_chunks.append(chunk)
                yield chunk  # ← возвращаем по частям

            # Этап 6: Сохранение контекста и пост-анализ
            assistant_response = "".join(text_chunks)  # ← безопасно!
            self.logger.info(f"[DEBUG] Ответ ассистента: {str(assistant_response)[:100]}...")
            if self.track_data and self.track_data.get("track_id"):
                yield {"track_id": self.track_data["track_id"]}

            asyncio.create_task(
                self._background_task(
                    self._save_context_and_post_analyze(session_context, assistant_response, metadata),
                    "save_context"
                )
            )
            asyncio.create_task(
                self._background_task(
                    self._maybe_save_debug(user_profile, metadata, message_history, victor_profile, emotional_access,
            system_prompt, context_prompt, assistant_response),
                    "save_debug"
                )
            )

            self.logger.info("[INFO] Пайплайн коммуникации успешно завершен")

        except Exception as e:
            self.logger.exception(f"[ERROR] Ошибка в пайплайне коммуникации: {e}")
            raise

    async def _build_extra_context(self) -> Optional[str]:
        """Формирует extra_context, если нужно. Возвращает строку или None."""
        if not self.function_call:
            return None

        latitude = self.geo.lat if self.geo else None
        longitude = self.geo.lon if self.geo else None
        self.logger.info(f"[GEO] lat={latitude}, lon={longitude}")

        if self.function_call == "weather":
            if latitude is None or longitude is None:
                self.logger.warning("Погода: геолокация недоступна")

            builder = WeatherContextBuilder()
            return await builder.build(latitude, longitude)

        elif self.function_call == "places":
            if latitude is None or longitude is None:
                self.logger.warning("Места: геолокация недоступна")

            builder = PlacesContextBuilder()
            return builder.build(latitude, longitude)  # ← sync, если так

        elif self.function_call == "playlist":
            self.track_data, context = await run_playlist_chain(account_id=self.account_id)
            return context

        return None

    async def _analyze_message(self) -> Tuple[UserProfile, MessageMetadata, ReactionFragments, SessionContext]:
        """Запускает анализ сообщения через MessageAnalyzer."""
        self.logger.debug("[DEBUG] Анализ сообщения")
        try:
            return await self.message_analyzer.run()
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при анализе сообщения: {e}")
            raise

    async def _evaluate_emotional_state(self, session_context, metadata) -> VictorState:
        """Оценивает эмоциональное состояние через ViktorEmotionEvaluator."""
        self.logger.debug("[DEBUG] Оценка эмоционального состояния")
        try:
            evaluator = ViktorEmotionEvaluator(session_context, metadata)
            victor_profile = evaluator.update_emotional_state()
            self.logger.info("[DEBUG] Эмоциональное состояние обновлено")
            return victor_profile
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при оценке эмоционального состояния: {e}")
            raise

    def _update_session_context(self, session_context: SessionContext, victor_profile: VictorState) -> None:
        """Обновляет контекст сессии на основе профиля Виктора."""
        self.logger.debug("[DEBUG] Обновление контекста сессии")
        try:
            update_session_context_from_victor_state(session_context, victor_profile)
            self.logger.debug("[DEBUG] Контекст сессии успешно обновлен")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при обновлении контекста сессии: {e}")
            raise

    def _calculate_emotional_access(self, user_profile: UserProfile, victor_profile: VictorState,
                                    metadata: MessageMetadata) -> int:
        """Вычисляет уровень эмоционального доступа."""
        self.logger.debug("[DEBUG] Вычисление эмоционального доступа")
        try:
            predicted_depth = estimate_communication_depth(
                victor_profile=victor_profile,
                user_profile=user_profile,
                metadata=metadata
            )
            self.logger.debug(f"[DEBUG] Предсказанная глубина: {predicted_depth}")

            max_allowed = MAX_EMOTIONAL_ACCESS_BY_RELATIONSHIP.get(user_profile.relationship)
            if max_allowed is None:
                self.logger.warning(
                    f"[WARN] Не найден уровень доступа для отношения: {user_profile.relationship}, используется дефолт = 2")
                max_allowed = 2
            self.logger.debug(f"[DEBUG] Максимально допустимая глубина: {max_allowed}")

            emotional_access = min(predicted_depth, max_allowed)
            return emotional_access
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при вычислении эмоционального доступа: {e}")
            raise

    async def _build_prompts(self, user_profile: UserProfile, victor_profile: VictorState,
                             metadata: MessageMetadata, reaction_data: ReactionFragments,
                             emotional_access: int, session_context: SessionContext) -> Tuple[str, str]:
        """Строит системный и контекстный промпты."""
        self.logger.debug("[DEBUG] Построение промптов")
        try:
            builder = SystemPromptBuilder(self.system_prompt_path)
            system_prompt = builder.build(
                gender=user_profile.gender,
                relationship=user_profile.relationship,
                message_category=metadata.message_category,
                victor_mood=victor_profile.mood,
                victor_intensity=victor_profile.intensity,
                emotional_access=emotional_access,
                required_depth_level=MAX_EMOTIONAL_ACCESS_BY_RELATIONSHIP.get(user_profile.relationship)
            )

            context = ContextBuilder(self.context_prompt_path)
            context_prompt = context.build(
                victor_profile=victor_profile,
                user_profile=user_profile,
                metadata=metadata,
                reaction_data=reaction_data,
                emotional_access=emotional_access,
                session_context=session_context,
                extra_context=self.extra_context
            )
            return system_prompt, context_prompt
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при построении промптов: {e}")
            raise

    def _extract_message_history(self, metadata: MessageMetadata) -> List[str]:
        """Извлекает историю сообщений из метаданных."""
        self.logger.debug("[DEBUG] Извлечение истории сообщений")
        try:
            message_history = metadata.message_history.splitlines()

            # Убираем последнее сообщение пользователя, если оно есть
            if message_history and message_history[-1].startswith('user:'):
                message_history = message_history[:-1]

            self.logger.debug(f"[DEBUG] История сообщений: {str(message_history)[:100]}...")

            self.logger.debug(f"[DEBUG] История сообщений: {str(message_history)[:100]}...")
            return message_history
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при извлечении истории сообщений: {e}")
            raise

    async def _generate_response(self, system_prompt: str, context_prompt: str, message_history: List[str]) -> AsyncGenerator[str, None]:
        """Генерирует ответ ассистента."""
        self.logger.debug("[DEBUG] Запуск стриминга ответа")
        try:
            async for chunk in self.llm_client.get_response_stream(
                    system_prompt=system_prompt,
                    context_prompt=context_prompt,
                    message_history=message_history,
                    new_message=self.user_message,
                    temperature=0.8
            ):
                yield chunk
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при генерации ответа: {e}")
            raise


    async def _save_context_and_post_analyze(self, session_context: SessionContext, assistant_response: str,
                                             metadata: MessageMetadata) -> None:
        """Сохраняет контекст сессии и запускает пост-анализ."""
        self.logger.debug("[DEBUG] Сохранение контекста и пост-анализ")
        try:
            session_context.add_assistant_message(assistant_response)
            self.logger.debug(f"[DEBUG] Контекст сессии до сохранения: {session_context}")

            save_history = SessionContextStore(settings.SESSION_CONTEXT_DIR)
            await run_in_executor(save_history.save, session_context)
            self.logger.debug("[DEBUG] Контекст сессии сохранен")

            await self.key_info_analyzer.process(self.account_id, self.user_message, metadata)
            self.logger.debug("[DEBUG] Пост-анализ завершен")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при сохранении контекста или пост-анализе: {e}")
            raise

    async def _maybe_save_debug(
            self, user_profile: UserProfile, metadata: MessageMetadata, message_history: list[str], victor_profile: VictorState,
            emotional_access: int, system_prompt: str, context_prompt: str, assistant_response: str,
    ):
        """
        Сохраняет в infrastructure/logging/debug_dataset/debug_dataset.jsonl все параметры + запрос + ответ.
        """
        os.makedirs("infrastructure/logging/debug_dataset", exist_ok=True)
        output_path = "infrastructure/logging/debug_dataset/debug_dataset.jsonl"

        debug_entry = {
            "analysis": {
                "account_id": user_profile.account_id,
                "gender": user_profile.gender.value,
                "relationship": user_profile.relationship.value,
                "victor_mood": victor_profile.mood.value,
                "victor_intensity": victor_profile.intensity,
                "impressive_score": victor_profile.has_impressive,
                "emotional_access": emotional_access,
                "mood": metadata.mood.value,
                "mood_level": metadata.mood_level.value,
                "message_category": metadata.message_category.value,
                "dialog_weight": metadata.dialog_weight,
                "emotional_anchor": metadata.emotional_anchor,
                "focus_phrases": metadata.focus_phrases,
                "memories": metadata.memories,
            },
            "request_messages_preview": {
                "system_prompt": system_prompt,
                "context_prompt": context_prompt,
                "recent_messages": message_history,
                "current_message": metadata.text
            },
            "assistant_response": assistant_response
        }

        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(debug_entry, ensure_ascii=False) + "\n")
            self.logger.info("[DEBUG: Запись добавлена в debug_dataset.jsonl]")

    async def _background_task(self, coro, name: str):
        """Безопасный запуск фоновой задачи."""
        try:
            await coro
        except Exception as e:
            self.logger.exception(f"[ERROR] Фоновая задача '{name}' упала: {e}")

