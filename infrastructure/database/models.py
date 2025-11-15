from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Float, Text, DateTime, BigInteger, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM
import enum

from infrastructure.database.database_enums import EnergyDescription, TemperatureDescription

Base = declarative_base()


class TrackUserDescription(Base):
    __tablename__ = "track_user_descriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String, ForeignKey("chat_meta.account_id"), nullable=False)
    track_id = Column(Integer, ForeignKey("music_tracks.id"), nullable=False)
    energy_description = Column(
        ENUM(EnergyDescription, name="energydescription", create_type=True),
        nullable=True
    )
    temperature_description = Column(
        ENUM(TemperatureDescription, name="temperaturedescription", create_type=True),
        nullable=True
    )

    # Связи
    user = relationship("ChatMeta", back_populates="track_descriptions")
    track = relationship("MusicTrack", back_populates="user_descriptions")

    def __repr__(self):
        return (f"<TrackUserDescription account_id={self.account_id}, "
                f"track_id={self.track_id}, "
                f"energy={self.energy_description}, "
                f"temperature={self.temperature_description}>")


class ChatMeta(Base):
    __tablename__ = "chat_meta"

    account_id = Column(String, primary_key=True)
    model = Column(String, default="deepseek-chat")
    trust_level = Column(Integer, default=0)
    raw_trust_score = Column(Integer, nullable=True)
    gender = Column(String, default="другое")
    relationship_level = Column(String, default="незнакомец")  # ← было relationship
    is_creator = Column(Boolean, default=False)
    trust_established = Column(Boolean, default=False)
    trust_test_completed = Column(Boolean, default=False)
    trust_test_timestamp = Column(String, nullable=True)
    last_updated = Column(String, nullable=True)

    track_descriptions = relationship("TrackUserDescription", back_populates="user")


class KeyInfo(Base):
    __tablename__ = 'key_info'

    account_id = Column(String, primary_key=True)
    time = Column(String)
    category = Column(String, primary_key=True)
    subcategory = Column(String, primary_key=True)
    fact = Column(Text, primary_key=True)
    mood = Column(String)
    mood_level = Column(String)
    frequency = Column(Integer)
    last_used = Column(String)
    type = Column(String)
    impressive = Column(Integer)
    critical = Column(Integer, default=0)
    first_disclosure = Column(Integer)

class DialogueHistory(Base):
    __tablename__ = 'dialogue_history'

    id = Column(Integer, primary_key=True, autoincrement=True)  # уникальный id
    account_id = Column(String, index=True)
    dialogue_id = Column(String)

    role = Column(String)                 # кто отправил: user / assistant
    text = Column(Text)                  # текст сообщения
    mood = Column(String)                # detected mood
    message_type = Column(String)        # тип сообщения
    message_category = Column(String)    # категория

    focus_points = Column(Text)          # JSON-строка: list[str] focus_points_list = json.loads(record.focus_points)
    has_strong_focus = Column(Text)      # JSON-строка: list[bool] has_strong_focus_list = json.loads(record.has_strong_focus)

    anchor_link = Column(String)
    has_strong_anchor = Column(Boolean)
    memories = Column(Text)
    anchor = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # timestamp для сортировки

    # Индексы для быстрой пагинации и поиска
    __table_args__ = (
        Index('idx_account_created_desc', 'account_id', 'created_at'),
        Index('idx_account_id_desc', 'account_id', 'id'),
    )

class Diary(Base):
    __tablename__ = "diary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String, index=True)
    entry_text = Column(Text)               # ← здесь ты назвала колонку text
    assistant_answer = Column(Text)  # ← всё ок
    timestamp = Column(DateTime)

class ModelUsage(Base):
    __tablename__ = "model_usage"

    id = Column(Integer, primary_key=True)
    account_id = Column(String, nullable=True, default="test_user")
    model_name = Column(String, nullable=False)
    provider = Column(String, nullable=False)

    # Использовано
    input_tokens_used = Column(BigInteger, default=0)
    output_tokens_used = Column(BigInteger, default=0)

    # Цены
    input_token_price = Column(Float, default=0.00001)   # $ за токен
    output_token_price = Column(Float, default=0.00003)

    # Баланс
    account_balance = Column(Float, default=0.00001)


class MusicTrack(Base):
    __tablename__ = "music_tracks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    title = Column(String)
    artist = Column(String)
    album = Column(String)
    year = Column(Integer)
    genre = Column(String)
    duration = Column(Float)
    track_number = Column(Integer)
    bitrate = Column(Integer)
    file_size = Column(Integer)

    user_descriptions = relationship("TrackUserDescription", back_populates="track")
    play_history = relationship("TrackPlayHistory", back_populates="track")

    def __repr__(self):
        return f"<MusicTrack {self.artist} - {self.title}>"


class TrackPlayHistory(Base):
    __tablename__ = "track_play_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    track_id = Column(Integer, ForeignKey("music_tracks.id"), nullable=False)
    account_id = Column(String, ForeignKey("chat_meta.account_id"), nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_played = Column(Float, nullable=True)  # в секундах

    energy_on_play = Column(
        ENUM(EnergyDescription, name="energy_on_play_enum", create_type=True),
        nullable=True
    )
    temperature_on_play = Column(
        ENUM(TemperatureDescription, name="temperature_on_play_enum", create_type=True),
        nullable=True
    )

    # связи
    track = relationship("MusicTrack", back_populates="play_history")
    user = relationship("ChatMeta")

    def __repr__(self):
        return f"<TrackPlayHistory track_id={self.track_id}, started_at={self.started_at}>"










