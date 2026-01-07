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

"""
Схемы для эндпоинта /care_bank.

Содержит модели для работы с Care Bank - системой помощи пользователям
в заказе товаров и услуг, включая автоматизацию доставки и такси.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CareBankEntryCreate(BaseModel):
    """
    Запрос на создание или обновление записи Care Bank.
    
    Содержит информацию о желаемом товаре/услуге пользователя
    и координаты для автоматизации процесса заказа в WebView.
    Поддерживает camelCase и snake_case для совместимости с клиентом.
    
    Attributes:
        emoji: Эмодзи-идентификатор категории желания (🍕, 🚕, 🎁).
        account_id: ID пользователя.
        value: Текстовое описание желания (название товара/услуги).
        timestamp_ms: Временная метка создания в миллисекундах.
            Если не указана, устанавливается автоматически.
        
        Поля для автоматизации заказа в WebView:
        search_url: URL страницы поиска (например, Яндекс.Еда).
        search_field: Координаты поля поиска для ввода текста.
        add_to_cart_1_coords: Координаты первой кнопки "В корзину".
        add_to_cart_2_coords: Координаты второй кнопки "В корзину".
        add_to_cart_3_coords: Координаты третьей кнопки "В корзину".
        add_to_cart_4_coords: Координаты четвертой кнопки "В корзину".
        add_to_cart_5_coords: Координаты пятой кнопки "В корзину".
        open_cart_coords: Координаты кнопки открытия корзины.
        place_order_coords: Координаты кнопки оформления заказа.
    
    Notes:
        - Координаты в формате "x,y" (пиксели)
        - При наличии записи с тем же emoji она обновляется
    """
    emoji: str = Field(..., description="Эмодзи-категория")
    account_id: str = Field(..., alias="accountId")
    value: str = Field(..., description="Описание желания")
    timestamp_ms: Optional[int] = Field(default=None, alias="timestamp")

    # Поля для автоматизации
    search_url: Optional[str] = Field(default=None, alias="searchUrl")
    search_field: Optional[str] = Field(default=None, alias="searchField")
    add_to_cart_1_coords: Optional[str] = Field(default=None, alias="addToCart1Coords")
    add_to_cart_2_coords: Optional[str] = Field(default=None, alias="addToCart2Coords")
    add_to_cart_3_coords: Optional[str] = Field(default=None, alias="addToCart3Coords")
    add_to_cart_4_coords: Optional[str] = Field(default=None, alias="addToCart4Coords")
    add_to_cart_5_coords: Optional[str] = Field(default=None, alias="addToCart5Coords")
    open_cart_coords: Optional[str] = Field(default=None, alias="openCartCoords")
    place_order_coords: Optional[str] = Field(default=None, alias="placeOrderCoords")

    class Config:
        populate_by_name = True
        from_attributes = True


class CareBankEntryRead(BaseModel):
    """
    Запись Care Bank для возврата клиенту.
    
    Содержит полную информацию о сохранённом желании пользователя,
    включая все координаты для автоматизации заказа.
    
    Attributes:
        id: Уникальный ID записи в базе данных.
        emoji: Эмодзи-идентификатор категории.
        account_id: ID пользователя.
        value: Описание желания.
        timestamp_ms: Временная метка создания в миллисекундах.
        
        Остальные поля: см. CareBankEntryCreate.
    """
    id: int
    emoji: str
    account_id: str
    value: str
    timestamp_ms: int

    # Поля для автоматизации
    search_url: Optional[str] = None
    search_field: Optional[str] = None
    add_to_cart_1_coords: Optional[str] = None
    add_to_cart_2_coords: Optional[str] = None
    add_to_cart_3_coords: Optional[str] = None
    add_to_cart_4_coords: Optional[str] = None
    add_to_cart_5_coords: Optional[str] = None
    open_cart_coords: Optional[str] = None
    place_order_coords: Optional[str] = None

    class Config:
        from_attributes = True


class CareBestResponse(BaseModel):
    """
    Ответ о лучшем выборе варианта Care Bank.
    
    Используется ИИ для обоснования выбора конкретного
    товара или услуги среди нескольких вариантов.
    
    Attributes:
        reason: Текстовое объяснение выбора.
        bestChoice: Флаг, является ли данный вариант лучшим.
    """
    reason: str
    bestChoice: bool


class ItemSelectionResponse(BaseModel):
    """
    Ответ от эндпоинта выбора позиции из скриншота.
    
    Используется при анализе скриншота страницы доставки
    для автоматического выбора наиболее подходящей позиции
    на основе запроса пользователя.
    
    Attributes:
        id: ID выбранной позиции (порядковый номер на странице).
        selected_item: Название выбранной позиции.
        match_type: Тип совпадения с запросом пользователя:
            - "exact" - точное совпадение
            - "similar" - похожий вариант
            - "none" - совпадений не найдено
        user_message: Сообщение для пользователя с объяснением выбора.
    """
    id: str = Field(..., description="ID выбранной позиции")
    selected_item: str = Field(
        ...,
        alias="selectedItem",
        description="Название выбранной позиции"
    )
    match_type: str = Field(
        ...,
        alias="matchType",
        description="Тип совпадения: exact, similar или none"
    )
    user_message: str = Field(
        ...,
        alias="userMessage",
        description="Сообщение для пользователя"
    )

    class Config:
        populate_by_name = True
        from_attributes = True


class TaxiClass(str, Enum):
    """
    Класс такси для заказа через Care Bank.
    
    Определяет предпочтительный класс комфорта при
    автоматическом заказе такси через Яндекс.Такси
    или аналогичные сервисы.
    """
    ECONOMY = "economy"
    COMFORT = "comfort"
    COMFORT_PLUS = "comfort_plus"
    BUSINESS = "business"
    MINIVAN = "minivan"


class CareBankSettingsUpdate(BaseModel):
    """
    Запрос на обновление настроек Care Bank.
    
    Используется для частичного обновления персональных настроек
    системы помощи. Все поля опциональны - обновляются только
    переданные значения.
    
    Attributes:
        account_id: ID пользователя.
        auto_approved: Автоматическое подтверждение заказов без запроса.
        presence_address: Адрес присутствия для доставки по умолчанию.
        max_order_cost: Максимальная стоимость автоподтверждаемого заказа (руб.).
        preferred_taxi_class: Предпочтительный класс такси.
    
    Notes:
        - При auto_approved=True заказы до max_order_cost выполняются автоматически
        - presence_address используется как адрес доставки по умолчанию
    """
    account_id: str = Field(..., alias="accountId")

    auto_approved: Optional[bool] = Field(default=None, alias="autoApproved")
    presence_address: Optional[str] = Field(default=None, alias="presenceAddress")
    max_order_cost: Optional[int] = Field(default=None, alias="maxOrderCost")
    preferred_taxi_class: Optional[TaxiClass] = Field(
        default=None,
        alias="preferredTaxiClass",
    )

    class Config:
        populate_by_name = True
        use_enum_values = True


class CareBankSettingsRead(BaseModel):
    """
    Настройки Care Bank для возврата клиенту.
    
    Содержит полную конфигурацию персональных настроек
    системы помощи пользователя.
    
    Attributes:
        id: ID записи настроек в базе данных.
        account_id: ID пользователя.
        auto_approved: Автоподтверждение заказов.
        presence_address: Адрес присутствия по умолчанию.
        max_order_cost: Максимальная стоимость автоподтверждения.
        preferred_taxi_class: Предпочтительный класс такси.
    """
    id: int
    account_id: str
    auto_approved: bool
    presence_address: Optional[str] = None
    max_order_cost: Optional[int] = None
    preferred_taxi_class: Optional[TaxiClass] = None

    class Config:
        from_attributes = True
