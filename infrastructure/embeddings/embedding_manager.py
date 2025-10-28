# Victor AI Project
# Copyright (c) 2025 Olga Kalinina
# All rights reserved.

import time

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import ClassVar
from collections import OrderedDict

from infrastructure.logging.logger import setup_logger
from settings import settings

logger = setup_logger("embeddings_manager")

class EmbeddingManager:
    _embedding_model = None
    _embedding_cache: ClassVar[OrderedDict[str, np.ndarray]] = OrderedDict()

    MAX_CACHE_SIZE = 1000  # регулировать по состоянию

    @classmethod
    def get_embedding_model(cls) -> SentenceTransformer:
        start_time = time.time()
        if cls._embedding_model is None:
            logger.info("Загрузка SentenceTransformer...")
            cls._embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
            logger.info(f"SentenceTransformer загружен за {time.time() - start_time:.2f} секунд")
        return cls._embedding_model

    @classmethod
    def get_embedding(cls, text: str) -> np.ndarray:
        normalized_text = text.strip().lower()
        if normalized_text not in cls._embedding_cache:
            model = cls.get_embedding_model()
            embedding = model.encode(normalized_text, show_progress_bar=False)
            embedding = np.asarray(embedding)

            # Добавляем в кэш
            if len(cls._embedding_cache) >= cls.MAX_CACHE_SIZE:
                cls._embedding_cache.popitem(last=False)  # удаляем самый старый
            cls._embedding_cache[normalized_text] = embedding

        return cls._embedding_cache[normalized_text]

    @classmethod
    def calculate_similarity(cls, text1, text2) -> float:
        start_time = time.time()
        emb1 = EmbeddingManager.get_embedding(text1)
        emb2 = EmbeddingManager.get_embedding(text2)
        similarity = cosine_similarity([emb1], [emb2])[0][0]
        logger.debug(f"[DEBUG] Cosine similarity вычислен за {time.time() - start_time:.2f} секунд")
        return similarity

