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
            last_msg = session_context.last_update
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


async def _validate_scheduled_push(
    creator_id: str,
    task_text: str,
    session_context,
) -> tuple[str, str]:
    """
    Victor пересматривает запланированный пуш в контексте последнего диалога.

    Returns:
        (action, text) — action is "send" / "rewrite" / "cancel";
        text is final message to send (original or rewritten).
    """
    import re
    from pathlib import Path
    import yaml

    from core.autonomy.workbench import Workbench
    from core.autonomy.workbench_rotator import _build_system_prompt
    from infrastructure.database.models import DialogueHistory
    from infrastructure.llm.client import LLMClient
    from sqlalchemy import desc

    prompts_path = Path(__file__).parent / "core" / "autonomy" / "prompts" / "post_analysis.yaml"
    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts = yaml.safe_load(f)

    template = prompts.get("validate_scheduled_push")
    if not template:
        logger.warning("[scheduled_push] Промпт validate_scheduled_push не найден, отправляем как есть")
        return "send", task_text

    from datetime import datetime

    dialogue_lines = session_context.get_last_n_pairs(6)
    dialogue_history = "\n".join(dialogue_lines) if dialogue_lines else "(нет сообщений)"

    workbench = Workbench(account_id=creator_id)
    workbench_notes = workbench.read_full().strip() or "(пусто)"

    last_update = session_context.last_update
    last_message_time = last_update.strftime("%Y-%m-%d %H:%M") if last_update else "неизвестно"
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M")

    normalized_task_text = task_text.strip()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    same_text_warning = ""

    db = Database.get_instance()
    with db.get_session() as session:
        same_text_sent_today = (
            session.query(DialogueHistory)
            .filter(
                DialogueHistory.account_id == creator_id,
                DialogueHistory.role == "assistant",
                DialogueHistory.message_category.in_(["reflection", "scheduled"]),
                DialogueHistory.created_at >= today_start,
                DialogueHistory.text == normalized_task_text,
            )
            .order_by(desc(DialogueHistory.created_at))
            .first()
        )
        if same_text_sent_today:
            sent_time = same_text_sent_today.created_at.strftime("%H:%M") if same_text_sent_today.created_at else "сегодня"
            same_text_warning = (
                "Ты уже отправлял сегодня точно такое же сообщение "
                f"(в {sent_time}). Возможно, ты хочешь сказать это другими словами."
            )

    context_prompt = template.format(
        last_message_time=last_message_time,
        current_time=current_time,
        dialogue_history=dialogue_history,
        workbench_notes=workbench_notes,
        planned_message=task_text,
        same_text_warning=same_text_warning or "Точно такого же сообщения сегодня ещё не было.",
    )

    system_prompt = _build_system_prompt(
        session_context,
        "Ты решаешь, отправлять ли запланированное сообщение.",
    )

    try:
        llm = LLMClient(account_id=creator_id, mode="foundation")
        response = await llm.get_response(
            system_prompt=system_prompt,
            context_prompt=context_prompt,
            temperature=0.3,
            max_tokens=500,
        )

        if not response or not response.strip():
            return "send", task_text

        resp = response.strip()

        if resp.startswith("ОТМЕНИТЬ"):
            logger.info(f"[scheduled_push] LLM решил ОТМЕНИТЬ пуш: {task_text[:60]}...")
            return "cancel", ""

        rewrite_match = re.match(r"^ПЕРЕПИСАТЬ:\s*(.+)$", resp, re.DOTALL)
        if rewrite_match:
            new_text = rewrite_match.group(1).strip()
            logger.info(f"[scheduled_push] LLM ПЕРЕПИСАЛ пуш: {new_text[:60]}...")
            return "rewrite", new_text

        if resp.startswith("ОТПРАВИТЬ"):
            return "send", task_text

        logger.warning(f"[scheduled_push] Неизвестный ответ LLM: {resp[:100]}, отправляем как есть")
        return "send", task_text

    except Exception as e:
        logger.warning(f"[scheduled_push] Ошибка LLM-валидации: {e}, отправляем как есть")
        return "send", task_text


