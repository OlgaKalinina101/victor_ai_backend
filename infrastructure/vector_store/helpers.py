from typing import List, Dict, Any
from datetime import datetime

from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline


class MemoryProcessor:
    """Класс для обработки воспоминаний и формирования биографии пользователя."""

    def __init__(
            self,
            embedding_pipeline: Any = None,
            k_4: int = 2,
            k_3: int = 2,
            k_2: int = 3
    ):
        """
        Инициализирует процессор воспоминаний.

        :param embedding_pipeline: Объект для получения данных воспоминаний (по умолчанию PersonaEmbeddingPipeline).
        """
        self.embedding_pipeline = embedding_pipeline or PersonaEmbeddingPipeline()
        self.k_4 = k_4
        self.k_3 = k_3
        self.k_2 = k_2

    def _parse_created_at(self, memory: Dict) -> datetime:
        """
        Парсит дату создания из словаря воспоминания.

        :param memory: Словарь с данными воспоминания.
        :return: Объект datetime или минимальная дата при ошибке.
        """
        created_at_str = memory.get('metadata', {}).get('created_at', '1970-01-01T00:00:00+00:00')
        try:
            return datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except ValueError:
            return datetime.min

    def filter_memories_by_impressive(
            self,
            memories: List[Dict]
    ) -> List[Dict]:
        """
        Фильтрует воспоминания по значению impressive.

        :param memories: Список словарей с воспоминаниями.
        :return: Отфильтрованный список словарей.
        """
        # Фильтруем по impressive
        impressive_4 = [m for m in memories if m.get('metadata', {}).get('impressive') == 4]
        impressive_3 = [m for m in memories if m.get('metadata', {}).get('impressive') == 3]
        impressive_2 = [m for m in memories if m.get('metadata', {}).get('impressive') == 2]

        # Сортируем по created_at (от новых к старым)
        impressive_4 = sorted(impressive_4, key=self._parse_created_at, reverse=True)
        impressive_3 = sorted(impressive_3, key=self._parse_created_at, reverse=True)
        impressive_2 = sorted(impressive_2, key=self._parse_created_at, reverse=True)

        # Возвращаем первые k_4, k_3, k_2 записей
        return impressive_4[:self.k_4] + impressive_3[:self.k_3] + impressive_2[:self.k_2]

    def get_memory(self, account_id: str, user_message: str = None) -> str:
        """
        Получает выжимку из биографии пользователя.

        :param account_id: account_id пользователя.
        :param user_message: Сообщение пользователя (опционально).
        :return: Выжимка из биографии в виде строки.
        """
        # Получаем воспоминания
        collection_contents = self.embedding_pipeline.get_collection_contents(account_id)

        # Фильтруем воспоминания
        filtered_memories = self.filter_memories_by_impressive(collection_contents)

        if not filtered_memories:
            return "Нет доступных воспоминаний для формирования биографии."

        # Извлекаем текст воспоминаний
        memory_texts = [memory['text'] for memory in filtered_memories]

        biography = "\n".join(f"- {text}" for text in memory_texts)
        return biography

if __name__ == "__main__":
    processor = MemoryProcessor()
    result = processor.get_memory(account_id="test_user")
    print(result)