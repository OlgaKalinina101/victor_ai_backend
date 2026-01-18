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

from datetime import datetime
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Form, UploadFile, File, Depends
from fastapi.encoders import jsonable_encoder
from starlette.responses import Response, StreamingResponse

from api.dependencies.runtime import get_context_store, get_db, get_logger
from api.helpers import (
    clean_message_text,
    safe_json_loads,
    add_user_message_to_context,
    update_victor_state_from_emoji
)
from api.schemas.chat import (
    UpdateHistoryRequest,
    UpdateHistoryResponse,
    ChatHistoryResponse,
    SearchResult,
    UpdateEmojiRequest
)
from api.schemas.common import Message
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database import Database, DialogueRepository
from infrastructure.logging.logger import setup_logger
from settings import settings
import emoji as emoji_lib

from tools.communication.communication_tool import run_communication

logger = setup_logger("chat")

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/get_history", response_model=ChatHistoryResponse)
async def get_chat_history(
        account_id: str = Query(..., min_length=1),
        limit: int = Query(25, ge=1, le=100),
        before_id: Optional[int] = Query(None, description="ID сообщения, до которого загружать (для скролла вверх)"),
        db: Database = Depends(get_db)
):
    """
    Получает историю диалога из базы данных с поддержкой пагинации.

    Простой и надежный алгоритм пагинации:
    - Все сообщения загружаются из PostgreSQL (таблица dialogue_history)
    - При первом запросе (before_id=None) возвращаются последние N сообщений
    - При последующих запросах (before_id указан) загружаются более старые сообщения
    - Поддерживает бесконечный скролл вверх по истории

    Особенности:
    - Порядок в ответе: от новых к старым (для удобства отображения в чате)
    - Автоматическая очистка текста от системных префиксов
    - oldest_id и newest_id корректно указывают на границы выборки

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        limit: Количество сообщений для загрузки за один запрос.
               Минимум 1, максимум 100. По умолчанию 25.
        before_id: ID сообщения, до которого загружать историю.
                   Используется для пагинации при скролле вверх.
                   Если None - загружаются последние сообщения.

    Returns:
        ChatHistoryResponse содержащий:
        - messages: Список сообщений, отсортированных от новых к старым
        - has_more: Флаг наличия дополнительных (более старых) сообщений
        - oldest_id: ID самого старого сообщения в текущей выборке
        - newest_id: ID самого нового сообщения в текущей выборке

    Raises:
        HTTPException 500: При ошибках базы данных.

    Examples:
        GET /get_history?account_id=user123&limit=20
        GET /get_history?account_id=user123&limit=20&before_id=150
    """
    logger.info(f"[CHAT_HISTORY] account_id={account_id}, limit={limit}, before_id={before_id}")

    db_session = db.get_session()

    try:
        # Создаем репозиторий
        dialogue_repo = DialogueRepository(db_session)
        
        # Загружаем сообщения из БД
        db_messages, has_more = dialogue_repo.get_paginated(
            account_id=account_id, limit=limit, before_id=before_id
        )

        logger.info(f"[DB] Загружено {len(db_messages)} записей, before_id={before_id}, has_more={has_more}")

        if not db_messages:
            # Нет сообщений - возвращаем пустой ответ
            logger.info("[CHAT_HISTORY] История пуста")
            empty_response = ChatHistoryResponse(
                messages=[],
                has_more=False,
                oldest_id=None,
                newest_id=None
            )
            empty_payload = jsonable_encoder(empty_response)
            empty_body = json.dumps(empty_payload, ensure_ascii=False).encode("utf-8")
            logger.info(f"[CHAT_HISTORY_BYTES] bytes={len(empty_body)} (empty)")
            return Response(content=empty_body, media_type="application/json")

        # Конвертируем DialogueHistory -> Message
        messages = []
        for record in db_messages:
            # Очищаем текст от префиксов (если они есть в legacy данных)
            clean_text = clean_message_text(record.text, record.role)

            messages.append(Message(
                text=clean_text,
                is_user=(record.role == "user"),
                timestamp=int(record.created_at.timestamp()) if record.created_at else int(
                    datetime.now().timestamp()),
                id=record.id,
                vision_context=record.vision_context,
                emoji=record.emoji,
                swiped_message_id=getattr(record, "swiped_message_id", None),
                swiped_message_text=getattr(record, "swiped_message_text", None),
            ))

        # Реверсируем для отображения (от новых к старым)
        messages.reverse()

        # Определяем границы для пагинации
        # db_messages после reverse содержит [старые -> новые]
        # значит db_messages[0] = самое старое, db_messages[-1] = самое новое
        oldest_id = db_messages[0].id
        newest_id = db_messages[-1].id

        logger.info(
            f"[RESPONSE] messages_count={len(messages)}, oldest_id={oldest_id}, newest_id={newest_id}, has_more={has_more}"
        )

        # Отладочный лог: показываем первые и последние сообщения
        if len(messages) > 0:
            logger.debug(f"[FIRST_MSG] id={messages[0].id}, is_user={messages[0].is_user}, text={messages[0].text[:50]}...")
        if len(messages) > 1:
            logger.debug(f"[LAST_MSG] id={messages[-1].id}, is_user={messages[-1].is_user}, text={messages[-1].text[:50]}...")

        response_model = ChatHistoryResponse(
            messages=messages,
            has_more=has_more,
            oldest_id=oldest_id,
            newest_id=newest_id
        )
        payload = jsonable_encoder(response_model)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        logger.info(
            f"[CHAT_HISTORY_BYTES] bytes={len(body)} messages={len(messages)} has_more={has_more}"
        )
        return Response(content=body, media_type="application/json")

    except Exception as e:
        logger.error(f"[CHAT_HISTORY_ERROR] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db_session.close()


@router.put("/update_history", response_model=UpdateHistoryResponse)
async def update_chat_history(
        request: UpdateHistoryRequest,
        account_id: str = Query(..., min_length=1),
        db: Database = Depends(get_db)
):
    """
    Обновляет историю чата после редактирования сообщения.

    Используется когда пользователь редактирует сообщение в истории диалога.
    При вызове выполняется:
    1. Заменяет message_history в SessionContext (YAML) на последние 6 сообщений
    2. Находит отредактированное сообщение в БД и обновляет его текст

    Алгоритм работы:
    - С фронта приходят последние 6 сообщений (3 пары user-assistant)
    - Эти 6 сообщений полностью заменяют message_history в SessionContext
    - В БД обновляется только текст конкретного отредактированного сообщения
    - Остальные метаданные (mood, category и т.д.) остаются без изменений

    Args:
        request: UpdateHistoryRequest содержащий:
            - messages: Последние 6 сообщений для SessionContext
            - edited_message_id: ID отредактированного сообщения
            - edited_message_text: Новый текст сообщения
        account_id: Идентификатор пользователя (обязательный параметр).

    Returns:
        UpdateHistoryResponse:
        {
            "success": True/False,
            "message": "Описательное сообщение о результате",
            "session_updated": обновлён ли SessionContext,
            "db_updated": обновлено ли сообщение в БД
        }

    Raises:
        HTTPException 400: Если запрос содержит невалидные данные.
        HTTPException 404: Если отредактированное сообщение не найдено.
        HTTPException 500: При ошибках записи в БД или файловую систему.

    Examples:
        PUT /update_history?account_id=user123
        {
            "messages": [
                {"id": 1, "text": "...", "is_user": true, ...},
                ...
            ],
            "edited_message_id": 4,
            "edited_message_text": "NEW EDITED TEXT"
        }
    """
    logger.info(f"[UPDATE_HISTORY] account_id={account_id}, edited_message_id={request.edited_message_id}, messages_count={len(request.messages)}")
    
    db_session = db.get_session()
    
    session_updated = False
    db_updated = False
    
    try:
        # ========== 1. Обновление SessionContext (YAML) ==========
        session_context_store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
        session_context = session_context_store.load(
            account_id=account_id,
            db_session=db_session
        )

        # Сортируем сообщения по ID (от старых к новым)
        sorted_messages = sorted(request.messages, key=lambda msg: msg.id if msg.id else 0)
        
        # Конвертируем 6 последних Message в строковый формат "user: текст" / "assistant: текст"
        new_message_history = []
        for msg in sorted_messages:
            prefix = "user: " if msg.is_user else "assistant: "
            new_message_history.append(f"{prefix}{msg.text}")

        # ПОЛНОСТЬЮ заменяем message_history на новые 6 сообщений
        session_context.message_history = new_message_history

        # Сохраняем в YAML
        session_context_store.save(session_context)
        session_updated = True
        logger.info(f"[UPDATE_HISTORY] SessionContext обновлён: {len(new_message_history)} сообщений (отсортировано по ID)")

        # ========== 2. Обновление текста в БД ==========
        dialogue_repo = DialogueRepository(db_session)
        
        # Находим и обновляем только отредактированное сообщение
        updated_message = dialogue_repo.update_message_text(
            account_id=account_id,
            message_id=request.edited_message_id,
            new_text=request.edited_message_text
        )
        
        if not updated_message:
            logger.warning(f"[UPDATE_HISTORY] Сообщение id={request.edited_message_id} не найдено в БД для account_id={account_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Сообщение с ID {request.edited_message_id} не найдено или не принадлежит пользователю"
            )
        
        db_updated = True
        logger.info(f"[UPDATE_HISTORY] Сообщение id={request.edited_message_id} обновлено в БД")

        return UpdateHistoryResponse(
            success=True,
            message=f"История обновлена: SessionContext ({len(new_message_history)} сообщений), БД (сообщение {request.edited_message_id})",
            session_updated=session_updated,
            db_updated=db_updated
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPDATE_HISTORY] Ошибка обновления истории: {e}", exc_info=True)
        db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db_session.close()


@router.get("/history/search", response_model=SearchResult)
async def search_chat_history(
    account_id: str = Query(..., min_length=1),
    query: str = Query(..., min_length=1, description="Поисковый запрос"),
    offset: int = Query(0, ge=0, description="Смещение для навигации по результатам (0 = первый результат)"),
    context_before: int = Query(10, ge=0, le=50, description="Количество сообщений до найденного"),
    context_after: int = Query(10, ge=0, le=50, description="Количество сообщений после найденного"),
    db: Database = Depends(get_db)
):
    """
    Поиск сообщений в истории диалога с возвращением контекста вокруг найденных совпадений.

    Реализует полнотекстовый поиск по истории сообщений пользователя с поддержкой:
    - Пагинации по результатам поиска
    - Загрузки контекста вокруг найденного сообщения
    - Навигации "вперед/назад" по результатам

    Алгоритм работы:
    1. Поиск сообщений, содержащих запрос (регистронезависимый)
    2. Сортировка результатов от новых к старым
    3. Загрузка N сообщений до и после найденного для контекста
    4. Возврат структурированного результата с мета-информацией

    Args:
        account_id: Идентификатор пользователя (обязательный параметр).
        query: Поисковый запрос (минимум 1 символ).
        offset: Смещение по результатам поиска.
                0 = самый новый результат, 1 = следующий по старшинству.
        context_before: Сколько сообщений загрузить ДО найденного сообщения.
                       От 0 до 50, по умолчанию 10.
        context_after: Сколько сообщений загрузить ПОСЛЕ найденного сообщения.
                      От 0 до 50, по умолчанию 10.

    Returns:
        SearchResult содержащий:
        - messages: Контекст вокруг найденного сообщения (включая само сообщение)
        - matched_message_id: ID найденного сообщения
        - total_matches: Общее количество найденных совпадений
        - current_match_index: Индекс текущего результата (равен offset)
        - has_next: Есть ли следующий результат
        - has_prev: Есть ли предыдущий результат

    Raises:
        HTTPException 400: Если query пустой или параметры вне допустимых диапазонов.
        HTTPException 500: При ошибках поиска в базе данных.

    Examples:
        # Первый результат поиска
        GET /history/search?query=привет&offset=0&context_before=5&context_after=5

        # Второй результат поиска
        GET /history/search?query=привет&offset=1&context_before=10&context_after=10
    """
    db_session = db.get_session()

    try:
        # Создаем репозиторий
        dialogue_repo = DialogueRepository(db_session)
        
        # Ищем сообщения
        results, total_count = dialogue_repo.search(
            account_id=account_id, query_text=query, offset=offset
        )

        if not results:
            # Ничего не найдено
            return SearchResult(
                messages=[],
                matched_message_id=None,
                total_matches=total_count,
                current_match_index=offset,
                has_next=False,
                has_prev=False
            )

        # Берем найденное сообщение
        matched_message = results[0]

        # Получаем контекст вокруг
        context_messages = dialogue_repo.get_context(
            account_id=account_id,
            message_id=matched_message.id,
            context_before=context_before,
            context_after=context_after
        )

        # Конвертируем в Message
        messages = []
        for record in context_messages:
            # Очищаем текст от префиксов (как в /chat/history)
            clean_text = clean_message_text(record.text, record.role)

            messages.append(Message(
                text=clean_text,
                is_user=(record.role == "user"),
                timestamp=int(record.created_at.timestamp()) if record.created_at else int(datetime.now().timestamp()),
                id=record.id,
                vision_context=record.vision_context,
                emoji=record.emoji,
                swiped_message_id=getattr(record, "swiped_message_id", None),
                swiped_message_text=getattr(record, "swiped_message_text", None),
            ))

        logger.info(
            f"[SEARCH] query='{query}', matched_id={matched_message.id}, context_size={len(messages)}, total_matches={total_count}")

        return SearchResult(
            messages=messages,
            matched_message_id=matched_message.id,
            total_matches=total_count,
            current_match_index=offset,
            has_next=(offset + 1) < total_count,
            has_prev=offset > 0
        )

    except Exception as e:
        logger.error(f"[search] Ошибка поиска в истории: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db_session.close()


@router.patch("/update_emoji")
async def update_message_emoji(request: UpdateEmojiRequest, db: Database = Depends(get_db)):
    """
    Обновляет emoji для конкретного сообщения в истории диалога.
    
    Позволяет пользователю установить, изменить или удалить emoji-реакцию
    на любое сообщение в истории диалога. Используется для маркировки
    важных или эмоционально значимых сообщений.
    
    Особенности:
    - Проверяет, что сообщение принадлежит указанному пользователю
    - Поддерживает установку нового emoji
    - Поддерживает изменение существующего emoji
    - Поддерживает удаление emoji (если передать None или пустую строку)
    
    Args:
        request: UpdateEmojiRequest содержащий:
            - account_id: Идентификатор пользователя
            - backend_id: ID сообщения в базе данных
            - emoji: Emoji для установки (None или пустая строка для удаления)
    
    Returns:
        Объект с результатом операции:
        {
            "success": True/False,
            "message": "Описательное сообщение о результате",
            "message_id": ID обновленного сообщения,
            "emoji": Установленное emoji
        }
    
    Raises:
        HTTPException 404: Если сообщение не найдено или не принадлежит пользователю.
        HTTPException 500: При ошибках базы данных.
    
    Examples:
        PATCH /update_emoji
        {
            "account_id": "user123",
            "backend_id": 42,
            "emoji": "❤️"
        }
    """
    logger.info(f"[UPDATE_EMOJI] account_id={request.account_id}, backend_id={request.backend_id}, emoji={request.emoji}")
    
    db_session = db.get_session()
    
    try:
        dialogue_repo = DialogueRepository(db_session)
        
        # Нормализуем emoji: пустая строка → None
        emoji_value = request.emoji if request.emoji else None
        
        # Обновляем emoji с проверкой прав доступа
        updated_message = dialogue_repo.update_emoji(
            account_id=request.account_id,
            message_id=request.backend_id,
            emoji=emoji_value
        )
        
        if not updated_message:
            logger.warning(f"[UPDATE_EMOJI] Сообщение не найдено: account_id={request.account_id}, backend_id={request.backend_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Сообщение с ID {request.backend_id} не найдено или не принадлежит пользователю"
            )
        
        logger.info(f"[UPDATE_EMOJI] Успешно обновлено: message_id={updated_message.id}, emoji='{updated_message.emoji}'")
        
        # Обновляем victor_mood и victor_intensity если emoji установлен
        if emoji_value:
            try:
                # Проверяем что это действительно emoji
                if emoji_lib.is_emoji(emoji_value):
                    # Загружаем session_context
                    context_store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
                    session_context = context_store.load(request.account_id, db_session)
                    
                    if session_context:
                        # Обновляем состояние Victor'а на основе emoji
                        update_victor_state_from_emoji(session_context, emoji_value)
                        
                        # Сохраняем обновленный контекст
                        context_store.save(session_context, db_session)
                        logger.info(f"[UPDATE_EMOJI] Victor state обновлен на основе emoji '{emoji_value}'")
                    else:
                        logger.warning(f"[UPDATE_EMOJI] Session context не найден для account_id={request.account_id}")
                else:
                    logger.debug(f"[UPDATE_EMOJI] '{emoji_value}' не является валидным emoji")
            except Exception as e:
                # Не прерываем выполнение если обновление Victor state упало
                logger.error(f"[UPDATE_EMOJI] Ошибка обновления Victor state: {e}", exc_info=True)
        
        return {
            "success": True,
            "message": f"Emoji успешно {'удалено' if not emoji_value else 'обновлено'}",
            "message_id": updated_message.id,
            "emoji": updated_message.emoji
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPDATE_EMOJI] Ошибка обновления emoji: {e}", exc_info=True)
        db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db_session.close()

@router.post("/communicate_stream")
async def communicate_stream(
    account_id: str = Form(...),
    text: str = Form(...),
    function_call: str = Form(...),

    geo: Optional[str] = Form(None),           # JSON-строка
    extra_context: Optional[str] = Form(None), # если нужно

    image: Optional[UploadFile] = File(None),
    mime_type: str = Form("image/png"),

    db=Depends(get_db),
    context_store=Depends(get_context_store),
    logger=Depends(get_logger),
):
    """
    Принимает пользовательское сообщение (и опционально изображение) и возвращает потоковый ответ
    демо-версии веб-чата.

    Эндпоинт предназначен для web demo: принимает `account_id`, текст и заранее определённый `function_call`,
    после чего запускает `run_communication(...)` и стримит чанки ответа по мере генерации.

    Формат запроса: multipart/form-data
    - account_id (str): идентификатор аккаунта
    - text (str): текст сообщения пользователя
    - function_call (str): имя/ключ маршрута или действия, которое нужно выполнить
    - geo (str, optional): JSON-строка с геоданными/контекстом (будет распарсена в объект)
    - extra_context (str, optional): дополнительный контекст для пайплайна
    - image (file, optional): изображение (png/jpeg/webp)
    - mime_type (str, optional): MIME-тип изображения (по умолчанию "image/png")

    Ответ:
    - StreamingResponse: поток текста, который приходит чанками по мере работы пайплайна.

    Ошибки:
    - 400: некорректный JSON в `geo`
    - 413: изображение слишком большое (если включён лимит)
    - 415: неподдерживаемый `mime_type`
    """
    geo_obj = safe_json_loads(geo)

    # ✅ как в дефолтном роуте — добавляем user msg перед default handler
    add_user_message_to_context(account_id, text, db, context_store, logger)

    image_bytes: Optional[bytes] = None
    resolved_mime = mime_type

    if image is not None:
        resolved_mime = image.content_type or resolved_mime
        image_bytes = await image.read()

        logger.info(f"[WEB_DEMO][VISION] image={len(image_bytes)} bytes mime={resolved_mime}")

        if resolved_mime not in {"image/png", "image/jpeg", "image/webp"}:
            raise HTTPException(status_code=415, detail=f"Unsupported mime_type: {resolved_mime}")

        if image_bytes and len(image_bytes) > 8 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image too large (max 8MB)")
    else:
        logger.info("[WEB_DEMO][VISION] image not provided")

    async def gen():
        async for chunk in run_communication(
            account_id=account_id,
            text=text,
            function_call=function_call,
            geo=geo_obj,
            extra_context=extra_context,
            llm_client=None,  # 🔥 как в default_route: не передаем, если пайплайн сам разрулит
            db=db,
            session_context_store=context_store,
            embedding_pipeline=None,
            image_bytes=image_bytes,
            mime_type=resolved_mime,
        ):
            yield chunk

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")