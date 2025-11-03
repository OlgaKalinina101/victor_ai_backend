# models.py
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, JSON, text, UniqueConstraint, BigInteger
)
from sqlalchemy.orm import relationship

from geoalchemy2 import Geometry
from datetime import datetime

from infrastructure.database.models import Base
from infrastructure.database.session import Database

db = Database()

class OSMElement(Base):
    __tablename__ = 'osm_elements'

    id = Column(BigInteger, primary_key=True)  # OSM ID
    type = Column(String(10))  # 'node', 'way'
    tags = Column(JSON, nullable=True)  # все теги
    geometry = Column(Geometry('GEOMETRY', srid=4326))

if __name__ == "__main__":
    db = Database()
    print("Создаём таблицы в victor_db...")
    Base.metadata.create_all(bind=db.engine)
    print("Готово! Таблицы: regions, places, tags, place_tags")