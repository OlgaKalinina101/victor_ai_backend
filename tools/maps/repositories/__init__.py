"""Репозитории для работы с БД."""

from .game_location_repository import GameLocationRepository
from .osm_repository import OSMRepository
from .place_caption_repository import PlaceCaptionRepository
from .achievement_repository import AchievementRepository
from .journal_repository import JournalRepository
from .stats_repository import StatsRepository
from .walk_session_repository import WalkSessionRepository

__all__ = [
    "GameLocationRepository",
    "OSMRepository",
    "PlaceCaptionRepository",
    "AchievementRepository",
    "JournalRepository",
    "StatsRepository",
    "WalkSessionRepository",
]

