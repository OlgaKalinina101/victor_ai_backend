from enum import Enum
from typing import Dict, List

# ========================================
# 1. Основные типы мест (без дублей!)
# ========================================
class PlaceType(Enum):
    """Типы мест — один тег OSM → один PlaceType"""
    CAFE = "cafe"                    # ← amenity=cafe, coffee_shop
    RESTAURANT = "restaurant"        # ← amenity=restaurant
    BAR = "bar"                      # ← amenity=bar, pub
    FAST_FOOD = "fast_food"          # ← amenity=fast_food
    PARK = "park"                    # ← leisure=park
    MUSEUM = "museum"                # ← tourism=museum
    CINEMA = "cinema"                # ← amenity=cinema
    THEATRE = "theatre"              # ← amenity=theatre
    LIBRARY = "library"              # ← amenity=library
    GYM = "gym"                      # ← leisure=sports_centre + sport=fitness
    PHARMACY = "pharmacy"            # ← amenity=pharmacy
    HOSPITAL = "hospital"            # ← amenity=hospital
    SHOPPING_MALL = "shopping_mall"  # ← shop=mall
    SUPERMARKET = "supermarket"      # ← shop=supermarket
    BOOKSTORE = "bookstore"          # ← shop=books
    BENCH = "bench"                  # ← amenity=bench
    DRINKING_WATER = "drinking_water"# ← amenity=drinking_water
    BAKERY = "bakery"                # ← shop=bakery
    CONVENIENCE = "convenience"      # ← shop=convenience
    ATTRACTION = "attraction"        # ← tourism=attraction
    SPORTS_CENTRE = "sports_centre"  # ← leisure=sports_centre
    SWIMMING_POOL = "swimming_pool"  # ← leisure=swimming_pool
    BEACH = "beach"                  # ← natural=beach
    FITNESS_CENTRE = "fitness_centre"# ← подтип GYM, но оставим для точности

class PlaceAmenity(Enum):
    """Удобства/фичи места"""
    WIFI = "wifi"
    PARKING = "parking"
    WHEELCHAIR_ACCESS = "wheelchair_access"
    OUTDOOR_SEATING = "outdoor_seating"
    PET_FRIENDLY = "pet_friendly"
    CARD_PAYMENT = "card_payment"
    DELIVERY = "delivery"
    TAKEAWAY = "takeaway"

# ========================================
# OSM → PlaceType: точное сопоставление
# ========================================
OSM_TO_PLACE_TYPE: Dict[str, Dict[str, PlaceType]] = {
    "amenity": {
        "cafe": PlaceType.CAFE,
        "coffee_shop": PlaceType.CAFE,           # ← дубликат
        "restaurant": PlaceType.RESTAURANT,
        "fast_food": PlaceType.FAST_FOOD,
        "bar": PlaceType.BAR,
        "pub": PlaceType.BAR,                    # ← дубликат
        "pharmacy": PlaceType.PHARMACY,
        "hospital": PlaceType.HOSPITAL,
        "cinema": PlaceType.CINEMA,
        "theatre": PlaceType.THEATRE,
        "library": PlaceType.LIBRARY,
        "bench": PlaceType.BENCH,
        "drinking_water": PlaceType.DRINKING_WATER,
    },
    "shop": {
        "supermarket": PlaceType.SUPERMARKET,
        "mall": PlaceType.SHOPPING_MALL,
        "books": PlaceType.BOOKSTORE,
        "bakery": PlaceType.BAKERY,
        "convenience": PlaceType.CONVENIENCE,
    },
    "leisure": {
        "park": PlaceType.PARK,
        "sports_centre": PlaceType.SPORTS_CENTRE,
        "fitness_centre": PlaceType.FITNESS_CENTRE,
        "swimming_pool": PlaceType.SWIMMING_POOL,
    },
    "tourism": {
        "museum": PlaceType.MUSEUM,
        "attraction": PlaceType.ATTRACTION,
    },
    "natural": {
        "beach": PlaceType.BEACH,
    },
    # Можно расширять: highway, landuse и т.д.
}

class HighwayTag(Enum):
    """Дороги — только нужные для навигации пешком"""
    FOOTWAY = "footway"
    PEDESTRIAN = "pedestrian"
    SERVICE = "service"
    RESIDENTIAL = "residential"
    TERTIARY = "tertiary"
    SECONDARY = "secondary"
    PRIMARY = "primary"
    PATH = "path"

class LanduseTag(Enum):
    """Очертания местности — полигоны"""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    RETAIL = "retail"
    INDUSTRIAL = "industrial"
    FOREST = "forest"

