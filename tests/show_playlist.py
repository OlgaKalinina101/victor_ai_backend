# scripts/view_tracks.py
import argparse
from typing import Optional
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from infrastructure.database.models import MusicTrack
from infrastructure.database.session import Database

db = Database()
def view_tracks(
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
):
    with Session(db.engine) as session:
        query = select(MusicTrack)

        # Фильтр по поиску (title, artist, album)
        if search:
            like_pattern = f"%{search}%"
            query = query.where(
                MusicTrack.title.ilike(like_pattern) |
                MusicTrack.artist.ilike(like_pattern) |
                MusicTrack.album.ilike(like_pattern)
            )

        # Сортировка
        order_column = getattr(MusicTrack, sort_by, MusicTrack.id)
        if order == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column)

        # Пагинация
        query = query.limit(limit).offset(offset)

        tracks = session.scalars(query).all()

        if not tracks:
            print("No tracks found.")
            return

        # Красивый вывод
        print(f"\nFound {len(tracks)} tracks:\n")
        print("-" * 120)
        for t in tracks:
            print(
                f"ID: {t.id:<4} | "
                f"Title: {t.title or 'Unknown':<30} | "
                f"Artist: {t.artist or 'Unknown':<20} | "
                f"Album: {t.album or '—':<25} | "
                f"Year: {t.year or '—':<4} | "
                f"Duration: {format_duration(t.duration):<6} | "
                f"File: {t.filename}"
            )
        print("-" * 120)


def format_duration(seconds: Optional[float]) -> str:
    if not seconds:
        return "—"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View music tracks from DB")
    parser.add_argument("--limit", type=int, default=50, help="Max tracks to show")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N tracks")
    parser.add_argument("--search", type=str, help="Search in title/artist/album")
    parser.add_argument("--sort", type=str, default="id", choices=["id", "title", "artist", "year", "duration"])
    parser.add_argument("--order", type=str, default="asc", choices=["asc", "desc"])

    args = parser.parse_args()

    view_tracks(
        limit=args.limit,
        offset=args.offset,
        search=args.search,
        sort_by=args.sort,
        order=args.order
    )