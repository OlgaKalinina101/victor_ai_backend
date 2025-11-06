from fastapi import APIRouter, HTTPException

from api.response_models import JournalEntryIn
from infrastructure.database.session import Database
from tools.places import models


router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("/")
def list_entries(account_id: str):
    db = Database()
    session = db.get_session()
    try:
        entries = (
            session.query(models.JournalEntry)
            .join(models.WalkSession)
            .filter(models.WalkSession.account_id == account_id)
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
