import asyncio

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api import assistant
from infrastructure.embeddings.runner import preload_models
from infrastructure.pushi.reminders_sender import check_and_send_reminders_pushi
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline

logger = setup_logger("assistant")
preload_models() #Инициализация локальных моделей

app = FastAPI(
    title="Victor AI",
    version="0.1.0",
    description="Что мы будем делать сегодня?"
)

# Разрешаем доступ с телефона
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем всем
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем эндпоинты
app.include_router(assistant.router)

@app.get("/")
def root():
    return {"status": "ok"}

@app.on_event("startup")
async def start_reminder_checker():
    async def worker():
        while True:
            try:
                check_and_send_reminders_pushi()
            except Exception as e:
                logger.error("[reminders] worker error:", e)
            await asyncio.sleep(60)
    asyncio.create_task(worker())








