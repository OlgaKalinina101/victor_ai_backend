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

"""Репозиторий для работы с достижениями (Achievements)."""

from typing import List, Optional
from sqlalchemy.orm import Session

from tools.maps.models import Achievement
from infrastructure.logging.logger import setup_logger

logger = setup_logger("achievement_repository")


class AchievementRepository:
    """Репозиторий для работы с достижениями пользователя."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_all(self, account_id: str) -> List[Achievement]:
        """
        Получает все достижения пользователя.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список всех достижений пользователя
        """
        return (
            self.session.query(Achievement)
            .filter(Achievement.account_id == account_id)
            .all()
        )
    
    def get_by_id(self, achievement_id: int) -> Optional[Achievement]:
        """Получает достижение по ID."""
        return self.session.query(Achievement).filter_by(id=achievement_id).first()
    
    def get_unlocked(self, account_id: str) -> List[Achievement]:
        """
        Получает только разблокированные достижения.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список разблокированных достижений (где unlocked_at != None)
        """
        return (
            self.session.query(Achievement)
            .filter(
                Achievement.account_id == account_id,
                Achievement.unlocked_at.isnot(None)
            )
            .all()
        )
    
    def get_locked(self, account_id: str) -> List[Achievement]:
        """
        Получает только заблокированные достижения.
        
        Args:
            account_id: ID пользователя
            
        Returns:
            Список заблокированных достижений (где unlocked_at == None)
        """
        return (
            self.session.query(Achievement)
            .filter(
                Achievement.account_id == account_id,
                Achievement.unlocked_at.is_(None)
            )
            .all()
        )
    
    def count_unlocked(self, account_id: str) -> int:
        """Считает количество разблокированных достижений."""
        return (
            self.session.query(Achievement)
            .filter(
                Achievement.account_id == account_id,
                Achievement.unlocked_at.isnot(None)
            )
            .count()
        )

