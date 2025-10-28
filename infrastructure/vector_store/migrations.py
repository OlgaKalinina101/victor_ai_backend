from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline


def migrate_account_id(pipeline: PersonaEmbeddingPipeline, default_account_id: str) -> None:
    """Добавляет account_id в метаданные существующих записей."""
    try:
        #Получаем все записи (без фильтра по account_id)
        results = pipeline.collection.get(include=["documents", "metadatas", "embeddings"])
        if not results["ids"]:
            print("Коллекция пуста, миграция не требуется")
            return
        for doc_id, doc, metadata, embedding in zip(
            results["ids"], results["documents"], results["metadatas"], results["embeddings"]
            ):
            if "account_id" not in metadata:
            #Удаляем старую запись
                pipeline.collection.delete(ids=[doc_id])
                #Обновляем метаданные
                metadata["account_id"] = default_account_id
                #Добавляем запись заново
                pipeline.collection.add(
                documents=[doc],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[doc_id]
                )
                print(f"Обновлена запись {doc_id} с account_id={default_account_id}")
    except Exception as e:
        print(f"Ошибка при миграции: {str(e)}")

if __name__ == "__main__":
    pipeline = PersonaEmbeddingPipeline()
    migrate_account_id(pipeline, default_account_id="test_user")

