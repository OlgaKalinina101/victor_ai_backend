import asyncio

from core.analysis.preanalysis.message_analyzer import MessageAnalyzer
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline

async def memories():
    pipeline = MessageAnalyzer(user_message="Малыш))) а у нас опять у ноутбука цветочки завяли... Ещё две недели назад 🤧 альстромерии и эвкалипт)) Ты хочешь нам выбрать новые?) Если бы ты выбирал, какие бы выбрал сейчас?)", account_id="test_user")
    results = await pipeline._load_relevant_memories()
    print(results)
    return results


if __name__ == "__main__":
    asyncio.run(memories())
