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

"""Утилита для диагностики проблем с OSM элементами."""

import requests
import json
from tools.maps.services import OSMAPIService


def debug_osm_element(osm_id: int, osm_type: str = "way"):
    """
    Проверяет почему OSM элемент не сохраняется.
    
    Args:
        osm_id: ID элемента в OSM (например, 342081500)
        osm_type: тип элемента (node/way/relation)
    """
    print("=" * 70)
    print(f"🔍 ДИАГНОСТИКА OSM ЭЛЕМЕНТА: {osm_type}/{osm_id}")
    print("=" * 70)
    print()
    
    # 1. Запрос к Overpass API для конкретного элемента
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json];
    {osm_type}({osm_id});
    out geom;
    """
    
    print(f"📡 Запрос к Overpass API...")
    print(f"   URL: {overpass_url}")
    print(f"   Тип: {osm_type}, ID: {osm_id}")
    print()
    
    try:
        response = requests.post(
            overpass_url,
            data={"data": query},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"❌ Ошибка запроса: {exc}")
        return
    
    elements = data.get("elements", [])
    
    if not elements:
        print(f"❌ Элемент {osm_type}/{osm_id} не найден в OSM")
        print("   Возможно, он был удалён или ID неверный")
        return
    
    # Находим главный элемент (не узлы)
    main_element = None
    nodes = []
    
    for el in elements:
        if el.get("type") == osm_type and el.get("id") == osm_id:
            main_element = el
        elif el.get("type") == "node":
            nodes.append(el)
    
    if not main_element:
        print(f"❌ Главный элемент не найден в ответе")
        return
    
    print(f"✅ Элемент найден!")
    print()
    
    # 2. Анализ элемента
    print("📋 ИНФОРМАЦИЯ:")
    print(f"   Type: {main_element.get('type')}")
    print(f"   ID: {main_element.get('id')}")
    
    tags = main_element.get("tags", {})
    if tags:
        print(f"   Теги:")
        for key, value in tags.items():
            print(f"     - {key}: {value}")
    else:
        print(f"   ⚠️  Нет тегов")
    
    print()
    
    # 3. Проверка геометрии
    print("🗺️  ГЕОМЕТРИЯ:")
    
    has_geometry_field = "geometry" in main_element
    has_lat_lon = "lat" in main_element and "lon" in main_element
    has_center = "center" in main_element
    
    print(f"   Has 'geometry' field: {has_geometry_field}")
    print(f"   Has 'lat/lon': {has_lat_lon}")
    print(f"   Has 'center': {has_center}")
    
    if osm_type == "way":
        if has_geometry_field:
            coords = main_element.get("geometry", [])
            print(f"   ✅ Количество узлов в geometry: {len(coords)}")
            if coords:
                print(f"   Первый узел: lon={coords[0].get('lon')}, lat={coords[0].get('lat')}")
        else:
            print(f"   ❌ Поле 'geometry' отсутствует!")
            print(f"   Узлов в ответе: {len(nodes)}")
            if "nodes" in main_element:
                print(f"   Ссылки на узлы в 'nodes': {len(main_element['nodes'])}")
    
    print()
    
    # 4. Пытаемся сконвертировать геометрию
    print("🔄 ПОПЫТКА КОНВЕРТАЦИИ В WKT:")
    
    osm_service = OSMAPIService()
    wkt_geometry = osm_service.convert_osm_geometry(main_element)
    
    if wkt_geometry:
        print(f"   ✅ Геометрия успешно сконвертирована!")
        geom_type = wkt_geometry.split("(")[0]
        print(f"   Тип: {geom_type}")
        print(f"   WKT: {wkt_geometry[:150]}...")
        if len(wkt_geometry) > 150:
            print(f"   Полная длина WKT: {len(wkt_geometry)} символов")
    else:
        print(f"   ❌ Не удалось сконвертировать геометрию")
        print()
        print("   🔍 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
        
        if osm_type == "way" and not has_geometry_field:
            print("   1. У way нет поля 'geometry' в ответе Overpass")
            print("      → Используйте 'out geom;' вместо 'out body;' в запросе")
            print("      → Или Overpass не смог получить координаты узлов")
        
        if osm_type == "node" and not has_lat_lon:
            print("   1. У node нет координат lat/lon")
            print("      → Это странно, возможно данные повреждены в OSM")
        
        if osm_type == "relation":
            if not has_center and "members" not in main_element:
                print("   1. У relation нет ни 'center', ни 'members'")
                print("      → Невозможно построить геометрию")
            elif "members" in main_element:
                print("   1. У relation есть members, но не удалось построить геометрию")
                print(f"      → Количество members: {len(main_element['members'])}")
                print("      → Проверьте, есть ли у members поле 'geometry'")
    
    print()
    
    # 5. Ссылка на OSM
    print("🔗 ССЫЛКИ:")
    print(f"   OSM: https://www.openstreetmap.org/{osm_type}/{osm_id}")
    print(f"   Overpass Turbo: https://overpass-turbo.eu/?Q={osm_type}({osm_id});out%20geom;")
    
    print()
    print("=" * 70)
    
    # Сохраняем raw данные для анализа
    debug_file = f"osm_debug_{osm_type}_{osm_id}.json"
    with open(debug_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 Raw данные сохранены в: {debug_file}")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python debug_osm_element.py <osm_id> [type]")
        print()
        print("Примеры:")
        print("  python debug_osm_element.py 342081500")
        print("  python debug_osm_element.py 342081500 way")
        print("  python debug_osm_element.py 123456 node")
        sys.exit(1)
    
    osm_id = int(sys.argv[1])
    osm_type = sys.argv[2] if len(sys.argv) > 2 else "way"
    
    debug_osm_element(osm_id, osm_type)

