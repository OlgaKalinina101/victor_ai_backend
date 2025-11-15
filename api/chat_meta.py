import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from api.assistant import logger
from api.request_models import ChatMetaUpdateRequest
from api.response_models import ChatMetaBase
from infrastructure.database.models import ChatMeta
from infrastructure.database.repositories import get_chat_meta
from infrastructure.database.session import Database

router = APIRouter(prefix="/chat_meta", tags=["ChatMeta"])

@router.get("/{account_id}", response_model=ChatMetaBase)
def get_authorisation(account_id: str):
    """
    Возвращает информацию о пользователе (ChatMeta) по account_id.
    """
    db = Database()
    session: Session = db.get_session()

    try:
        user_data = get_chat_meta(session=session, account_id=account_id)
        if not user_data:
            logger.warning(f"[auth] ChatMeta not found for account_id={account_id}")
            raise HTTPException(status_code=404, detail="ChatMeta not found")

        logger.info(f"[auth] Авторизация успешно получена для {account_id}")
        return user_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[auth] Ошибка при запросе ChatMeta ({account_id}): {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    finally:
        session.close()


@router.patch("/{account_id}", response_model=ChatMetaBase)
def update_chat_meta(account_id: str, update_data: ChatMetaUpdateRequest):
    """
    Обновляет информацию о пользователе (частично).
    """
    db = Database()
    session: Session = db.get_session()
    chat_meta = session.query(ChatMeta).filter_by(account_id=account_id).first()

    if not chat_meta:
        raise HTTPException(status_code=404, detail="ChatMeta not found")

    # 🔄 Применяем только те поля, что реально пришли в запросе
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(chat_meta, field, value)

    chat_meta.last_updated = datetime.datetime.utcnow().isoformat()
    session.commit()
    session.refresh(chat_meta)
    return chat_meta