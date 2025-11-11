from fastapi import APIRouter, HTTPException

from api.response_models import JournalEntryIn
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from tools.places import models

logger=setup_logger("journal")
router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("/")
def list_entries(account_id: str):
    db = Database()
    session = db.get_session()
    try:
        entries = (
            session.query(models.JournalEntry)
            .filter(models.JournalEntry.account_id == account_id)  # ✅ Фильтр напрямую
            .order_by(models.JournalEntry.date.desc())
            .all()
        )
        return [
            {
                "id": e.id,
                "date": e.date,
                "text": e.text,
                "photo_path": e.photo_path,
                "poi_name": e.poi_name,
                "session_id": e.session_id,
            }
            for e in entries
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении дневника: {e}")
    finally:
        session.close()


@router.post("/")
def create_entry(payload: JournalEntryIn):
    logger.info(f"create_entry: {payload}")
    db = Database()
    session = db.get_session()
    try:
        entry = models.JournalEntry(**payload.dict())
        session.add(entry)
        session.commit()
        return {"status": "ok", "entry_id": entry.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании записи: {e}")
    finally:
        session.close()
