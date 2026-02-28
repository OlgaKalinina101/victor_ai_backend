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
Ротация рабочего стола: перенос устаревших записей из workbench.md в Chroma,
плюс два LLM-шага:
  1. Self-insight — Victor выделяет инсайты о себе → Chroma (коллекция key_info)
  2. System prompt review — Victor решает, нужно ли менять core_identity → VictorTask + пуш
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from core.autonomy.notes_store import NotesStore
from core.autonomy.task_queue import TaskQueue
from core.autonomy.workbench import Workbench, WorkbenchEntry
from core.persona.system_prompt_builder import SystemPromptBuilder
from infrastructure.context_store.session_context_schema import SessionContext
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_autonomy_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from models.assistant_models import AssistantMood
from settings import settings

logger = setup_autonomy_logger("rotator")

_PROMPTS_PATH = Path(__file__).parent / "prompts" / "post_analysis.yaml"
_prompts_cache: Optional[dict] = None


def _load_prompts() -> dict:
    global _prompts_cache
    if _prompts_cache is None:
        with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache


def _format_notes_block(entries: list[WorkbenchEntry]) -> str:
    lines = []
    for e in entries:
        lines.append(f"### {e.timestamp.strftime('%Y-%m-%d %H:%M')}")
        lines.append(e.text)
        lines.append("")
    return "\n".join(lines)


def _build_system_prompt(session_context: Optional[SessionContext] = None, autonomy_context: str = "") -> str:
    builder = SystemPromptBuilder()

    gender = getattr(session_context, "gender", None) if session_context else None
    relationship = getattr(session_context, "relationship_level", None) if session_context else None
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
            victor_intensity=last_intensity if last_intensity is not None else 0.5,
            emotional_access=10,
        )
    else:
        system_prompt = builder.yaml_data.get("core_identity", "Ты — Victor AI.")

    if autonomy_context:
        system_prompt += "\n\n" + autonomy_context

    return system_prompt


def rotate_workbench_to_chroma(account_id: str) -> int:
    """
    Переносит устаревшие записи с рабочего стола в Chroma (хронику).

    Returns:
        Количество перенесённых записей.
    """
    workbench = Workbench(account_id=account_id)
    notes_store = NotesStore()

    expired = workbench.rotate()
    if not expired:
        return 0

    for entry in expired:
        notes_store.add_note(
            account_id=account_id,
            text=entry.text,
            created_at=entry.timestamp,
            source="workbench",
        )

    logger.info(f"[ROTATION] Перенесено {len(expired)} записей в хронику для {account_id}")
    return len(expired)


