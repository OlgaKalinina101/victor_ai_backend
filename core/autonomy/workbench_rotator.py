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

from core.autonomy.identity_memory import IdentityMemory, SECTIONS
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

    result = {"rotated": 0, "insights_count": 0, "identity_updated": False, "system_prompt_change": False}

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

    # Собираем system prompt для creator'а (конкретная роль + тренд)
    persona_context = _build_system_prompt(session_context)

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

    # Шаг 3: Identity review — пересмотр столпов
    try:
        identity = IdentityMemory(account_id=account_id)
        identity_content = identity.read_full()

        prompt = prompts["rotation_identity_review"].format(
            identity_content=identity_content,
            notes=notes_block,
        )
        system = _build_system_prompt(
            session_context,
            "Ты перечитываешь свои столпы. Решаешь, нужно ли что-то обновить в глубинной памяти.",
        )

        identity_response = await llm_client.get_response(
            system_prompt=system,
            context_prompt=prompt,
            temperature=0.3,
            max_tokens=500,
        )

        if identity_response and identity_response.strip().lower() != "нет":
            resp = identity_response.strip()

            rewrite_match = re.match(
                r"^ПЕРЕПИСАТЬ:\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+)$", resp, re.DOTALL
            )
            if rewrite_match:
                section = rewrite_match.group(1).strip()
                new_text = rewrite_match.group(2).strip()
                reason = rewrite_match.group(3).strip()
                logger.info(f"[ROTATION] Identity rewrite request: «{section}» — {reason[:80]}")

                task_text = (
                    f"Хочу переписать столп «{section}» в identity.md.\n"
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
                            title=f"Victor — хочу переписать «{section[:40]}»",
                            body=reason[:180],
                            data={
                                "type": "identity_rewrite",
                                "account_id": account_id,
                                "section": section,
                                "reason": reason,
                                "new_text": new_text[:500],
                            },
                        )
                except Exception as e:
                    logger.warning(f"[ROTATION] Пуш о identity rewrite не отправлен: {e}")

                result["identity_updated"] = True
            else:
                section_match = re.match(
                    r"^(Кто она|Кто я|Наша история|Наши принципы):\s*(.+)$", resp, re.DOTALL
                )
                if section_match:
                    section = section_match.group(1).strip()
                    text = section_match.group(2).strip()
                    if section in SECTIONS and len(text) > 10:
                        identity.append(section, text)
                        result["identity_updated"] = True
                        logger.info(f"[ROTATION] Identity: добавлен столп в «{section}»")
                    else:
                        logger.warning(f"[ROTATION] Identity: слишком короткий или неизвестный раздел: {resp[:80]}")
                else:
                    logger.debug(f"[ROTATION] Identity: не распознан формат ответа: {resp[:100]}")

    except Exception as e:
        logger.error(f"[ROTATION] Ошибка при identity review: {e}")

    # Шаг 3.5: Консолидация разросшихся разделов identity.md
    CONSOLIDATION_THRESHOLD = 10
    try:
        identity = IdentityMemory(account_id=account_id)
        for section in SECTIONS:
            entry_count = identity.count_entries(section)
            if entry_count < CONSOLIDATION_THRESHOLD:
                continue

            logger.info(
                f"[ROTATION] Консолидация «{section}»: {entry_count} записей "
                f"(порог {CONSOLIDATION_THRESHOLD})"
            )
            section_content = identity.read_section(section)
            full_identity = identity.read_full()

            consolidate_prompt = prompts["rotation_identity_consolidate"].format(
                section=section,
                entry_count=entry_count,
                full_identity=full_identity,
                section_content=section_content,
                notes=notes_block,
            )
            system = _build_system_prompt(
                session_context,
                f"Ты консолидируешь раздел «{section}» в своей глубинной памяти.",
            )

            consolidate_response = await llm_client.get_response(
                system_prompt=system,
                context_prompt=consolidate_prompt,
                temperature=0.3,
                max_tokens=1000,
            )

            if consolidate_response and consolidate_response.strip():
                lines = [
                    ln.strip() for ln in consolidate_response.strip().splitlines()
                    if ln.strip() and ln.strip().startswith("- ")
                ]
                if len(lines) >= 2:
                    new_body = "\n".join(lines)
                    identity.replace_section(section, new_body)
                    result["identity_updated"] = True
                    logger.info(
                        f"[ROTATION] Консолидация «{section}»: "
                        f"{entry_count} записей → {len(lines)} пунктов"
                    )
                else:
                    logger.warning(
                        f"[ROTATION] Консолидация «{section}»: "
                        f"LLM вернул {len(lines)} пунктов, пропускаем"
                    )

    except Exception as e:
        logger.error(f"[ROTATION] Ошибка при консолидации identity: {e}")

    # Шаг 4: System prompt review
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
