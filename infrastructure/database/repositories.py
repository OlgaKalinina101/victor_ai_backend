import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict

from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from infrastructure.database.models import KeyInfo, ChatMeta, DialogueHistory, Diary, ModelUsage, TrackUserDescription, \
    MusicTrack
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from models.communication_models import MessageMetadata

logger = setup_logger("database")

def get_key_info_by_account_id(session: Session, account_id: str) -> list[type[KeyInfo]]:
    """Получает key_info из PostreSQL по account_id"""
    return session.query(KeyInfo).filter_by(account_id=account_id).all()

def save_key_info(session: Session, record: KeyInfo):
    """Сохраняет key_info в PostreSQL"""
    session.merge(record)
    session.commit()

def get_chat_meta(session: Session, account_id: str) -> ChatMeta | None:
    """Получает chat_meta из PostreSQL по account_id"""
    return session.query(ChatMeta).filter_by(account_id=account_id).first()

def save_chat_meta(session: Session, meta: ChatMeta):
    """Сохраняет chat_meta в PostreSQL"""
    session.merge(meta)
    session.commit()

def get_dialogue_history(session: Session, account_id: str) -> DialogueHistory | None:
    """Получает dialogue_history из PostreSQL по account_id"""
    return session.query(ChatMeta).filter_by(account_id=account_id).first()

def save_dialogue_history(session: Session, history: DialogueHistory):
    """Сохраняет dialogue_history в PostreSQL"""
    session.merge(history)
    session.commit()

def save_session_context_as_history(session: Session, context_dict: dict):
    """
    Сохраняет содержимое session_context (в виде словаря) в таблицу DialogueHistory.
    Все anchor и focus сохраняются целиком, без парсинга.
    """
    dialogue_id = str(uuid.uuid4())

    try:
        messages = context_dict.get("message_history", [])
        roles = ["user" if i % 2 == 0 else "assistant" for i in range(len(messages))]

        mood_list = context_dict.get("victor_mood_history", [])
        impressive_list = context_dict.get("victor_impressive_history", [])
        intensity_list = context_dict.get("victor_intensity_history", [])
        category_list = context_dict.get("message_category_history", [])

        anchor_block = json.dumps(context_dict.get("anchor_link_history", []))
        focus_block = json.dumps(context_dict.get("focus_points_history", []))
        mem_text = json.dumps(context_dict.get("key_info_history", []))

        account_id = context_dict.get("account_id", "unknown")

        for i, (role, text) in enumerate(zip(roles, messages)):
            mood = mood_list[i] if i < len(mood_list) else None
            impressive = impressive_list[i] if i < len(impressive_list) else None
            intensity = intensity_list[i] if i < len(intensity_list) else None
            category = category_list[i] if i < len(category_list) else None

            record = DialogueHistory(
                account_id=account_id,
                dialogue_id=dialogue_id,
                role=role,
                text=text,

                mood=mood,
                message_type=None,
                message_category=category,

                focus_points=focus_block,
                has_strong_focus=None,
                anchor_link=anchor_block,
                has_strong_anchor=None,
                memories=mem_text,
                anchor=None,
            )
            session.add(record)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[ERROR] Ошибка при сохранении диалога: {e}")
        raise

def save_memory_as_key_info(session: Session, account_id: str, category: str, memory: str, impressive: int, metadata: MessageMetadata):
    """Сохраняет запись с воспоминанием в PostreSQL"""
    try:
        record = KeyInfo(
        account_id=account_id,
        time=datetime.now(timezone.utc),
        category=category,
        subcategory="БезПодкатегории",
        fact=memory,
        mood=metadata.mood.value,
        mood_level=metadata.mood_level.value,
        frequency=0,
        last_used=datetime.now(timezone.utc),
        type=metadata.message_category.value,
        impressive=impressive,
        critical=0,
        first_disclosure=0
        )
        session.add(record)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[ERROR] Ошибка при сохранении диалога: {e}")
        raise

def save_diary(session: Session, account_id: str, entry_text: str = None, timestamp: datetime = None):
    """Сохраняет запись дневника в PostgreSQL"""
    try:
        record = Diary(
            account_id=account_id,
            entry_text=entry_text,
            assistant_answer=None,
            timestamp=timestamp or datetime.utcnow(),
        )
        session.add(record)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[ERROR] Ошибка при сохранении дневника: {e}")
        raise

def update_model_usage(account_id: str, model_name: str, provider: str, input_tokens: int, output_tokens: int):
    """Обновляет количество использованных токенов"""
    db = Database()
    with db.get_session() as session:
        result = session.execute(
            select(ModelUsage).where(
                and_(
                    ModelUsage.model_name == model_name,
                    ModelUsage.provider == provider
                )
            )
        )
        usage = result.scalar_one_or_none()

        if usage:
            usage.input_tokens_used += input_tokens
            usage.output_tokens_used += output_tokens
        else:
            usage = ModelUsage(
                account_id=account_id,
                model_name=model_name,
                provider=provider,
                input_tokens_used=input_tokens,
                output_tokens_used=output_tokens
            )
            session.add(usage)

        session.commit()

def get_model_usage(account_id: str, session: Session) -> list[type[ModelUsage]]:
    """Получает все записи model_usage по account_id"""
    return session.query(ModelUsage).filter_by(account_id=account_id).all()


def get_music_tracks_with_descriptions(session: Session, account_id: str) -> List[Dict]:
    """
    Получает все треки с их описаниями из PostgreSQL для заданного account_id.

    :param session: Сессия SQLAlchemy.
    :param account_id: ID пользователя.
    :return: Список словарей с данными треков и их описаниями.
    """
    # Запрашиваем все треки и их описания для account_id
    stmt = (
        select(MusicTrack, TrackUserDescription)
        .outerjoin(
            TrackUserDescription,
            (MusicTrack.id == TrackUserDescription.track_id) &
            (TrackUserDescription.account_id == account_id)
        )
    )
    result = session.execute(stmt).all()

    tracks = []
    for music_track, description in result:
        track_data = {
            "id": music_track.id,
            "filename": music_track.filename,
            "file_path": music_track.file_path,
            "title": music_track.title,
            "artist": music_track.artist,
            "album": music_track.album,
            "year": music_track.year,
            "genre": music_track.genre,
            "duration": music_track.duration,
            "track_number": music_track.track_number,
            "bitrate": music_track.bitrate,
            "file_size": music_track.file_size,
            "energy_description": description.energy_description.value if description and description.energy_description else None,
            "temperature_description": description.temperature_description.value if description and description.temperature_description else None
        }
        tracks.append(track_data)

    return tracks


def get_track_description(session: Session, account_id: str, track_id: int) -> TrackUserDescription | None:
    """
    Получает описание трека из PostgreSQL по account_id и track_id.

    :param session: Сессия SQLAlchemy.
    :param account_id: ID пользователя.
    :param track_id: ID трека.
    :return: Объект TrackUserDescription или None, если запись не найдена.
    """
    return session.query(TrackUserDescription).filter_by(
        account_id=account_id,
        track_id=track_id
    ).first()

def save_track_description(session: Session, description: TrackUserDescription):
    """
    Сохраняет или обновляет описание трека в PostgreSQL.

    :param session: Сессия SQLAlchemy.
    :param description: Объект TrackUserDescription для сохранения.
    """
    try:
        session.merge(description)
        session.commit()
    except Exception as e:
        session.rollback()
        raise Exception(f"Ошибка при сохранении описания: {e}")


