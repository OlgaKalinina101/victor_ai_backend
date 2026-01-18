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

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, JSON, BigInteger, Float, Text, Date, Boolean, Index
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from infrastructure.database.models import Base
from infrastructure.database.session import Database

db = Database.get_instance()

# --- уровни ---
class GameLocation(Base):
    __tablename__ = 'game_locations'

    id = Column(Integer, primary_key=True)
    account_id = Column(String)
    name = Column(String)
    description = Column(Text, nullable=True)

    bbox_south = Column(Float)
    bbox_west = Column(Float)
    bbox_north = Column(Float)
    bbox_east = Column(Float)

    is_active = Column(Boolean, default=True)
    difficulty = Column(String, nullable=True)          # "easy", "medium", "hard"
    location_type = Column(String, nullable=True)       # "urban", "park", "historic"

    osm_elements = relationship(
        "OSMElement",
        secondary="game_location_osm_elements",
        back_populates="locations",
    )

# --- элементы ---
class OSMElement(Base):
    __tablename__ = 'osm_elements'

    id = Column(BigInteger, primary_key=True)  # OSM ID из OSM
    type = Column(String(10))                  # 'node', 'way', 'relation'
    tags = Column(JSON, nullable=True)         # все теги
    geometry = Column(Geometry('GEOMETRY', srid=4326))

    # Больше НЕТ прямого location_id тут
    locations = relationship(
        "GameLocation",
        secondary="game_location_osm_elements",
        back_populates="osm_elements",
    )

class GameLocationOSMElement(Base):
    __tablename__ = "game_location_osm_elements"

    # составной PK – одна строка = связь "эта локация содержит этот объект"
    game_location_id = Column(
        Integer,
        ForeignKey("game_locations.id"),
        primary_key=True,
    )
    osm_element_id = Column(
        BigInteger,
        ForeignKey("osm_elements.id"),
        primary_key=True,
    )


class POICaption(Base):
    """
    Кеш коротких подписей к POI по тегам (для карты).

    Сохраняем:
    - идентификатор POI (osm_element_id + osm_element_type)
    - теги (JSON) и их hash (для инвалидации при изменении)
    - caption (строка ответа)
    - created_at (дата вызова)
    """

    __tablename__ = "poi_captions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String, nullable=False, index=True)

    osm_element_id = Column(BigInteger, ForeignKey("osm_elements.id"), nullable=True, index=True)
    osm_element_type = Column(String(10), nullable=True)

    poi_name = Column(String, nullable=True)
    tags = Column(JSON, nullable=False)
    tags_hash = Column(String(64), nullable=False)

    caption = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    osm_element = relationship("OSMElement", lazy="selectin")

    __table_args__ = (
        Index(
            "ix_poi_captions_lookup",
            "account_id",
            "osm_element_id",
            "osm_element_type",
            "tags_hash",
            unique=True,
        ),
    )

# --- прогулка ---
class WalkSession(Base):
    __tablename__ = "walk_sessions"
    id = Column(Integer, primary_key=True)
    account_id = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    distance_m = Column(Float)  # пройдено метров
    steps = Column(Integer)
    mode = Column(String)  # short / medium / adventure
    notes = Column(Text, nullable=True)

    poi_visits = relationship("POIVisit", back_populates="session")
    steps_points = relationship("StepPoint", back_populates="session")

# --- точки пути ---
class StepPoint(Base):
    __tablename__ = "step_points"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("walk_sessions.id"))
    lat = Column(Float)
    lon = Column(Float)
    timestamp = Column(DateTime)

    session = relationship("WalkSession", back_populates="steps_points")

# --- посещения мест ---
class POIVisit(Base):
    __tablename__ = "poi_visits"
    id = Column(Integer, primary_key=True)
    account_id = Column(String)  # ← добавили
    session_id = Column(Integer, ForeignKey("walk_sessions.id"))
    poi_id = Column(String)
    poi_name = Column(String)
    distance_from_start = Column(Float)
    found_at = Column(DateTime)
    emotion_emoji = Column(String, nullable=True)
    emotion_label = Column(String, nullable=True)
    emotion_color = Column(String, nullable=True)

    session = relationship("WalkSession", back_populates="poi_visits")


# --- достижения ---
class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True)
    account_id = Column(String)
    name = Column(String)
    description = Column(String)
    unlocked_at = Column(DateTime)
    type = Column(String)
    icon = Column(String, nullable=True)

# --- streak ---
class Streak(Base):
    __tablename__ = "streaks"
    id = Column(Integer, primary_key=True)
    account_id = Column(String)
    start_date = Column(Date)
    last_active_date = Column(Date)
    current_length = Column(Integer)
    longest_streak = Column(Integer)

# --- дневник ---
class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True)
    account_id = Column(String)  # ← добавили
    date = Column(Date)
    session_id = Column(Integer, ForeignKey("walk_sessions.id"))
    text = Column(Text)
    photo_path = Column(String, nullable=True)
    poi_id = Column(String, nullable=True)
    poi_name = Column(String, nullable=True)

    session = relationship("WalkSession")