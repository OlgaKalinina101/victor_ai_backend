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

from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Text, BigInteger, Boolean, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from infrastructure.database.models import Base

class CareBankEntry(Base):
    __tablename__ = "care_bank_entries"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(64), index=True, nullable=False)
    emoji = Column(String(16), nullable=False)
    value = Column(Text, nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False)  # Long из Kotlin

    # Новые поля для автоматизации
    search_url = Column(Text, nullable=True)
    search_field = Column(String(255), nullable=True)
    add_to_cart_1_coords = Column(String(32), nullable=True)  # x,y координаты
    add_to_cart_2_coords = Column(String(32), nullable=True)
    add_to_cart_3_coords = Column(String(32), nullable=True)
    add_to_cart_4_coords = Column(String(32), nullable=True)
    add_to_cart_5_coords = Column(String(32), nullable=True)
    open_cart_coords = Column(String(32), nullable=True)
    place_order_coords = Column(String(32), nullable=True)


class TaxiClass(str, PyEnum):
    ECONOMY = "economy"
    COMFORT = "comfort"
    COMFORT_PLUS = "comfort_plus"
    BUSINESS = "business"
    MINIVAN = "minivan"

class CareBankSettings(Base):
    __tablename__ = "care_bank_settings"

    id = Column(Integer, primary_key=True, index=True)

    # Привязка к аккаунту (1:1 с пользователем/аккаунтом)
    account_id = Column(String(64), nullable=False, unique=True, index=True)

    # Автоодобрение заказов
    auto_approved = Column(Boolean, nullable=False, default=False)

    # Адрес присутствия (куда обычно всё доставляем)
    presence_address = Column(Text, nullable=True)

    # Максимальная стоимость заказа (можно хранить в у.е. целым числом)
    max_order_cost = Column(Integer, nullable=True)

    # Предпочитаемый класс такси
    preferred_taxi_class = Column(String(32), nullable=True)

class FoodOrder(Base):
    __tablename__ = "food_orders"

    id = Column(Integer, primary_key=True, index=True)

    # кто заказывал
    account_id = Column(String(64), nullable=False, index=True)

    # связка с care_bank (какой смайлик)
    emoji = Column(String(16), nullable=False, index=True)

    # сам заказ (словарь с блюдами/метаданными)
    order_data = Column(JSONB, nullable=False)

    # когда заказ был сформирован
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

