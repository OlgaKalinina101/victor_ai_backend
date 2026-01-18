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
Репозиторий для работы с CareBank entries и settings.

Изолирован в tools/carebank/ для лёгкого удаления всей фичи.
"""

from typing import Optional, List
import time
from sqlalchemy.orm import Session

from tools.carebank.models import CareBankEntry, CareBankSettings, FoodOrder
from infrastructure.logging.logger import setup_logger

logger = setup_logger("care_bank_repository")


class CareBankRepository:
    """Репозиторий для работы с CareBank."""
    
    def __init__(self, session: Session):
        self.session = session
    
    # ============ CareBankEntry ============
    
    def get_entry_by_id(self, entry_id: int) -> Optional[CareBankEntry]:
        """Получает запись по ID."""
        return self.session.query(CareBankEntry).filter_by(id=entry_id).first()
    
    def get_entry_by_emoji(self, account_id: str, emoji: str) -> Optional[CareBankEntry]:
        """
        Получает запись по account_id + emoji.
        
        Args:
            account_id: ID пользователя
            emoji: Эмодзи (уникальный ключ для пользователя)
            
        Returns:
            CareBankEntry или None
        """
        return (
            self.session.query(CareBankEntry)
            .filter(
                CareBankEntry.account_id == account_id,
                CareBankEntry.emoji == emoji
            )
            .one_or_none()
        )
    
    def get_all_entries(self, account_id: str) -> List[CareBankEntry]:
        """
        Получает все записи пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список записей, отсортированный по timestamp (новые первыми)
        """
        return (
            self.session.query(CareBankEntry)
            .filter(CareBankEntry.account_id == account_id)
            .order_by(CareBankEntry.timestamp_ms.desc())
            .all()
        )
    
    def upsert_entry(
        self,
        account_id: str,
        emoji: str,
        value: str,
        timestamp_ms: Optional[int] = None,
        **coords
    ) -> CareBankEntry:
        """
        Создаёт или обновляет запись CareBank.
        
        Если запись с таким emoji уже существует - обновляет её.
        Если нет - создаёт новую.
        
        Args:
            account_id: ID пользователя
            emoji: Эмодзи
            value: Значение (описание товара/услуги)
            timestamp_ms: Unix timestamp в миллисекундах (если None - текущее время)
            **coords: Координаты для автоматизации (search_url, add_to_cart_1_coords, etc)
            
        Returns:
            Созданная или обновлённая запись
        """
        timestamp_ms = timestamp_ms or int(time.time() * 1000)
        
        # Пытаемся найти существующую
        existing = self.get_entry_by_emoji(account_id, emoji)
        
        if existing:
            # Обновляем существующую
            existing.value = value
            existing.timestamp_ms = timestamp_ms
            
            # Обновляем координаты (если переданы)
            for key, value in coords.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            
            self.session.commit()
            self.session.refresh(existing)
            logger.info(f"Обновлена запись CareBank: {account_id}/{emoji}")
            return existing
        else:
            # Создаём новую
            entry = CareBankEntry(
                account_id=account_id,
                emoji=emoji,
                value=value,
                timestamp_ms=timestamp_ms,
                **coords
            )
            self.session.add(entry)
            self.session.commit()
            self.session.refresh(entry)
            logger.info(f"Создана запись CareBank: {account_id}/{emoji}")
            return entry
    
    def delete_entry(self, entry_id: int) -> bool:
        """
        Удаляет запись по ID.
        
        Returns:
            True если удалена, False если не найдена
        """
        entry = self.get_entry_by_id(entry_id)
        if entry:
            self.session.delete(entry)
            self.session.commit()
            logger.info(f"Удалена запись CareBank: id={entry_id}")
            return True
        return False
    
    # ============ CareBankSettings ============
    
    def get_settings(self, account_id: str) -> Optional[CareBankSettings]:
        """Получает настройки CareBank для пользователя."""
        return (
            self.session.query(CareBankSettings)
            .filter(CareBankSettings.account_id == account_id)
            .first()
        )
    
    def create_or_update_settings(
        self,
        account_id: str,
        **fields
    ) -> CareBankSettings:
        """
        Создаёт или обновляет настройки CareBank.
        
        Args:
            account_id: ID пользователя
            **fields: Поля для обновления (auto_approved, presence_address, etc)
            
        Returns:
            Настройки CareBank
        """
        settings = self.get_settings(account_id)
        
        if settings:
            # Обновляем
            for key, value in fields.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            logger.debug(f"Обновлены настройки CareBank для {account_id}")
        else:
            # Создаём
            settings = CareBankSettings(account_id=account_id, **fields)
            self.session.add(settings)
            logger.debug(f"Созданы настройки CareBank для {account_id}")
        
        self.session.commit()
        self.session.refresh(settings)
        return settings
    
    # ============ FoodOrder ============
    
    def create_food_order(
        self,
        account_id: str,
        emoji: str,
        order_data: dict
    ) -> FoodOrder:
        """
        Создаёт заказ еды.
        
        Args:
            account_id: ID пользователя
            emoji: Эмодзи связанной CareBank записи
            order_data: Данные заказа (JSON)
            
        Returns:
            Созданный заказ
        """
        order = FoodOrder(
            account_id=account_id,
            emoji=emoji,
            order_data=order_data
        )
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)
        logger.info(f"Создан заказ еды: {account_id}/{emoji}")
        return order
    
    def get_recent_orders(self, account_id: str, limit: int = 10) -> List[FoodOrder]:
        """Получает последние заказы пользователя."""
        return (
            self.session.query(FoodOrder)
            .filter(FoodOrder.account_id == account_id)
            .order_by(FoodOrder.created_at.desc())
            .limit(limit)
            .all()
        )

