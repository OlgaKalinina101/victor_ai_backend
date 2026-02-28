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
from datetime import datetime

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

    # Старт фонового воркера рефлексии Victor (автономия)
    app.state.reflection_task = asyncio.create_task(_reflection_worker())

    # Старт воркера отложенных пушей Victor (VictorTask TIME)
    app.state.scheduled_push_task = asyncio.create_task(_scheduled_push_worker())

    yield

    # Shutdown: останавливаем фоновые задачи
    for task_name in ("reminders_task", "reflection_task", "scheduled_push_task"):
        task = getattr(app.state, task_name, None)
        if task:
            task.cancel()
            try:
                await task
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


# ---------- Reflection (Autonomy) ----------

_last_reflection_time: datetime | None = None


async def _reflection_worker() -> None:
    """
    Фоновый воркер рефлексии Victor (автономия).

    Каждые 60 секунд проверяет условия запуска:
      1. Есть creator_account_id в settings.
      2. С последнего сообщения прошло >= REFLECTION_COOLDOWN_HOURS (4ч).
      3. С последней рефлексии прошло >= REFLECTION_MIN_INTERVAL_HOURS (12ч).
    Если все условия выполнены — запускает ReflectionEngine.
    """
    from datetime import datetime, timedelta, timezone
    from core.autonomy.reflection_engine import ReflectionEngine
    from infrastructure.context_store.session_context_schema import to_serializable

    global _last_reflection_time

    logger.info("[reflection] Старт фонового воркера рефлексии")

    while True:
        try:
            creator_id = settings.creator_account_id
            if not creator_id:
                await asyncio.sleep(300)
                continue

            db = Database.get_instance()
            context_store = SessionContextStore(storage_path=settings.SESSION_CONTEXT_DIR)

            db_session = db.get_session()
            try:
                session_context = context_store.load(creator_id, db_session)
            finally:
                db_session.close()

            # Проверка cooldown: прошло ли достаточно времени с последнего сообщения
            last_msg = session_context.last_assistant_message
            if last_msg:
                if last_msg.tzinfo is None:
                    since_last = datetime.now() - last_msg
                else:
                    since_last = datetime.now(timezone.utc) - last_msg
                hours_since = since_last.total_seconds() / 3600
            else:
                hours_since = float("inf")

            cooldown_ok = hours_since >= settings.REFLECTION_COOLDOWN_HOURS

            # Проверка интервала: прошло ли достаточно времени с последней рефлексии
            if _last_reflection_time:
                since_reflection = (datetime.now() - _last_reflection_time).total_seconds() / 3600
                interval_ok = since_reflection >= settings.REFLECTION_MIN_INTERVAL_HOURS
            else:
                interval_ok = True

            if cooldown_ok and interval_ok:
                logger.info(
                    f"[reflection] Условия выполнены: "
                    f"{hours_since:.1f}ч с последнего сообщения, запускаем рефлексию"
                )

                # Определяем модель из ChatMeta (как в роутере)
                from core.router.message_router import MessageTypeManager
                mgr = MessageTypeManager(db=db, context_store=context_store)
                llm_client = mgr._create_llm_client(creator_id)

                engine = ReflectionEngine(
                    account_id=creator_id,
                    llm_client=llm_client,
                )
                await engine.run(session_context)
                _last_reflection_time = datetime.now()

                logger.info("[reflection] Рефлексия завершена")
            else:
                logger.debug(
                    f"[reflection] Пропуск: cooldown={'OK' if cooldown_ok else 'WAIT'}, "
                    f"interval={'OK' if interval_ok else 'WAIT'}"
                )

        except Exception:
            logger.exception("[reflection] Ошибка в воркере рефлексии")

        await asyncio.sleep(60)


# ---------- Scheduled Push Worker (VictorTask TIME) ----------


async def _scheduled_push_worker() -> None:
    """
    Отдельный воркер: каждую минуту проверяет VictorTask с trigger_type=TIME
    и отправляет пуши, если время наступило.
    """
    from datetime import datetime, timedelta
    from infrastructure.database.repositories.task_repository import TaskRepository
    from infrastructure.database.models import VictorTaskTrigger, VictorTaskStatus
    from infrastructure.pushi.push_notifications import send_pushy_notification
    from infrastructure.firebase.tokens import get_user_tokens

    logger.info("[scheduled_push] Старт воркера отложенных пушей")

    while True:
        try:
            creator_id = settings.creator_account_id
            if not creator_id:
                await asyncio.sleep(300)
                continue

            db = Database.get_instance()
            with db.get_session() as session:
                repo = TaskRepository(session)
                tasks = repo.get_pending_by_trigger(creator_id, VictorTaskTrigger.TIME)

                now = datetime.now()
                for task in tasks:
                    if not task.trigger_value:
                        continue

                    try:
                        scheduled_time = datetime.strptime(task.trigger_value.strip(), "%Y-%m-%d %H:%M")
                    except ValueError:
                        logger.warning(f"[scheduled_push] Невалидное время в задаче #{task.id}: {task.trigger_value}")
                        continue

                    if scheduled_time <= now:
                        # Сохраняем в dialogue_history
                        try:
                            from infrastructure.database import DialogueRepository
                            dialogue_repo = DialogueRepository(session)
                            dialogue_repo.save_message(
                                account_id=creator_id,
                                role="assistant",
                                text=task.text,
                                message_category="scheduled",
                            )
                        except Exception as e:
                            logger.warning(f"[scheduled_push] Ошибка записи в dialogue_history: {e}")

                        tokens = get_user_tokens(creator_id)
                        if tokens:
                            for token in tokens:
                                try:
                                    send_pushy_notification(
                                        token=token,
                                        title="Victor",
                                        body=task.text[:200],
                                        data={
                                            "type": "scheduled_message",
                                            "account_id": creator_id,
                                            "text": task.text,
                                            "task_id": str(task.id),
                                        },
                                    )
                                except Exception as e:
                                    logger.warning(f"[scheduled_push] Ошибка отправки пуша: {e}")

                            logger.info(f"[scheduled_push] Задача #{task.id} отправлена ({len(tokens)} токенов)")
                        else:
                            logger.warning(f"[scheduled_push] Нет токенов для {creator_id}")

                        repo.mark_done(task.id)

        except Exception:
            logger.exception("[scheduled_push] Ошибка в воркере отложенных пушей")

        await asyncio.sleep(60)





