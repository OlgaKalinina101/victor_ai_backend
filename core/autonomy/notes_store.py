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
Хроника Victor — долговременная память заметок в Chroma DB.

Отдельная коллекция для мыслей Victor (отличается от коллекции воспоминаний
пользователя). Используется для:
  - архивации записей с рабочего стола (ротация workbench → Chroma)
  - семантического поиска по прошлым мыслям (search_notes в рефлексии)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from infrastructure.embeddings.embedding_manager import EmbeddingManager
from infrastructure.logging.logger import setup_autonomy_logger
from infrastructure.vector_store.client import get_chroma_client
from settings import settings

logger = setup_autonomy_logger("notes_store")


class NotesStore:
    """CRUD для коллекции заметок Victor в Chroma DB."""

    def __init__(self, client=None):
        self.client = client or get_chroma_client()
        self.collection = self.client.get_or_create_collection(
            name=settings.VICTOR_NOTES_COLLECTION,
        )

    def add_note(
        self,
        account_id: str,
        text: str,
        created_at: Optional[datetime] = None,
        source: str = "workbench",
        mood: Optional[str] = None,
    ) -> str:
        """
        Добавляет одну заметку в Chroma.

        Args:
            account_id: ID аккаунта (creator).
            text: Текст заметки.
            created_at: Когда мысль была записана.
            source: Откуда пришла — workbench / reflection / postanalysis.
            mood: Эмоциональный фон момента.

        Returns:
            ID записи в Chroma.
        """
        ts = created_at or datetime.now(timezone.utc)
        note_id = str(uuid.uuid4())

        embedding = EmbeddingManager.get_embedding(text).tolist()

        metadata = {
            "account_id": account_id,
            "created_at": ts.isoformat(),
            "source": source,
        }
        if mood:
            metadata["mood"] = mood

        self.collection.add(
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[note_id],
        )

        logger.info(f"[NOTES] Добавлена заметка {note_id[:8]}... source={source}")
        return note_id

    def search(
        self,
        query: str,
        account_id: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Семантический поиск по заметкам.

        Args:
            query: Поисковый запрос.
            account_id: Фильтр по аккаунту (если нужен).
            top_k: Сколько результатов вернуть.

        Returns:
            Список словарей {id, text, score, metadata}.
        """
        embedding = EmbeddingManager.get_embedding(query).tolist()

        where_filter = {"account_id": account_id} if account_id else None

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where_filter,
        )

        if not results or not results["documents"] or not results["documents"][0]:
            return []

        output = []
        for i, doc in enumerate(results["documents"][0]):
            output.append({
                "id": results["ids"][0][i],
                "text": doc,
                "score": results["distances"][0][i] if results.get("distances") else None,
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            })

        logger.debug(f"[NOTES] Поиск по '{query[:50]}...': найдено {len(output)} результатов")
        return output
