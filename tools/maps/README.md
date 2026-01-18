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

# Maps Module - Архитектура

Модуль для работы с картами, игровыми локациями и OSM данными.

## 📁 Структура

```
tools/maps/
├── services/              # Бизнес-логика
│   ├── game_location_service.py    # Управление локациями
│   └── osm_api_service.py          # Работа с Overpass API
├── repositories/          # Работа с БД
│   ├── game_location_repository.py # CRUD для GameLocation
│   └── osm_repository.py           # CRUD для OSMElement
├── config/                # Конфигурация
│   └── overpass_queries.yaml       # Шаблоны Overpass запросов
├── models.py             # SQLAlchemy модели
├── exceptions.py         # Кастомные исключения
└── README.md             # Эта документация
```

## 🏗️ Архитектура (Layered Architecture)

```
┌─────────────────────────────────────┐
│     API Layer (assistant.py)        │  ← Тонкий слой, только валидация
├─────────────────────────────────────┤
│   Service Layer (services/)         │  ← Бизнес-логика
│   ├── GameLocationService           │
│   └── OSMAPIService                 │
├─────────────────────────────────────┤
│   Repository Layer (repositories/)  │  ← Работа с БД (CRUD)
│   ├── GameLocationRepository        │
│   └── OSMRepository                 │
├─────────────────────────────────────┤
│   Models Layer (models.py)          │  ← SQLAlchemy модели
└─────────────────────────────────────┘
```

## 🎯 Принципы

1. **Single Responsibility Principle (SRP)**
   - Каждый класс отвечает за одну вещь
   - API сервис только для внешних запросов
   - Репозитории только для БД
   - Сервисы только для бизнес-логики

2. **Dependency Injection**
   - Все зависимости передаются через конструктор
   - Легко мокать для тестов

3. **Repository Pattern**
   - Абстракция над БД
   - Легко заменить реализацию

4. **Clean Code**
   - Читаемые имена
   - Маленькие функции
   - Логирование на каждом этапе

## 📝 Примеры использования

### Получение мест для точки

```python
from infrastructure.database.session import Database
from tools.maps.services import GameLocationService

# В эндпоинте
db = Database()
session = db.get_session()

try:
    service = GameLocationService(session)
    
    # Находит или создаёт локацию
    location = service.get_or_create_location_for_point(
        account_id="user123",
        latitude=55.7558,
        longitude=37.6173,
        radius_km=2.0,
    )
    
    # Получает элементы
    result = service.get_osm_elements_for_location(
        location=location,
        limit=500,
        offset=0,
    )
    
    session.commit()
finally:
    session.close()
```

### Работа с репозиториями напрямую

```python
from tools.maps.repositories import GameLocationRepository

repo = GameLocationRepository(session)

# Получить все локации аккаунта
locations = repo.get_active_locations_by_account("user123")

# Создать новую локацию
location = repo.create(
    account_id="user123",
    name="Москва Центр",
    bbox_south=55.7,
    bbox_west=37.5,
    bbox_north=55.8,
    bbox_east=37.7,
)

# Деактивировать локацию
repo.deactivate(location.id)
```

### Работа с Overpass API

```python
from tools.maps.services import OSMAPIService

# Дефолтный сервис (загружает все типы объектов)
osm_api = OSMAPIService()

# Или с конкретным типом запроса
osm_api = OSMAPIService(query_type="amenities_only")  # только кафе/рестораны
osm_api = OSMAPIService(query_type="nature_only")     # только парки/вода
osm_api = OSMAPIService(query_type="minimal")         # минимальный набор

# Посмотреть доступные типы запросов
available = osm_api.get_available_query_types()
# {'full': 'Полный набор объектов...', 'amenities_only': '...', ...}

# Рассчитать bbox
south, west, north, east = osm_api.calculate_bounding_box(
    lat=55.7558,
    lon=37.6173,
    radius_km=2.0,
)

# Получить данные из Overpass
bbox_str = f"{south},{west},{north},{east}"
elements = osm_api.fetch_osm_data(bbox_str)

# Или с конкретным типом запроса для этого вызова
elements = osm_api.fetch_osm_data(bbox_str, query_type="minimal")

# Конвертировать геометрию
for item in elements:
    geometry = osm_api.convert_osm_geometry(item)
```

