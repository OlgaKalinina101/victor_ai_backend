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

from sqlalchemy.orm import Session
from sqlalchemy import func
from infrastructure.database.models import TrackUserDescription
from typing import List, Dict, Optional

from infrastructure.database.session import Database


def count_track_descriptions(session: Session, account_id: Optional[str] = None) -> List[Dict]:
    """
    Подсчитывает количество треков по каждому сочетанию energy_description и temperature_description.

    :param session: Сессия SQLAlchemy.
    :param account_id: ID пользователя для фильтрации (опционально).
    :return: Список словарей с комбинациями и их количеством.
    """
    try:
        # Запрос с группировкой
        query = (
            session.query(
                TrackUserDescription.energy_description,
                TrackUserDescription.temperature_description,
                func.count().label("count")
            )
            .group_by(TrackUserDescription.energy_description, TrackUserDescription.temperature_description)
        )

        # Фильтрация по account_id, если указан
        if account_id:
            query = query.filter(TrackUserDescription.account_id == account_id)

        # Сортировка для предсказуемого порядка
        query = query.order_by(
            TrackUserDescription.energy_description,
            TrackUserDescription.temperature_description
        )

        results = query.all()

        # Форматируем результат
        return [
            {
                "energy_description": result.energy_description.value if result.energy_description else None,
                "temperature_description": result.temperature_description.value if result.temperature_description else None,
                "count": result.count
            }
            for result in results
        ]
    except Exception as e:
        print(f"Ошибка при подсчёте описаний: {e}")
        return []


if __name__ == "__main__":
    db = Database()
    session = db.get_session()
    try:
        stats = count_track_descriptions(session, account_id="test_user")
        print("Статистика по описаниям треков:")
        for stat in stats:
            print(f"Энергия: {stat['energy_description'] or 'Не указано'}, "
                  f"Температура: {stat['temperature_description'] or 'Не указано'}, "
                  f"Количество: {stat['count']}")
    finally:
        session.close()