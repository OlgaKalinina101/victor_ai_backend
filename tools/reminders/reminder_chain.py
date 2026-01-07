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

import json
from datetime import datetime
from pathlib import Path

from langchain_community.callbacks import get_openai_callback
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from infrastructure.llm.usage import track_usage
from infrastructure.logging.logger import setup_logger
from infrastructure.utils.io_utils import yaml_safe_load
from settings import settings  # Конфигурация, содержащая API-ключ
from tools.reminders.reminder_store import ReminderStore  # Хранилище для напоминаний

# Настройка логгера для текущего модуля
logger = setup_logger("reminders")

# Загрузка промптов из YAML
PROMPTS_PATH = Path(__file__).parent / "reminder_prompts.yaml"
PROMPTS = yaml_safe_load(PROMPTS_PATH, logger)

class ReminderChain:
    def __init__(self, account_id: str):
        self.account_id = account_id
        # Инициализация модели ChatOpenAI
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            temperature=0.5,
            api_key=settings.DEEPSEEK_API_KEY,  # Новый ключ
            base_url="https://api.deepseek.com/v1",
        )

        # Первый промпт: определение типа напоминания (одноразовое или повторяющееся)
        self.repeat_type_prompt = PromptTemplate(
            input_variables=["input"],
            template=PROMPTS.get("repeat_type_prompt", "")
        )

        # Создание шаблона запроса для модели
        # - input_variables: Переменные, которые будут подставлены в шаблон
        # - template: Текст запроса с инструкцией для модели вернуть JSON
        self.prompt = PromptTemplate(
            input_variables=["now", "input", "weekday"],
            template=PROMPTS.get("reminder_parsing_prompt", "")
        )

        # Создание цепочек обработки: шаблон + модель
        self.repeat_type_chain = self.repeat_type_prompt | self.llm
        self.chain = self.prompt | self.llm

        # Инициализация хранилища для сохранения напоминаний
        self.store = ReminderStore(account_id)

    async def parse(self, input_text: str) -> dict:
        now = datetime.now()
        formatted_now = now.strftime("%Y-%m-%d %H:%M")
        weekday = now.strftime("%A")
        repeat_result = None
        result = None

        try:
            # Шаг 1: Определяем тип напоминания (одноразовое или повторяющееся)
            repeat_result = await self._call_chain_repeat_type({
                "input": input_text,
            })

            repeat_data = json.loads(repeat_result["assistant_response"])
            repeat_weekly = repeat_data.get("repeat_weekly", False)

            logger.info(
                "[📅] Тип напоминания определён: repeat_weekly=%s",
                repeat_weekly
            )

            # Шаг 2: Парсим время и текст напоминания
            result = await self._call_chain({
                "input": input_text,
                "now": formatted_now,
                "weekday": weekday,
            })

            content = json.loads(result["assistant_response"])
            
            # Добавляем repeat_weekly к данным напоминания
            content["repeat_weekly"] = repeat_weekly
            
            # Сохраняем напоминание с полученным типом
            self.store.save(content)
            return content

        except Exception as e:
            logger.error(
                "[❌] Ошибка при парсинге JSON: %s | repeat_result: %s | result: %s",
                str(e),
                repeat_result["assistant_response"] if repeat_result else "NO_RESULT",
                result["assistant_response"] if result else "NO_RESULT"
            )
            raise

    async def _call_chain_repeat_type(self, input_data: dict) -> dict:
        """Вызывает цепочку для определения типа напоминания (repeat_weekly)."""
        @track_usage(
            account_id=self.account_id,
            logger=logger,
            model_name="deepseek-chat",
            provider="deepseek"
        )
        async def _wrapped():
            result: BaseMessage = await self.repeat_type_chain.ainvoke(input_data)

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
            "usage": response["usage"]
        }

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


