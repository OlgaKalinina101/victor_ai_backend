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

import time
import gc
import torch
from transformers import pipeline, AutoTokenizer
from typing import Dict, List

from infrastructure.logging.logger import setup_logger

logger = setup_logger("emotion_recognizer")


class EmotionRecognizer:
    """
    Класс-обёртка для детекции эмоций.
    Поддерживает мультиязычные модели.
    """

    _emotion_recognizer = None
    _tokenizer = None
    _current_model = None
    _predict_calls = 0

    # Если используется CUDA, можно периодически чистить кэш, чтобы избежать “ползущего” роста памяти.
    # 0 = не чистить автоматически (кроме смены модели).
    GPU_CACHE_CLEAR_EVERY_N = 0

    MODELS = {
        "ru": "seara/rubert-base-cased-russian-emotion-detection-cedr",  # лёгкая русскоязычная (~80МБ)
        "en": "j-hartmann/emotion-english-distilroberta-base"  # англ (~300МБ)
    }

    @classmethod
    def _cleanup_old_model(cls) -> None:
        """Очищает старую модель из памяти перед загрузкой новой (особенно важно при смене языка)."""
        if cls._emotion_recognizer is None and cls._tokenizer is None and cls._current_model is None:
            return

        logger.info("Очистка старой модели EmotionRecognizer из памяти...")

        try:
            if cls._emotion_recognizer is not None:
                del cls._emotion_recognizer
            if cls._tokenizer is not None:
                del cls._tokenizer
        finally:
            cls._emotion_recognizer = None
            cls._tokenizer = None
            cls._current_model = None

        # Сборка мусора помогает быстрее освободить большие графы объектов HF/PyTorch.
        gc.collect()

        # Очищаем GPU кэш если используется CUDA
        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except Exception as e:
                logger.warning(f"Не удалось очистить GPU cache: {e}")

    @classmethod
    def get_emotion_recognizer(cls, lang: str = "ru"):
        """
        Загружает пайплайн детекции эмоций и токенизатор для нужного языка.
        """
        start_time = time.time()
        model_name = cls.MODELS.get(lang, cls.MODELS["ru"])

        if cls._emotion_recognizer is None or cls._current_model != model_name:
            # FIX: при смене языка/модели обязательно чистим старую модель,
            # иначе она остаётся в памяти и “утечка” накапливается.
            if cls._current_model is not None and cls._current_model != model_name:
                cls._cleanup_old_model()

            logger.info(f"Загрузка emotion recognizer [{lang}]...")
            cls._emotion_recognizer = pipeline(
                "text-classification",
                model=model_name,
                device=0 if torch.cuda.is_available() else -1,
                top_k=None
            )
            cls._tokenizer = AutoTokenizer.from_pretrained(model_name)
            cls._current_model = model_name
            logger.info(
                f"Emotion recognizer [{lang}] загружен за {time.time() - start_time:.2f} секунд"
            )

        return cls._emotion_recognizer

    @classmethod
    def truncate_text(cls, text: str, lang: str = "ru", max_length: int = 512) -> str:
        """
        Универсальная обрезка текста для текущей модели.

        Args:
            text (str): Исходный текст.
            lang (str): "ru" или "en".
            max_length (int): Максимальное число токенов.

        Returns:
            str: Усечённый текст.
        """
        model_name = cls.MODELS.get(lang, cls.MODELS["ru"])
        if cls._tokenizer is None or cls._current_model != model_name:
            cls._tokenizer = AutoTokenizer.from_pretrained(model_name)

        # FIX: не создаём torch tensor'ы (return_tensors="pt"), чтобы не накапливать память (особенно на GPU).
        tokens = cls._tokenizer.encode(text, truncation=True, max_length=max_length)
        decoded = cls._tokenizer.decode(tokens, skip_special_tokens=True)
        del tokens
        return decoded

    @classmethod
    def predict(cls, text: str, lang: str = "ru") -> List[Dict[str, float]]:
        """
        Делает предсказание эмоций, автоматически обрезая текст.
        """
        recognizer = cls.get_emotion_recognizer(lang)
        clean_text = cls.truncate_text(text, lang)

        # На всякий случай: избегаем лишних графов/градиентов (для HF pipeline это обычно уже так, но безопасно).
        try:
            with torch.inference_mode():
                result = recognizer(clean_text)
        except Exception:
            result = recognizer(clean_text)

        # Приводим к единому формату
        if isinstance(result, list) and isinstance(result[0], list):
            result = result[0]

        formatted = [
            {"label": r["label"].lower(), "score": float(r["score"])}
            for r in result
        ]

        # Опционально: периодическая очистка GPU cache (если включено).
        cls._predict_calls += 1
        if cls.GPU_CACHE_CLEAR_EVERY_N and cls._predict_calls % int(cls.GPU_CACHE_CLEAR_EVERY_N) == 0:
            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except Exception as e:
                    logger.warning(f"Не удалось очистить GPU cache: {e}")

        return formatted

    @classmethod
    def cleanup(cls) -> None:
        """Публичный метод для полной очистки памяти EmotionRecognizer."""
        cls._cleanup_old_model()
