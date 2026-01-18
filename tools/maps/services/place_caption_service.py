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

"""VictorPlacesCaption: генерация и кеширование короткой подписи к POI по OSM-тегам."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from sqlalchemy.orm import Session

from infrastructure.database.repositories.chat_meta_repository import ChatMetaRepository
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from tools.maps.repositories import OSMRepository, PlaceCaptionRepository

logger = setup_logger("place_caption_service")

DEFAULT_PROMPTS_PATH = Path(__file__).parent.parent / "config" / "place_caption_prompts.yaml"


def _tags_to_lines(tags: Dict[str, Any]) -> str:
    # Стабильный порядок — проще дебажить и кешировать.
    lines = []
    for k in sorted(tags.keys()):
        v = tags.get(k)
        if v is None:
            continue
        # Приводим к строке максимально предсказуемо.
        if isinstance(v, bool):
            v_str = "yes" if v else "no"
        else:
            v_str = str(v)
        v_str = v_str.strip()
        if not v_str:
            continue
        lines.append(f"{k}={v_str}")
    return "\n".join(lines).strip()


def _tags_hash(tags_lines: str) -> str:
    return hashlib.sha256(tags_lines.encode("utf-8")).hexdigest()


def _infer_llm_mode_from_model(model: str) -> str:
    m = (model or "").lower()
    # Простая эвристика под текущие три провайдера в LLMClient.
    if "deepseek" in m:
        return "foundation"
    if "grok" in m:
        return "creative"
    # default: OpenAI family (gpt-*)
    return "advanced"


def _sanitize_caption(text: str) -> str:
    # Берём первую непустую строку, убираем кавычки/лишние пробелы.
    if not text:
        return "Выпьем кофе?"
    for line in text.splitlines():
        s = line.strip()
        if s:
            text = s
            break
    text = text.strip().strip('"').strip("'").strip()
    # На всякий случай — убираем списки.
    if text.startswith(("-", "•")):
        text = text.lstrip("-•").strip()
    # Ограничение по длине из ТЗ (~80 символов)
    if len(text) > 80:
        text = text[:80].rstrip()
    return text or "Выпьем кофе?"


class PlaceCaptionService:
    """Сервис генерации подписи к месту по тегам."""

    def __init__(self, db_session: Session, prompts_path: Optional[Path] = None):
        self.db_session = db_session
        self.prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
        self._prompts = self._load_prompts(self.prompts_path)
        self._osm_repo = OSMRepository(db_session)
        self._caption_repo = PlaceCaptionRepository(db_session)

    @staticmethod
    def _load_prompts(path: Path) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise RuntimeError(f"PlaceCaption prompts YAML not found: {path}")
        prompts = (cfg.get("victor_places_caption") or {})
        if not isinstance(prompts, dict):
            raise RuntimeError(f"Invalid prompts format in {path}")
        if "{tags}" not in (prompts.get("system_prompt_template") or ""):
            raise RuntimeError(f"system_prompt_template must contain '{{tags}}' placeholder in {path}")
        return prompts

    def _get_model_for_account(self, account_id: str) -> str:
        repo = ChatMetaRepository(self.db_session)
        meta = repo.get_by_account_id(account_id)
        if meta and meta.model:
            return meta.model
        # Fallback: если meta нет — используем "gpt-4o" (как в SessionContext.empty)
        return "gpt-4o"

    async def generate_caption(
        self,
        account_id: str,
        poi_osm_id: int,
        poi_osm_type: str,
        tags: Optional[Dict[str, Any]] = None,
    ) -> str:
        # 1) Теги: либо из запроса, либо из БД по OSMElement
        if tags is None:
            osm_el = self._osm_repo.get_by_id(poi_osm_id)
            if osm_el is None:
                raise ValueError(f"OSMElement not found for poi_osm_id={poi_osm_id}")
            tags = osm_el.tags or {}
        poi_name = (tags.get("name") if isinstance(tags, dict) else None) or None

        tags_lines = _tags_to_lines(tags)
        if not tags_lines:
            tags_lines = "amenity=cafe"
        th = _tags_hash(tags_lines)

        # 2) Кеш: если уже есть запись с теми же тегами — сразу отдаём
        cached = self._caption_repo.get_by_lookup(
            account_id=account_id,
            osm_element_id=poi_osm_id,
            osm_element_type=poi_osm_type,
            tags_hash=th,
        )
        if cached:
            return cached.caption

        # 3) Генерация через LLM
        model = self._get_model_for_account(account_id)
        mode = _infer_llm_mode_from_model(model)

        system_prompt = (self._prompts.get("system_prompt_template") or "").format(tags=tags_lines)
        context_prompt = self._prompts.get("context_prompt") or "Сгенерируй одну короткую подпись к месту по его тегам."
        temperature = float(self._prompts.get("temperature", 0.7))
        max_tokens = int(self._prompts.get("max_tokens", 80))
        fallback_caption = self._prompts.get("fallback_caption") or "Выпьем кофе?"

        llm_client = LLMClient(account_id=account_id, mode=mode)
        # Если в ChatMeta указан другой model в рамках того же провайдера — подменим.
        try:
            if model and model != llm_client.model_name:
                llm_client.update_config(mode, model=model)
        except Exception as exc:
            logger.warning("Не удалось применить кастомную модель '%s' для mode=%s: %s", model, mode, exc)

        raw = await llm_client.get_response(
            system_prompt=system_prompt,
            context_prompt=context_prompt,
            message_history=None,
            new_message=None,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        caption = _sanitize_caption(raw) or fallback_caption

        # 4) Сохраняем в БД (кеш)
        self._caption_repo.create(
            account_id=account_id,
            osm_element_id=poi_osm_id,
            osm_element_type=poi_osm_type,
            poi_name=poi_name,
            tags=tags,
            tags_hash=th,
            caption=caption,
        )
        self.db_session.commit()
        return caption