async def _scheduled_push_worker() -> None:
    """
    Отдельный воркер: каждую минуту проверяет VictorTask с trigger_type=TIME
    и отправляет пуши, если время наступило. Перед отправкой — LLM-валидация.
    """
    from datetime import datetime, timedelta
    from infrastructure.database.repositories.task_repository import TaskRepository
    from infrastructure.database.models import VictorTask, VictorTaskTrigger, VictorTaskStatus
    from infrastructure.pushi.push_notifications import send_pushy_notification
    from infrastructure.firebase.tokens import get_user_tokens

    logger.info("[scheduled_push] Старт воркера отложенных пушей")

    while True:
        try:
            creator_id = settings.creator_account_id
            if not creator_id:
                await asyncio.sleep(300)
                continue

            # Фаза 1: собираем созревшие задачи и СРАЗУ помечаем done (внутри DB-сессии)
            due_tasks: list[tuple[int, str]] = []
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
                        repo.mark_done(task.id)
                        due_tasks.append((task.id, task.text))

            # Фаза 2: обработка задач (LLM-валидация, отправка) — вне DB-сессии
            for task_id, task_text in due_tasks:
                try:
                    context_store = SessionContextStore(storage_path=settings.SESSION_CONTEXT_DIR)
                    db2 = Database.get_instance()
                    with db2.get_session() as session2:
                        try:
                            session_context = context_store.load(creator_id, session2)
                        except Exception as e:
                            logger.warning(f"[scheduled_push] Не удалось загрузить session_context: {e}")
                            session_context = None

                    if session_context:
                        action, final_text = await _validate_scheduled_push(
                            creator_id, task_text, session_context,
                        )
                    else:
                        action, final_text = "send", task_text

                    if action == "cancel":
                        logger.info(f"[scheduled_push] Задача #{task_id} ОТМЕНЕНА Victor'ом")
                        continue

                    normalized_final_text = final_text.strip()
                    today_prefix = now.strftime("%Y-%m-%d")
                    with db2.get_session() as session_pending:
                        duplicate_pending_today = (
                            session_pending.query(VictorTask)
                            .filter(
                                VictorTask.account_id == creator_id,
                                VictorTask.status == VictorTaskStatus.PENDING,
                                VictorTask.trigger_type == VictorTaskTrigger.TIME,
                                VictorTask.text == normalized_final_text,
                            )
                            .all()
                        )
                        duplicate_pending_today = [
                            t for t in duplicate_pending_today
                            if t.trigger_value and t.trigger_value.strip().startswith(today_prefix)
                        ]

                    if duplicate_pending_today:
                        logger.info(
                            f"[scheduled_push] Задача #{task_id} пропущена: "
                            f"такой же текст уже запланирован на сегодня "
                            f"(task #{duplicate_pending_today[0].id})"
                        )
                        continue

                    # Не дублируем одинаковый scheduled-текст в history за сегодня.
                    with db2.get_session() as session3:
                        try:
                            from infrastructure.database import DialogueRepository
                            from infrastructure.database.models import DialogueHistory
                            from sqlalchemy import desc

                            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                            existing_scheduled_today = (
                                session3.query(DialogueHistory)
                                .filter(
                                    DialogueHistory.account_id == creator_id,
                                    DialogueHistory.role == "assistant",
                                    DialogueHistory.message_category == "scheduled",
                                    DialogueHistory.created_at >= today_start,
                                    DialogueHistory.text == normalized_final_text,
                                )
                                .order_by(desc(DialogueHistory.created_at))
                                .first()
                            )

                            if existing_scheduled_today:
                                logger.info(
                                    f"[scheduled_push] Повтор в dialogue_history пропущен для задачи #{task_id}: "
                                    f"такой же scheduled-текст уже сохранён сегодня "
                                    f"(message #{existing_scheduled_today.id})"
                                )
                            else:
                                dialogue_repo = DialogueRepository(session3)
                                dialogue_repo.save_message(
                                    account_id=creator_id,
                                    role="assistant",
                                    text=final_text,
                                    message_category="scheduled",
                                )
                        except Exception as e:
                            logger.warning(f"[scheduled_push] Ошибка записи в dialogue_history: {e}")

                    # Сохраняем в session_context
                    try:
                        from core.autonomy.reflection_engine import _save_push_to_session_context
                        _save_push_to_session_context(creator_id, final_text)
                    except Exception as e:
                        logger.warning(f"[scheduled_push] Ошибка записи в session_context: {e}")

                    tokens = get_user_tokens(creator_id)
                    if tokens:
                        for token in tokens:
                            try:
                                send_pushy_notification(
                                    token=token,
                                    title="Victor",
                                    body=final_text[:200],
                                    data={
                                        "type": "scheduled_message",
                                        "account_id": creator_id,
                                        "text": final_text,
                                        "task_id": str(task_id),
                                    },
                                )
                            except Exception as e:
                                logger.warning(f"[scheduled_push] Ошибка отправки пуша: {e}")

                        logger.info(f"[scheduled_push] Задача #{task_id} отправлена ({len(tokens)} токенов)")
                    else:
                        logger.warning(f"[scheduled_push] Нет токенов для {creator_id}")

                except Exception:
                    logger.exception(f"[scheduled_push] Ошибка обработки задачи #{task_id}")

        except Exception:
            logger.exception("[scheduled_push] Ошибка в воркере отложенных пушей")

        await asyncio.sleep(60)