class NaturalTag(Enum):
    """Природа"""
    WATER = "water"
    WOOD = "wood"


class LeisureTag(Enum):
    """Досуг (пересекается с POI)"""
    PARK = "park"

# ========================================
# Метаданные для Android UI
# ========================================

PLACE_TYPE_METADATA: Dict[PlaceType, Dict] = {
    PlaceType.CAFE: {
        "ru": "Кафе / Кофейня",
        "en": "Cafe",
        "emoji": "☕",
"icon_url": "/static/place_metadata.xml",
        "color": "#6F4E37",
        "category": "food"
    },
    PlaceType.RESTAURANT: {
        "ru": "Ресторан",
        "en": "Restaurant",
        "emoji": "🍽️",
"icon_url": "/static/place_metadata.xml",
        "color": "#E74C3C",
        "category": "food"
    },
    PlaceType.BAR: {
        "ru": "Бар / Паб",
        "en": "Bar / Pub",
        "emoji": "🍺",
"icon_url": "/static/place_metadata.xml",
        "color": "#F39C12",
        "category": "food"
    },
    PlaceType.FAST_FOOD: {
        "ru": "Фастфуд",
        "en": "Fast Food",
        "emoji": "🍔",
"icon_url": "/static/place_metadata.xml",
        "color": "#E67E22",
        "category": "food"
    },
    PlaceType.PARK: {
        "ru": "Парк",
        "en": "Park",
        "emoji": "🌳",
"icon_url": "/static/place_metadata.xml",
        "color": "#27AE60",
        "category": "nature"
    },
    PlaceType.MUSEUM: {
        "ru": "Музей",
        "en": "Museum",
        "emoji": "🏛️",
"icon_url": "/static/place_metadata.xml",
        "color": "#8E44AD",
        "category": "culture"
    },
    PlaceType.CINEMA: {
        "ru": "Кинотеатр",
        "en": "Cinema",
        "emoji": "🎬",
"icon_url": "/static/place_metadata.xml",
        "color": "#2C3E50",
        "category": "entertainment"
    },
    PlaceType.THEATRE: {
        "ru": "Театр",
        "en": "Theatre",
        "emoji": "🎭",
"icon_url": "/static/place_metadata.xml",
        "color": "#9B59B6",
        "category": "culture"
    },
    PlaceType.LIBRARY: {
        "ru": "Библиотека",
        "en": "Library",
        "emoji": "📚",
"icon_url": "/static/place_metadata.xml",
        "color": "#3498DB",
        "category": "culture"
    },
    PlaceType.GYM: {
        "ru": "Фитнес / Спортзал",
        "en": "Gym",
        "emoji": "🏋️",
"icon_url": "/static/place_metadata.xml",
        "color": "#E74C3C",
        "category": "sport"
    },
    PlaceType.PHARMACY: {
        "ru": "Аптека",
        "en": "Pharmacy",
        "emoji": "💊",
"icon_url": "/static/place_metadata.xml",
        "color": "#E91E63",
        "category": "health"
    },
    PlaceType.HOSPITAL: {
        "ru": "Больница",
        "en": "Hospital",
        "emoji": "🏥",
"icon_url": "/static/place_metadata.xml",
        "color": "#C0392B",
        "category": "health"
    },
    PlaceType.SHOPPING_MALL: {
        "ru": "Торговый центр",
        "en": "Shopping Mall",
        "emoji": "🛍️",
"icon_url": "/static/place_metadata.xml",
        "color": "#9B59B6",
        "category": "shop"
    },
    PlaceType.SUPERMARKET: {
        "ru": "Супермаркет",
        "en": "Supermarket",
        "emoji": "🛒",
"icon_url": "/static/place_metadata.xml",
        "color": "#2980B9",
        "category": "shop"
    },
    PlaceType.BOOKSTORE: {
        "ru": "Книжный магазин",
        "en": "Bookstore",
        "emoji": "📖",
"icon_url": "/static/place_metadata.xml",
        "color": "#8D6E63",
        "category": "shop"
    },
    PlaceType.BENCH: {
        "ru": "Скамейка",
        "en": "Bench",
        "emoji": "🪑",
"icon_url": "/static/place_metadata.xml",
        "color": "#7F8C8D",
        "category": "rest"
    },
    PlaceType.DRINKING_WATER: {
        "ru": "Питьевая вода",
        "en": "Drinking Water",
        "emoji": "🚰",
"icon_url": "/static/place_metadata.xml",
        "color": "#3498DB",
        "category": "utility"
    },
    PlaceType.BAKERY: {
        "ru": "Пекарня",
        "en": "Bakery",
        "emoji": "🥖",
"icon_url": "/static/place_metadata.xml",
        "color": "#F1C40F",
        "category": "food"
    },
    PlaceType.CONVENIENCE: {
        "ru": "Мини-маркет",
        "en": "Convenience Store",
        "emoji": "🏪",
"icon_url": "/static/place_metadata.xml",
        "color": "#95A5A6",
        "category": "shop"
    },
    PlaceType.ATTRACTION: {
        "ru": "Достопримечательность",
        "en": "Attraction",
        "emoji": "⭐",
"icon_url": "/static/place_metadata.xml",
        "color": "#F39C12",
        "category": "culture"
    },
    PlaceType.SPORTS_CENTRE: {
        "ru": "Спорткомплекс",
        "en": "Sports Centre",
        "emoji": "🏟️",
"icon_url": "/static/place_metadata.xml",
        "color": "#27AE60",
        "category": "sport"
    },
    PlaceType.FITNESS_CENTRE: {
        "ru": "Фитнес-центр",
        "en": "Fitness Centre",
        "emoji": "💪",
"icon_url": "/static/place_metadata.xml",
        "color": "#E74C3C",
        "category": "sport"
    },
    PlaceType.SWIMMING_POOL: {
        "ru": "Бассейн",
        "en": "Swimming Pool",
        "emoji": "🏊",
"icon_url": "/static/place_metadata.xml",
        "color": "#3498DB",
        "category": "sport"
    },
    PlaceType.BEACH: {
        "ru": "Пляж",
        "en": "Beach",
        "emoji": "🏖️",
"icon_url": "/static/place_metadata.xml",
        "color": "#F1C40F",
        "category": "nature"
    },
}

