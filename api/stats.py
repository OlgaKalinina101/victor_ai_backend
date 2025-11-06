from fastapi import APIRouter, HTTPException
from datetime import date, timedelta

from infrastructure.database.session import Database
from tools.places.models import WalkSession, Streak, Achievement

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/")
def get_stats(account_id: str):
    db = Database()
    session = db.get_session()
    try:
        today = date.today()
        week_ago = today - timedelta(days=6)

        walks = (
            session.query(WalkSession)
            .filter(
                WalkSession.account_id == account_id,
                WalkSession.start_time >= week_ago
            )
            .all()
        )

        today_walks = [w for w in walks if w.start_time.date() == today]
        today_dist = sum(w.distance_m or 0 for w in today_walks)
        today_steps = sum(w.steps or 0 for w in today_walks)

        weekly_chart = [0] * 7
        for w in walks:
            idx = (today - w.start_time.date()).days
            if 0 <= idx < 7:
                weekly_chart[6 - idx] += w.distance_m or 0

        streak = session.query(Streak).filter_by(account_id=account_id).first()
        achievements = session.query(Achievement).all()

        return {
            "today_distance": today_dist,
            "today_steps": today_steps,
            "weekly_chart": weekly_chart,
            "streak": streak.current_length if streak else 0,
            "achievements": [a.name for a in achievements],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении статистики: {e}")
    finally:
        session.close()
