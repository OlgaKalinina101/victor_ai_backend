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

from infrastructure.logging.logger import setup_logger

logger=setup_logger("places")

FASTFOOD_KEYWORDS = ["rostic", "kfc", "burger king", "mcdonald", "макдоналд"]


def is_fastfood(place):
    name = place.get("name", "").lower()
    return any(keyword in name for keyword in FASTFOOD_KEYWORDS)


def get_restaurants_simple(lat, lng, radius=1500, limit=5):
    import requests

    query = f"""
    [out:json];
    node["amenity"="restaurant"](around:{radius},{lat},{lng});
    out {limit};
    """

    response = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={'data': query}
    )
    return response.json()


def prepare_restaurants_for_ai(osm_data):
    """Подготавливаем данные в удобном для AI формате - все теги как есть"""

    places_list = []
    for element in osm_data.get('elements', []):
        tags = element.get('tags', {})

        # Копируем все теги кроме name и contact (их обрабатываем отдельно)
        all_tags = tags.copy()

        # Убираем поля, которые обрабатываем отдельно
        excluded_fields = ['name', 'cuisine', 'contact:phone', 'contact:website',
                           'contact:email', 'contact:facebook', 'contact:vk',
                           'contact:instagram']

        for field in excluded_fields:
            all_tags.pop(field, None)

        place_info = {
            'name': tags.get('name', ''),
            'cuisine': tags.get('cuisine', ''),
            'tags': all_tags,  # Все остальные теги как есть
            'contacts': {
                'phone': tags.get('contact:phone'),
                'website': tags.get('contact:website'),
                'email': tags.get('contact:email')
            },
            'map_url': f"https://www.openstreetmap.org/?mlat={element['lat']}&mlon={element['lon']}#map=18/{element['lat']}/{element['lon']}"
        }

        places_list.append(place_info)

    return places_list


def format_restaurants_for_prompt(restaurants_list):
    """Форматируем для промпта"""

    formatted_places = []

    for i, place in enumerate(restaurants_list, 1):
        place_text = f"{i}. {place['name']}\n"

        # Кухня
        if place['cuisine']:
            place_text += f"   Кухня: {place['cuisine']}\n"

        # Все теги
        if place['tags']:
            tags_text = "   • " + "\n   • ".join([f"{k}: {v}" for k, v in place['tags'].items()])
            place_text += f"   Особенности:\n{tags_text}\n"

        # Контакты (только заполненные)
        contacts = []
        if place['contacts']['phone']:
            contacts.append(f"телефон: {place['contacts']['phone']}")
        if place['contacts']['website']:
            contacts.append(f"сайт: {place['contacts']['website']}")
        if place['contacts']['email']:
            contacts.append(f"email: {place['contacts']['email']}")

        if contacts:
            place_text += f"   Контакты: {', '.join(contacts)}\n"

        # Ссылка
        place_text += f"   Ссылка: {place['map_url']}\n"

        formatted_places.append(place_text)

    return "\n".join(formatted_places)

def get_nearby_restaurants_osm(latitude, longitude, radius=1500, limit=5):
    """Возвращаем сырые данные для AI"""
    osm_data = get_restaurants_simple(latitude, longitude, radius, limit)
    places_data = prepare_restaurants_for_ai(osm_data)
    return format_restaurants_for_prompt(places_data)