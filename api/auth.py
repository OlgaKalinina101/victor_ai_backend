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

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.runtime import (
    get_db,
    get_context_store,
    get_logger
)
from api.helpers import (
    normalize_demo_key,
    create_access_token,
    build_initial_state, normalize_account_id, validate_demo_key_from_file
)
from api.schemas.web_demo_auth import (
    WebDemoLoginResponse,
    WebDemoRegisterRequest,
    WebDemoResolveResponse,
    WebDemoResolveRequest
)
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database import (
    ChatMetaRepository
)
from models.user_enums import Gender
from settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/resolve", response_model=WebDemoResolveResponse)
async def resolve(
    req: WebDemoResolveRequest,
    db=Depends(get_db),
    context_store=Depends(get_context_store),
    logger=Depends(get_logger),
):
    """
    1) Принимает demo_key
    2) Если demo_key уже привязан в ChatMeta -> логин (token + initial_state)
    3) Если demo_key не найден -> просит регистрацию (account_id + gender)
    """
    demo_key = normalize_demo_key(req.demo_key)
    logger.info(f"demo_key={demo_key}")
    validate_demo_key_from_file(demo_key)

    db_session = db.get_session()
    try:
        repo = ChatMetaRepository(db_session)
        meta = repo.get_by_demo_key(demo_key)

        if not meta:
            return WebDemoResolveResponse(
                status="needs_registration",
                message="Я не запомню твое имя.",
                required_fields=["account_id", "gender"],
                gender_options=[g.value for g in Gender],
            )

        session_context = context_store.load(meta.account_id, db_session)
        token = create_access_token(meta.account_id)

        logger.info(f"[AUTH] resolve ok account_id={meta.account_id}")
        return WebDemoResolveResponse(
            status="ok",
            access_token=token,
            account_id=meta.account_id,
            initial_state=build_initial_state(chat_meta=meta),
        )
    finally:
        db_session.close()


@router.post("/register", response_model=WebDemoLoginResponse)
async def register(
    req: WebDemoRegisterRequest,
    db=Depends(get_db),
    context_store=Depends(get_context_store),
    logger=Depends(get_logger),
):
    """
    Регистрирует demo-аккаунт для demo_key:
    - проверяет, что demo_key ещё не занят
    - создаёт/обновляет ChatMeta для указанного account_id (ставит demo_key + gender)
    - поднимает SessionContext (он подтянет gender/relationship/trust из chat_meta)
    - возвращает token + initial_state
    """
    demo_key = normalize_demo_key(req.demo_key)
    account_id = normalize_account_id(req.account_id)

    db_session = db.get_session()
    try:
        repo = ChatMetaRepository(db_session)

        if repo.exists_demo_key(demo_key):
            raise HTTPException(status_code=409, detail="demo_key already in use")

        # запрещаем перетирать существующего пользователя:
        if repo.exists(account_id):
            raise HTTPException(status_code=409, detail="account_id already exists")

        meta = repo.create_or_update(
            account_id=account_id,
            demo_key=demo_key,
            gender=req.gender.value,                 # важно: попадёт в ChatMeta.gender
            relationship_level="незнакомец",
            trust_level=0,
            is_creator=False,
            model="deepseek-chat",                   # дефолтная модель для новых пользователей
        )

        token = create_access_token(account_id)
        logger.info(f"[AUTH] register ok account_id={account_id}")

        session_context_store = SessionContextStore(settings.SESSION_CONTEXT_DIR)
        session_context = session_context_store.load(
            account_id=account_id,
            db_session=db_session
        )
        session_context_store.save(
            context=session_context
        )

        return WebDemoLoginResponse(
            access_token=token,
            account_id=account_id,
            initial_state=build_initial_state(chat_meta=meta),
        )
    finally:
        db_session.close()
