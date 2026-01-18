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

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import pymorphy3
from ruwordnet import RuWordNet

from infrastructure.embeddings.embedding_manager import EmbeddingManager
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.client import get_chroma_client, get_chroma_collection
from models.user_enums import UserMoodLevel, Mood

logger = setup_logger("memory_builder")

# Инициализируем морфологический анализатор (singleton)
_morph_analyzer = None
_ruwordnet = None

def get_morph_analyzer():
    """Ленивая инициализация морфологического анализатора."""
    global _morph_analyzer
    if _morph_analyzer is None:
        _morph_analyzer = pymorphy3.MorphAnalyzer()
    return _morph_analyzer

def get_ruwordnet():
    """Ленивая инициализация RuWordNet с автоматическим скачиванием базы."""
    global _ruwordnet
    if _ruwordnet is None:
        try:
            _ruwordnet = RuWordNet()
            logger.info("[RUWORDNET] Инициализирован успешно")
        except Exception as e:
            # Если база не найдена — пробуем скачать
            if "was not found" in str(e) or "ruwordnet.db" in str(e):
                logger.info("[RUWORDNET] База не найдена, скачиваю...")
                try:
                    import subprocess
                    result = subprocess.run(
                        ["ruwordnet", "download"], 
                        capture_output=True, 
                        text=True,
                        timeout=300  # 5 минут на скачивание
                    )
                    if result.returncode == 0:
                        logger.info("[RUWORDNET] База скачана успешно, инициализирую...")
                        _ruwordnet = RuWordNet()
                        logger.info("[RUWORDNET] Инициализирован успешно")
                    else:
                        logger.warning(f"[RUWORDNET] Не удалось скачать базу: {result.stderr}")
                        _ruwordnet = False
                except Exception as download_error:
                    logger.warning(f"[RUWORDNET] Ошибка при скачивании: {download_error}")
                    _ruwordnet = False
            else:
                logger.warning(f"[RUWORDNET] Не удалось инициализировать: {e}")
                _ruwordnet = False
    return _ruwordnet if _ruwordnet else None

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

    def _split_to_sentences(self, message: str) -> list[str]:
        """Разбивает сообщение на значимые предложения для multi-query поиска."""
        import re
        # Разбиваем по точкам, восклицательным, вопросительным знакам
        sentences = re.split(r'[.!?]+', message)
        # Фильтруем короткие фрагменты (меньше 25 символов обычно не несут смысла)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 25]
        return sentences

    def _normalize_word(self, word: str) -> str:
        """Приводит слово к нормальной форме (лемме) с помощью pymorphy2."""
        try:
            morph = get_morph_analyzer()
            parsed = morph.parse(word)[0]
            return parsed.normal_form
        except Exception:
            return word

    def _get_synonyms(self, word: str) -> set[str]:
        """Получает синонимы и гипонимы из RuWordNet."""
        wn = get_ruwordnet()
        if not wn:
            return set()
        
        synonyms = set()
        
        try:
            # Ищем все синсеты для слова
            synsets = wn.get_synsets(word)
            
            for synset in synsets[:3]:  # Ограничиваем количество значений (для скорости)
                # Берём синонимы из synset (слова с тем же значением)
                for sense in synset.senses:
                    lemma = sense.name.lower()
                    if lemma != word:  # Не добавляем само слово
                        synonyms.add(lemma)
                
                # Добавляем гипонимы (более узкие понятия)
                # Например: цветок → роза, тюльпан
                for hypo_synset in synset.hyponyms[:5]:  # Ограничиваем
                    for sense in hypo_synset.senses[:3]:
                        synonyms.add(sense.name.lower())
        
        except Exception as e:
            logger.debug(f"[SYNONYMS] Не найдено для '{word}': {e}")
        
        if synonyms:
            logger.debug(f"[SYNONYMS] '{word}' → {synonyms}")
        
        return synonyms

    def _extract_keywords(self, message: str, expand_synonyms: bool = True) -> set[str]:
        """Извлекает ключевые слова из сообщения, нормализует и расширяет синонимами."""
        # Убираем эмодзи, пунктуацию и приводим к нижнему регистру
        clean = re.sub(r'[^\w\s]', ' ', message.lower())
        words = clean.split()
        
        # Стоп-слова (частые слова без смысла)
        stop_words = {
            'а', 'и', 'в', 'на', 'с', 'у', 'к', 'о', 'из', 'за', 'по', 'от', 'до',
            'что', 'как', 'это', 'так', 'ты', 'я', 'мы', 'он', 'она', 'они', 'вы',
            'не', 'да', 'но', 'же', 'ли', 'бы', 'то', 'ещё', 'еще', 'уже', 'вот',
            'все', 'всё', 'мне', 'меня', 'тебе', 'тебя', 'нам', 'нас', 'мой', 'твой',
            'если', 'когда', 'чтобы', 'потому', 'очень', 'только', 'просто', 'прям',
            'какие', 'какой', 'какая', 'какое', 'который', 'которая', 'которое',
            'хочешь', 'хочу', 'могу', 'можешь', 'буду', 'будет', 'есть', 'был', 'была',
            'опять', 'снова', 'теперь', 'сейчас', 'тоже', 'также', 'быть', 'этот'
        }
        
        # Фильтруем и нормализуем: только слова длиннее 3 символов, не стоп-слова
        keywords = set()
        base_lemmas = []  # Сохраняем для расширения синонимами
        
        for w in words:
            if len(w) > 3 and w not in stop_words:
                lemma = self._normalize_word(w)
                if lemma not in stop_words:
                    keywords.add(lemma)
                    base_lemmas.append(lemma)
        
        # Расширяем синонимами (только для основных слов, не для самих синонимов)
        if expand_synonyms:
            for lemma in base_lemmas:
                synonyms = self._get_synonyms(lemma)
                keywords.update(synonyms)
        
        logger.debug(f"[KEYWORDS] Извлечено {len(keywords)} ключевых слов (с синонимами): {list(keywords)[:10]}...")
        return keywords

    def _extract_lemmas_from_text(self, text: str) -> set[str]:
        """Извлекает леммы из текста для сравнения."""
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        words = clean.split()
        lemmas = set()
        for w in words:
            if len(w) > 3:
                lemmas.add(self._normalize_word(w))
        return lemmas

    def _apply_keyword_boost(self, results: dict, keywords: set[str], boost_factor: float = 0.25) -> dict:
        """
        Применяет keyword boost к результатам.
        1. Совпадение лемм (pymorphy2) — базовый буст
        2. Точное совпадение слова в тексте — дополнительный буст
        """
        for result in results.values():
            text_lower = result["text"].lower()
            text_lemmas = self._extract_lemmas_from_text(result["text"])
            
            # 1. Считаем совпадения лемм
            matched_lemmas = keywords & text_lemmas
            lemma_matches = len(matched_lemmas)
            
            original_score = result["score"]
            
            if lemma_matches > 0:
                # Уменьшаем score за совпадения лемм
                result["score"] = max(0.01, result["score"] - (lemma_matches * boost_factor))
                logger.debug(f"[LEMMA-BOOST] '{result['text'][:50]}...' lemmas={matched_lemmas}, score: {original_score:.3f} → {result['score']:.3f}")
            
            # 2. Дополнительный буст для точных совпадений (слово в исходной форме)
            exact_matches = []
            for kw in keywords:
                if kw in text_lower:
                    exact_matches.append(kw)
                    result["score"] = max(0.01, result["score"] - boost_factor)
            
            if exact_matches:
                logger.debug(f"[EXACT-MATCH] exact={exact_matches} в '{result['text'][:50]}...' score → {result['score']:.3f}")
        
        return results

    def _apply_recency_boost(self, results: dict) -> dict:
        """
        Применяет временной штраф к результатам.
        - impressive=4 НЕ получает штраф (важные факты всегда актуальны)
        - Остальные: очень старые воспоминания (>60 дней) получают небольшой штраф
        
        Примечание: совсем свежие уже отфильтрованы через days_cutoff в query_similar.
        """
        now = datetime.now()
        
        for result in results.values():
            # impressive=4 не гасим по времени — это важные факты
            impressive = result.get("metadata", {}).get("impressive")
            try:
                impressive = int(impressive) if impressive is not None else 0
            except (ValueError, TypeError):
                impressive = 0
                
            if impressive >= 4:
                # Не применяем recency penalty к очень важным воспоминаниям
                continue
            
            last_used_str = result.get("metadata", {}).get("last_used")
            created_at_str = result.get("metadata", {}).get("created_at")
            
            # Используем last_used или created_at
            date_str = last_used_str or created_at_str
            if not date_str:
                continue
                
            try:
                memory_date = datetime.fromisoformat(date_str.replace('+00:00', '').replace('Z', ''))
                memory_date = memory_date.replace(tzinfo=None)
                days_ago = (now - memory_date).days
                
                # Штраф для очень старых воспоминаний (>60 дней)
                if days_ago > 60:
                    penalty = min(0.1, (days_ago - 60) * 0.001)  # макс +0.1 к distance
                    result["score"] += penalty
                    logger.debug(f"[RECENCY-PENALTY] '{result['text'][:40]}...' days_ago={days_ago}, penalty=+{penalty:.3f}")
                    
            except (ValueError, TypeError) as e:
                logger.debug(f"[RECENCY] Не удалось распарсить дату: {date_str}, ошибка: {e}")
                continue
        
        return results

    def _apply_impressive_boost(self, results: dict) -> dict:
        """
        Применяет буст на основе важности (impressive) воспоминания.
        - impressive=4 → большой буст (-0.12)
        - impressive=3 → маленький буст (-0.05)
        - impressive=2,1 → нет буста
        """
        for result in results.values():
            impressive = result.get("metadata", {}).get("impressive")
            
            if impressive is None:
                continue
            
            # Приводим к int (может быть float из ChromaDB)
            try:
                impressive = int(impressive)
            except (ValueError, TypeError):
                continue
            
            original_score = result["score"]
            
            if impressive >= 4:
                # Большой буст для очень важных воспоминаний
                result["score"] = max(0.01, original_score - 0.12)
                logger.debug(f"[IMPRESSIVE-BOOST] '{result['text'][:40]}...' impressive={impressive}, score: {original_score:.3f} → {result['score']:.3f}")
            elif impressive == 3:
                # Маленький буст для важных воспоминаний
                result["score"] = max(0.01, original_score - 0.05)
                logger.debug(f"[IMPRESSIVE-BOOST] '{result['text'][:40]}...' impressive={impressive}, score: {original_score:.3f} → {result['score']:.3f}")
            # impressive <= 2 — нет буста
        
        return results

    def query_similar_multi(
            self,
            account_id: str,
            message: str,
            top_k: int = 5,
            per_query_k: int = 3,
            days_cutoff: int = 2,
    ) -> list[dict]:
        """
        Multi-query поиск: разбивает сообщение на предложения и ищет по каждому,
        затем дедуплицирует и возвращает лучшие результаты с keyword boost.

        Args:
            account_id: ID пользователя
            message: Полное сообщение пользователя
            top_k: Сколько результатов вернуть в итоге
            per_query_k: Сколько результатов искать на каждый запрос
            days_cutoff: Фильтр по давности использования

        Returns:
            Список уникальных релевантных memories, отсортированных по score
        """
        # Извлекаем ключевые слова для boost
        keywords = self._extract_keywords(message)
        logger.debug(f"[MULTI-QUERY] Ключевые слова для boost: {keywords}")

        # Формируем список запросов
        queries = [message]  # всегда включаем полное сообщение

        # Добавляем отдельные предложения (если сообщение достаточно длинное)
        if len(message) > 80:
            sentences = self._split_to_sentences(message)
            queries.extend(sentences[:4])  # максимум 4 предложения

        logger.debug(f"[MULTI-QUERY] Сформировано {len(queries)} запросов для поиска")

        all_results = {}

        for query in queries:
            results = self.query_similar(
                account_id=account_id,
                query=query,
                top_k=per_query_k,
                days_cutoff=days_cutoff
            )
            for r in results:
                # Храним лучший (меньший) score для каждого документа
                if r["id"] not in all_results or r["score"] < all_results[r["id"]]["score"]:
                    all_results[r["id"]] = r

        # Применяем keyword boost (лемматизация через pymorphy2)
        all_results = self._apply_keyword_boost(all_results, keywords)
        
        # Применяем impressive boost (важные воспоминания выше)
        all_results = self._apply_impressive_boost(all_results)
        
        # Применяем recency boost (штраф для очень старых воспоминаний)
        all_results = self._apply_recency_boost(all_results)

        # Сортируем по score (меньше = лучше для distance) и возвращаем top_k
        sorted_results = sorted(all_results.values(), key=lambda x: x["score"])
        logger.info(f"[MULTI-QUERY] Найдено {len(all_results)} уникальных результатов, возвращаем {min(top_k, len(sorted_results))}")
        return sorted_results[:top_k]

    def query_similar(
            self,
            account_id: str,
            query: str,
            top_k: int = 3,
            days_cutoff: int = 2,
    ) -> list[dict]:
        """
        Находит top_k ближайших по смыслу записей к запросу,
        исключая те, что использовались менее чем N дней назад.
        """
        embedding = EmbeddingManager.get_embedding(query).tolist()
        results = self.collection.query(
            query_embeddings=[embedding], 
            n_results=top_k * 2, 
            where={"account_id": account_id},
            include=["documents", "metadatas", "distances", "embeddings"]  # embeddings для детерминированности
        )
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

    def update_memory_usage_by_id(self, doc_id: str):
        """Обновляет frequency и last_used по ID документа (без поиска)."""
        try:
            # 1. Получаем данные по ID
            results = self.collection.get(
                ids=[doc_id],
                include=["embeddings", "documents", "metadatas"]
            )
            
            if not results or not results['ids']:
                logger.warning(f"[SKIP] Документ с ID {doc_id} не найден")
                return

            old_metadata = results.get('metadatas', [None])[0]
            old_embedding = results.get('embeddings', [None])[0]
            document = results.get('documents', [None])[0]

            if any(x is None for x in (old_metadata, old_embedding, document)):
                logger.warning(f"[SKIP] Документ с ID {doc_id} не содержит всех нужных данных.")
                return

            # 2. Удаляем старую запись
            self.collection.delete(ids=[doc_id])

            # 3. Обновляем metadata
            updated_metadata = old_metadata.copy()
            updated_metadata['frequency'] = int(old_metadata.get('frequency', 0)) + 1
            updated_metadata['last_used'] = datetime.now().isoformat()

            # 4. Добавляем заново
            self.collection.add(
                documents=[document],
                embeddings=[old_embedding],
                metadatas=[updated_metadata],
                ids=[doc_id]
            )

            logger.info(f"[OK] Обновлено по ID: {doc_id}")

        except Exception as e:
            logger.exception(f"[ERROR] Ошибка при обновлении документа по ID {doc_id}: {e}")

    def update_memory_usage(self, account_id: str, target_doc: str):
        """Обновляет frequency и last_used через поиск по эмбеддингу (fallback)."""

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

            logger.info(f"[OK] Обновлено по эмбеддингу: {doc_id}")

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
            Exception: Для других ошибок при работе с ChromaDB.
        """
        try:
            # Получаем все данные
            results = self.collection.get(include=["documents", "metadatas", "embeddings"],
                                          where={"account_id": account_id})
            # Важно: "пусто" — это нормальный сценарий (у пользователя ещё нет воспоминаний).
            # Не считаем это ошибкой, чтобы API мог вернуть 200 + [] вместо 500.
            ids = results.get("ids") or []
            if not ids:
                return []

            # Формируем список записей
            records = []
            for doc_id, doc, metadata in zip(ids, results.get("documents") or [], results.get("metadatas") or []):
                record = {
                    "id": doc_id,
                    "text": doc,
                    "metadata": metadata
                }
                records.append(record)

            return records

        except Exception as e:
            # Не маскируем первичную причину, но добавляем контекст.
            raise Exception(f"Ошибка при получении содержимого коллекции: {str(e)}") from e

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






