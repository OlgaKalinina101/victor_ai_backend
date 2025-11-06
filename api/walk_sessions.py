from fastapi import APIRouter, HTTPException

from api.response_models import WalkSessionCreate
from infrastructure.database.session import Database
from tools.places import models

router = APIRouter(prefix="/api/walk_sessions", tags=["walks"])

@router.post("/")
def create_walk_session(payload: WalkSessionCreate):
    """
    Создаёт прогулку и сохраняет все шаги и посещённые POI.
    """
    db = Database()
    session = db.get_session()

    try:
        # 1️⃣ создаём саму прогулку
        new_walk = models.WalkSession(
            account_id=payload.account_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            distance_m=payload.distance_m,
            steps=payload.steps,
            mode=payload.mode,
            notes=payload.notes
        )
        session.add(new_walk)
        session.flush()  # теперь у new_walk есть .id

        # 2️⃣ сохраняем посещённые POI
        for poi in payload.poi_visits:
            visit = models.POIVisit(
                session_id=new_walk.id,
                poi_id=poi.poi_id,
                poi_name=poi.poi_name,
                distance_from_start=poi.distance_from_start,
                found_at=poi.found_at,
                emotion_emoji=poi.emotion_emoji,
                emotion_label=poi.emotion_label,
                emotion_color=poi.emotion_color
            )
            session.add(visit)

        # 3️⃣ сохраняем шаги
        for step in payload.step_points:
            point = models.StepPoint(
                session_id=new_walk.id,
                lat=step.lat,
                lon=step.lon,
                timestamp=step.timestamp
            )
            session.add(point)

        # 4️⃣ фиксируем в базе
        session.commit()

        return {"status": "ok", "session_id": new_walk.id}

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании прогулки: {e}")

    finally:
        session.close()
