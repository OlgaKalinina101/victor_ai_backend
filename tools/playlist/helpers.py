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

from sqlalchemy.orm import Session
from sqlalchemy import select
from infrastructure.database.models import MusicTrack, TrackUserDescription, EnergyDescription, TemperatureDescription
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


def get_artists_by_description(
        session: Session,
        account_id: str,
        energy_description: str | None = None,  # имя члена enum, например "WARM_HEARTED"
        temperature_description: str | None = None  # имя члена enum, например "WARM"
) -> str:
    """
    Возвращает список уникальных исполнителей, соответствующих указанным energy_description и temperature_description.

    :param session: Сессия SQLAlchemy.
    :param account_id: ID пользователя.
    :param energy_description: Имя члена EnergyDescription (например, 'WARM_HEARTED').
    :param temperature_description: Имя члена TemperatureDescription (например, 'WARM').
    :return: Отформатированная строка со списком исполнителей.
    """
    try:
        # Валидация energy_description
        energy_enum = None
        if energy_description:
            try:
                energy_enum = EnergyDescription[energy_description.upper()]
                logger.info(f"Валидное energy_description: {energy_description} -> {energy_enum.value}")
            except KeyError:
                logger.error(f"Недопустимое имя energy_description: {energy_description}")
                return f"Ошибка: Недопустимое имя энергии '{energy_description}'"

        # Валидация temperature_description
        temp_enum = None
        if temperature_description:
            try:
                temp_enum = TemperatureDescription[temperature_description.upper()]
                logger.info(f"Валидное temperature_description: {temperature_description} -> {temp_enum.value}")
            except KeyError:
                logger.error(f"Недопустимое имя temperature_description: {temperature_description}")
                return f"Ошибка: Недопустимое имя температуры '{temperature_description}'"

        # Запрос
        query = (
            select(MusicTrack.artist)
            .distinct()
            .join(
                TrackUserDescription,
                MusicTrack.id == TrackUserDescription.track_id
            )
            .filter(TrackUserDescription.account_id == account_id)
        )
        if energy_enum:
            query = query.filter(TrackUserDescription.energy_description == energy_enum)
        if temp_enum:
            query = query.filter(TrackUserDescription.temperature_description == temp_enum)

        results = session.execute(query).scalars().all()
        logger.info(f"Найдено {len(results)} исполнителей для account_id={account_id}, "
                    f"energy={energy_description}, temp={temperature_description}")

        # Проверка промежуточных данных
        if not results:
            # Проверяем, есть ли записи в track_user_descriptions
            desc_count = session.query(TrackUserDescription).filter(
                TrackUserDescription.account_id == account_id,
                TrackUserDescription.energy_description == energy_enum if energy_enum else True,
                TrackUserDescription.temperature_description == temp_enum if temp_enum else True
            ).count()
            logger.info(f"Найдено {desc_count} записей в track_user_descriptions")
            if desc_count > 0:
                # Проверяем, есть ли треки для этих track_id
                track_ids = session.query(TrackUserDescription.track_id).filter(
                    TrackUserDescription.account_id == account_id,
                    TrackUserDescription.energy_description == energy_enum if energy_enum else True,
                    TrackUserDescription.temperature_description == temp_enum if temp_enum else True
                ).all()
                track_count = session.query(MusicTrack).filter(MusicTrack.id.in_([tid[0] for tid in track_ids])).count()
                logger.info(f"Найдено {track_count} треков в music_tracks для track_ids={track_ids}")
            return "Нет исполнителей для указанных описаний."

        artists = sorted({a for a in results if a})
        return f"Исполнители: {', '.join(artists)}"
    except Exception as e:
        logger.exception(f"Ошибка при получении исполнителей: {e}")
        return "Ошибка при загрузке исполнителей."


