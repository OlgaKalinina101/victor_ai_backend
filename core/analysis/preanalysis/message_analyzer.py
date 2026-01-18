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
from infrastructure.database import DialogueRepository
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

from typing import Tuple, Optional, Dict
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
        self.memories_mapping: Dict[str, str] = {}  # text -> id для обновления usage
        self.analysis_result: Optional[AnalysisResult] = None
        self.user_profile: Optional[UserProfile] = None
        self.metadata: Optional[MessageMetadata] = None
        self.reaction_fragments: Optional[ReactionFragments] = None
        # Если клиент не передан, создаём дефолтный
        self.llm_client_foundation = llm_client_foundation or LLMClient(account_id=self.account_id, mode="foundation")
        self.llm_client_advanced = llm_client_advanced or LLMClient(account_id=self.account_id, mode="advanced")
        self.llm_client_creative = llm_client_creative or LLMClient(account_id=self.account_id, mode="creative")
        self.db = db or Database.get_instance()
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
                
                # Проверяем не устарела ли сессия (прошло > 6 часов)
                if is_session_stale(raw_data):
                    self.logger.info("[INFO] Сессия устарела (> 6 часов), выполняем сброс")

                    # Важно: текущее user-сообщение уже добавлено в YAML роутером (update_timestamp=False).
                    # При сбросе нельзя его потерять, иначе YAML история рассинхронится (assistant добавится, а user пропадёт).
                    current_user_text = self.session_context.get_last_user_message(fallback="").strip()
                    
                    # Сохраняем последние 3 пары для контекста.
                    # Важно: берём из БД (стабильная сортировка по id), т.к. YAML может быть "грязным"
                    # (например, несколько user подряд после сбоев/параллельных запросов).
                    last_pairs = self._get_last_n_pairs_from_db(db_session=db_session, n=3)
                    if not last_pairs:
                        # Fallback: если БД пуста/недоступна — берём из YAML как раньше
                        last_pairs = self.session_context.get_last_n_pairs(n=3)
                    
                    # Сбрасываем контекст для новой сессии
                    self.session_context = self.session_context.reset_after_save(
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

                    # Возвращаем текущее user-сообщение последним (если оно есть и ещё не в конце)
                    if current_user_text:
                        last_line = self.session_context.message_history[-1] if self.session_context.message_history else ""
                        expected_line = f"user: {current_user_text}"
                        if last_line != expected_line:
                            self.session_context.message_history.append(expected_line)
                    
                    # Сохраняем сброшенный контекст в YAML
                    self.session_context_store.save(self.session_context)
                    self.logger.info(f"[INFO] Сессия сброшена и сохранена. Восстановлено {len(last_pairs)} сообщений.")
                    self.logger.debug(f"[session_context] {self.session_context}")
                
                # User-сообщение уже добавлено в message_router, не дублируем
                self.logger.info(f"[DEBUG] Контекст сессии успешно загружен: {self.session_context}")
            finally:
                db_session.close()
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при загрузке контекста сессии: {e}")
            raise

    def _get_last_n_pairs_from_db(
        self,
        db_session,
        n: int = 3,
        scan_limit: int = 50,
        trailing_users_limit: int = 3,
    ) -> list[str]:
        """
        Возвращает последние N пар (user+assistant) из БД.

        Используем устойчивый порядок по id (через DialogueRepository.get_paginated),
        и собираем пары даже если в истории встречаются "дырки" (например, несколько user подряд).
        """
        try:
            repo = DialogueRepository(db_session)
            messages, _has_more = repo.get_paginated(
                account_id=self.account_id,
                limit=scan_limit,
                before_id=None,
            )  # messages: старые -> новые

            if not messages:
                return []

            # Debug-метрика: помогает поймать ситуации "несколько user подряд" и т.п.
            try:
                roles_tail = [m.role for m in messages[-12:]]
                self.logger.debug(f"[CTX_RESET][DB_TAIL_ROLES] last_roles={roles_tail}")
            except Exception:
                pass

            def _strip_legacy_prefix(role: str, text: str) -> str:
                if not text:
                    return text
                if role == "user" and text.startswith("user: "):
                    return text[6:]
                if role == "assistant" and text.startswith("assistant: "):
                    return text[11:]
                return text

            # 1) Сохраняем хвостовые user-сообщения без пары (если стрим оборвался/упал)
            trailing: list[str] = []
            i = len(messages) - 1
            while i >= 0 and messages[i].role == "user" and len(trailing) < trailing_users_limit:
                user_text = _strip_legacy_prefix("user", messages[i].text).strip()
                trailing.insert(0, f"user: {user_text}")
                i -= 1

            # 2) Добираем последние N полных пар (user + assistant)
            pairs: list[str] = []
            while i >= 0 and len(pairs) < n * 2:
                m = messages[i]
                if m.role == "assistant":
                    # Ищем ближайшее user-сообщение ДО этого assistant
                    j = i - 1
                    while j >= 0 and messages[j].role != "user":
                        j -= 1
                    if j >= 0:
                        user_text = _strip_legacy_prefix("user", messages[j].text).strip()
                        asst_text = _strip_legacy_prefix("assistant", m.text).strip()
                        pairs.insert(0, f"user: {user_text}")
                        pairs.insert(1, f"assistant: {asst_text}")
                        i = j - 1
                    else:
                        i -= 1
                else:
                    i -= 1

            # Возвращаем пары + хвостовые user (если были)
            return pairs + trailing
        except Exception as e:
            self.logger.warning(f"[WARN] Не удалось восстановить пары из БД: {e}")
            return []

    async def _load_relevant_memories(self) -> str:
        """Загружает релевантные воспоминания из embedding pipeline (multi-query)."""
        self.logger.debug("[DEBUG] Загрузка релевантных воспоминаний (multi-query)")
        try:
            top_memories = self.embedding_pipeline.query_similar_multi(
                account_id=self.account_id,
                message=self.user_message,
                top_k=5
            )
            self.logger.info(f"[DEBUG] Найдено воспоминаний: {len(top_memories)}")

            # Форматируем с временными метками и сохраняем mapping text -> id
            memories_payload = []
            self.memories_mapping = {}  # Очищаем перед заполнением
            
            for m in top_memories:
                created_at = m.get("metadata", {}).get("created_at")
                time_label = humanize_timestamp(created_at)
                text = m["text"]
                memory_id = m.get("id")
                
                # Нормализуем текст для mapping (убираем лишние пробелы)
                import re
                text_normalized = re.sub(r'\s+', ' ', text).strip()
                
                # Сохраняем mapping: нормализованный текст -> id
                self.memories_mapping[text_normalized] = memory_id
                memories_payload.append(f"{time_label}: {text}")

            memories_str = "\n".join([f'- "{m}"' for m in memories_payload])
            self.logger.debug(f"[DEBUG] Форматированные воспоминания: {memories_str}")
            self.logger.debug(f"[DEBUG] Mapping: {list(self.memories_mapping.keys())[:3]}...")
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

    def _strip_time_label(self, text: str) -> str:
        """Убирает time_label из текста воспоминания (например, 'месяц назад: текст' → 'текст')."""
        # Time labels: "сегодня:", "вчера:", "X дней назад:", "неделю назад:", "месяц назад:", etc.
        import re
        # Паттерн: начало строки + (слово/число + "назад:" или "сегодня:"/"вчера:") + пробел
        pattern = r'^(?:сегодня|вчера|\d+\s*(?:дней?|недел[ьи]|месяц(?:а|ев)?|год(?:а)?)\s*назад)\s*:\s*'
        return re.sub(pattern, '', text, flags=re.IGNORECASE).strip()

    async def _update_memory_usage(self) -> None:
        """Асинхронно обновляет использование памяти в pipeline по ID."""
        self.logger.debug("[DEBUG] Обновление использования памяти")

        if not self.metadata or not self.metadata.memories:
            self.logger.info("[INFO] Нет воспоминаний для обновления — пропускаем шаг.")
            return

        try:
            # Ищем ID по тексту воспоминания через mapping
            memory_text_raw = self.metadata.memories
            self.logger.debug(f"[DEBUG] Исходный текст от LLM: {memory_text_raw[:80]}...")
            
            # Убираем time_label (LLM возвращает "месяц назад: текст", а в mapping только "текст")
            memory_text = self._strip_time_label(memory_text_raw)
            self.logger.debug(f"[DEBUG] После strip time_label: {memory_text[:80]}...")
            
            # Нормализуем: убираем "..." в конце + лишние пробелы
            import re
            memory_text_clean = re.sub(r'\s+', ' ', memory_text).strip().rstrip('.')
            
            # 1. Пробуем точное совпадение
            memory_id = self.memories_mapping.get(memory_text_clean)
            
            if not memory_id:
                # 2. Пробуем без учёта обрезания (...) - ищем по началу
                for text, mid in self.memories_mapping.items():
                    # Проверяем: начало текста из mapping совпадает с тем что вернул LLM
                    if text.startswith(memory_text_clean) or memory_text_clean.startswith(text[:50]):
                        memory_id = mid
                        self.logger.debug(f"[DEBUG] Найден ID по началу текста: {mid}")
                        break
            
            if not memory_id:
                # 3. Fallback: частичное вхождение
                for text, mid in self.memories_mapping.items():
                    if memory_text_clean in text or text in memory_text_clean:
                        memory_id = mid
                        self.logger.debug(f"[DEBUG] Найден ID по частичному совпадению: {mid}")
                        break
            
            if not memory_id:
                self.logger.warning(f"[WARNING] Не найден ID для воспоминания: {memory_text_clean[:50]}...")
                self.logger.debug(f"[DEBUG] Доступные ключи в mapping: {list(self.memories_mapping.keys())[:3]}")
                self.logger.warning(f"[WARNING] Используем поиск по эмбеддингу.")
                # Fallback на старый метод
                pipeline = PersonaEmbeddingPipeline()
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(executor, pipeline.update_memory_usage, self.account_id, memory_text_clean)
            else:
                self.logger.debug(f"[DEBUG] Обновляем по ID: {memory_id}")
                pipeline = PersonaEmbeddingPipeline()
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(executor, pipeline.update_memory_usage_by_id, memory_id)
            
            self.logger.debug("[DEBUG] Использование памяти успешно обновлено")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при обновлении использования памяти: {e}")
            raise
