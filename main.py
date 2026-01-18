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
Главная точка входа FastAPI-приложения Victor AI.

Здесь:
- создаётся экземпляр FastAPI;
- настраивается CORS для мобильного клиента;
- подключаются все роутеры API;
- запускаются фоновые задачи (предзагрузка моделей, проверка напоминаний).
"""

import asyncio

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api import (
    achievements,
    alarms,
    assistant,
    care_bank,
    chat,
    chat_meta,
    journal,
    places,
    reminders,
    stats,
    tracks,
    walk_sessions,
    auth,
)
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database import Database
from infrastructure.embeddings.runner import preload_models
from infrastructure.logging.logger import setup_logger
from infrastructure.pushi.reminders_sender import check_and_send_reminders_pushi
from settings import settings

logger = setup_logger("assistant")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Используем singleton Database
    app.state.logger = setup_logger("web_demo_chat")
    app.state.db = Database.get_instance()
    app.state.context_store = SessionContextStore(storage_path=settings.SESSION_CONTEXT_DIR)

    app.state.logger.info("[startup] Запуск Victor AI backend")

    # Предзагрузка моделей (делаем ДО принятия запросов)
    try:
        app.state.logger.info("[startup] Предзагрузка локальных моделей...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, preload_models)
        app.state.logger.info("[startup] Локальные модели успешно предзагружены")
    except Exception:
        # Не падаем целиком, но логируем стек
        app.state.logger.exception("[startup] Ошибка при предзагрузке моделей")

    # Старт фонового воркера напоминаний
    app.state.reminders_task = asyncio.create_task(_reminders_worker())

    yield

    # Shutdown: останавливаем фоновые задачи
    reminders_task = getattr(app.state, "reminders_task", None)
    if reminders_task:
        reminders_task.cancel()
        try:
            await reminders_task
        except asyncio.CancelledError:
            pass
    
    # Cleanup: dispose database connection pool
    if hasattr(app.state, "db"):
        app.state.db.dispose()
        app.state.logger.info("[shutdown] Database connection pool disposed")


app = FastAPI(
    title="Victor AI",
    version="0.1.0",
    description="Что мы будем делать сегодня?",
    lifespan=lifespan
)

# ---------- CORS ----------

# Разрешаем доступ с телефона (и вообще отовсюду, пока всё локальное)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Можно сузить до конкретных доменов, есть прод
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Routers ----------

# Подключаем эндпоинты
app.include_router(assistant.router)
app.include_router(alarms.router)
app.include_router(chat.router)
app.include_router(reminders.router)
app.include_router(places.router)
app.include_router(stats.router)
app.include_router(journal.router)
app.include_router(achievements.router)
app.include_router(walk_sessions.router)
app.include_router(tracks.router)
app.include_router(chat_meta.router)
app.include_router(care_bank.router)
app.include_router(auth.router)


@app.get("/")
def root():
    """
    Простейший health-check эндпоинт.

    Используется клиентом и мониторингом для проверки того, что
    приложение запущено и отвечает корректно.

    Returns:
        dict: Краткий статус приложения. Поле "status" равно "ok",
        если сервер поднят и обрабатывает запросы.
    """
    return {"status": "ok"}


async def _reminders_worker() -> None:
    """
    Фоновый воркер для отправки напоминаний.

    Каждую минуту:
    - вызывает check_and_send_reminders_pushi(), который находит
      просроченные/активные напоминания и отправляет пуши;
    - логирует все ошибки, но не останавливает цикл.
    """
    logger.info("[reminders] Старт фонового воркера напоминаний")
    while True:
        try:
            check_and_send_reminders_pushi()
        except Exception:
            logger.exception("[reminders] Ошибка в воркере отправки напоминаний")
        await asyncio.sleep(60)









