from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from api.assistant import logger
from api.response_models import ChatMetaBase
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