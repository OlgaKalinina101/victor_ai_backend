"""Сервисы для работы с картами и локациями."""

from .game_location_service import GameLocationService
from .osm_api_service import OSMAPIService
from .place_caption_service import PlaceCaptionService

__all__ = ["GameLocationService", "OSMAPIService", "PlaceCaptionService"]

