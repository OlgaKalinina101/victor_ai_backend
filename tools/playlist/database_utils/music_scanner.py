# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

import os
import logging
from pathlib import Path
from tinytag import TinyTag
from sqlalchemy import text, func

from infrastructure.database.models import MusicTrack
from infrastructure.database.session import Database

logger = logging.getLogger("music_scanner")


class MusicScanner:
    def __init__(self, music_folder: str):
        self.music_folder = Path(music_folder)
        self.supported_formats = {'.mp3', '.wav', '.flac', '.m4a'}


        self.db = Database()

    def extract_metadata(self, file_path: Path) -> dict:
        """Извлекает метаданные из аудиофайла"""
        try:
            tag = TinyTag.get(file_path)

            return {
                'filename': file_path.name,
                'file_path': str(file_path),
                'title': tag.title or file_path.stem,
                'artist': tag.artist or 'Unknown Artist',
                'album': tag.album or 'Unknown Album',
                'year': int(tag.year) if tag.year and tag.year.isdigit() else None,
                'genre': tag.genre or 'Unknown',
                'duration': tag.duration,
                'track_number': int(tag.track) if tag.track else None,
                'bitrate': tag.bitrate,
                'file_size': tag.filesize
            }
        except Exception as e:
            logger.error(f"Ошибка чтения {file_path}: {e}")
            return None

    def scan_folder(self):
        """Сканирует папку и сохраняет треки в БД"""
        logger.info(f"Сканирую папку: {self.music_folder}")

        if not self.music_folder.exists():
            raise FileNotFoundError(f"Папка не найдена: {self.music_folder}")

        music_files = [
            f for f in self.music_folder.iterdir()
            if f.is_file() and f.suffix.lower() in self.supported_formats
        ]

        logger.info(f"Найдено файлов: {len(music_files)}")

        # Используем твою стандартную сессию
        db_session = self.db.get_session()

        try:
            processed = 0

            for file_path in music_files:
                try:
                    metadata = self.extract_metadata(file_path)
                    if metadata:
                        # Проверка дубликатов
                        existing = db_session.execute(
                            text("SELECT id FROM music_tracks WHERE file_path = :file_path"),
                            {"file_path": metadata['file_path']}
                        ).scalar()

                        if not existing:
                            track = MusicTrack(**metadata)
                            db_session.add(track)
                            logger.info(f"✅ Добавлен: {metadata['artist']} - {metadata['title']}")
                        else:
                            logger.info(f"⏭️ Уже в БД: {metadata['artist']} - {metadata['title']}")

                    processed += 1
                    if processed % 10 == 0:  # Коммитим каждые 10 файлов
                        db_session.commit()
                        logger.info(f"💾 Сохранено {processed}/{len(music_files)}")

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки {file_path}: {e}")
                    continue

            # Финальный коммит
            db_session.commit()
            logger.info("🎵 Сканирование завершено!")

        except Exception as e:
            db_session.rollback()
            logger.error(f"❌ Критическая ошибка: {e}")
            raise
        finally:
            db_session.close()

    def get_statistics(self):
        session = self.db.get_session()
        try:
            # Получаем статистику
            total_tracks = session.query(MusicTrack).count()
            unique_artists = session.query(func.count(func.distinct(MusicTrack.artist))).scalar()
            unique_genres = session.query(func.count(func.distinct(MusicTrack.genre))).scalar()
            unique_albums = session.query(func.count(func.distinct(MusicTrack.album))).scalar()
            avg_duration = session.query(func.avg(MusicTrack.duration)).scalar() or 0
            total_size = session.query(func.sum(MusicTrack.file_size)).scalar() or 0
            avg_bitrate = session.query(func.avg(MusicTrack.bitrate)).scalar() or 0
            min_duration = session.query(func.min(MusicTrack.duration)).scalar() or 0
            max_duration = session.query(func.max(MusicTrack.duration)).scalar() or 0

            # Все жанры с количеством треков
            genres = (
                session.query(MusicTrack.genre, func.count(MusicTrack.id).label("count"))
                .group_by(MusicTrack.genre)
                .order_by(func.count(MusicTrack.id).desc())
                .all()
            )
            genres = [{"genre": g.genre or "Unknown", "count": g.count} for g in genres]

            # Все исполнители с количеством треков
            artists = (
                session.query(MusicTrack.artist, func.count(MusicTrack.id).label("count"))
                .group_by(MusicTrack.artist)
                .order_by(func.count(MusicTrack.id).desc())
                .all()
            )
            artists = [{"artist": a.artist or "Unknown", "count": a.count} for a in artists]

            # Все альбомы с количеством треков
            albums = (
                session.query(MusicTrack.album, func.count(MusicTrack.id).label("count"))
                .group_by(MusicTrack.album)
                .order_by(func.count(MusicTrack.id).desc())
                .all()
            )
            albums = [{"album": a.album or "Unknown", "count": a.count} for a in albums]

            # Все годы с количеством треков
            years = (
                session.query(MusicTrack.year, func.count(MusicTrack.id).label("count"))
                .group_by(MusicTrack.year)
                .order_by(MusicTrack.year)
                .all()
            )
            years = [{"year": y.year or "Unknown", "count": y.count} for y in years]

            return {
                "total_tracks": total_tracks,
                "unique_artists": unique_artists,
                "unique_genres": unique_genres,
                "unique_albums": unique_albums,
                "avg_duration_sec": round(avg_duration, 2),
                "total_size_mb": round(total_size / (1024 * 1024), 2),  # Переводим в МБ
                "avg_bitrate_kbps": round(avg_bitrate, 2),
                "duration_range_sec": {"min": round(min_duration, 2), "max": round(max_duration, 2)},
                "genres": genres,
                "artists": artists,
                "albums": albums,
                "years": years
            }
        finally:
            session.close()