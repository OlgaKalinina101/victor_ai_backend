from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from infrastructure.database.database_enums import EnergyDescription, TemperatureDescription
from infrastructure.database.models import TrackPlayHistory, MusicTrack, TrackUserDescription
from infrastructure.database.session import Database

router = APIRouter(prefix="/tracks", tags=["tracks"])

@router.get("/history")
async def get_track_history(account_id: str = Query(...)):
    """Возвращает историю прослушиваний пользователя"""
    db = Database()
    session = db.get_session()
    try:
        history = (
            session.query(TrackPlayHistory)
            .options(joinedload(TrackPlayHistory.track))
            .filter(TrackPlayHistory.account_id == account_id)
            .order_by(TrackPlayHistory.started_at.desc())
            .all()
        )

        result = []
        for h in history:
            result.append({
                "id": h.id,
                "track_id": h.track_id,
                "title": h.track.title if h.track else None,
                "artist": h.track.artist if h.track else None,
                "album": h.track.album if h.track else None,
                "started_at": h.started_at.isoformat() if h.started_at else None,
                "ended_at": h.ended_at.isoformat() if h.ended_at else None,
                "duration_played": h.duration_played,
                "energy_on_play": h.energy_on_play.value if h.energy_on_play else None,
                "temperature_on_play": h.temperature_on_play.value if h.temperature_on_play else None,
            })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения истории: {e}")
    finally:
        session.close()

@router.get("/stats")
async def get_track_statistics(
    account_id: str = Query(...),
    period: str = Query("week", description="week or month")
):
    """Возвращает агрегированную статистику по прослушиваниям пользователя"""
    db = Database()
    session = db.get_session()
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        now = datetime.utcnow()
        start = now - timedelta(days=30 if period == "month" else 7)

        # 🔹 Все прослушивания за период
        q = (
            session.query(TrackPlayHistory)
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.started_at >= start
            )
        )

        total_plays = q.count()
        if total_plays == 0:
            return {
                "period": period,
                "from": start.isoformat(),
                "to": now.isoformat(),
                "total_plays": 0,
                "top_tracks": [],
                "top_energy": None,
                "top_temperature": None,
                "average_duration": 0
            }

        # 🔹 Топ треков
        top_tracks_q = (
            session.query(
                MusicTrack.title,
                MusicTrack.artist,
                func.count(TrackPlayHistory.id).label("plays")
            )
            .join(MusicTrack, MusicTrack.id == TrackPlayHistory.track_id)
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.started_at >= start
            )
            .group_by(MusicTrack.title, MusicTrack.artist)
            .order_by(func.count(TrackPlayHistory.id).desc())
            .limit(5)
            .all()
        )
        top_tracks = [
            {"title": t.title, "artist": t.artist, "plays": t.plays}
            for t in top_tracks_q
        ]

        # 🔹 Энергия / температура
        top_energy = (
            session.query(TrackPlayHistory.energy_on_play, func.count().label("cnt"))
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.energy_on_play.isnot(None),
                TrackPlayHistory.started_at >= start
            )
            .group_by(TrackPlayHistory.energy_on_play)
            .order_by(func.count().desc())
            .first()
        )

        top_temperature = (
            session.query(TrackPlayHistory.temperature_on_play, func.count().label("cnt"))
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.temperature_on_play.isnot(None),
                TrackPlayHistory.started_at >= start
            )
            .group_by(TrackPlayHistory.temperature_on_play)
            .order_by(func.count().desc())
            .first()
        )

        # 🔹 Средняя длительность
        avg_duration = (
            session.query(func.avg(TrackPlayHistory.duration_played))
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.duration_played.isnot(None),
                TrackPlayHistory.started_at >= start
            )
            .scalar() or 0
        )

        return {
            "period": period,
            "from": start.isoformat(),
            "to": now.isoformat(),
            "total_plays": total_plays,
            "top_tracks": top_tracks,
            "top_energy": top_energy[0].value if top_energy else None,
            "top_temperature": top_temperature[0].value if top_temperature else None,
            "average_duration": round(avg_duration, 1)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении статистики: {e}")
    finally:
        session.close()

@router.post("/run_playlist_wave")
async def run_playlist_wave(
    account_id: str = Query(...),
    energy: Optional[str] = Query(None),
    temperature: Optional[str] = Query(None),
    limit: int = Query(20)   # сколько треков в “волне”
):
    """
    Подбираем треки под энергию + температуру и отдаём волну.
    """
    energy_enum = EnergyDescription.from_value(energy) if energy else None
    temp_enum = TemperatureDescription.from_value(temperature) if temperature else None

    db = Database()
    session = db.get_session()
    try:
        q = (
            session.query(MusicTrack)
            .join(
                TrackUserDescription,
                TrackUserDescription.track_id == MusicTrack.id
            )
            .filter(TrackUserDescription.account_id == account_id)
        )

        # фильтр по энергии
        if energy_enum:
            q = q.filter(TrackUserDescription.energy_description == energy_enum)

        # фильтр по температуре
        if temp_enum:
            q = q.filter(TrackUserDescription.temperature_description == temp_enum)

        # немного рандома, чтобы это была "волна", а не всегда один порядок
        q = q.order_by(func.random()).limit(limit)

        tracks: List[MusicTrack] = q.all()

        if not tracks:
            return {
                "tracks": [],
                "message": "Нет треков под такие энергию и температуру"
            }

        # собираем лёгкий payload для фронта
        payload = []
        for t in tracks:
            # берём описание именно этого пользователя
            desc = next(
                (d for d in t.user_descriptions if d.account_id == account_id),
                None
            )
            payload.append({
                "id": t.id,
                "title": t.title,
                "artist": t.artist,
                "duration": t.duration,
                "energy_description": getattr(desc, "energy_description", None),
                "temperature_description": getattr(desc, "temperature_description", None),
                # удобный URL для ExoPlayer:
                "stream_url": f"/stream/{t.id}?account_id={account_id}",
            })

        return {
            "tracks": payload,
            "energy": energy,
            "temperature": temperature,
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка подбора волны: {e}")
    finally:
        session.close()
