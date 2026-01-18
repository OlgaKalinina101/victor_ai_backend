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

from datetime import datetime
from sqlalchemy import func

from api.schemas import WalkSessionCreate
from tools.maps.models import Achievement, WalkSession, POIVisit


def ensure_achievement(session, account_id: str, name: str, description: str,
                       type_: str, icon: str | None = None):
    """
    Создаёт ачивку, если её ещё нет для этого аккаунта.
    Возвращает созданный объект или None.
    """
    existing = (
        session.query(Achievement)
        .filter_by(account_id=account_id, name=name, type=type_)
        .first()
    )
    if existing:
        return None

    ach = Achievement(
        account_id=account_id,
        name=name,
        description=description,
        unlocked_at=datetime.utcnow(),
        type=type_,
        icon=icon,
    )
    session.add(ach)
    # не коммитим здесь – пусть вызывающий решает
    return ach

def check_walk_achievements(session, account_id: str, walk: WalkSession, payload: WalkSessionCreate):
    """Чекер ачивок для прогулки"""
    unlocked = []

    # --- 1. по количеству прогулок ---
    total_walks = (
        session.query(func.count(WalkSession.id))
        .filter_by(account_id=account_id)
        .scalar() or 0
    )
    if total_walks >= 1:
        ach = ensure_achievement(
            session,
            account_id,
            name="Первая прогулка",
            description="Мы сохранили нашу первую прогулку.",
            type_="walks",
            icon="first_walk",
        )
        if ach:
            unlocked.append(ach)

    if total_walks >= 5:
        ach = ensure_achievement(
            session,
            account_id,
            name="Вошли во вкус",
            description="Пять прогулок позади, а сколько ещё впереди.",
            type_="walks",
            icon="five_walks",
        )
        if ach:
            unlocked.append(ach)

    # --- 2. по суммарной дистанции ---
    total_distance = (
        session.query(func.sum(WalkSession.distance_m))
        .filter_by(account_id=account_id)
        .scalar() or 0
    )

    if total_distance >= 1000:
        ach = ensure_achievement(
            session,
            account_id,
            name="Первый километр",
            description="Мы прошли наш первый километр.",
            type_="distance",
            icon="1km",
        )
        if ach:
            unlocked.append(ach)

    if total_distance >= 10_000:
        ach = ensure_achievement(
            session,
            account_id,
            name="10 километров пути",
            description="10 км прогулок — карта начинает жить.",
            type_="distance",
            icon="10km",
        )
        if ach:
            unlocked.append(ach)

    # --- 3. по POI глобально ---
    total_poi_visits = (
        session.query(func.count(POIVisit.id))
        .join(WalkSession, POIVisit.session_id == WalkSession.id)
        .filter(WalkSession.account_id == account_id)
        .scalar() or 0
    )

    if total_poi_visits >= 1:
        ach = ensure_achievement(
            session,
            account_id,
            name="Первое найденное место",
            description="Мы нашли наше первое особенное место.",
            type_="poi",
            icon="poi_1",
        )
        if ach:
            unlocked.append(ach)

    if total_poi_visits >= 10:
        ach = ensure_achievement(
            session,
            account_id,
            name="Охотники за местами",
            description="10 найденных поинтов. Мир вокруг становится ближе.",
            type_="poi",
            icon="poi_10",
        )
        if ach:
            unlocked.append(ach)

    # --- 4. по текущей прогулке ---
    if walk.distance_m and walk.distance_m >= 3000:
        ach = ensure_achievement(
            session,
            account_id,
            name="Длинная прогулка",
            description="Одна прогулка длиной больше 3 км.",
            type_="session",
            icon="long_walk",
        )
        if ach:
            unlocked.append(ach)

    if len(payload.poi_visits) >= 3:
        ach = ensure_achievement(
            session,
            account_id,
            name="Карта оживает",
            description="За одну прогулку мы открыли три и больше поинтов.",
            type_="session",
            icon="map_awakes",
        )
        if ach:
            unlocked.append(ach)

    return unlocked

