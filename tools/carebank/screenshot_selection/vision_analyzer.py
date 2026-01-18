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
Анализ скриншотов доставки через vision-модель.

Этот модуль - domain-specific обертка над VisionClient для анализа
скриншотов доставки в рамках функционала CareBank.
"""

from typing import Optional, Dict, Any
from logging import Logger
from pathlib import Path

from infrastructure.vision import VisionClient
from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load


# Путь к промптам CareBank
PROMPTS_PATH = Path(__file__).parent.parent / "carebank_choice_prompts.yaml"


class VisionAnalyzer:
    """
    Анализирует скриншоты доставки через vision-модель.
    
    Domain-specific обертка над VisionClient для CareBank.
    Использует специфичные промпты из carebank_choice_prompts.yaml.
    """
    
    def __init__(
        self,
        model: str = "Qwen/Qwen3-VL-8B-Instruct:novita",
        api_url: str = "https://router.huggingface.co/v1/chat/completions",
        api_token: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        """
        Инициализирует анализатор скриншотов для CareBank.
        
        Args:
            model: Название vision-модели
            api_url: URL API для vision-модели
            api_token: Токен для API (если None - берется из settings)
            logger: Логгер (если None - создается новый)
        """
        self.logger = logger or setup_logger("vision_analyzer")
        
        # Создаем VisionClient из infrastructure
        self.client = VisionClient(
            model=model,
            api_url=api_url,
            api_token=api_token,
            logger=self.logger,
            timeout=30,
        )
        
        # Загружаем промпты для CareBank
        self.prompts = yaml_safe_load(PROMPTS_PATH, self.logger)
    
    async def analyze_screenshot(
        self,
        image_bytes: bytes,
        search_query: str,
        mime_type: str = "image/png",
    ) -> Dict[str, Any]:
        """
        Анализирует скриншот выдачи доставки и извлекает информацию о позициях.
        
        Args:
            image_bytes: Байты изображения скриншота
            search_query: Поисковый запрос пользователя
            mime_type: MIME-тип изображения
            
        Returns:
            dict: JSON с найденными позициями вида:
                {
                    "options": [
                        {"id": 1, "name": "...", "state": "..."},
                        {"id": 2, "name": "...", "state": "..."}
                    ]
                }
        """
        self.logger.info(f"[CAREBANK_VISION] Анализ скриншота для запроса: {search_query}")
        
        # Получаем промпты из конфига CareBank
        system_prompt = self.prompts.get("CARE_BANK_VISION_SYSTEM_PROMPT", "")
        user_prompt = self.prompts.get("CARE_BANK_VISION_SELECTION_PROMPT", "").format(
            search_query=search_query
        )
        
        # Вызываем VisionClient с JSON-форматом ответа
        try:
            result = await self.client.analyze_json(
                image=image_bytes,
                prompt=user_prompt,
                system_prompt=system_prompt,
                mime_type=mime_type,
                temperature=0.0,
            )
            
            # Проверяем структуру ответа
            if "options" not in result:
                self.logger.warning("[CAREBANK_VISION] Ответ не содержит 'options', возвращаем пустой список")
                result = {"options": []}
            
            self.logger.info(f"[CAREBANK_VISION] Найдено позиций: {len(result.get('options', []))}")
            return result
            
        except Exception as e:
            self.logger.exception(f"[CAREBANK_VISION] Ошибка при анализе скриншота: {e}")
            raise
