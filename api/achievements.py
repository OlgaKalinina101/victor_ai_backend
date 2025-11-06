from fastapi import APIRouter, HTTPException

from infrastructure.database.session import Database
from tools.places import models

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


@router.get("/")
def get_all():
    db = Database()
    session = db.get_session()
    try:
        achievements = session.query(models.Achievement).all()
        return [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "type": a.type,
                "icon": a.icon,
                "unlocked_at": a.unlocked_at
            }
            for a in achievements
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении достижений: {e}")
    finally:
        session.close()
