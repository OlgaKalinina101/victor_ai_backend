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

"""Выбор лучшей позиции из скриншота доставки"""

import json
from pathlib import Path
from typing import Optional
from logging import Logger

from core.analysis.preanalysis.preanalysis_helpers import parse_llm_json
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load
from settings import settings
from .vision_analyzer import VisionAnalyzer


class ItemSelector:
    """Выбирает лучшую позицию из скриншота доставки на основе контекста диалога"""

    def __init__(
        self,
        account_id: str,
        logger: Optional[Logger] = None,
    ):
        """
        Args:
            account_id: ID аккаунта пользователя
            logger: Логгер (если None - создается новый)
        """
        self.account_id = account_id
        self.logger = logger or setup_logger("item_selector")

        # Инициализация зависимостей
        self.vision_analyzer = VisionAnalyzer(logger=self.logger)
        self.context_store = SessionContextStore(
            storage_path=settings.SESSION_CONTEXT_DIR
        )

        # Загружаем промпты
        prompts_path = Path(__file__).parent.parent / "carebank_choice_prompts.yaml"
        self.prompts = yaml_safe_load(prompts_path, self.logger)

    async def select_item(
        self,
        screenshot_bytes: bytes,
        search_query: str,
        mime_type: str = "image/png",
        db_session=None,
    ) -> dict:
        """
        Анализирует скриншот и выбирает лучшую позицию

        Args:
            screenshot_bytes: Байты изображения скриншота
            search_query: Поисковый запрос (например, "блинчики")
            mime_type: MIME-тип изображения
            db_session: Сессия БД (для загрузки контекста)

        Returns:
            dict: Результат выбора вида:
                {
                    "id": "1",
                    "selected_item": "Блинчики с творогом",
                    "match_type": "exact" | "similar" | "none",
                    "user_message": "Нашел блинчики с творогом. ✨"
                }
        """
        self.logger.info(f"[SELECTOR] Старт выбора позиции для запроса: {search_query}")

        # Шаг 1: Анализируем скриншот через vision-модель
        vision_result = await self.vision_analyzer.analyze_screenshot(
            image_bytes=screenshot_bytes,
            search_query=search_query,
            mime_type=mime_type,
        )
        self.logger.info(f"[SELECTOR] Vision-результат: {vision_result}")

        # Шаг 2: Получаем контекст пользователя
        session_context = self.context_store.load(self.account_id, db_session)

        # Получаем последнюю пару сообщений (1 пара = user + assistant)
        last_messages = session_context.get_last_n_pairs(n=1)
        last_user_message = ""
        if last_messages:
            # Берем последнее user-сообщение
            for msg in last_messages:
                if msg.startswith("user:"):
                    last_user_message = msg.replace("user:", "").strip()
                    break

        self.logger.info(f"[SELECTOR] Последнее сообщение пользователя: {last_user_message}")

        # Шаг 3: Инициализируем LLM клиент с моделью из контекста
        llm_client = LLMClient(
            account_id=self.account_id,
            mode="advanced",  # можно параметризовать при необходимости
        )

        # Формируем промпты
        system_prompt = self.prompts.get("CARE_BANK_CHOICE_SYSTEM_PROMPT", "")
        user_prompt = self.prompts.get("CARE_BANK_CHOICE_USER_PROMPT", "").format(
            last_user_message=last_user_message,
            vision_model_json=json.dumps(vision_result.get("options", []), ensure_ascii=False, indent=2),
        )

        self.logger.debug(f"[SELECTOR] System prompt: {system_prompt[:100]}...")
        self.logger.debug(f"[SELECTOR] User prompt: {user_prompt[:100]}...")

        # Шаг 4: Вызываем LLM для выбора
        try:
            response = await llm_client.get_response(
                system_prompt=system_prompt,
                context_prompt="",  # весь контекст уже в user_prompt
                message_history=[],
                new_message=user_prompt,
                temperature=0.3,  # низкая температура для более детерминированного выбора
                max_tokens=500,
                stream=False,
            )

            self.logger.debug(f"[SELECTOR] LLM ответ (raw): {response}")

            # Парсим JSON-ответ
            result = parse_llm_json(response)
            self.logger.info(
                f"[SELECTOR] Выбрана позиция: id={result.get('id')}, "
                f"match_type={result.get('match_type')}"
            )

            return result

        except json.JSONDecodeError as e:
            self.logger.error(f"[SELECTOR] Ошибка парсинга JSON от LLM: {e}, response={response}")
            # Возвращаем дефолтный ответ в случае ошибки
            return {
                "id": "1",
                "selected_item": vision_result.get("options", [{}])[0].get("name", "Неизвестно"),
                "match_type": "none",
                "user_message": "Что-то пошло не так при выборе, но вот первая позиция из списка 🤔",
            }

        except Exception as e:
            self.logger.exception(f"[SELECTOR] Ошибка при вызове LLM: {e}")
            raise