### Кастомизация Overpass запросов

Все запросы к Overpass API настраиваются через `config/overpass_queries.yaml`:

```yaml
queries:
  full:
    description: "Полный набор объектов для игры"
    query: |
      [out:json][timeout:{timeout}];
      (
        node["amenity"~"cafe|restaurant"]({bbox});
        way["leisure"="park"]({bbox});
      );
      out body;
```

**Доступные типы запросов:**
- `full` - полный набор (дефолт): кафе, парки, дороги, здания
- `amenities_only` - только заведения (кафе, рестораны, бары)
- `nature_only` - только природные объекты (парки, леса, вода)
- `infrastructure_only` - только инфраструктура (дороги, здания)
- `minimal` - минимальный набор для тестов

Можно легко добавить свой тип запроса в конфиг!

## 🧪 Тестирование

Благодаря слоистой архитектуре, каждый слой легко тестировать:

```python
# Мок репозитория
mock_repo = Mock(spec=GameLocationRepository)
mock_repo.get_active_locations_by_account.return_value = []

# Тест сервиса с моками
service = GameLocationService(
    session=mock_session,
    osm_api_service=mock_osm_api,
)
```

## ⚠️ Важные моменты

1. **Flush перед связыванием**
   - Всегда делай `session.flush()` после создания OSMElement
   - Только потом создавай связи в `game_location_osm_elements`

2. **Обработка ошибок**
   - Все сервисы логируют ошибки
   - Кастомные исключения в `exceptions.py`

3. **Транзакции**
   - Сервисы НЕ коммитят сами
   - Коммит делается в эндпоинте или вызывающем коде

## 🔄 Миграция со старого кода

**Было:**
```python
from tools.maps.map_loader import get_osm_items_for_account_location

result = get_osm_items_for_account_location(...)
```

**Стало:**
```python
from tools.maps.services import GameLocationService

service = GameLocationService(session)
location = service.get_or_create_location_for_point(...)
result = service.get_osm_elements_for_location(location, ...)
```

## 📊 Производительность

- **Кеширование bbox**: Существующие локации не запрашивают Overpass
- **Пагинация**: `limit` и `offset` для больших наборов данных
- **PostGIS индексы**: Быстрые пространственные запросы
- **Переиспользование элементов**: OSMElement создаются один раз

## ⚙️ Конфигурация

### Структура конфига `config/overpass_queries.yaml`

```yaml
queries:
  custom_query:
    description: "Описание запроса"
    query: |
      [out:json][timeout:{timeout}];
      (
        node["amenity"="cafe"]({bbox});
      );
      out geom;  # ← ВАЖНО: используй 'out geom;' для автоматической загрузки координат

defaults:
  query_type: "full"
  timeout: 90
  overpass_url: "https://overpass-api.de/api/interpreter"
```

**Плейсхолдеры:**
- `{timeout}` - подставляется автоматически из настроек
- `{bbox}` - подставляется в формате `south,west,north,east`

**⚠️ ВАЖНО:** Всегда используй `out geom;` в конце запроса!
- ✅ `out geom;` - автоматически загружает координаты узлов для way'ев
- ❌ `out body;` - требует дополнительно `>; out center meta;` (устаревший подход)

С `out geom;` будет **намного меньше** пропущенных объектов!

### Добавление нового типа запроса

1. Открой `config/overpass_queries.yaml`
2. Добавь новый тип в `queries`:

```yaml
queries:
  shopping_only:
    description: "Только магазины и торговые центры"
    query: |
      [out:json][timeout:{timeout}];
      (
        node["shop"]({bbox});
        way["shop"]({bbox});
        way["building"="retail"]({bbox});
      );
      out body;
      >;
      out center meta;
```

3. Используй в коде:

```python
osm_api = OSMAPIService(query_type="shopping_only")
```

## 🐛 Отладка и диагностика

### Пропущенные объекты без геометрии

Если видишь warning'и типа:
```
[WARNING] Пропуск элемента id=342081500 type=way (highway: 'Тверская улица') - нет геометрии. Has geometry field: False
```

**Почему это происходит:**

