import asyncio

from core.analysis.preanalysis.message_analyzer import MessageAnalyzer
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline

async def memories():
    pipeline = MessageAnalyzer(user_message="надеюсь что я ничего не поломала 🙈🙈🙈", account_id="test_user")
    results = await pipeline._load_relevant_memories()
    return results


if __name__ == "__main__":
    asyncio.run(memories())
