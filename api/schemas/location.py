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

"""
Схемы для эндпоинта /places (игровые локации).

Содержит модели для работы с игровыми локациями -
географическими областями для геймифицированных прогулок
с заданиями и достижениями.
"""

from typing import Optional
from pydantic import BaseModel, Field


class GameLocationResponse(BaseModel):
    """
    Полная информация о сохранённой игровой локации.
    
    Используется для возврата детальной информации о локации,
    включая её границы, статус активности и игровые характеристики.
    
    Attributes:
        id: Уникальный ID локации в базе данных.
        account_id: ID пользователя-создателя локации.
        name: Название локации (например, "Парк Горького", "Арбат").
        description: Текстовое описание локации и её особенностей.
        bbox_south: Южная граница локации (широта, градусы).
        bbox_west: Западная граница локации (долгота, градусы).
        bbox_north: Северная граница локации (широта, градусы).
        bbox_east: Восточная граница локации (долгота, градусы).
        is_active: Флаг активности локации в игровом процессе.
        difficulty: Уровень сложности заданий:
            - "easy" - легкий
            - "medium" - средний
            - "hard" - сложный
        location_type: Тип локации (парк, улица, квартал, район и т.д.).
    
    Notes:
        - bbox определяет прямоугольную область на карте
        - Только активные локации (is_active=True) используются в игре
    """
    id: int
    account_id: str
    name: str
    description: Optional[str] = None
    bbox_south: float
    bbox_west: float
    bbox_north: float
    bbox_east: float
    is_active: bool
    difficulty: Optional[str] = None
    location_type: Optional[str] = None
    
    class Config:
        from_attributes = True


class GameLocationListItem(BaseModel):
    """
    Краткая информация о локации для списков.
    
    Используется при возврате списка локаций, где не требуется
    полная информация о границах. Оптимизирует размер ответа API.
    
    Attributes:
        id: ID локации.
        name: Название локации.
        description: Краткое описание.
        is_active: Статус активности.
        difficulty: Уровень сложности.
        location_type: Тип локации.
    """
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    difficulty: Optional[str] = None
    location_type: Optional[str] = None


class UpdateLocationRequest(BaseModel):
    """
    Запрос на частичное обновление локации.
    
    Все поля опциональны - обновляются только переданные значения.
    Используется для изменения характеристик существующей локации
    без необходимости пересылать все данные.
    
    Attributes:
        name: Новое название локации (1-255 символов).
        description: Новое описание локации (до 1000 символов).
        difficulty: Новый уровень сложности ("easy", "medium", "hard").
        location_type: Новый тип локации (до 50 символов).
    
    Notes:
        - Границы локации (bbox) обновляются отдельным эндпоинтом
        - Валидация difficulty проверяет только разрешенные значения
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    difficulty: Optional[str] = Field(None, pattern="^(easy|medium|hard)$")
    location_type: Optional[str] = Field(None, max_length=50)


class GameLocationDeleteResponse(BaseModel):
    """
    Ответ при успешном удалении локации.
    
    Подтверждает удаление локации и возвращает информацию
    об удалённой записи для логирования или отображения уведомления.
    
    Attributes:
        detail: Текстовое сообщение о результате операции.
        location_id: ID удалённой локации.
        name: Название удалённой локации.
    """
    detail: str
    location_id: int
    name: str

    class Config:
        from_attributes = True