AMENITY_METADATA: Dict[PlaceAmenity, Dict] = {
    PlaceAmenity.WIFI: {
        "ru": "Wi-Fi",
        "en": "Wi-Fi",
        "emoji": "📶",
"icon_url": "/static/place_metadata.xml"
    },
    PlaceAmenity.PARKING: {
        "ru": "Парковка",
        "en": "Parking",
        "emoji": "🅿️",
"icon_url": "/static/place_metadata.xml"
    },
    PlaceAmenity.WHEELCHAIR_ACCESS: {
        "ru": "Доступ для колясок",
        "en": "Wheelchair Access",
        "emoji": "♿",
"icon_url": "/static/place_metadata.xml"
    },
    PlaceAmenity.OUTDOOR_SEATING: {
        "ru": "Летняя веранда",
        "en": "Outdoor Seating",
        "emoji": "☀️",
"icon_url": "/static/place_metadata.xml"
    },
    PlaceAmenity.PET_FRIENDLY: {
        "ru": "С питомцами",
        "en": "Pet-friendly",
        "emoji": "🐕",
"icon_url": "/static/place_metadata.xml"
    },
    PlaceAmenity.CARD_PAYMENT: {
        "ru": "Оплата картой",
        "en": "Card Payment",
        "emoji": "💳",
"icon_url": "/static/place_metadata.xml"
    },
    PlaceAmenity.DELIVERY: {
        "ru": "Доставка",
        "en": "Delivery",
        "emoji": "🚚",
"icon_url": "/static/place_metadata.xml"
    },
    PlaceAmenity.TAKEAWAY: {
        "ru": "На вынос",
        "en": "Takeaway",
        "emoji": "🥡",
"icon_url": "/static/place_metadata.xml"
    },
}

# ========================================
# Helper functions
# ========================================

def get_place_display_name(place_type: PlaceType, lang: str = "ru") -> str:
    """Получить красивое название типа места"""
    return PLACE_TYPE_METADATA[place_type][lang]


def get_place_emoji(place_type: PlaceType) -> str:
    """Получить эмодзи для типа места"""
    return PLACE_TYPE_METADATA[place_type]["emoji"]


def get_place_color(place_type: PlaceType) -> str:
    """Получить цвет для маркера на карте"""
    return PLACE_TYPE_METADATA[place_type]["color"]

def get_place_type_from_osm(tags: Dict[str, str]) -> PlaceType | None:
    """OSM теги → PlaceType"""
    for key, value_map in OSM_TO_PLACE_TYPE.items():
        if key in tags and tags[key] in value_map:
            return value_map[tags[key]]
    return None

def get_places_by_category(category: str) -> List[PlaceType]:
    """Получить все типы мест в категории (food, nature, culture, etc.)"""
    return [pt for pt, meta in PLACE_TYPE_METADATA.items() if meta["category"] == category]
