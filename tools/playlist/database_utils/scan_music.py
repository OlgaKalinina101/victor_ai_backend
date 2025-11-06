#!/usr/bin/env python3
import asyncio
import sys
import os

from api.assistant import get_tracks_with_descriptions
from tools.playlist.database_utils.music_scanner import MusicScanner

# Добавляем корень проекта в Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    music_folder = r"C:\Users\Alien\Downloads\Downloads"
    scanner = MusicScanner(music_folder)
    print("🎵 Запускаю сканирование музыки...")
    scanner.scan_folder()  # Раскомментируй, если нужно обновить данные
    print("📊 Получаю статистику...")
    stats = scanner.get_statistics()

    print("\n" + "=" * 50)
    print("МУЗЫКАЛЬНАЯ СТАТИСТИКА:")
    print(f"Всего треков: {stats['total_tracks']}")
    print(f"Уникальных исполнителей: {stats['unique_artists']}")
    print(f"Уникальных жанров: {stats['unique_genres']}")
    print(f"Уникальных альбомов: {stats['unique_albums']}")
    print(f"Средняя длительность: {stats['avg_duration_sec']} сек")
    print(f"Общий размер: {stats['total_size_mb']} МБ")
    print(f"Средний битрейт: {stats['avg_bitrate_kbps']} кбит/с")
    print(f"Диапазон длительности: {stats['duration_range_sec']['min']} - {stats['duration_range_sec']['max']} сек")

    print("\nВсе жанры:")
    for genre in stats['genres']:
        print(f"  {genre['genre']}: {genre['count']} треков")

    print("\nВсе исполнители:")
    for artist in stats['artists']:
        print(f"  {artist['artist']}: {artist['count']} треков")

    print("\nВсе альбомы:")
    for album in stats['albums']:
        print(f"  {album['album']}: {album['count']} треков")

    print("\nВсе годы:")
    for year in stats['years']:
        print(f"  {year['year']}: {year['count']} треков")

    print("=" * 50)


if __name__ == "__main__":
    main()
    #tracks = asyncio.run(get_tracks_with_descriptions(account_id="test_user"))
    #print(tracks)