def get_tracks_by_artist(
        session: Session,
        artist: str,
        account_id: str | None = None,
        energy_description: str | None = None,  # имя члена enum, например "WARM_HEARTED"
        temperature_description: str | None = None  # имя члена enum, например "WARM"
) -> str:
    """
    Получает список названий треков по исполнителю с опциональной фильтрацией по energy_description и temperature_description.

    :param session: Сессия SQLAlchemy.
    :param artist: Имя исполнителя.
    :param account_id: ID пользователя для фильтрации по тегам (опционально).
    :param energy_description: Имя члена EnergyDescription (например, 'WARM_HEARTED').
    :param temperature_description: Имя члена TemperatureDescription (например, 'WARM').
    :return: Отформатированная строка со списком названий треков.
    """
    try:
        # Валидация energy_description
        energy_enum = None
        if energy_description:
            try:
                energy_enum = EnergyDescription[energy_description.upper()]
                logger.info(f"Валидное energy_description: {energy_description} -> {energy_enum.value}")
            except KeyError:
                logger.error(f"Недопустимое имя energy_description: {energy_description}")
                return f"Ошибка: Недопустимое имя энергии '{energy_description}'"

        # Валидация temperature_description
        temp_enum = None
        if temperature_description:
            try:
                temp_enum = TemperatureDescription[temperature_description.upper()]
                logger.info(f"Валидное temperature_description: {temperature_description} -> {temp_enum.value}")
            except KeyError:
                logger.error(f"Недопустимое имя temperature_description: {temperature_description}")
                return f"Ошибка: Недопустимое имя температуры '{temperature_description}'"

        # Запрос
        query = select(MusicTrack.title).filter(MusicTrack.artist == artist)

        # Если указаны account_id и теги, добавляем JOIN
        if account_id and (energy_enum or temp_enum):
            query = (
                query
                .join(
                    TrackUserDescription,
                    MusicTrack.id == TrackUserDescription.track_id
                )
                .filter(TrackUserDescription.account_id == account_id)
            )
            if energy_enum:
                query = query.filter(TrackUserDescription.energy_description == energy_enum)
            if temp_enum:
                query = query.filter(TrackUserDescription.temperature_description == temp_enum)

        query = query.order_by(MusicTrack.title)
        results = session.execute(query).scalars().all()
        logger.info(f"Найдено {len(results)} треков для исполнителя {artist}, "
                    f"account_id={account_id}, energy={energy_description}, temp={temperature_description}")

        # Форматируем результат
        if not results:
            return f"Нет треков для исполнителя {artist} с указанными описаниями."

        titles = [title for title in results if title]  # Фильтруем None
        if not titles:
            return f"Нет треков с названием для исполнителя {artist}."

        return f"Треки {artist}: {', '.join(sorted(titles))}"
    except Exception as e:
        logger.exception(f"Ошибка при получении треков: {e}")
        return "Ошибка при загрузке треков."


def is_single_artist_by_description(
        session: Session,
        account_id: str,
        energy_description: str | None = None,  # имя члена enum, например "WARM_HEARTED"
        temperature_description: str | None = None  # имя члена enum, например "WARM"
) -> Tuple[bool, str | None]:
    """
    Проверяет, является ли количество исполнителей ровно одним для указанных energy_description и temperature_description.

    :param session: Сессия SQLAlchemy.
    :param account_id: ID пользователя.
    :param energy_description: Имя члена EnergyDescription (например, 'WARM_HEARTED').
    :param temperature_description: Имя члена TemperatureDescription (например, 'WARM').
    :return: Кортеж (is_single, artist), где is_single=True, если ровно один исполнитель, и artist — его имя.
    """
    try:
        # Валидация energy_description
        energy_enum = None
        if energy_description:
            try:
                energy_enum = EnergyDescription[energy_description.upper()]
                logger.info(f"Валидное energy_description: {energy_description} -> {energy_enum.value}")
            except KeyError:
                logger.error(f"Недопустимое имя energy_description: {energy_description}")
                return False, None

        # Валидация temperature_description
        temp_enum = None
        if temperature_description:
            try:
                temp_enum = TemperatureDescription[temperature_description.upper()]
                logger.info(f"Валидное temperature_description: {temperature_description} -> {temp_enum.value}")
            except KeyError:
                logger.error(f"Недопустимое имя temperature_description: {temperature_description}")
                return False, None

        # Запрос
        query = (
            select(MusicTrack.artist)
            .distinct()
            .join(
                TrackUserDescription,
                MusicTrack.id == TrackUserDescription.track_id
            )
            .filter(TrackUserDescription.account_id == account_id)
        )
        if energy_enum:
            query = query.filter(TrackUserDescription.energy_description == energy_enum)
        if temp_enum:
            query = query.filter(TrackUserDescription.temperature_description == temp_enum)

        results = session.execute(query).scalars().all()
        logger.info(f"Найдено {len(results)} исполнителей для account_id={account_id}, "
                    f"energy={energy_description}, temp={temperature_description}")

        # Проверяем количество исполнителей
        artists = [a for a in results if a]  # Фильтруем None
        if len(artists) == 1:
            return True, artists[0]
        return False, None
    except Exception as e:
        logger.exception(f"Ошибка при проверке исполнителей: {e}")
        return False, None


