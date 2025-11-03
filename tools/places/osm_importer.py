from geoalchemy2.shape import from_shape

from infrastructure.database.session import Database
from tools.places.models import OSMElement

db = Database()
OVERPASS_API = "https://overpass-api.de/api/interpreter"


# ========================================
# 2. Скачать OSM объекты
# ========================================
import requests

def fetch_osm_data(bbox: str):
    min_lat, min_lon, max_lat, max_lon = map(float, bbox.split(","))

    # ПРАВИЛЬНЫЙ ПОРЯДОК для Overpass!
    south = f"{min_lat:.6f}"    # 55.835976
    west = f"{min_lon:.6f}"     # 37.330899
    north = f"{max_lat:.6f}"    # 55.858960
    east = f"{max_lon:.6f}"     # 37.412310

    overpass_query = f"""
    [out:json][timeout:90];
    (
      node["amenity"]({south},{west},{north},{east});
      way["amenity"]({south},{west},{north},{east});
      relation["amenity"]({south},{west},{north},{east});

      node["shop"]({south},{west},{north},{east});
      way["shop"]({south},{west},{north},{east});

      node["leisure"]({south},{west},{north},{east});
      way["leisure"]({south},{west},{north},{east});

      node["tourism"]({south},{west},{north},{east});
      way["tourism"]({south},{west},{north},{east});
    );
    out body;
    >;
    out center meta;
    """

    # ПРАВИЛЬНЫЙ ЛОГ!
    print(f"Overpass bbox (south,west,north,east): {south},{west},{north},{east}")

    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={'data': overpass_query},
            timeout=90
        )
        response.raise_for_status()
        data = response.json()
        elements = data.get('elements', [])
        print(f"Overpass вернул {len(elements)} элементов")
        if not elements:
            print(f"Пусто! Raw JSON: {data}")
        return elements
    except Exception as e:
        print(f"Ошибка: {e}")
        return []



# load_to_db.py
import json
import os
from sqlalchemy import create_engine, Column, BigInteger, String, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geometry
from shapely.geometry import shape as shapely_shape
from shapely.geometry import Point, LineString, Polygon

# === НАСТРОЙКИ ===

FILE_PATH = r"C:\Users\Alien\Victor_AI_Map\Assets\Resources\export.json"

db = Database()
session = db.get_session()
# === ДВИЖОК ===

Session = sessionmaker(bind=db.engine)


# === ЗАГРУЗКА ===
def load_osm_json():
    if not os.path.exists(FILE_PATH):
        print(f"Файл не найден: {FILE_PATH}")
        return

    print(f"Читаем {FILE_PATH}...")
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ПРОВЕРКА ФОРМАТА
    if 'features' not in data:
        print(f"ОШИБКА: ожидался GeoJSON, но ключ 'features' не найден")
        print(f"Ключи в файле: {list(data.keys())}")
        return

    features = data['features']
    print(f"Найдено features: {len(features)}")

    added = 0
    skipped = 0

    for feature in features:
        # Проверка структуры
        if feature.get('type') != 'Feature':
            skipped += 1
            continue

        geom_data = feature.get('geometry')
        props = feature.get('properties', {})

        if not geom_data:
            skipped += 1
            continue

        # Извлекаем OSM ID из properties
        osm_id_str = props.get('@id', '')  # например "node/13007137293"
        if not osm_id_str:
            skipped += 1
            continue

        # Парсим ID и тип
        try:
            osm_type, osm_id = osm_id_str.split('/')
            osm_id = int(osm_id)
        except (ValueError, AttributeError):
            skipped += 1
            continue

        # Конвертируем GeoJSON geometry в Shapely
        try:
            shp = shapely_shape(geom_data)
        except Exception as e:
            print(f"Ошибка парсинга геометрии: {e}")
            skipped += 1
            continue

        # WKB для PostGIS
        wkb = from_shape(shp, srid=4326)

        # Убираем служебное поле '@id' из тегов
        tags = {k: v for k, v in props.items() if k != '@id'}

        # Объект
        obj = OSMElement(
            id=osm_id,
            type=osm_type,
            tags=tags,
            geometry=wkb
        )

        session.merge(obj)
        added += 1

        if added % 100 == 0:
            print(f"Обработано: {added}...")

    session.commit()
    print(f"✅ Готово! Добавлено/обновлено: {added}, пропущено: {skipped}")


# === ЗАПУСК ===
if __name__ == "__main__":
    load_osm_json()