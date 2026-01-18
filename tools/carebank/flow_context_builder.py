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

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load
from tools.carebank.models import FoodOrder

logger = setup_logger("care_bank")

PROMPTS_PATH = Path(__file__).parent / "carebank_prompts.yaml"
PROMPTS = yaml_safe_load(PROMPTS_PATH, logger)

def build_flow_prompt(account_id: str, db_session: Session) -> str:
    """
    Собирает промпт на основе последнего заказа пользователя.

    - Берёт последнюю запись из food_orders по account_id
    - Превращает order_data (dict или list) в маркированный список
    - Возвращает текстовый блок, готовый для подстановки в extra_context

    Если заказа нет — возвращает пустую строку.
    """
    # 1. Достаём последний заказ пользователя
    last_order: Optional[FoodOrder] = (
        db_session.query(FoodOrder)
        .filter(FoodOrder.account_id == account_id)
        .order_by(FoodOrder.created_at.desc())
        .first()
    )

    if not last_order or not last_order.order_data:
        return ""

    order_data = last_order.order_data

    # 2. Нормализуем в список строк
    items: list[str] = []

    if isinstance(order_data, dict):
        # сортируем по ключу, чтобы порядок был стабильным ("1","2","3"...)
        for _, value in sorted(order_data.items(), key=lambda kv: str(kv[0])):
            if value:
                items.append(str(value).strip())
    elif isinstance(order_data, list):
        for value in order_data:
            if value:
                items.append(str(value).strip())
    else:
        # Нестандартный формат — просто одна строка
        items.append(str(order_data).strip())

    if not items:
        return ""

    # 3. Собираем маркированный список
    bullet_list = "\n".join(f"- {item}" for item in items)

    if not bullet_list:
        return ""

    # 4. Оборачиваем в понятный кусок для модели
    extra_context = PROMPTS.get(
        "food_flow_completed_prompt",
        ""
    ).format(bullet_list=bullet_list)

    return extra_context