def get_single_track_by_artist(session: Session, artist: str) -> str:
    """
    Проверяет, есть ли у исполнителя ровно один трек, и возвращает его название.

    :param session: Сессия SQLAlchemy.
    :param artist: Имя исполнителя.
    :return: Название трека, если он ровно один, иначе пустая строка.
    """
    try:
        # Запрос
        query = (
            select(MusicTrack.title)
            .filter(MusicTrack.artist == artist)
            .order_by(MusicTrack.title)
        )

        results = session.execute(query).scalars().all()
        logger.info(f"Найдено {len(results)} треков для исполнителя {artist}")

        # Проверяем количество треков
        titles = [title for title in results if title]  # Фильтруем None
        if len(titles) == 1:
            return titles[0]
        return ""
    except Exception as e:
        logger.exception(f"Ошибка при получении треков: {e}")
        return ""


def get_track_id_by_artist_and_title(
        session,
        account_id: str,
        artist: str,
        title: str
) -> Optional[int]:
    """
    Находит track_id по исполнителю и названию трека.

    :param session: Сессия БД
    :param account_id: ID пользователя
    :param artist: Имя исполнителя
    :param title: Название трека
    :return: track_id или None
    """
    try:
        result = (
            session.query(MusicTrack.id)
            .join(TrackUserDescription, MusicTrack.id == TrackUserDescription.track_id)
            .filter(
                TrackUserDescription.account_id == account_id,
                MusicTrack.artist == artist,
                MusicTrack.title == title
            )
            .first()
        )

        if result:
            return result[0]  # result — это tuple (id,)
        return None

    except Exception as e:
        logger.error(f"Ошибка при поиске track_id: {e}")
        return None

def get_track_atmosphere_by_id(
    session: Session,
    account_id: str,
    track_id: int
) -> Optional[Dict[str, str]]:
    """
    Возвращает реальные данные трека + атмосферу по track_id.
    """
    try:
        result = (
            session.query(
                MusicTrack.title,
                MusicTrack.artist,
                MusicTrack.genre,
                TrackUserDescription.energy_description,        # ← ИСПРАВЛЕНО
                TrackUserDescription.temperature_description   # ← ИСПРАВЛЕНО
            )
            .join(TrackUserDescription, MusicTrack.id == TrackUserDescription.track_id)
            .filter(
                TrackUserDescription.account_id == account_id,
                MusicTrack.id == track_id
            )
            .first()
        )

        if not result:
            logger.warning(f"Трек не найден: track_id={track_id}, account_id={account_id}")
            return None

        title, artist, genre, energy_enum, temp_enum = result

        return {
            "title": title or "Unknown Track",
            "artist": artist or "Unknown Artist",
            "genre": genre or "unknown",
            "energy": energy_enum.value if energy_enum else "unknown",  # ← .value
            "temperature": temp_enum.value if temp_enum else "unknown",  # ← .value
            "track_id": track_id
        }

    except Exception as e:
        logger.error(f"Ошибка в get_track_atmosphere_by_id: {e}")
        return None