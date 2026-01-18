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

from fastapi import APIRouter, HTTPException, Depends

from api.dependencies.runtime import get_db
from infrastructure.database.session import Database
from tools.maps.repositories import StatsRepository
from infrastructure.logging.logger import setup_logger

router = APIRouter(prefix="/api/stats", tags=["stats"])
logger = setup_logger("stats_api")

@router.get("/")
def get_stats(account_id: str, db: Database = Depends(get_db)):
    """
    Возвращает статистику прогулок пользователя за текущий день и неделю.

    Агрегирует данные о физической активности пользователя: пройденное расстояние,
    количество шагов, серийную активность (streak) и доступные достижения.
    Используется для отображения дашборда с мотивационными показателями
    и отслеживания прогресса в фитнес-привычках.

    Args:
        account_id: Идентификатор пользователя (query-параметр, обязательный).

    Returns:
        Dict[str, Any] с ключами:
            - today_distance: Общее расстояние, пройденное сегодня (в метрах)
            - today_steps: Общее количество шагов за сегодня
            - weekly_chart: Список из 7 чисел, представляющих пройденное расстояние
                            за каждый из последних 7 дней (от самого старого к самому свежему)
            - streak: Текущая длина серии дней с активностью (дней подряд)
            - achievements: Список названий доступных достижений пользователя

    Raises:
        HTTPException 500: При внутренней ошибке базы данных или обработки данных.

    Notes:
        - Статистика рассчитывается за последние 7 полных дней (включая сегодня)
        - Расстояние измеряется в метрах, шаги - в целых числах
        - Weekly_chart всегда содержит 7 элементов, даже если в некоторые дни не было активности
        - Серия (streak) прерывается, если пользователь не совершал прогулок в течение дня
    """
    with db.get_session() as session:
        try:
            repo = StatsRepository(session)
            
            # Получаем полную статистику через репозиторий
            stats = repo.get_full_stats(account_id)
            achievements = repo.get_all_achievements()
            
            logger.info(
                f"[stats] Статистика для {account_id}: "
                f"distance={stats['today_distance']}m, steps={stats['today_steps']}, "
                f"streak={stats['streak']}"
            )
            
            return {
                **stats,
                "achievements": achievements,
            }

        except Exception as e:
            logger.error(f"[stats] Ошибка при получении статистики: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении статистики: {e}")
