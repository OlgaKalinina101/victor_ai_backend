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

import re
import googlemaps
from settings import settings

FASTFOOD_KEYWORDS = ["rostic", "kfc", "burger king", "mcdonald", "макдоналд"]

def is_fastfood(place):
    name = place.get("name", "").lower()
    return any(keyword in name for keyword in FASTFOOD_KEYWORDS)


def get_nearby_restaurants(latitude, longitude, radius=1500, limit=3):
    """Делает запрос к API GOOGLE MAPS и фильтрует fast_food"""
    gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)

    places_result = gmaps.places_nearby(
        location=(latitude, longitude),
        radius=radius,
        type="restaurant",
        rank_by="prominence"
    )

    all_places = places_result.get("results", [])
    print(f"DEBUG all_places {all_places}")

    # Фильтруем те, что НЕ fast_food
    filtered = [
        place for place in all_places
        if "fast_food" not in place.get("types", []) and not is_fastfood(place)
    ]

    top_places = filtered[:limit]

    return [
        {
            "name": place.get("name"),
            "rating": place.get("rating"),
            "address": place.get("vicinity"),
            "location": place.get("geometry", {}).get("location"),
            "types": place.get("types", []),
            "map_url": (
                f"https://www.google.com/maps/search/?api=1&query={place['geometry']['location']['lat']},{place['geometry']['location']['lng']}"
                if place.get("geometry") and place["geometry"].get("location")
                else None
            )
        }
        for place in top_places
    ]
