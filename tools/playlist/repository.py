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

"""Репозиторий для работы с музыкальными треками."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from infrastructure.database.models import (
    MusicTrack,
    TrackPlayHistory,
    TrackUserDescription,
    PlaylistMoment,
)
from infrastructure.database.database_enums import (
    EnergyDescription,
    TemperatureDescription,
)
from infrastructure.logging.logger import setup_logger

logger = setup_logger("playlist_repository")


class PlaylistRepository:
    """Репозиторий для работы с треками и историей прослушиваний."""
    
    def __init__(self, session: Session):
        self.session = session
    
    # ============ MusicTrack ============
    
    def get_all_tracks(self) -> List[MusicTrack]:
        """Получает все треки."""
        return self.session.query(MusicTrack).all()
    
    def get_track_by_id(self, track_id: int) -> Optional[MusicTrack]:
        """Получает трек по ID."""
        return self.session.query(MusicTrack).filter_by(id=track_id).first()
    
    def get_random_track(self) -> Optional[MusicTrack]:
        """Получает случайный трек."""
        return self.session.query(MusicTrack).order_by(func.random()).first()
    
    def get_tracks_with_descriptions(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Получает все треки с их описаниями для пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список словарей с данными треков и их описаниями
        """
        # LEFT JOIN для получения описаний (если есть)
        stmt = (
            self.session.query(MusicTrack, TrackUserDescription)
            .outerjoin(
                TrackUserDescription,
                (MusicTrack.id == TrackUserDescription.track_id) &
                (TrackUserDescription.account_id == account_id)
            )
        )
        result = stmt.all()
        
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
    
    # ============ TrackUserDescription ============
    
    def get_track_description(self, account_id: str, track_id: int) -> Optional[TrackUserDescription]:
        """Получает описание трека для пользователя."""
        return (
            self.session.query(TrackUserDescription)
            .filter_by(account_id=account_id, track_id=track_id)
            .first()
        )
    
    def upsert_track_description(
        self,
        account_id: str,
        track_id: int,
        energy_description: Optional[EnergyDescription] = None,
        temperature_description: Optional[TemperatureDescription] = None
    ) -> TrackUserDescription:
        """
        Создаёт или обновляет описание трека.
        
        Args:
            account_id: ID пользователя
            track_id: ID трека
            energy_description: Энергия трека
            temperature_description: Температура трека
            
        Returns:
            Созданное/обновлённое описание
        """
        # ВАЖНО: в таблице PK = id (autoincrement), поэтому session.merge() без id
        # может создавать дубли. Делаем явный upsert через поиск по (account_id, track_id).
        description = (
            self.session.query(TrackUserDescription)
            .filter_by(account_id=account_id, track_id=track_id)
            .order_by(TrackUserDescription.id.desc())
            .first()
        )

        if description:
            description.energy_description = energy_description
            description.temperature_description = temperature_description
        else:
            description = TrackUserDescription(
                account_id=account_id,
                track_id=track_id,
                energy_description=energy_description,
                temperature_description=temperature_description,
            )
            self.session.add(description)

        self.session.commit()
        self.session.refresh(description)

        logger.info(f"Upsert описание трека {track_id} для {account_id}")
        return description
    
    # ============ TrackPlayHistory ============
    
    def get_play_history(self, account_id: str, limit: Optional[int] = None) -> List[TrackPlayHistory]:
        """
        Получает историю прослушиваний пользователя.
        
        Args:
            account_id: ID пользователя
            limit: Ограничение количества записей (опционально)
            
        Returns:
            Список истории, отсортированный по дате (новые первыми)
        """
        query = (
            self.session.query(TrackPlayHistory)
            .options(joinedload(TrackPlayHistory.track))
            .filter(TrackPlayHistory.account_id == account_id)
            .order_by(TrackPlayHistory.started_at.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def create_play_record(
        self,
        account_id: str,
        track_id: int,
        started_at: datetime,
        ended_at: Optional[datetime] = None,
        duration_played: Optional[int] = None,
        energy_on_play: Optional[EnergyDescription] = None,
        temperature_on_play: Optional[TemperatureDescription] = None
    ) -> TrackPlayHistory:
        """
        Создаёт запись о прослушивании трека.
        
        Args:
            account_id: ID пользователя
            track_id: ID трека
            started_at: Время начала
            ended_at: Время окончания (опционально)
            duration_played: Длительность (секунды)
            energy_on_play: Энергия при прослушивании
            temperature_on_play: Температура при прослушивании
            
        Returns:
            Созданная запись
        """
        record = TrackPlayHistory(
            account_id=account_id,
            track_id=track_id,
            started_at=started_at,
            ended_at=ended_at,
            duration_played=duration_played,
            energy_on_play=energy_on_play,
            temperature_on_play=temperature_on_play
        )
        
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        
        logger.info(f"Создана запись прослушивания: track={track_id}, user={account_id}")
        return record
    
    def get_track_statistics(self, account_id: str, track_id: int) -> Dict[str, Any]:
        """
        Получает статистику прослушиваний конкретного трека.
        
        Args:
            account_id: ID пользователя
            track_id: ID трека
            
        Returns:
            Словарь со статистикой (play_count, total_duration, etc)
        """
        history = (
            self.session.query(TrackPlayHistory)
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.track_id == track_id
            )
            .all()
        )
        
        play_count = len(history)
        total_duration = sum(h.duration_played or 0 for h in history)
        
        return {
            "play_count": play_count,
            "total_duration": total_duration,
            "last_played": history[0].started_at if history else None
        }
    
    def get_most_played_tracks(self, account_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получает топ самых прослушиваемых треков.
        
        Args:
            account_id: ID пользователя
            limit: Количество треков в топе
            
        Returns:
            Список треков с количеством прослушиваний
        """
        result = (
            self.session.query(
                MusicTrack,
                func.count(TrackPlayHistory.id).label('play_count')
            )
            .join(TrackPlayHistory, MusicTrack.id == TrackPlayHistory.track_id)
            .filter(TrackPlayHistory.account_id == account_id)
            .group_by(MusicTrack.id)
            .order_by(func.count(TrackPlayHistory.id).desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                "track_id": track.id,
                "title": track.title,
                "artist": track.artist,
                "play_count": count
            }
            for track, count in result
        ]
    
    def get_tracks_by_energy_temperature(
        self,
        account_id: str,
        energy: Optional[EnergyDescription] = None,
        temperature: Optional[TemperatureDescription] = None,
        limit: int = 20
    ) -> List[MusicTrack]:
        """
        Подбирает треки по энергии и температуре (для "волны").
        
        Args:
            account_id: ID пользователя
            energy: Фильтр по энергии (опционально)
            temperature: Фильтр по температуре (опционально)
            limit: Максимальное количество треков
            
        Returns:
            Список треков в случайном порядке
        """
        query = (
            self.session.query(MusicTrack)
            .join(
                TrackUserDescription,
                TrackUserDescription.track_id == MusicTrack.id
            )
            .filter(TrackUserDescription.account_id == account_id)
        )
        
        # Фильтр по энергии
        if energy:
            query = query.filter(TrackUserDescription.energy_description == energy)
        
        # Фильтр по температуре
        if temperature:
            query = query.filter(TrackUserDescription.temperature_description == temperature)
        
        # Случайный порядок для "волны"
        query = query.order_by(func.random()).limit(limit)
        
        return query.all()
    
    def get_period_statistics(self, account_id: str, start_date: datetime) -> Dict[str, Any]:
        """
        Получает агрегированную статистику за период.
        
        Args:
            account_id: ID пользователя
            start_date: Начало периода
            
        Returns:
            Словарь со статистикой (total_plays, top_tracks, top_energy, etc)
        """
        # Все прослушивания за период
        history_query = (
            self.session.query(TrackPlayHistory)
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.started_at >= start_date
            )
        )
        
        total_plays = history_query.count()
        
        if total_plays == 0:
            return {
                "total_plays": 0,
                "top_tracks": [],
                "top_energy": None,
                "top_temperature": None,
                "average_duration": 0
            }
        
        # Топ треков за период
        top_tracks_q = (
            self.session.query(
                MusicTrack.title,
                MusicTrack.artist,
                func.count(TrackPlayHistory.id).label("plays")
            )
            .join(MusicTrack, MusicTrack.id == TrackPlayHistory.track_id)
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.started_at >= start_date
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
        
        # Самая частая энергия
        top_energy = (
            self.session.query(TrackPlayHistory.energy_on_play, func.count().label("cnt"))
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.energy_on_play.isnot(None),
                TrackPlayHistory.started_at >= start_date
            )
            .group_by(TrackPlayHistory.energy_on_play)
            .order_by(func.count().desc())
            .first()
        )
        
        # Самая частая температура
        top_temperature = (
            self.session.query(TrackPlayHistory.temperature_on_play, func.count().label("cnt"))
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.temperature_on_play.isnot(None),
                TrackPlayHistory.started_at >= start_date
            )
            .group_by(TrackPlayHistory.temperature_on_play)
            .order_by(func.count().desc())
            .first()
        )
        
        # Средняя длительность
        avg_duration = (
            self.session.query(func.avg(TrackPlayHistory.duration_played))
            .filter(
                TrackPlayHistory.account_id == account_id,
                TrackPlayHistory.duration_played.isnot(None),
                TrackPlayHistory.started_at >= start_date
            )
            .scalar() or 0
        )
        
        return {
            "total_plays": total_plays,
            "top_tracks": top_tracks,
            "top_energy": top_energy[0].value if top_energy else None,
            "top_temperature": top_temperature[0].value if top_temperature else None,
            "average_duration": round(avg_duration, 1)
        }
    
    # ============ PlaylistMoment ============
    
    def create_playlist_moment(
        self,
        account_id: str,
        stage1_text: Optional[str] = None,
        stage2_text: Optional[str] = None,
        stage3_text: Optional[str] = None,
        track_id: Optional[int] = None
    ) -> PlaylistMoment:
        """
        Создаёт запись момента выбора плейлиста.
        
        Args:
            account_id: ID пользователя
            stage1_text: Текст из stage 1 (выбор энергии/температуры)
            stage2_text: Текст из stage 2 (выбор артиста)
            stage3_text: Текст из stage 3 (выбор трека)
            track_id: ID выбранного трека
            
        Returns:
            Созданная запись
        """
        moment = PlaylistMoment(
            account_id=account_id,
            stage1_text=stage1_text,
            stage2_text=stage2_text,
            stage3_text=stage3_text,
            track_id=track_id
        )
        
        self.session.add(moment)
        self.session.commit()
        self.session.refresh(moment)
        
        logger.info(f"Создан playlist moment: id={moment.id}, user={account_id}, track={track_id}")
        return moment
    
    def get_playlist_moments(
        self,
        account_id: str,
        limit: Optional[int] = 20
    ) -> List[PlaylistMoment]:
        """
        Получает историю моментов выбора плейлиста.
        
        Args:
            account_id: ID пользователя
            limit: Ограничение количества записей
            
        Returns:
            Список моментов, отсортированный по дате (новые первыми)
        """
        query = (
            self.session.query(PlaylistMoment)
            .filter(PlaylistMoment.account_id == account_id)
            .order_by(PlaylistMoment.created_at.desc())
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

