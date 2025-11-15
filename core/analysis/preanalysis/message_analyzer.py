from core.analysis.preanalysis.analysis_prompts import (
    ANALYZE_DIALOGUE_ANCHORS_PROMPT,
    ANALYZE_DIALOGUE_FOCUS_PROMPT,
    PROMPT_QUESTIONS_PROFILE,
    PROMPT_REACTION_CORE,
    PROMPT_REACTION_START,
    PROMPT_TYPE_MEANING,
    PROMPT_APPROVE_MEMORIES, PROMPT_END_BLOCK,
)
from core.analysis.preanalysis.analysis_result import AnalysisResult
from core.analysis.preanalysis.emotion_analyzer import EmotionInterpreter
from core.analysis.preanalysis.preanalysis import analyze_dialogue
from core.analysis.preanalysis.preanalysis_helpers import is_more_than_6_hours_passed, humanize_timestamp

from infrastructure.context_store.session_context_schema import SessionContext, update_reaction_counters, \
    update_session_context_from_metadata, to_serializable
from infrastructure.context_store.session_context_store import SessionContextStore, is_session_stale
from infrastructure.database.repositories import save_session_context_as_history
from infrastructure.database.session import Database
from infrastructure.embeddings.emotion_recognizer import EmotionRecognizer
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline

from models.assistant_models import ReactionFragments
from models.communication_enums import MessageCategory
from models.communication_models import MessageMetadata
from models.user_enums import UserMoodLevel
from models.user_models import UserProfile

from settings import settings

from typing import Tuple, Optional
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Инициализация ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=5)


