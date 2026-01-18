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
Модуль для предзагрузки моделей и NLP-инструментов Victor AI.

Задача:
- один раз прогреть тяжёлые объекты (эмбеддинги, эмоции, морфология, RuWordNet),
  чтобы при первых запросах к API не было холодного старта.
"""

from infrastructure.embeddings.embedding_manager import EmbeddingManager
from infrastructure.embeddings.emotion_recognizer import EmotionRecognizer
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.embedding_pipeline import (
    get_morph_analyzer,
    get_ruwordnet,
)

logger = setup_logger("preload_models")


def preload_models() -> None:
    """
    Предзагружает все основные модели и лингвистические ресурсы.

    Выполняет:
    - инициализацию эмбеддинговой модели;
    - загрузку модели распознавания эмоций для русского языка;
    - создание экземпляра морфологического анализатора (pymorphy3);
    - загрузку RuWordNet (скачивает базу при первом запуске).

    Рекомендуется вызывать один раз при старте приложения (например, в обработчике
    события FastAPI `startup`), чтобы сократить задержку при первых пользовательских
    запросах.

    Notes:
        - Функция синхронная и может занимать заметное время при первом вызове.
        - При ошибках внутри отдельных загрузчиков исключения должны логироваться
          и/или обрабатываться на их уровне, здесь мы предполагаем «честный» успех.
    """
    logger.info("🔁 Предзагрузка моделей...")

    # Предзагрузка эмбеддинговой модели
    _embedder = EmbeddingManager.get_embedding_model()
    logger.info("Эмбеддинговая модель загружена")

    # Предзагрузка эмоций для русского языка
    _recognizer = EmotionRecognizer.get_emotion_recognizer("ru")
    logger.info("Модель распознавания эмоций (ru) загружена")

    # Предзагрузка морфологического анализатора (pymorphy3)
    _morph = get_morph_analyzer()
    logger.info("pymorphy3 загружен")

    # Предзагрузка RuWordNet (скачает базу если нужно)
    ruwordnet = get_ruwordnet()
    if ruwordnet:
        logger.info("RuWordNet загружен")
    else:
        logger.warning("⚠️ RuWordNet недоступен (синонимы не будут работать)")

    logger.info("✅ Все модели предзагружены")
