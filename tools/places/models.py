from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, JSON, text, UniqueConstraint, BigInteger, Float, Text, Date
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from infrastructure.database.models import Base
from infrastructure.database.session import Database

db = Database()

class OSMElement(Base):
    __tablename__ = 'osm_elements'

    id = Column(BigInteger, primary_key=True)  # OSM ID
    type = Column(String(10))  # 'node', 'way'
    tags = Column(JSON, nullable=True)  # все теги
    geometry = Column(Geometry('GEOMETRY', srid=4326))

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
    account_id = Column(String)  # ← добавили
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
    poi_id = Column(String, nullable=True)  # ← исправили на String
    poi_name = Column(String, nullable=True)

    session = relationship("WalkSession")