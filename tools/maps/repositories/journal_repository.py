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

"""Репозиторий для работы с журналом (Journal)."""

from typing import List, Optional
from sqlalchemy.orm import Session

from tools.maps.models import JournalEntry
from infrastructure.logging.logger import setup_logger

logger = setup_logger("journal_repository")


class JournalRepository:
    """Репозиторий для работы с записями журнала пользователя."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_all(self, account_id: str) -> List[JournalEntry]:
        """
        Получает все записи журнала пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список записей, отсортированный по дате (новые первыми)
        """
        return (
            self.session.query(JournalEntry)
            .filter(JournalEntry.account_id == account_id)
            .order_by(JournalEntry.date.desc())
            .all()
        )
    
    def get_by_id(self, entry_id: int) -> Optional[JournalEntry]:
        """Получает запись по ID."""
        return self.session.query(JournalEntry).filter_by(id=entry_id).first()
    
    def create(self, **fields) -> JournalEntry:
        """
        Создаёт новую запись в журнале.
        
        Args:
            **fields: Поля записи (account_id, date, text, photo_path, poi_name, session_id)
            
        Returns:
            Созданная запись
        """
        entry = JournalEntry(**fields)
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        logger.info(f"Создана запись журнала: id={entry.id}, account_id={entry.account_id}")
        return entry
    
    def update(self, entry_id: int, **fields) -> Optional[JournalEntry]:
        """
        Обновляет запись в журнале.
        
        Args:
            entry_id: ID записи
            **fields: Обновляемые поля
            
        Returns:
            Обновлённая запись или None если не найдена
        """
        entry = self.get_by_id(entry_id)
        if not entry:
            return None
        
        for key, value in fields.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        self.session.commit()
        self.session.refresh(entry)
        logger.info(f"Обновлена запись журнала: id={entry_id}")
        return entry
    
    def delete(self, entry_id: int) -> bool:
        """
        Удаляет запись из журнала.
        
        Returns:
            True если удалена, False если не найдена
        """
        entry = self.get_by_id(entry_id)
        if entry:
            self.session.delete(entry)
            self.session.commit()
            logger.info(f"Удалена запись журнала: id={entry_id}")
            return True
        return False
    
    def get_by_session(self, session_id: str) -> List[JournalEntry]:
        """Получает записи по session_id."""
        return (
            self.session.query(JournalEntry)
            .filter(JournalEntry.session_id == session_id)
            .order_by(JournalEntry.date.desc())
            .all()
        )