1. **У way нет поля `geometry`** в ответе Overpass
   - ✅ **Решение:** Проверь, что в запросе используется `out geom;` (не `out body;`)
   - Overpass не вернул координаты узлов
   - Узлы удалены из OSM или данные неполные

2. **Это может быть:**
   - 🌳 Парки, леса (`leisure=park`, `landuse=forest`)
   - 💧 Водоёмы (`natural=water`, `waterway=river`)
   - 🛣️ Дороги (`highway=*`)
   - 🏢 Здания (`building=*`)
   - Любые объекты с неполными данными в OSM

3. **Служебные way/relation:**
   - Используются только для связей, не для рендеринга
   - Не имеют физической геометрии

**С `out geom;` таких проблем должно быть минимум!**

**Что делать:**

1. Посмотри статистику в логах:
```
[INFO] Статистика пропущенных объектов по типам:
[INFO]   - highway: 15 шт.
[INFO]   - natural: 8 шт.
[INFO]   - building: 3 шт.
```

2. Используй утилиту диагностики:
```bash
python tools/maps/debug_osm_element.py 342081500 way
```

Она покажет:
- Что это за объект (теги, название)
- Есть ли в ответе Overpass поле `geometry`
- Почему геометрия не сконвертировалась
- Ссылки на OSM для ручной проверки

3. Если это массовая проблема - возможно:
   - ❗ **Проверь, что используется `out geom;` в конфиге!**
   - Overpass API перегружен (попробуй позже)
   - Данные в OSM неполные для этого региона

### Оптимизация и производительность

**Новая версия (WKT напрямую):**
- ✅ Геометрия строится напрямую в WKT формате (без Shapely)
- ✅ Быстрее конвертация
- ✅ Меньше зависимостей
- ✅ `out geom;` автоматически включает координаты узлов

**Что изменилось:**
```python
# Старый подход (через Shapely)
from shapely.geometry import Point, LineString
geometry = Point(lon, lat)
wkb = from_shape(geometry, srid=4326)

# Новый подход (WKT напрямую)
from geoalchemy2 import WKTElement
wkt = f"POINT({lon} {lat})"
geometry = WKTElement(wkt, srid=4326)
```

**Поддерживаемые типы геометрии:**
- `POINT` - для node (кафе, рестораны, POI)
- `LINESTRING` - для way-линий (дороги, границы)
- `POLYGON` - для way-полигонов (парки, здания, водоёмы)
- `MULTIPOLYGON` - для relation (сложные парки, административные границы)

### Проверка конфигурации

Посмотреть доступные типы запросов:
```bash
python tools/maps/config/show_queries.py
```

## 🌐 API Эндпоинты

### Основные эндпоинты

1. **GET `/assistant/places`** - Получить места для точки (автосоздание локации)
   ```bash
   curl "http://localhost:8000/assistant/places?account_id=user&latitude=55.7558&longitude=37.6173"
   ```

2. **GET `/assistant/locations`** - Список всех сохранённых локаций
   ```bash
   curl "http://localhost:8000/assistant/locations?account_id=user"
   ```

3. **GET `/assistant/locations/{id}`** - Информация о конкретной локации
   ```bash
   curl "http://localhost:8000/assistant/locations/1?account_id=user"
   ```

4. **GET `/assistant/locations/{id}/places`** - OSM элементы для сохранённой локации
   ```bash
   curl "http://localhost:8000/assistant/locations/1/places?account_id=user"
   ```

5. **PATCH `/assistant/locations/{id}`** - Обновить название/описание локации
   ```bash
   curl -X PATCH "http://localhost:8000/assistant/locations/1?account_id=user" \
     -H "Content-Type: application/json" \
     -d '{"name": "Новое название", "difficulty": "easy"}'
   ```

**Подробная документация:** См. `api/LOCATIONS_API.md`

## 🚀 Будущие улучшения

- [ ] Асинхронная загрузка из Overpass
- [ ] Кеширование результатов
- [ ] Batch операции для множественных запросов
- [ ] Метрики и мониторинг
- [ ] Unit и integration тесты
- [ ] DELETE эндпоинт для удаления локаций
- [x] Конфигурируемые Overpass запросы
- [x] Разные типы запросов (full, minimal, amenities_only и т.д.)
- [x] CRUD эндпоинты для управления локациями

