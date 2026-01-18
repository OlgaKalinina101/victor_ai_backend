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

"""Репозиторий для работы с дневником пользователя."""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from infrastructure.database.models import Diary
from infrastructure.logging.logger import setup_logger

logger = setup_logger("diary_repository")


class DiaryRepository:
    """
    Репозиторий для работы с дневником пользователя.
    
    Инкапсулирует логику работы с Diary:
    - Сохранение записей дневника
    - Получение истории записей
    - Обновление записей
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def save_entry(
        self,
        account_id: str,
        entry_text: Optional[str] = None,
        assistant_answer: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Diary:
        """
        Сохраняет запись дневника.
        
        Args:
            account_id: ID пользователя
            entry_text: Текст записи пользователя
            assistant_answer: Ответ ассистента (опционально)
            timestamp: Время записи (по умолчанию текущее время)
            
        Returns:
            Созданная запись Diary
        """
        try:
            record = Diary(
                account_id=account_id,
                entry_text=entry_text,
                assistant_answer=assistant_answer,
                timestamp=timestamp or datetime.utcnow(),
            )
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            
            logger.info(f"Создана запись дневника для {account_id}, id={record.id}")
            return record
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка при сохранении дневника: {e}")
            raise
    
    def get_by_id(self, entry_id: int) -> Optional[Diary]:
        """
        Получает запись дневника по ID.
        
        Args:
            entry_id: ID записи
            
        Returns:
            Запись Diary или None
        """
        return self.session.query(Diary).filter_by(id=entry_id).first()
    
    def get_all_entries(
        self,
        account_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Diary]:
        """
        Получает все записи дневника пользователя.
        
        Args:
            account_id: ID пользователя
            limit: Максимальное количество записей (опционально)
            offset: Смещение для пагинации
            
        Returns:
            Список записей Diary (от новых к старым)
        """
        query = (
            self.session.query(Diary)
            .filter_by(account_id=account_id)
            .order_by(desc(Diary.timestamp))
        )
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def update_assistant_answer(
        self,
        entry_id: int,
        assistant_answer: str
    ) -> Optional[Diary]:
        """
        Обновляет ответ ассистента для записи дневника.
        
        Args:
            entry_id: ID записи
            assistant_answer: Ответ ассистента
            
        Returns:
            Обновлённая запись или None
        """
        entry = self.get_by_id(entry_id)
        
        if not entry:
            logger.warning(f"Запись дневника с id={entry_id} не найдена")
            return None
        
        entry.assistant_answer = assistant_answer
        
        self.session.commit()
        self.session.refresh(entry)
        
        logger.info(f"Обновлён ответ ассистента для записи id={entry_id}")
        return entry
    
    def delete_entry(self, entry_id: int) -> bool:
        """
        Удаляет запись дневника.
        
        Args:
            entry_id: ID записи
            
        Returns:
            True если удалена, False если не найдена
        """
        entry = self.get_by_id(entry_id)
        
        if not entry:
            logger.warning(f"Запись дневника с id={entry_id} не найдена для удаления")
            return False
        
        self.session.delete(entry)
        self.session.commit()
        
        logger.info(f"Удалена запись дневника id={entry_id}")
        return True
    
    def get_entries_by_date_range(
        self,
        account_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Diary]:
        """
        Получает записи дневника за период.
        
        Args:
            account_id: ID пользователя
            start_date: Начало периода
            end_date: Конец периода
            
        Returns:
            Список записей Diary
        """
        return (
            self.session.query(Diary)
            .filter(
                Diary.account_id == account_id,
                Diary.timestamp >= start_date,
                Diary.timestamp <= end_date
            )
            .order_by(desc(Diary.timestamp))
            .all()
        )
    
    def get_recent_entries(self, account_id: str, days: int = 7) -> List[Diary]:
        """
        Получает недавние записи дневника.
        
        Args:
            account_id: ID пользователя
            days: Количество дней назад
            
        Returns:
            Список записей Diary за последние N дней
        """
        from datetime import timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        return (
            self.session.query(Diary)
            .filter(
                Diary.account_id == account_id,
                Diary.timestamp >= start_date
            )
            .order_by(desc(Diary.timestamp))
            .all()
        )

