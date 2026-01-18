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

"""Тест для проверки корректности YAML конфига."""

import yaml
from pathlib import Path


def test_yaml_config():
    """Проверяет что конфиг парсится без ошибок."""
    config_path = Path(__file__).parent / "config" / "overpass_queries.yaml"
    
    print("=" * 70)
    print("TEST KONFIGURACII OVERPASS QUERIES")
    print("=" * 70)
    print()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        print("[OK] YAML file parsed successfully")
        print()
        
        # Проверяем структуру
        queries = config.get("queries", {})
        defaults = config.get("defaults", {})
        
        print(f"[INFO] Found {len(queries)} query types")
        print()
        
        # Проверяем каждый запрос
        for qtype, qconfig in queries.items():
            print(f"[+] {qtype}")
            
            if "description" not in qconfig:
                print(f"  [WARN] No description")
            else:
                print(f"  Описание: {qconfig['description']}")
            
            if "query" not in qconfig:
                print(f"  [ERROR] No 'query' field!")
            else:
                query = qconfig["query"]
                lines = query.strip().split("\n")
                print(f"  Строк в запросе: {len(lines)}")
                
                # Проверяем наличие плейсхолдеров
                if "{timeout}" not in query:
                    print(f"  [WARN] No {{timeout}} placeholder")
                if "{bbox}" not in query:
                    print(f"  [WARN] No {{bbox}} placeholder")
                
                # Проверяем синтаксис
                if not query.strip().startswith("[out:json]"):
                    print(f"  [WARN] Does not start with [out:json]")
                if "out geom" not in query:
                    print(f"  [WARN] No 'out geom;' at the end")
            
            print()
        
        # Проверяем defaults
        print("[DEFAULTS]")
        print(f"  query_type: {defaults.get('query_type', 'НЕ УКАЗАН')}")
        print(f"  timeout: {defaults.get('timeout', 'НЕ УКАЗАН')}")
        print(f"  overpass_url: {defaults.get('overpass_url', 'НЕ УКАЗАН')}")
        print()
        
        # Проверяем что дефолтный тип существует
        default_type = defaults.get("query_type")
        if default_type and default_type not in queries:
            print(f"[ERROR] Default type '{default_type}' not found in queries!")
        else:
            print(f"[OK] Default type '{default_type}' exists")
        
        print()
        print("=" * 70)
        print("[SUCCESS] ALL CHECKS PASSED")
        print("=" * 70)
        
        return True
        
    except yaml.YAMLError as exc:
        print(f"[ERROR] YAML parsing error:")
        print(exc)
        return False
    except FileNotFoundError:
        print(f"[ERROR] File not found: {config_path}")
        return False
    except Exception as exc:
        print(f"[ERROR] Unexpected error:")
        print(exc)
        return False


if __name__ == "__main__":
    success = test_yaml_config()
    exit(0 if success else 1)