class MessageAnalyzer:
    """Оркестрирует анализ сообщения пользователя для создания метаданных, профилей и контекста диалога."""

    def __init__(
            self,
            user_message: str,
            account_id: str,
            llm_client_foundation: Optional["LLMClient"] = None,
            llm_client_advanced: Optional["LLMClient"] = None,
            llm_client_creative: Optional["LLMClient"] = None,
            session_context_store: Optional["SessionContextStore"] = None,
            db: Optional["Database"] = None,
            embedding_pipeline: Optional["PersonaEmbeddingPipeline"] = None,
            logger=None,
    ) -> None:
        self.user_message = user_message
        self.account_id = account_id
        self.mood: Optional[str] = None
        self.mood_level: Optional[UserMoodLevel] = None
        self.dialog_weight: Optional[float] = None
        self.session_context: Optional[SessionContext] = None
        self.message_history_str: Optional[str] = None
        self.memories_str: Optional[str] = None
        self.analysis_result: Optional[AnalysisResult] = None
        self.user_profile: Optional[UserProfile] = None
        self.metadata: Optional[MessageMetadata] = None
        self.reaction_fragments: Optional[ReactionFragments] = None
        # Если клиент не передан, создаём дефолтный
        self.llm_client_foundation = llm_client_foundation or LLMClient(account_id=self.account_id, mode="foundation")
        self.llm_client_advanced = llm_client_advanced or LLMClient(account_id=self.account_id, mode="advanced")
        self.llm_client_creative = llm_client_creative or LLMClient(account_id=self.account_id, mode="creative")
        self.db = db or Database()
        self.session_context_store = session_context_store or SessionContextStore(settings.SESSION_CONTEXT_DIR)
        self.embedding_pipeline = embedding_pipeline or PersonaEmbeddingPipeline()
        self.logger = logger or setup_logger("message_analyzer")

    async def run(self) -> Tuple[UserProfile, MessageMetadata, ReactionFragments, SessionContext]:
        """
        Оркестрирует многоэтапный анализ сообщения пользователя для создания метаданных и контекста.

        Этапы:
        1. Загрузка контекста сессии и базовый анализ (эмоции, якоря и т.д.).
        2. Загрузка кэшированных данных и предварительный анализ (настроение, сложность, ключевая информация).
        3. Формирование профиля пользователя, метаданных сообщения и контекста диалога.

        Returns:
            Tuple containing UserProfile, MessageMetadata, ReactionFragments, SessionContext.
        """
        start_time = time.perf_counter()
        self.logger.info(f"[INFO] Начало анализа сообщения для account_id: {self.account_id}")

        try:
            # Этап 1: Загрузка контекста и воспоминаний
            await self._load_session_context()
            self.message_history_str = self.session_context.get_recent_pairs()
            self.memories_str = await self._load_relevant_memories()

            # Этап 2: Анализ сообщения
            await self._analyze_message()

            # Этап 3: Формирование объектов метаданных
            self.user_profile, self.metadata, self.reaction_fragments = await self._finalize_analysis()
            self._update_session_context()

            # Асинхронное обновление памяти в pipeline
            await self._update_memory_usage()

            self.logger.info(f"[INFO] Анализ завершен за {time.perf_counter() - start_time:.2f}s")
            return self.user_profile, self.metadata, self.reaction_fragments, self.session_context

        except Exception as e:
            self.logger.exception(f"[ERROR] Ошибка при анализе сообщения: {e}")
            raise

    async def _load_session_context(self) -> None:
        """Загружает контекст сессии."""
        self.logger.debug("[DEBUG] Загрузка контекста сессии")
        try:
            db_session = self.db.get_session()

            try:
                self.session_context = self.session_context_store.load(
                    account_id=self.account_id, db_session=db_session
                )
                raw_data = to_serializable(self.session_context)
                if is_session_stale(raw_data):
                    last_pairs = self.session_context.get_last_n_pairs(n=3)

                    # Создаем копию для сохранения БЕЗ последних 3 пар (они будут восстановлены)
                    save_data = raw_data.copy()
                    if last_pairs:
                        # Исключаем последние N сообщений из сохранения
                        save_data["message_history"] = raw_data["message_history"][:-len(last_pairs)]

                    # Сохраняем в БД только если есть что сохранять (история не пустая)
                    if save_data.get("message_history"):
                        await asyncio.get_event_loop().run_in_executor(
                            None, save_session_context_as_history, db_session, save_data
                        )
                    else:
                        self.logger.info("[INFO] История сообщений пуста после исключения последних пар - пропускаем сохранение в БД")
                    self.session_context_store = self.session_context_store.load(account_id=self.account_id,
                                                                       db_session=db_session)
                    self.session_context=self.session_context.reset_after_save(
                        self.session_context.gender,
                        self.session_context.relationship_level,
                        self.session_context.trust_level,
                        self.session_context.is_creator,
                        self.session_context.model,
                        self.session_context.last_assistant_message,
                        self.session_context.last_anchor
                    )
                    # Восстанавливаем последние 3 пары
                    self.session_context.message_history = last_pairs
                    self.logger.debug(f"[session_context] {self.session_context}")
                self.session_context.add_user_message(self.user_message)
                self.logger.info(f"[DEBUG] Контекст сессии успешно загружен: {self.session_context}")
            finally:
                db_session.close()
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при загрузке контекста сессии: {e}")
            raise

    async def _load_relevant_memories(self) -> str:
        """Загружает релевантные воспоминания из embedding pipeline."""
        self.logger.debug("[DEBUG] Загрузка релевантных воспоминаний")
        try:
            top_memories = self.embedding_pipeline.query_similar(
                account_id=self.account_id,
                query=self.user_message,
                top_k=5
            )
            self.logger.info(f"[DEBUG] Найдено воспоминаний: {len(top_memories)}")

            # Форматируем с временными метками
            memories_payload = []
            for m in top_memories:
                created_at = m.get("metadata", {}).get("created_at")
                time_label = humanize_timestamp(created_at)
                text = m["text"]
                memories_payload.append(f"{time_label}: {text}")

            memories_str = "\n".join([f'- "{m}"' for m in memories_payload])
            self.logger.debug(f"[DEBUG] Форматированные воспоминания: {memories_str}")
            return memories_str

        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при загрузке воспоминаний: {e}")
            raise

    async def _analyze_message(self) -> None:
        """Выполняет анализ сообщения."""
        self.logger.debug("[DEBUG] Начало анализа сообщения")
        try:
            self.analysis_result = await self._analyze_dialogue_structure()
            self.session_context.update_emotion_weights(self.analysis_result.mood_data)

            interpreter = EmotionInterpreter(self.analysis_result.mood_data)
            self.mood = interpreter.get_mood()
            self.mood_level = interpreter.get_mood_level()
            self.logger.info(f"[DEBUG] Результат анализа: mood={self.mood}, mood_level={self.mood_level}")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при анализе сообщения: {e}")
            raise

    async def _analyze_emotion_structure(self) -> list[dict[str, float]]:
        """Выполняет эмоциональный анализ сообщения."""
        self.logger.debug("[DEBUG] Эмоциональный анализ сообщения")
        try:
            recognizer = EmotionRecognizer()
            mood_data = recognizer.predict(self.user_message)
            self.logger.debug(f"[DEBUG] Результат эмоционального анализа: {mood_data}")
            return mood_data
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при эмоциональном анализе: {e}")
            raise

    async def _analyze_dialogue_structure(self) -> AnalysisResult:
        """Выполняет анализ структуры диалога."""
        self.logger.debug("[DEBUG] Анализ структуры диалога")
        try:
            results = await asyncio.gather(
                self._analyze_emotion_structure(),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=ANALYZE_DIALOGUE_FOCUS_PROMPT,
                    user_message=self.user_message
                ),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=ANALYZE_DIALOGUE_ANCHORS_PROMPT,
                    user_message=self.user_message
                ),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=PROMPT_TYPE_MEANING,
                    user_message=self.user_message
                ),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=PROMPT_REACTION_START,
                    message_history=self.message_history_str
                ),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=PROMPT_REACTION_CORE,
                    message_history=self.message_history_str
                ),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=PROMPT_QUESTIONS_PROFILE,
                    message_history=self.message_history_str
                ),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=PROMPT_END_BLOCK,
                    message_history=self.message_history_str,
                    memories=self.memories_str
                ),
                analyze_dialogue(
                    llm_client=self.llm_client_foundation,
                    prompt_template=PROMPT_APPROVE_MEMORIES,
                    message_history=self.message_history_str,
                    memories=self.memories_str
                ),
                return_exceptions=True
            )

            # Проверка ошибок в результатах
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"[ERROR] Ошибка в задаче анализа #{i}: {result}")
                    raise result

            mood_data, focus_result, anchor_result, type_result, reaction_start_result, reaction_core_result, question_result, end_result, memories_result = results

            return AnalysisResult(
                mood_data=mood_data,
                focus_result=focus_result,
                anchor_result=anchor_result,
                type_result=type_result,
                reaction_start_result=reaction_start_result,
                reaction_core_result=reaction_core_result,
                question_result=question_result,
                end_result=end_result,
                memories_result=memories_result
            )
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при анализе структуры диалога: {e}")
            raise

    async def _finalize_analysis(self) -> Tuple[UserProfile, MessageMetadata, ReactionFragments]:
        """Формирует объекты метаданных."""
        self.logger.debug("[DEBUG] Финализация анализа")
        try:
            approved_memory = next(
                (k for k, v in self.analysis_result.memories_result.items()
                 if (isinstance(v, str) and v.lower() == "true") or v is True),
                None
            )
            self.logger.debug(f"[DEBUG] Одобренная память: {approved_memory}")

            self.user_profile = UserProfile(
                account_id=self.account_id,
                gender=self.session_context.gender,
                relationship=self.session_context.relationship_level,
                trust_level=self.session_context.trust_level,
                model=self.session_context.model,
            )
            self.metadata = MessageMetadata(
                text=self.user_message,
                message_history=self.message_history_str,
                mood=self.mood,
                mood_level=self.mood_level,
                dialog_weight=self.dialog_weight,
                message_category=MessageCategory.from_str(self.analysis_result.type_result.get("type"),
                                                          default=MessageCategory.PHATIC),
                emotional_anchor=self.analysis_result.anchor_result,
                focus_phrases=self.analysis_result.focus_result,
                has_first_disclosure=False,
                memories=approved_memory
            )
            self.reaction_fragments = ReactionFragments(
                start=list(self.analysis_result.reaction_start_result.values())[0],
                core=list(self.analysis_result.reaction_core_result.values())[0],
                question=list(self.analysis_result.question_result.values())[0],
                end=list(self.analysis_result.end_result.values())[0],
            )
            self.logger.info(f"[DEBUG] Сформированы метаданные: {self.metadata}")
            return self.user_profile, self.metadata, self.reaction_fragments
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при финализации анализа: {e}")
            raise

    def _update_session_context(self) -> None:
        """Обновляет контекст сессии на основе метаданных."""
        self.logger.debug("[DEBUG] Обновление контекста сессии")
        try:
            update_reaction_counters(self.session_context, self.reaction_fragments)
            update_session_context_from_metadata(self.session_context, self.metadata)
            self.logger.debug("[DEBUG] Контекст сессии успешно обновлен")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при обновлении контекста сессии: {e}")
            raise

    async def _update_memory_usage(self) -> None:
        """Асинхронно обновляет использование памяти в pipeline."""
        self.logger.debug("[DEBUG] Обновление использования памяти")

        if not self.metadata or not self.metadata.memories:
            self.logger.info("[INFO] Нет воспоминаний для обновления — пропускаем шаг.")
            return

        try:
            pipeline = PersonaEmbeddingPipeline()
            loop = asyncio.get_event_loop()
            self.logger.debug(f"Обновляем {self.metadata.memories}")
            await loop.run_in_executor(executor, pipeline.update_memory_usage, self.account_id, self.metadata.memories)
            self.logger.debug("[DEBUG] Использование памяти успешно обновлено")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при обновлении использования памяти: {e}")
            raise