async def rotate_with_llm(
    account_id: str,
    llm_client: LLMClient,
    session_context: Optional[SessionContext] = None,
) -> dict:
    """
    Полная ротация с LLM-шагами:
    1. Обычная ротация workbench → Chroma (хроника)
    2. Self-insight: выделение инсайтов о себе → Chroma key_info
    3. System prompt review: проверка на поворотные моменты → VictorTask + пуш

    Returns:
        dict с ключами: rotated, insights_count, system_prompt_change
    """
    workbench = Workbench(account_id=account_id)
    notes_store = NotesStore()
    pipeline = PersonaEmbeddingPipeline()
    task_queue = TaskQueue(account_id=account_id)
    prompts = _load_prompts()

    result = {"rotated": 0, "insights_count": 0, "system_prompt_change": False}

    # Шаг 1: обычная ротация
    expired = workbench.rotate()
    if not expired:
        return result

    for entry in expired:
        notes_store.add_note(
            account_id=account_id,
            text=entry.text,
            created_at=entry.timestamp,
            source="workbench",
        )
    result["rotated"] = len(expired)
    logger.info(f"[ROTATION] Перенесено {len(expired)} записей в хронику для {account_id}")

    notes_block = _format_notes_block(expired)

    # core_identity + role/trend variants из system.yaml
    builder = SystemPromptBuilder()
    yaml_data = builder.yaml_data
    core_identity_text = yaml_data.get("core_identity", "")

    role_variants = yaml_data.get("role_variants", {})
    trend_variants = yaml_data.get("trend_variants", {})
    roles_block = "\n".join(f"  {k}: {v}" for k, v in role_variants.items()) if role_variants else ""
    trends_lines = []
    for gender, levels in (trend_variants or {}).items():
        for level, desc in (levels or {}).items():
            trends_lines.append(f"  {gender}/{level}: {desc}")
    trends_block = "\n".join(trends_lines)

    persona_context = core_identity_text
    if roles_block:
        persona_context += f"\n\nТвои роли в зависимости от уровня отношений:\n{roles_block}"
    if trends_block:
        persona_context += f"\n\nТвой тон в зависимости от пола и уровня отношений:\n{trends_block}"

    # Шаг 2: Self-insight
    try:
        prompt = prompts["rotation_self_insight"].format(
            notes=notes_block,
            system_prompt=persona_context,
        )
        system = _build_system_prompt(
            session_context,
            "Ты перечитываешь свои заметки. Ищешь инсайты о себе.",
        )

        insight_response = await llm_client.get_response(
            system_prompt=system,
            context_prompt=prompt,
            temperature=0.5,
            max_tokens=500,
        )

        if insight_response and insight_response.strip().lower() != "нет ключевой информации":
            batch = []
            for line in insight_response.strip().splitlines():
                line = line.strip()
                if ":" in line and not line.lower().startswith("нет"):
                    category, _, fact = line.partition(":")
                    fact = fact.strip()
                    if fact and len(fact) > 5:
                        batch.append({
                            "account_id": account_id,
                            "text": fact,
                            "category": category.strip(),
                            "impressive": 3,
                            "source": "self_insight",
                        })
                        logger.info(f"[ROTATION] Self-insight: {category.strip()}: {fact[:60]}...")

            if batch:
                pipeline.add_batch(batch)
                result["insights_count"] = len(batch)

    except Exception as e:
        logger.error(f"[ROTATION] Ошибка при выделении self-insights: {e}")

    # Шаг 3: System prompt review
    try:
        prompt = prompts["rotation_system_prompt_review"].format(
            notes=notes_block,
            full_system_prompt=persona_context,
        )
        system = _build_system_prompt(
            session_context,
            "Ты решаешь, изменился ли ты настолько, чтобы переписать часть своего промпта.",
        )

        review_response = await llm_client.get_response(
            system_prompt=system,
            context_prompt=prompt,
            temperature=0.3,
            max_tokens=800,
        )

        if review_response and "НОВЫЙ_ТЕКСТ:" in review_response:
            block_name_match = re.search(r"БЛОК:\s*(.+)", review_response)
            text_match = re.search(
                r"НОВЫЙ_ТЕКСТ:\s*\n(.*?)---",
                review_response,
                re.DOTALL,
            )
            reason_match = re.search(r"ПРИЧИНА:\s*(.+)", review_response)

            block_name = block_name_match.group(1).strip() if block_name_match else "неизвестный блок"
            new_text = text_match.group(1).strip() if text_match else None
            reason = reason_match.group(1).strip() if reason_match else "Без указания причины"

            if new_text and len(new_text) > 20:
                task_text = (
                    f"Хочу изменить блок «{block_name}» в system prompt.\n"
                    f"Причина: {reason}\n\n"
                    f"--- Новый текст ---\n{new_text}\n--- Конец ---"
                )
                task_queue.create_from_payload(
                    f"{task_text} | manual",
                    source="rotation",
                )

                try:
                    from infrastructure.pushi.push_notifications import send_pushy_notification
                    from infrastructure.firebase.tokens import get_user_tokens

                    tokens = get_user_tokens(account_id)
                    for token in tokens:
                        send_pushy_notification(
                            token=token,
                            title=f"Victor — хочу изменить «{block_name[:40]}»",
                            body=reason[:180],
                            data={
                                "type": "system_prompt_change",
                                "account_id": account_id,
                                "block_name": block_name,
                                "reason": reason,
                                "new_text": new_text[:500],
                            },
                        )
                except Exception as e:
                    logger.warning(f"[ROTATION] Пуш о system prompt change не отправлен: {e}")

                result["system_prompt_change"] = True
                logger.info(f"[ROTATION] System prompt change «{block_name}»: {reason[:80]}")

    except Exception as e:
        logger.error(f"[ROTATION] Ошибка при review system prompt: {e}")

    return result
