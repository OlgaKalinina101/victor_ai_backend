import chromadb
from chromadb.api.models.Collection import Collection

from settings import settings


def inspect_collection(path: str, collection_name: str):
    """
    Подключается к ChromaDB по указанному пути и выводит содержимое коллекции.

    Args:
        path: Путь к директории ChromaDB
        collection_name: Имя коллекции
    """
    # Подключаемся к ChromaDB
    client = chromadb.PersistentClient(path=path)

    # Получаем коллекцию
    collection = client.get_collection(name=collection_name)

    # Выводим общую информацию
    print(f"📦 Коллекция: {collection_name}")
    print(f"📊 Количество записей: {collection.count()}")
    print("\n" + "=" * 80 + "\n")

    # Получаем все данные
    results = collection.get(
        include=["documents", "metadatas", "embeddings"]
    )

    # Выводим каждую запись
    for i, (doc_id, doc, metadata) in enumerate(zip(
            results["ids"],
            results["documents"],
            results["metadatas"]
    ), 1):
        print(f"🔹 Запись #{i}")
        print(f"ID: {doc_id}")
        print(f"Текст: {doc}")
        print(f"Метаданные: {metadata}")
        print("-" * 80)


# Использование:
if __name__ == "__main__":
    # Укажи свой путь и имя коллекции
    VECTOR_STORE_PATH = "C:/Users/Alien/PycharmProjects/Victor_AI_Core/infrastructure/vector_store"  # или settings.VECTOR_STORE_DIR
    COLLECTION_NAME = settings.CHROMA_COLLECTION_NAME  # или settings.CHROMA_COLLECTION_NAME

    inspect_collection(VECTOR_STORE_PATH, COLLECTION_NAME)

