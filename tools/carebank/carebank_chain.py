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

import json
from pathlib import Path

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from infrastructure.llm.usage import track_usage
from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load
from settings import settings

# Настройка логгера для текущего модуля
logger = setup_logger("care_bank")

# Загрузка промптов из YAML
PROMPTS_PATH = Path(__file__).parent / "carebank_prompts.yaml"
PROMPTS = yaml_safe_load(PROMPTS_PATH, logger)

class CareBankChain:
    def __init__(self, account_id: str):
        self.account_id = account_id
        # Инициализация модели ChatOpenAI
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            temperature=0.5,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
        )

        # Промпт: выделение списка продуктов из сообщения
        self.care_bank_parsing_prompt = PromptTemplate(
            input_variables=["input"],
            template=PROMPTS.get("care_bank_parsing_prompt", "")
        )

        self.chain = self.care_bank_parsing_prompt | self.llm

    async def parse(self, input_text: str) -> dict:
        """Выделяет из сообщения user список продуктов"""
        try:
            # Шаг 1:
            result = await self._call_chain({
                "input": input_text,
            })

            content = json.loads(result["assistant_response"])

            # делаем обёртку: и отдельный ключ food, и старые ключи
            wrapped = {"food": content}

            return wrapped

        except Exception as e:
            logger.error(
                "[❌] Ошибка при парсинге JSON: %s | result: %s",
                str(e),
                result["assistant_response"] if result else "NO_RESULT"
            )
            raise

    async def _call_chain(self, input_data: dict) -> dict:
        # Оборачиваем только сам вызов LLM — внутри usage-трекинга
        @track_usage(
            account_id=self.account_id,
            logger=logger,
            model_name="deepseek-chat",
            provider="deepseek"
        )
        async def _wrapped():
            result: BaseMessage = await self.chain.ainvoke(input_data)

            token_usage = {}
            if hasattr(result, 'response_metadata') and 'token_usage' in result.response_metadata:
                token_usage = result.response_metadata['token_usage']

            usage = {
                "prompt_tokens": token_usage.get('prompt_tokens', 0),
                "completion_tokens": token_usage.get('completion_tokens', 0),
                "total_tokens": token_usage.get('total_tokens', 0)
            }

            return {
                "result": result,
                "usage": usage
            }

        response = await _wrapped()

        return {
            "assistant_response": response["result"].content,
            "usage": response["usage"]  # Теперь extract_usage_info увидит это
        }
