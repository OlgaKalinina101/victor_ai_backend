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

"""Репозиторий для работы с будильниками пользователей."""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from infrastructure.database.models import UserAlarms
from infrastructure.logging.logger import setup_logger

logger = setup_logger("alarms_repository")


class AlarmsRepository:
    """Репозиторий для работы с будильниками."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_account_id(self, account_id: str) -> Optional[UserAlarms]:
        """
        Получает конфигурацию будильников пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            UserAlarms или None если не найдено
        """
        return self.session.query(UserAlarms).filter_by(account_id=account_id).first()
    
    def upsert(self, account_id: str, alarms: List[Dict[str, Any]], selected_track_id: Optional[int] = None) -> UserAlarms:
        """
        Создаёт или обновляет будильники пользователя.
        
        Args:
            account_id: ID пользователя
            alarms: Список будильников (dict)
            selected_track_id: ID выбранного трека (опционально)
            
        Returns:
            Созданный/обновлённый объект UserAlarms
        """
        user_alarms = UserAlarms(
            account_id=account_id,
            alarms=alarms,
            selected_track_id=selected_track_id
        )
        
        merged_alarms = self.session.merge(user_alarms)
        self.session.commit()
        self.session.refresh(merged_alarms)
        
        logger.info(f"Обновлены будильники для {account_id}: {len(alarms)} записей")
        return merged_alarms
    
    def update_selected_track(self, account_id: str, track_id: int) -> Optional[UserAlarms]:
        """
        Обновляет выбранный трек для будильника.
        
        Args:
            account_id: ID пользователя
            track_id: ID трека
            
        Returns:
            Обновлённый UserAlarms или None если не найдено
        """
        user_alarms = self.get_by_account_id(account_id)
        
        if not user_alarms:
            logger.warning(f"UserAlarms не найден для {account_id}")
            return None
        
        user_alarms.selected_track_id = track_id
        self.session.commit()
        self.session.refresh(user_alarms)
        
        logger.info(f"Обновлён трек для {account_id}: track_id={track_id}")
        return user_alarms
    
    def delete(self, account_id: str) -> bool:
        """
        Удаляет все будильники пользователя.
        
        Returns:
            True если удалено, False если не найдено
        """
        user_alarms = self.get_by_account_id(account_id)
        
        if user_alarms:
            self.session.delete(user_alarms)
            self.session.commit()
            logger.info(f"Удалены будильники для {account_id}")
            return True
        
        return False

