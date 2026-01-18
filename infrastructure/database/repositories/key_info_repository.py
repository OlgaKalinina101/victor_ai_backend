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

"""Репозиторий для работы с KeyInfo (воспоминания пользователя)."""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from infrastructure.database.models import KeyInfo
from infrastructure.logging.logger import setup_logger
from models.communication_models import MessageMetadata

logger = setup_logger("key_info_repository")


class KeyInfoRepository:
    """
    Репозиторий для работы с ключевой информацией (воспоминаниями).
    
    Инкапсулирует логику работы с KeyInfo:
    - Получение воспоминаний по account_id
    - Сохранение/обновление воспоминаний
    - Создание воспоминаний из сообщений
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_account_id(self, account_id: str) -> List[KeyInfo]:
        """
        Получает все воспоминания пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список записей KeyInfo
        """
        return self.session.query(KeyInfo).filter_by(account_id=account_id).all()
    
    def save(self, record: KeyInfo) -> KeyInfo:
        """
        Сохраняет или обновляет запись KeyInfo.
        
        Args:
            record: Запись KeyInfo для сохранения
            
        Returns:
            Сохранённая запись
        """
        self.session.merge(record)
        self.session.commit()
        self.session.refresh(record)
        
        logger.debug(f"Сохранена запись KeyInfo для {record.account_id}")
        return record
    
    def create_from_memory(
        self,
        account_id: str,
        category: str,
        memory: str,
        impressive: int,
        metadata: MessageMetadata
    ) -> KeyInfo:
        """
        Создаёт запись воспоминания из анализа сообщения.
        
        Args:
            account_id: ID пользователя
            category: Категория воспоминания
            memory: Текст воспоминания
            impressive: Уровень впечатлительности
            metadata: Метаданные сообщения (настроение, категория и т.д.)
            
        Returns:
            Созданная запись KeyInfo
        """
        try:
            record = KeyInfo(
                account_id=account_id,
                time=datetime.now(timezone.utc),
                category=category,
                subcategory="БезПодкатегории",
                fact=memory,
                mood=metadata.mood.value,
                mood_level=metadata.mood_level.value,
                frequency=0,
                last_used=datetime.now(timezone.utc),
                type=metadata.message_category.value,
                impressive=impressive,
                critical=0,
                first_disclosure=0
            )
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            
            logger.info(f"Создано воспоминание для {account_id}: {category}")
            return record
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка при создании воспоминания: {e}")
            raise
    
    def get_by_category(self, account_id: str, category: str) -> List[KeyInfo]:
        """
        Получает воспоминания по категории.
        
        Args:
            account_id: ID пользователя
            category: Категория воспоминания
            
        Returns:
            Список записей KeyInfo
        """
        return (
            self.session.query(KeyInfo)
            .filter_by(account_id=account_id, category=category)
            .all()
        )
    
    def update_frequency(self, record_id: int) -> Optional[KeyInfo]:
        """
        Обновляет частоту использования воспоминания.
        
        Args:
            record_id: ID записи
            
        Returns:
            Обновлённая запись или None
        """
        record = self.session.query(KeyInfo).filter_by(id=record_id).first()
        
        if not record:
            logger.warning(f"KeyInfo с id={record_id} не найдена")
            return None
        
        record.frequency += 1
        record.last_used = datetime.now(timezone.utc)
        
        self.session.commit()
        self.session.refresh(record)
        
        logger.debug(f"Обновлена частота использования для KeyInfo id={record_id}")
        return record
    
    def delete(self, record_id: int) -> bool:
        """
        Удаляет запись воспоминания.
        
        Args:
            record_id: ID записи
            
        Returns:
            True если удалена, False если не найдена
        """
        record = self.session.query(KeyInfo).filter_by(id=record_id).first()
        
        if not record:
            logger.warning(f"KeyInfo с id={record_id} не найдена для удаления")
            return False
        
        self.session.delete(record)
        self.session.commit()
        
        logger.info(f"Удалена запись KeyInfo id={record_id}")
        return True

