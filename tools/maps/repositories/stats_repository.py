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

"""Репозиторий для работы со статистикой прогулок."""

from typing import List, Dict, Any
from datetime import date, timedelta
from sqlalchemy.orm import Session

from tools.maps.models import WalkSession, Streak, Achievement
from infrastructure.logging.logger import setup_logger

logger = setup_logger("stats_repository")


class StatsRepository:
    """Репозиторий для работы со статистикой прогулок пользователя."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_weekly_walks(self, account_id: str, days: int = 7) -> List[WalkSession]:
        """
        Получает прогулки за последние N дней.
        
        Args:
            account_id: ID пользователя
            days: Количество дней (по умолчанию 7)
            
        Returns:
            Список прогулок за указанный период
        """
        today = date.today()
        start_date = today - timedelta(days=days - 1)
        
        return (
            self.session.query(WalkSession)
            .filter(
                WalkSession.account_id == account_id,
                WalkSession.start_time >= start_date
            )
            .all()
        )
    
    def get_today_stats(self, account_id: str) -> Dict[str, int]:
        """
        Получает статистику за сегодня.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Dict с ключами distance (метры) и steps (шаги)
        """
        today = date.today()
        
        walks = (
            self.session.query(WalkSession)
            .filter(
                WalkSession.account_id == account_id,
                WalkSession.start_time >= today
            )
            .all()
        )
        
        total_distance = sum(w.distance_m or 0 for w in walks)
        total_steps = sum(w.steps or 0 for w in walks)
        
        return {
            "distance": total_distance,
            "steps": total_steps
        }
    
    def get_weekly_chart(self, account_id: str) -> List[int]:
        """
        Получает график расстояний за последние 7 дней.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список из 7 чисел (расстояние в метрах за каждый день)
        """
        today = date.today()
        walks = self.get_weekly_walks(account_id, days=7)
        
        # Инициализируем массив нулями
        weekly_chart = [0] * 7
        
        # Заполняем данными
        for walk in walks:
            walk_date = walk.start_time.date()
            days_ago = (today - walk_date).days
            
            if 0 <= days_ago < 7:
                # Индекс в массиве (0 = сегодня, 6 = неделю назад)
                # Поэтому используем (6 - days_ago)
                weekly_chart[6 - days_ago] += walk.distance_m or 0
        
        return weekly_chart
    
    def get_streak(self, account_id: str) -> int:
        """
        Получает текущую серию дней с активностью.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Длина серии (0 если нет)
        """
        streak = (
            self.session.query(Streak)
            .filter_by(account_id=account_id)
            .first()
        )
        
        return streak.current_length if streak else 0
    
    def get_full_stats(self, account_id: str) -> Dict[str, Any]:
        """
        Получает полную статистику пользователя за неделю.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Dict с полной статистикой (today_distance, today_steps, weekly_chart, streak)
        """
        today_stats = self.get_today_stats(account_id)
        weekly_chart = self.get_weekly_chart(account_id)
        streak = self.get_streak(account_id)
        
        return {
            "today_distance": today_stats["distance"],
            "today_steps": today_stats["steps"],
            "weekly_chart": weekly_chart,
            "streak": streak,
        }
    
    def get_all_achievements(self) -> List[str]:
        """
        Получает названия всех достижений в системе.
        
        Returns:
            Список названий достижений
        """
        achievements = self.session.query(Achievement).all()
        return [a.name for a in achievements]

