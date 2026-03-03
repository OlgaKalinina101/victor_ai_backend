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
Постанализ автономии: после каждого диалога Victor заходит в свой журнал.

- impressive 1-2: краткая пометка в workbench
- impressive 3-4: развёрнутая запись

Victor может также поставить отложенный пуш через [SCHEDULE_MESSAGE].
Identity-анализ перенесён в ротацию workbench (workbench_rotator.py).
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from core.autonomy.task_queue import TaskQueue
from core.autonomy.workbench import Workbench
from core.persona.system_prompt_builder import SystemPromptBuilder
from infrastructure.context_store.session_context_schema import SessionContext
from infrastructure.database.models import VictorTaskTrigger, VictorTaskStatus
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_autonomy_logger
from models.assistant_models import AssistantMood
from settings import settings

logger = setup_autonomy_logger("post_analyzer")

_PROMPTS_PATH = Path(__file__).parent / "prompts" / "post_analysis.yaml"
_prompts_cache: Optional[dict] = None

_SCHEDULE_PATTERN = re.compile(
    r"\[SCHEDULE_MESSAGE:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\|\s*(.+?)\]",
    re.DOTALL,
)


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is None:
        with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


class AutonomyPostAnalyzer:
    """
    Постанализ автономии — вызывается после каждого диалога (только для creator).

    Два режима:
      - impressive 1-2: краткая пометка в workbench (дыхание — непрерывное)
      - impressive 3-4: развёрнутая запись
    """

    def __init__(
        self,
        account_id: str,
        llm_client: Optional[LLMClient] = None,
        session_context: Optional[SessionContext] = None,
    ):
        self.account_id = account_id
        self.llm_client = llm_client or LLMClient(account_id=account_id, mode="foundation")
        self.session_context = session_context
        self.workbench = Workbench(account_id=account_id)
        self.task_queue = TaskQueue(account_id=account_id)
        self.prompts = _load_prompts()

    def _build_system_prompt(self, autonomy_context: str = "") -> str:
        """
        Собирает system prompt через SystemPromptBuilder (core_identity + роль + тренд + ...)
        и добавляет контекст автономии.
        """
        builder = SystemPromptBuilder()

        # Берём параметры из session_context (если есть)
        gender = getattr(self.session_context, "gender", None)
        relationship = getattr(self.session_context, "relationship_level", None)
        last_mood_str = self.session_context.get_last_victor_mood() if self.session_context else None
        last_intensity = self.session_context.get_last_victor_intensity() if self.session_context else None

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

    async def process(
        self,
        user_message: str,
        assistant_message: str,
        impressive: int = 1,
    ) -> None:
        """
        Основная точка входа.

        Args:
            user_message: Сообщение пользователя.
            assistant_message: Ответ Victor.
            impressive: Оценка значимости (1-4) из KeyInfoPostAnalyzer.
        """
        try:
            await self._write_workbench(user_message, assistant_message, impressive)

        except Exception as e:
            logger.exception(f"[AUTONOMY] Ошибка в постанализе автономии: {e}")

    # ------------------------------------------------------------------
    # Pending pushes block
    # ------------------------------------------------------------------

    def _build_pending_pushes_block(self) -> str:
        """Формирует блок: уже отправленные пуши за сегодня + запланированные (pending)."""
        lines: list[str] = []

        # 1. Уже отправленные сегодня (reflection + scheduled из dialogue_history)
        try:
            from infrastructure.database.session import Database
            from infrastructure.database import DialogueRepository
            from sqlalchemy import desc

            db = Database.get_instance()
            with db.get_session() as db_session:
                repo = DialogueRepository(db_session)
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                from infrastructure.database.models import DialogueHistory
                sent_today = (
                    db_session.query(DialogueHistory)
                    .filter(
                        DialogueHistory.account_id == self.account_id,
                        DialogueHistory.role == "assistant",
                        DialogueHistory.message_category.in_(["reflection", "scheduled"]),
                        DialogueHistory.created_at >= today_start,
                    )
                    .order_by(desc(DialogueHistory.created_at))
                    .limit(10)
                    .all()
                )
            if sent_today:
                lines.append("Сообщения, которые ты уже отправил ей сегодня:")
                for m in sent_today:
                    time_str = m.created_at.strftime("%H:%M") if m.created_at else "?"
                    lines.append(f"  - [{time_str}] «{m.text[:100]}{'...' if len(m.text) > 100 else ''}»")
        except Exception as e:
            logger.warning(f"[AUTONOMY] Не удалось загрузить отправленные пуши: {e}")

        # 2. Запланированные (ещё не отправлены)
        try:
            tasks = self.task_queue.get_pending()
            time_tasks = [t for t in tasks if t.trigger_type == VictorTaskTrigger.TIME]
            if time_tasks:
                lines.append("Запланированные сообщения (ещё не отправлены):")
                for t in time_tasks:
                    lines.append(f"  - на {t.trigger_value}: «{t.text[:80]}{'...' if len(t.text) > 80 else ''}»")
        except Exception as e:
            logger.warning(f"[AUTONOMY] Не удалось загрузить pending пуши: {e}")

        if not lines:
            return "Ты сегодня ничего ей не отправлял и ничего не запланировал."

        lines.append("Не дублируй. Если хочешь — запланируй что-то новое, но не повторяй то, что уже сказал.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Schedule commands
    # ------------------------------------------------------------------

    def _handle_schedule_commands(self, llm_response: str) -> str:
        """
        Парсит [SCHEDULE_MESSAGE: ...] из ответа LLM, создаёт VictorTask.
        Если на то же время уже есть pending задача — отменяет старую (rewrite).
        Возвращает текст с вырезанными командами.
        """
        matches = list(_SCHEDULE_PATTERN.finditer(llm_response))
        if not matches:
            return llm_response

        for match in matches:
            time_str = match.group(1).strip()
            message_text = match.group(2).strip()
            try:
                self.task_queue.cancel_duplicate_time_task(time_str, source="postanalysis")
                self.task_queue.create_from_payload(
                    f"{message_text} | time:{time_str}",
                    source="postanalysis",
                )
                logger.info(f"[AUTONOMY] SCHEDULE_MESSAGE: пуш на {time_str}")
            except Exception as e:
                logger.warning(f"[AUTONOMY] Не удалось создать SCHEDULE_MESSAGE: {e}")

        return _SCHEDULE_PATTERN.sub("", llm_response).strip()

    async def _write_workbench(
        self,
        user_message: str,
        assistant_message: str,
        impressive: int,
    ) -> None:
        """Записывает мысль в workbench. Глубина зависит от impressive."""
        if impressive >= 3:
            prompt_template = self.prompts["workbench_deep"]
        else:
            prompt_template = self.prompts["workbench_brief"]

        pending_block = self._build_pending_pushes_block()

        prompt = prompt_template.format(
            user_message=user_message,
            assistant_message=assistant_message,
            impressive=impressive,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            pending_pushes_block=pending_block,
        )

        try:
            raw_note = await self.llm_client.get_response(
                system_prompt=self._build_system_prompt(
                    "Ты пишешь в свой внутренний журнал. Это не для неё — это для тебя."
                ),
                context_prompt=prompt,
                temperature=0.7,
                max_tokens=2500,
            )

            if not raw_note or not raw_note.strip():
                return

            note = self._handle_schedule_commands(raw_note)

            if note:
                self.workbench.append(note)
                logger.info(
                    f"[AUTONOMY] Workbench: записана {'развёрнутая' if impressive >= 3 else 'краткая'} "
                    f"заметка ({len(note)} символов)"
                )
        except Exception as e:
            logger.error(f"[AUTONOMY] Ошибка записи в workbench: {e}")

