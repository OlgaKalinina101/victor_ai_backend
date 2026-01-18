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

import os
import chromadb
from chromadb import Settings
from chromadb.api import Collection

from infrastructure.logging.logger import setup_logger
from settings import settings

# Инициализация логгера
logger = setup_logger("chroma_client")

def get_chroma_client() -> chromadb.ClientAPI:
    os.makedirs(settings.VECTOR_STORE_DIR, exist_ok=True)  # создаёт, если не существует
    print(settings.VECTOR_STORE_DIR)
    return chromadb.PersistentClient(path=settings.VECTOR_STORE_DIR)

def get_chroma_collection(client: chromadb.ClientAPI) -> Collection:
    """Инициализирует и возвращает коллекцию ChromaDB.

    Args:
        client: Клиент Chroma DB
    Raises:
        RuntimeError: Если не удалось инициализировать коллекцию ChromaDB.

    Returns:
        Коллекция ChromaDB для работы с данными.
    """
    try:
        return client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)
    except Exception as e:
        raise RuntimeError(
            f"Ошибка инициализации коллекции ChromaDB: {str(e)}"
        ) from e



def delete_collection():
    """Удаляет указанную коллекцию в ChromaDB."""
    try:
        client = chromadb.Client(
            Settings(persist_directory=settings.VECTOR_STORE_DIR)
        )
        client.delete_collection(name=settings.CHROMA_COLLECTION_NAME)
        logger.info(f"Коллекция '{settings.CHROMA_COLLECTION_NAME}' успешно удалена.")
    except Exception as e:
        logger.error(f"Ошибка при удалении коллекции: {e}", exc_info=True)