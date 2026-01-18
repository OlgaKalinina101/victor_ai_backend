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

"""Схемы для генерации короткой подписи к месту по OSM-тегам."""

from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel, Field


class PlaceCaptionRequest(BaseModel):
    """Запрос на генерацию подписи к месту по OSM-тегам."""

    account_id: str = Field(..., description="Идентификатор пользователя")
    poi_osm_id: int = Field(..., description="OSM ID POI (osm_elements.id)")
    poi_osm_type: Literal["node", "way", "relation"] = Field(
        ...,
        description="Тип OSM-объекта (node/way/relation). Нужен для идентификации POI.",
    )
    tags: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "OSM-теги места (key -> value). Если не переданы — будут взяты из БД по poi_osm_id."
        ),
    )


class PlaceCaptionResponse(BaseModel):
    """Ответ с подписью для карты."""

    caption: str = Field(..., description="Одна короткая подпись на русском (5–14 слов).")


