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

from fastapi import APIRouter, HTTPException, Depends

from api.assistant import logger
from api.dependencies.runtime import get_db
from api.schemas.chat_meta import ChatMetaUpdateRequest, ChatMetaBase
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.repositories.chat_meta_repository import ChatMetaRepository
from infrastructure.database.session import Database
from settings import settings

router = APIRouter(prefix="/chat_meta", tags=["ChatMeta"])

@router.get("/{account_id}", response_model=ChatMetaBase)
def get_authorisation(account_id: str, db: Database = Depends(get_db)):
    """
    Возвращает модель chat_meta по идентификатору аккаунта.

    Args:
        account_id: Идентификатор пользователя (path-параметр, обязательный).
                    Обычно UUID или уникальная строка, присвоенная при регистрации.

    Returns:
        ChatMetaBase: модель chat_meta

    Raises:
        HTTPException 400: Если account_id не соответствует формату.
        HTTPException 404: Если пользователь с таким account_id не найден.
        HTTPException 500: При внутренней ошибке базы данных или системы.

    Notes:
        - Эндпоинт используется при каждом запуске чата для восстановления сессии
        - При первом обращении пользователя автоматически создаётся запись с дефолтными значениями
        - Все даты возвращаются в формате ISO 8601
    """
    with db.get_session() as session:
        try:
            repo = ChatMetaRepository(session)
            user_data = repo.get_by_account_id(account_id)
            
            if not user_data:
                logger.warning(f"[auth] ChatMeta not found for account_id={account_id}")
                raise HTTPException(status_code=404, detail="ChatMeta not found")

            # Самовосстановление: если у пользователя нет TrackUserDescription — создаём дефолты из test_user
            try:
                repo.ensure_track_descriptions_seeded(account_id=account_id)
            except Exception as seed_exc:
                logger.warning(f"[auth] Не удалось seed TrackUserDescription для {account_id}: {seed_exc}")

            logger.info(f"[auth] Авторизация успешно получена для {account_id}")
            return user_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[auth] Ошибка при запросе ChatMeta ({account_id}): {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")


@router.patch("/{account_id}", response_model=ChatMetaBase)
def update_chat_meta(account_id: str, update_data: ChatMetaUpdateRequest, db: Database = Depends(get_db)):
    """
    Частично обновляет модель chat_meta.

    Поддерживает PATCH-семантику: обновляет только те поля, которые явно
    переданы в запросе. Автоматически обновляет timestamp последнего изменения.
    Используется для изменения настроек пользователя, модели ИИ, промптов
    и других персональных параметров системы.

    Args:
        account_id: Идентификатор пользователя (path-параметр, обязательный).
        update_data: ChatMetaUpdateRequest - объект с полями для обновления.

    Returns:
        ChatMetaBase: Обновлённый объект метаданных чата со всеми полями,
                      включая автоматически проставленный last_updated.

    Raises:
        HTTPException 404: Если chat_meta для такого account_id не найдена.

    Notes:
        - Поддерживает частичное обновление: можно отправить только изменяемые поля
        - Поле last_updated всегда обновляется автоматически
        - Валидация значений происходит на уровне Pydantic-модели
        - Изменения применяются немедленно и влияют на следующие запросы пользователя
    """
    with db.get_session() as session:
        try:
            repo = ChatMetaRepository(session)
            
            # Применяем только переданные поля (exclude_unset=True)
            update_fields = update_data.dict(exclude_unset=True)
            chat_meta = repo.update_partial(account_id, **update_fields)

            if not chat_meta:
                raise HTTPException(status_code=404, detail="ChatMeta not found")

            # Если меняли модель — синхронизируем SessionContext YAML, чтобы не "залипало" на старой.
            if "model" in update_fields:
                try:
                    context_store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
                    ctx = context_store.load(account_id=account_id, db_session=session)
                    ctx.model = chat_meta.model
                    # НЕ считаем смену модели "активностью" — не обновляем last_update (staleness).
                    context_store.save(ctx, update_timestamp=False)
                    logger.info(f"[chat_meta] SessionContext.model синхронизирован: {chat_meta.model}")
                except Exception as e:
                    logger.warning(f"[chat_meta] Не удалось синхронизировать SessionContext.model: {e}")

            logger.info(f"[chat_meta] Обновлён ChatMeta для {account_id}: {list(update_fields.keys())}")
            return chat_meta

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[chat_meta] Ошибка при обновлении ChatMeta ({account_id}): {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")