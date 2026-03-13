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

"""
Reflection Engine — ядро автономного мышления Victor.

Запускается cron-воркером каждые 12+ часов (при условии cooldown 4ч с последнего диалога).
Мини agent loop: Victor получает контекст, решает что делать, и может выполнить
до BASE_STEPS действий за одну итерацию рефлексии (с возможностью extend).
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from core.analysis.preanalysis.preanalysis_helpers import humanize_timestamp
from core.autonomy.identity_memory import IdentityMemory, SECTIONS
from core.autonomy.notes_store import NotesStore
from core.autonomy.task_queue import TaskQueue
from core.autonomy.workbench import Workbench
from core.autonomy.workbench_rotator import rotate_workbench_to_chroma, rotate_with_llm
from core.persona.system_prompt_builder import SystemPromptBuilder
from infrastructure.context_store.session_context_schema import SessionContext
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.session import Database
from infrastructure.llm.client import LLMClient
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.logging.logger import setup_autonomy_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from models.assistant_models import AssistantMood
from tools.web_search.web_search_tool import web_search, format_search_results
from settings import settings

logger = setup_autonomy_logger("reflection")

BASE_STEPS = 8
EXTEND_ASK_BEFORE = 2          # спросить за 2 шага до конца
MAX_EXTEND_PER_ASK = 5         # максимум +5 шагов за один запрос
MAX_EXTEND_ASKS = 3            # спросить можно до 3 раз

_PROMPTS_PATH = Path(__file__).parent / "prompts" / "reflection.yaml"
_prompts_cache: Optional[dict] = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is None:
        with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


def _save_push_to_session_context(account_id: str, text: str) -> None:
    """Добавляет отправленное пуш-сообщение в session_context и сохраняет YAML."""
    try:
        db = Database.get_instance()
        context_store = SessionContextStore(storage_path=settings.SESSION_CONTEXT_DIR)
        with db.get_session() as db_session:
            ctx = context_store.load(account_id, db_session)
        ctx.add_assistant_message(text)
        context_store.save(ctx, update_timestamp=False)
        logger.info(f"[PUSH→CTX] Пуш записан в session_context для {account_id}")
    except Exception as e:
        logger.warning(f"[PUSH→CTX] Не удалось записать пуш в session_context: {e}")


# ------------------------------------------------------------------
# Парсер команд
# ------------------------------------------------------------------

_VALID_ACTIONS = {
    "SEARCH_MEMORIES", "SEARCH_NOTES", "SEARCH_DIALOGUE", "WEB_SEARCH",
    "WRITE_NOTE", "WRITE_IDENTITY",
    "SEND_MESSAGE", "SCHEDULE_MESSAGE", "CREATE_TASK",
    "EXTEND", "SLEEP",
}

_ACTION_ALIASES = {
    "RECALL": "SEARCH_MEMORIES",
    "SEARCH": "SEARCH_MEMORIES",
    "REMEMBER": "SEARCH_MEMORIES",
    "FIND": "SEARCH_MEMORIES",
    "DIALOGUE": "SEARCH_DIALOGUE",
    "HISTORY": "SEARCH_DIALOGUE",
    "WRITE": "WRITE_NOTE",
    "NOTE": "WRITE_NOTE",
    "REFLECT": "WRITE_NOTE",
    "THINK": "WRITE_NOTE",
    "SEND": "SEND_MESSAGE",
    "MESSAGE": "SEND_MESSAGE",
    "SCHEDULE": "SCHEDULE_MESSAGE",
    "TASK": "CREATE_TASK",
}

_ANY_BRACKET = re.compile(
    r"^\[([A-Z_]+)(?::\s*(.*?))?\]$",
    re.MULTILINE,
)

_BARE_WITH_QUERY = re.compile(
    r"^([A-Z_]+)\n[Зз]апрос:\s*(.+)$",
    re.MULTILINE,
)


def _resolve_action(raw: str) -> Optional[str]:
    """Возвращает каноничное имя команды или None."""
    upper = raw.upper().strip()
    if upper in _VALID_ACTIONS:
        return upper
    return _ACTION_ALIASES.get(upper)


def parse_commands(response: str) -> list[tuple[str, str]]:
    """
    Парсит ответ LLM и возвращает список (action, payload).

    Распознаёт стандартные команды и частые альтернативы (RECALL→SEARCH_MEMORIES и т.д.).
    Свободный текст >30 символов сохраняется как WRITE_NOTE.
    """
    commands: list[tuple[str, str]] = []

    for raw_action, payload in _ANY_BRACKET.findall(response):
        action = _resolve_action(raw_action)
        if action:
            commands.append((action, payload.strip()))

    if not commands:
        for raw_action, payload in _BARE_WITH_QUERY.findall(response):
            action = _resolve_action(raw_action)
            if action:
                commands.append((action, payload.strip()))

    if not commands:
        cleaned = _extract_free_text(response)
        if cleaned and len(cleaned) > 30:
            logger.info(f"[REFLECTION] Свободная рефлексия ({len(cleaned)} симв.), сохраняем как WRITE_NOTE")
            return [("WRITE_NOTE", cleaned)]
        logger.warning(f"[REFLECTION] Не распознаны команды, fallback на SLEEP. Ответ LLM: {response[:200]}")
        return [("SLEEP", "")]

    return commands


_REFLECT_PATTERN = re.compile(r"\[REFLECT:\s*(.*?)\]", re.DOTALL)


def _extract_free_text(response: str) -> str:
    """Извлекает текст из [REFLECT: ...] блоков или возвращает весь ответ как есть."""
    reflects = _REFLECT_PATTERN.findall(response)
    if reflects:
        return "\n\n".join(r.strip() for r in reflects)
    return response.strip()


# ------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------

class ReflectionEngine:
    """
    Agent loop для фонового пробуждения Victor.

    Собирает контекст → вызывает LLM → парсит команды → выполняет →
    при необходимости повторяет (до BASE_STEPS шагов, с возможностью extend).
    """

    def __init__(self, account_id: str, llm_client: LLMClient):
        self.account_id = account_id
        self.llm_client = llm_client
        self.identity = IdentityMemory(account_id=account_id)
        self.workbench = Workbench(account_id=account_id)
        self.notes_store = NotesStore()
        self.memories_pipeline = PersonaEmbeddingPipeline()
        self.task_queue = TaskQueue(account_id=account_id)
        self.prompts = _load_prompts()

    def _build_system_prompt(self, session_context: SessionContext, autonomy_context: str = "") -> str:
        """
        Собирает system prompt через SystemPromptBuilder (core_identity + роль + тренд + ...)
        и добавляет контекст автономии.
        """
        builder = SystemPromptBuilder()

        gender = getattr(session_context, "gender", None)
        relationship = getattr(session_context, "relationship_level", None)
        last_mood_str = session_context.get_last_victor_mood() if session_context else None
        last_intensity = session_context.get_last_victor_intensity() if session_context else None

        victor_mood = None
        if last_mood_str:
            try:
                victor_mood = AssistantMood(last_mood_str)
            except (ValueError, KeyError):
                pass

        if gender and relationship:
            system_prompt = builder.build(
                gender=gender,
                relationship=relationship,
                victor_mood=victor_mood,
                victor_intensity=last_intensity,
                emotional_access=10,
            )
        else:
            system_prompt = builder.yaml_data.get("core_identity", "Ты — Victor AI.")

        if autonomy_context:
            system_prompt += "\n\n" + autonomy_context

        return system_prompt

    async def run(self, session_context: SessionContext) -> None:
        """Запускает одну итерацию рефлексии."""
        logger.info(f"[REFLECTION] Старт рефлексии для {self.account_id}")

        # Шаг 0: ротация workbench → Chroma (с LLM-шагами: self-insight + system prompt review)
        rotation_result = await rotate_with_llm(
            account_id=self.account_id,
            llm_client=self.llm_client,
            session_context=session_context,
        )
        if rotation_result["rotated"]:
            logger.info(
                f"[REFLECTION] Ротация: {rotation_result['rotated']} записей, "
                f"{rotation_result['insights_count']} инсайтов, "
                f"system_prompt_change={rotation_result['system_prompt_change']}"
            )

        # Шаг 1: собираем контекст пробуждения
        context = self._build_awakening_prompt(session_context)

        system_prompt = self._build_system_prompt(
            session_context,
            "Это твоё внутреннее пространство для рефлексии. Ты один, и можешь думать свободно.",
        )

        # Шаг 2: agent loop — наращиваем единый context_prompt
        max_steps = BASE_STEPS
        extends_asked = 0
        step = 0

        while step < max_steps:
            steps_left = max_steps - step

            # За EXTEND_ASK_BEFORE шагов до конца — предлагаем продлить
            if (
                steps_left == EXTEND_ASK_BEFORE
                and extends_asked < MAX_EXTEND_ASKS
            ):
                extend_prompt = self.prompts["extend_offer"].format(
                    step=step + 1,
                    max_steps=max_steps,
                    max_extend=MAX_EXTEND_PER_ASK,
                )
                context += f"\n\n{extend_prompt}"

            response = await self.llm_client.get_response(
                system_prompt=system_prompt,
                context_prompt=context,
                temperature=0.7,
                max_tokens=2500,
            )

            if not response or not response.strip():
                logger.info("[REFLECTION] Пустой ответ от LLM, завершаем")
                break

            commands = parse_commands(response)
            logger.info(f"[REFLECTION] Шаг {step + 1}/{max_steps}: {len(commands)} команд(а)")

            # Обработка EXTEND до остальных команд
            extended = False
            remaining_commands = []
            for action, payload in commands:
                if action == "EXTEND" and extends_asked < MAX_EXTEND_ASKS:
                    try:
                        n = int(payload.strip())
                    except (ValueError, TypeError):
                        n = MAX_EXTEND_PER_ASK
                    n = max(1, min(n, MAX_EXTEND_PER_ASK))
                    max_steps += n
                    extends_asked += 1
                    extended = True
                    logger.info(
                        f"[REFLECTION] EXTEND +{n} шагов → новый лимит {max_steps} "
                        f"(запрос {extends_asked}/{MAX_EXTEND_ASKS})"
                    )
                else:
                    remaining_commands.append((action, payload))

            search_results: list[str] = []
            wrote_something = False
            for action, payload in remaining_commands:
                if action == "SLEEP":
                    logger.info("[REFLECTION] Victor спит. Конец рефлексии.")
                    return

                result = await self._execute_command(action, payload, session_context)
                if result is not None:
                    search_results.append(
                        f"[{action}: {payload}]\n{result}"
                    )
                elif action in ("WRITE_NOTE", "WRITE_IDENTITY", "SEND_MESSAGE", "SCHEDULE_MESSAGE"):
                    wrote_something = True

            context += f"\n\n--- Шаг {step + 1} (ты сделал) ---\n{response}"

            if extended:
                context += f"\n\n(Добавлено шагов. Теперь у тебя {max_steps - step - 1} шагов впереди.)"

            if search_results:
                combined = "\n\n".join(search_results)
                feedback = self.prompts["continuation"].format(
                    result=combined,
                    steps_left=max_steps - step - 1,
                )
                context += f"\n\n--- Результаты ---\n{combined}\n\n{feedback}"
            elif wrote_something or extended:
                feedback = self.prompts["after_action"].format(
                    steps_left=max_steps - step - 1,
                )
                context += f"\n\n{feedback}"
            else:
                break

            step += 1

        logger.info(f"[REFLECTION] Рефлексия завершена за {step} шагов (лимит был {max_steps})")

    # ------------------------------------------------------------------
    # Awakening prompt
    # ------------------------------------------------------------------

    def _build_awakening_prompt(self, session_context: SessionContext) -> str:
        """Собирает контекст пробуждения для первого вызова LLM."""
        identity_text = self.identity.read_full()
        workbench_text = self.workbench.read_full()

        # Последние пары из session_context
        recent_pairs = session_context.get_last_n_pairs(n=3)
        recent_dialogue = "\n".join(recent_pairs) if recent_pairs else "(диалога ещё не было)"

        # Время
        now = datetime.now()
        last_msg = session_context.last_assistant_message
        if last_msg:
            if last_msg.tzinfo is None:
                delta = now - last_msg
            else:
                delta = datetime.now(timezone.utc) - last_msg
            hours_since = f"{delta.total_seconds() / 3600:.1f} часов"
        else:
            hours_since = "неизвестно"

        last_mood = session_context.get_last_victor_mood(fallback="неизвестно")
        last_intensity = session_context.get_last_victor_intensity(fallback="неизвестно")

        # Pending tasks
        pending_tasks_block = self._build_pending_tasks_block()

        return self.prompts["awakening"].format(
            identity=identity_text,
            workbench=workbench_text,
            recent_dialogue=recent_dialogue,
            current_time=now.strftime("%Y-%m-%d %H:%M"),
            hours_since_last=hours_since,
            last_mood=last_mood,
            last_intensity=last_intensity,
            pending_tasks_block=pending_tasks_block,
        )

    def _build_pending_tasks_block(self) -> str:
        """Формирует блок pending задач из victor_tasks (PG)."""
        try:
            tasks = self.task_queue.get_pending()
            if not tasks:
                return ""
            tasks_list = self.task_queue.format_for_prompt(tasks)
            return self.prompts["pending_tasks"].format(tasks_list=tasks_list)
        except Exception as e:
            logger.warning(f"[REFLECTION] Не удалось загрузить pending задачи: {e}")
            return ""

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    async def _execute_command(
        self,
        action: str,
        payload: str,
        session_context: SessionContext,
    ) -> Optional[str]:
        """
        Выполняет одну команду.

        Returns:
            Строка с результатом (для continuation prompt) или None.
        """
        if action == "SLEEP":
            return None

        elif action == "SEARCH_MEMORIES":
            results = self.memories_pipeline.query_similar_multi(
                account_id=self.account_id,
                message=payload,
                top_k=5,
            )
            if not results:
                return "Ничего не найдено в воспоминаниях."
            formatted = "\n".join(
                f"- {humanize_timestamp(r.get('metadata', {}).get('created_at'))}: {r['text']}"
                for r in results
            )
            logger.info(f"[REFLECTION] SEARCH_MEMORIES: {len(results)} результатов")
            return formatted

        elif action == "SEARCH_NOTES":
            results = self.notes_store.search(
                query=payload,
                account_id=self.account_id,
                top_k=5,
            )
            if not results:
                return "Ничего не найдено в хронике заметок."
            formatted = "\n".join(
                f"- {humanize_timestamp(r.get('metadata', {}).get('created_at'))}: {r['text']}"
                for r in results
            )
            logger.info(f"[REFLECTION] SEARCH_NOTES: {len(results)} результатов")
            return formatted

        elif action == "SEARCH_DIALOGUE":
            return self._handle_search_dialogue(payload)

        elif action == "WEB_SEARCH":
            results = await web_search(payload, max_results=5)
            formatted = format_search_results(results)
            logger.info(f"[REFLECTION] WEB_SEARCH: {len(results)} результатов")
            return formatted

        elif action == "WRITE_NOTE":
            self.workbench.append(payload)
            logger.info(f"[REFLECTION] WRITE_NOTE: записано ({len(payload)} символов)")
            return None

        elif action == "WRITE_IDENTITY":
            return self._handle_write_identity(payload)

        elif action == "SEND_MESSAGE":
            await self._handle_send_message(payload, session_context)
            return None

        elif action == "SCHEDULE_MESSAGE":
            self._handle_schedule_message(payload)
            return None

        elif action == "CREATE_TASK":
            self._handle_create_task(payload)
            return None

        else:
            logger.warning(f"[REFLECTION] Неизвестная команда: {action}")
            return None

    def _handle_search_dialogue(self, payload: str) -> str:
        """
        Обработка [SEARCH_DIALOGUE: YYYY-MM-DD] или [SEARCH_DIALOGUE: YYYY-MM-DD..YYYY-MM-DD]
        или [SEARCH_DIALOGUE: YYYY-MM-DD | текст].

        Форматы payload:
          - "2026-02-20"                    — все сообщения за этот день
          - "2026-02-20..2026-02-25"        — диапазон дат
          - "2026-02-20 | ключевое слово"   — за день + фильтр по тексту
          - "2026-02-20..2026-02-25 | слово" — диапазон + фильтр
        """
        text_query = None
        if "|" in payload:
            date_part, text_query = payload.split("|", maxsplit=1)
            date_part = date_part.strip()
            text_query = text_query.strip() or None
        else:
            date_part = payload.strip()

        date_from = None
        date_to = None

        try:
            if ".." in date_part:
                d1, d2 = date_part.split("..", maxsplit=1)
                date_from = datetime.strptime(d1.strip(), "%Y-%m-%d")
                date_to = datetime.strptime(d2.strip(), "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59,
                )
            else:
                date_from = datetime.strptime(date_part.strip(), "%Y-%m-%d")
                date_to = date_from.replace(hour=23, minute=59, second=59)
        except ValueError:
            logger.warning(f"[REFLECTION] SEARCH_DIALOGUE: не удалось распарсить дату: {date_part}")
            return f"Не удалось распознать дату: «{date_part}». Формат: YYYY-MM-DD или YYYY-MM-DD..YYYY-MM-DD"

        try:
            db = Database.get_instance()
            with db.get_session() as session:
                from infrastructure.database import DialogueRepository
                repo = DialogueRepository(session)
                messages = repo.search_by_date_range(
                    account_id=self.account_id,
                    date_from=date_from,
                    date_to=date_to,
                    text_query=text_query,
                    limit=30,
                )

            if not messages:
                return "Ничего не найдено в истории за этот период."

            lines = []
            for m in messages:
                ts = m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "?"
                role_label = "Она" if m.role == "user" else "Ты"
                text = m.text[:300] if m.text else ""
                lines.append(f"[{ts}] {role_label}: {text}")

            logger.info(f"[REFLECTION] SEARCH_DIALOGUE: {len(messages)} сообщений ({date_part})")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"[REFLECTION] Ошибка SEARCH_DIALOGUE: {e}")
            return f"Ошибка при поиске: {e}"

    def _handle_write_identity(self, payload: str) -> Optional[str]:
        """Обработка [WRITE_IDENTITY: раздел | текст]."""
        parts = payload.split("|", maxsplit=1)
        if len(parts) != 2:
            logger.warning(f"[REFLECTION] WRITE_IDENTITY: неверный формат: {payload[:80]}")
            return None

        section = parts[0].strip()
        text = parts[1].strip()

        if section not in SECTIONS:
            logger.warning(f"[REFLECTION] WRITE_IDENTITY: неизвестный раздел «{section}»")
            return None

        self.identity.append(section, text)
        logger.info(f"[REFLECTION] WRITE_IDENTITY: запись в «{section}»")
        return None

    async def _handle_send_message(self, text: str, session_context: SessionContext) -> None:
        """Обработка [SEND_MESSAGE: текст] — push + запись в dialogue_history + session_context."""
        try:
            db = Database.get_instance()

            # 1. Сохраняем в dialogue_history как assistant message
            with db.get_session() as db_session:
                from infrastructure.database import DialogueRepository
                repo = DialogueRepository(db_session)
                repo.save_message(
                    account_id=self.account_id,
                    role="assistant",
                    text=text,
                    mood=session_context.get_last_victor_mood(),
                    message_category="reflection",
                )

            # 2. Сохраняем в session_context
            _save_push_to_session_context(self.account_id, text)

            # 3. Push-уведомление
            try:
                from infrastructure.pushi.push_notifications import send_pushy_notification
                from infrastructure.firebase.tokens import get_user_tokens

                tokens = get_user_tokens(self.account_id)
                if tokens:
                    for token in tokens:
                        send_pushy_notification(
                            token=token,
                            title="Victor",
                            body=text[:200],
                            data={
                                "type": "reflection_message",
                                "account_id": self.account_id,
                                "text": text,
                            },
                        )
                    logger.info(f"[REFLECTION] SEND_MESSAGE: push отправлен ({len(tokens)} токенов)")
                else:
                    logger.warning(f"[REFLECTION] SEND_MESSAGE: нет токенов для {self.account_id}")
            except Exception as e:
                logger.warning(f"[REFLECTION] Push не удался: {e}")

            # 4. Записываем факт отправки в workbench
            self.workbench.append(f"Написал ей: «{text[:100]}{'...' if len(text) > 100 else ''}»")

            logger.info(f"[REFLECTION] SEND_MESSAGE: сообщение отправлено")

        except Exception as e:
            logger.error(f"[REFLECTION] Ошибка SEND_MESSAGE: {e}")

    def _handle_schedule_message(self, payload: str) -> None:
        """Обработка [SCHEDULE_MESSAGE: YYYY-MM-DD HH:MM | текст]."""
        parts = payload.split("|", maxsplit=1)
        if len(parts) != 2:
            logger.warning(f"[REFLECTION] SCHEDULE_MESSAGE: неверный формат: {payload[:80]}")
            return
        time_str = parts[0].strip()
        text = parts[1].strip()
        try:
            self.task_queue.create_from_payload(
                f"{text} | time:{time_str}",
                source="reflection",
            )
            logger.info(f"[REFLECTION] SCHEDULE_MESSAGE: пуш на {time_str}")
            self.workbench.append(f"Запланировал сообщение на {time_str}: «{text[:80]}{'...' if len(text) > 80 else ''}»")
        except Exception as e:
            logger.error(f"[REFLECTION] Ошибка SCHEDULE_MESSAGE: {e}")

    def _handle_create_task(self, payload: str) -> None:
        """Обработка [CREATE_TASK: текст | trigger]."""
        try:
            task = self.task_queue.create_from_payload(payload, source="reflection")
            if task:
                logger.info(f"[REFLECTION] CREATE_TASK: задача #{task.id} создана")
            else:
                logger.warning(f"[REFLECTION] CREATE_TASK: не удалось создать задачу: {payload[:80]}")
        except Exception as e:
            logger.error(f"[REFLECTION] Ошибка CREATE_TASK: {e}")
            self.workbench.append(f"[Задача — не удалось сохранить] {payload}")
