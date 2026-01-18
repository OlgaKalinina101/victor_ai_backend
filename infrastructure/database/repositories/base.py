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
Базовый репозиторий с общими CRUD операциями.

Использование опционально - можно писать репозитории без наследования,
как это сделано в tools/maps/repositories/osm_repository.py
"""

from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Базовый репозиторий с типовыми CRUD операциями.
    
    Можно наследоваться для DRY, но это не обязательно.
    Пример без наследования: tools/maps/repositories/osm_repository.py
    """
    
    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model
    
    def get_by_id(self, id: int) -> Optional[T]:
        """Получает запись по ID."""
        return self.session.query(self.model).filter_by(id=id).first()
    
    def get_by_account_id(self, account_id: str) -> List[T]:
        """Получает все записи по account_id (если поле есть)."""
        return self.session.query(self.model).filter_by(account_id=account_id).all()
    
    def create(self, entity: T) -> T:
        """Создаёт новую запись."""
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity
    
    def update(self, entity: T) -> T:
        """Обновляет существующую запись."""
        self.session.merge(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity
    
    def delete(self, entity: T) -> None:
        """Удаляет запись."""
        self.session.delete(entity)
        self.session.commit()
    
    def exists(self, **filters) -> bool:
        """Проверяет существование записи по фильтрам."""
        return self.session.query(
            self.session.query(self.model).filter_by(**filters).exists()
        ).scalar()

