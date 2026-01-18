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

"""Утилита для просмотра доступных типов Overpass запросов."""

from pathlib import Path
import yaml


def show_available_queries():
    """Показывает все доступные типы запросов из конфига."""
    config_path = Path(__file__).parent / "overpass_queries.yaml"
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ Конфиг не найден: {config_path}")
        return
    except yaml.YAMLError as exc:
        print(f"❌ Ошибка парсинга YAML: {exc}")
        return

    queries = config.get("queries", {})
    defaults = config.get("defaults", {})

    print("=" * 70)
    print("📋 ДОСТУПНЫЕ ТИПЫ OVERPASS ЗАПРОСОВ")
    print("=" * 70)
    print()
    
    if not queries:
        print("⚠️  Запросы не найдены в конфиге")
        return

    print(f"Всего типов запросов: {len(queries)}")
    print(f"Дефолтный тип: {defaults.get('query_type', 'не указан')}")
    print(f"Таймаут: {defaults.get('timeout', 90)}с")
    print()
    
    for i, (qtype, qconfig) in enumerate(queries.items(), 1):
        is_default = qtype == defaults.get('query_type')
        marker = "⭐" if is_default else f"{i}."
        
        description = qconfig.get("description", "Без описания")
        query = qconfig.get("query", "")
        
        # Подсчитываем количество строк в запросе
        query_lines = len([line for line in query.split('\n') if line.strip()])
        
        print(f"{marker} {qtype}")
        print(f"   Описание: {description}")
        print(f"   Размер запроса: {query_lines} строк")
        
        # Показываем первые несколько строк запроса
        query_preview = query.strip().split('\n')[:3]
        if query_preview:
            print(f"   Первые строки:")
            for line in query_preview:
                if line.strip():
                    print(f"     {line.strip()[:60]}...")
        print()

    print("=" * 70)
    print("💡 Использование:")
    print("    from tools.maps.services import OSMAPIService")
    print('    osm_api = OSMAPIService(query_type="amenities_only")')
    print("=" * 70)


if __name__ == "__main__":
    show_available_queries()

