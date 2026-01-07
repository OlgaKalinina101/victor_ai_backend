# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

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
    # Migration script - требует явный account_id
    import sys
    default_account_id = sys.argv[1] if len(sys.argv) > 1 else "test_user"
    pipeline = PersonaEmbeddingPipeline()
    migrate_account_id(pipeline, default_account_id=default_account_id)

