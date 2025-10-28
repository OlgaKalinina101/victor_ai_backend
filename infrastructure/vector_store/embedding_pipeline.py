# Victor AI Project
# Copyright (c) 2025 Olga Kalinina
# All rights reserved.

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from infrastructure.embeddings.embedding_manager import EmbeddingManager
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.client import get_chroma_client, get_chroma_collection
from models.user_enums import UserMoodLevel, Mood

logger = setup_logger("memory_builder")

def safe_metadata(**kwargs) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}

class PersonaEmbeddingPipeline:
    def __init__(self, client=None, collection=None) -> None:
        """Инициализирует клиента и коллекцию ChromaDB."""
        self.client = client or get_chroma_client()
        self.collection = collection or get_chroma_collection(self.client)

    def add_entry(
        self,
        account_id: str,
        memory: str,
        mood: Mood,
        mood_level: UserMoodLevel,
        category: str,
        subcategory: Optional[str] = None,
        impressive: int = 1,
        frequency: Optional[int] = None,
        last_used: Optional[datetime] = None,
        has_critical: bool = False,
        external_id: Optional[str] = None,
    ) -> None:
        """Добавляет одну запись в ChromaDB с эмбеддингами и метаданными."""
        embedding = EmbeddingManager.get_embedding(memory).tolist()

        metadata = safe_metadata(
            account_id=account_id,
            category=category,
            subcategory=subcategory,
            impressive=impressive,
            has_critical=has_critical,
            frequency=frequency,
            last_used=last_used.isoformat() if last_used else None,
            mood=mood.value,
            mood_level=mood_level.value,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        self.collection.add(
            documents=[memory],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[external_id or str(uuid.uuid4())],
        )

    def add_batch(self, entries: list[dict]) -> None:
        """Добавляет список записей в ChromaDB."""
        texts = [e["text"] for e in entries]
        embeddings = [EmbeddingManager.get_embedding(t).tolist() for t in texts]

        metadatas = [
            {
                "account_id": e["account_id"],
                "category": e["category"],
                "subcategory": e.get("subcategory"),
                "impressive": e.get("impressive", 1),
                "has_critical": e.get("has_critical", False),
                "frequency": e.get("frequency"),
                "last_used": e.get("last_used").isoformat() if e.get("last_used") else None,
            }
            for e in entries
        ]
        ids = [e.get("id", str(uuid.uuid4())) for e in entries]

        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def update_entry(self, entry_id: str, new_text: Optional[str] = None, new_metadata: Optional[dict] = None):
        """Обновляет запись в коллекции по ID."""
        self.collection.delete(ids=[entry_id])

        text = new_text or "PLACEHOLDER"
        embedding = EmbeddingManager.get_embedding(text).tolist()

        self.collection.add(
            documents=[text],
            embeddings=[embedding],
            metadatas=[new_metadata or {}],
            ids=[entry_id],
        )

    def query_similar(
            self,
            account_id: str,
            query: str,
            top_k: int = 3,
            days_cutoff: int = 5,
    ) -> list[dict]:
        """
        Находит top_k ближайших по смыслу записей к запросу,
        исключая те, что использовались менее чем N дней назад.
        """
        embedding = EmbeddingManager.get_embedding(query).tolist()
        results = self.collection.query(query_embeddings=[embedding], n_results=top_k * 2, where={"account_id": account_id})  # запас для фильтра
        logger.info(results)

        # Пороговая дата (например, 5 дней назад)
        threshold_date = datetime.now() - timedelta(days=days_cutoff)

        # Отфильтровываем по last_used
        filtered = []
        for res_id, doc, meta, score in zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
        ):
            last_used_str = meta.get("last_used")
            if last_used_str:
                try:
                    last_used_dt = datetime.fromisoformat(last_used_str)
                    last_used_dt = last_used_dt.replace(tzinfo=None)  # сделать naive
                    if last_used_dt >= threshold_date:
                        continue  # пропускаем, если слишком недавно использовалось
                except ValueError:
                    pass  # если вдруг формат повреждён — просто не фильтруем

            filtered.append({
                "id": res_id,
                "text": doc,
                "metadata": meta,
                "score": round(score, 3),
            })

            if len(filtered) >= top_k:
                break

        return filtered

    def update_memory_usage(self, account_id: str, target_doc: str):
        """Обновляет frequency и last_used через поиск по эмбеддингу"""

        try:
            # 1. Поиск ближайшего документа по эмбеддингу
            result = self.collection.query(query_texts=[target_doc], n_results=1, where={"account_id": account_id})
            logger.debug(f"result: {result}")

            if not result or not result['ids'] or not result['ids'][0]:
                logger.warning(f"[SKIP] Ничего не найдено по эмбеддингу: {target_doc[:80]}...")
                return

            doc_id = result['ids'][0][0]

            # 2. Получаем данные по найденному ID
            results = self.collection.get(
                ids=[doc_id],
                include=["embeddings", "documents", "metadatas"]
            )
            if results is None:
                logger.warning(f"[SKIP] Не удалось получить документ по ID: {doc_id}")
                return

            # 3. Проверка, что все поля есть
            old_metadata = results.get('metadatas', [None])[0]
            old_embedding = results.get('embeddings', [None])[0]
            document = results.get('documents', [None])[0]

            # 3. Проверка, что все поля есть
            if any(x is None for x in (old_metadata, old_embedding, document)):
                logger.warning(f"[SKIP] Документ с ID {doc_id} не содержит всех нужных данных.")
                return

            # 4. Удаляем старую запись
            self.collection.delete(ids=[doc_id])

            # 5. Обновляем metadata
            updated_metadata = old_metadata.copy()
            updated_metadata['frequency'] = int(old_metadata.get('frequency', 0)) + 1
            updated_metadata['last_used'] = datetime.now().isoformat()

            # 6. Добавляем заново
            self.collection.add(
                documents=[document],
                embeddings=[old_embedding],
                metadatas=[updated_metadata],
                ids=[doc_id]
            )

            logger.info(f"[OK] Обновлено: {doc_id}")

        except Exception as e:
            logger.exception(f"[ERROR] Ошибка при обновлении документа: {e}")

    def get_collection_contents(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Возвращает содержимое текущей коллекции ChromaDB.

        Args:
            account_id (str): ID пользователя для проверки.

        Returns:
            List[Dict[str, Any]]: Список записей с id, текстом и метаданными.

        Raises:
            ValueError: Если коллекция пуста или недоступна.
            Exception: Для других ошибок при работе с ChromaDB.
        """
        try:
            # Получаем все данные
            results = self.collection.get(include=["documents", "metadatas", "embeddings"],
                                          where={"account_id": account_id})
            if not results["ids"]:
                raise ValueError("Коллекция пуста или недоступна")

            # Формируем список записей
            records = []
            for doc_id, doc, metadata in zip(results["ids"], results["documents"], results["metadatas"]):
                record = {
                    "id": doc_id,
                    "text": doc,
                    "metadata": metadata
                }
                records.append(record)

            return records

        except Exception as e:
            raise Exception(f"Ошибка при получении содержимого коллекции: {str(e)}")

    def delete_collection_records(self, account_id: str, record_ids: List[str]) -> None:
        """
        Удаляет указанные записи из текущей коллекции ChromaDB.

        Args:
            account_id (str): ID пользователя для проверки.
            record_ids (List[str]): Список ID записей для удаления.

        Raises:
            ValueError: Если IDs некорректны или коллекция недоступна.
            Exception: Для других ошибок при работе с ChromaDB.
        """
        logger.info(f"Удаление записей: record_ids={record_ids}, account_id={account_id}, type(account_id)={type(account_id)}")
        try:
            if not record_ids:
                logger.warning("Список ID для удаления пуст")
                raise ValueError("Список ID для удаления пуст")

            if not isinstance(account_id, str):
                logger.error(f"account_id должен быть строкой, получен: {type(account_id)}")
                raise ValueError(f"account_id должен быть строкой, получен: {type(account_id)}")

            # Проверяем существующие записи
            results = self.collection.get(
                ids=record_ids,
                include=["metadatas"],
                where={"account_id": account_id}
            )
            logger.info(f"Найдено записей для удаления: {len(results['ids'])}, ids={results['ids']}")

            if not results["ids"]:
                logger.warning(f"Нет записей с ids={record_ids} для account_id={account_id}")
                raise ValueError(f"Нет записей с указанными ID для account_id={account_id}")

            if len(results["ids"]) != len(record_ids):
                logger.warning(f"Найдено только {len(results['ids'])} из {len(record_ids)} запрошенных записей")
                raise ValueError("Некоторые записи не принадлежат указанному account_id или не существуют")

            # Удаляем записи
            self.collection.delete(ids=record_ids)
            logger.info(f"Записи {record_ids} успешно удалены для account_id={account_id}")

        except Exception as e:
            logger.error(f"Ошибка при удалении записей: {str(e)}")
            raise

    def update_entry(self, account_id: str, record_id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Обновляет запись в коллекции ChromaDB по ID.

        Args:
            account_id (str): ID пользователя для проверки.
            record_id (str): ID записи для обновления.
            text (str): Новый текст воспоминания.
            metadata (Optional[Dict[str, Any]]): Новые метаданные (опционально).

        Raises:
            ValueError: Если запись не найдена или не принадлежит account_id.
            Exception: Для других ошибок.
        """
        logger.info(f"Обновление записи: record_id={record_id}, account_id={account_id}, text={text[:50]}...")
        try:
            # Проверяем, существует ли запись
            results = self.collection.get(
                ids=[record_id],
                include=["metadatas"],
                where={"account_id": account_id}
            )
            if not results["ids"]:
                logger.warning(f"Запись {record_id} не найдена для account_id={account_id}")
                raise ValueError(f"Запись {record_id} не найдена для account_id={account_id}")

            # Удаляем старую запись
            self.collection.delete(ids=[record_id])

            # Генерируем новый эмбеддинг
            embedding = EmbeddingManager.get_embedding(text).tolist()

            # Обновляем метаданные, сохраняя account_id
            updated_metadata = metadata or {}
            if "account_id" not in updated_metadata:
                updated_metadata["account_id"] = account_id
                logger.debug(f"Добавлен account_id={account_id} в метаданные")

            # Добавляем обновлённую запись
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                metadatas=[updated_metadata],
                ids=[record_id]
            )
            logger.info(f"Запись {record_id} успешно обновлена для account_id={account_id}")

        except Exception as e:
            logger.error(f"Ошибка при обновлении записи: {str(e)}")
            raise






