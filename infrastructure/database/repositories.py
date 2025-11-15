import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

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

                created_at=datetime.utcnow(),
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


def get_dialogue_history_paginated(
    session: Session,
    account_id: str,
    limit: int = 25,
    before_id: Optional[int] = None
) -> tuple[List[DialogueHistory], bool]:
    """
    Получает историю диалога с пагинацией.

    Args:
        session: Сессия SQLAlchemy
        account_id: ID пользователя
        limit: Количество сообщений для загрузки
        before_id: ID сообщения, до которого загружать (для скролла вверх)

    Returns:
        Tuple (список сообщений, есть ли еще сообщения)
    """
    query = session.query(DialogueHistory).filter(
        DialogueHistory.account_id == account_id
    )

    if before_id is not None:
        query = query.filter(DialogueHistory.id < before_id)

    # Сортируем по id в обратном порядке (новые первыми)
    query = query.order_by(DialogueHistory.id.desc())

    # Берем limit + 1 для проверки наличия еще записей
    messages = query.limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # Возвращаем в прямом порядке (старые первыми)
    messages.reverse()

    return messages, has_more


def search_dialogue_history(
    session: Session,
    account_id: str,
    query: str,
    offset: int = 0
) -> tuple[List[DialogueHistory], int]:
    """
    Ищет сообщения по ключевому слову.

    Args:
        session: Сессия SQLAlchemy
        account_id: ID пользователя
        query: Поисковый запрос
        offset: Смещение для навигации по результатам

    Returns:
        Tuple (список найденных сообщений, общее количество)
    """
    # Поиск по LIKE (можно улучшить до full-text search)
    search_filter = DialogueHistory.text.ilike(f"%{query}%")

    # Считаем общее количество результатов
    total_count = session.query(DialogueHistory).filter(
        and_(
            DialogueHistory.account_id == account_id,
            search_filter
        )
    ).count()

    # Получаем результаты с offset
    # Сортируем по id DESC (новые первыми)
    results = session.query(DialogueHistory).filter(
        and_(
            DialogueHistory.account_id == account_id,
            search_filter
        )
    ).order_by(DialogueHistory.id.desc()).offset(offset).limit(1).all()

    return results, total_count


def get_dialogue_context(
    session: Session,
    account_id: str,
    message_id: int,
    context_before: int = 10,
    context_after: int = 10
) -> List[DialogueHistory]:
    """
    Получает контекст вокруг найденного сообщения.

    Args:
        session: Сессия SQLAlchemy
        account_id: ID пользователя
        message_id: ID найденного сообщения
        context_before: Количество сообщений до
        context_after: Количество сообщений после

    Returns:
        Список сообщений с контекстом
    """
    # Получаем сообщения ДО найденного
    before_messages = session.query(DialogueHistory).filter(
        and_(
            DialogueHistory.account_id == account_id,
            DialogueHistory.id < message_id
        )
    ).order_by(DialogueHistory.id.desc()).limit(context_before).all()

    before_messages.reverse()  # Переворачиваем в прямой порядок

    # Получаем само сообщение
    target_message = session.query(DialogueHistory).filter(
        and_(
            DialogueHistory.account_id == account_id,
            DialogueHistory.id == message_id
        )
    ).first()

    # Получаем сообщения ПОСЛЕ найденного
    after_messages = session.query(DialogueHistory).filter(
        and_(
            DialogueHistory.account_id == account_id,
            DialogueHistory.id > message_id
        )
    ).order_by(DialogueHistory.id.asc()).limit(context_after).all()

    # Объединяем
    if target_message:
        return before_messages + [target_message] + after_messages
    else:
        return before_messages + after_messages


def merge_session_and_db_history(
    session_context: dict,
    db_messages: List[DialogueHistory]
) -> List[dict]:
    """
    Мержит SessionContext и БД, убирая дубли по (text, role).

    Args:
        session_context: Сериализованный SessionContext
        db_messages: Список сообщений из БД

    Returns:
        Объединенный список сообщений без дублей
    """
    # 1. Парсим SessionContext
    session_msgs = []
    for msg in session_context.get("message_history", []):
        if ":" in msg:
            role, text = msg.split(":", 1)
            session_msgs.append({
                "role": role.strip(),
                "text": text.strip(),
                "source": "session",
                "id": None,
                "created_at": None
            })

    # 2. Парсим БД
    db_msgs = []
    for record in db_messages:
        db_msgs.append({
            "id": record.id,
            "role": record.role,
            "text": record.text,
            "created_at": record.created_at,
            "source": "db"
        })

    # 3. Убираем дубли (SessionContext приоритетнее)
    seen = set()
    unique = []

    # Сначала SessionContext (свежие данные)
    for msg in session_msgs:
        key = (msg["role"], msg["text"])
        if key not in seen:
            seen.add(key)
            unique.append(msg)

    # Потом БД (старые данные)
    for msg in db_msgs:
        key = (msg["role"], msg["text"])
        if key not in seen:
            seen.add(key)
            unique.append(msg)

    return unique


