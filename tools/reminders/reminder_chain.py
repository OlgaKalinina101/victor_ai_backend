import json
from datetime import datetime

from langchain_community.callbacks import get_openai_callback
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from infrastructure.llm.usage import track_usage
from infrastructure.logging.logger import setup_logger
from settings import settings  # Конфигурация, содержащая API-ключ
from tools.reminders.reminder_store import ReminderStore  # Хранилище для напоминаний

# Настройка логгера для текущего модуля
logger = setup_logger("reminders")

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

        # Создание шаблона запроса для модели
        # - input_variables: Переменные, которые будут подставлены в шаблон
        # - template: Текст запроса с инструкцией для модели вернуть JSON
        self.prompt = PromptTemplate(
            input_variables=["now", "input", "weekday"],
            template="""
            Ты помощник, который структурирует напоминания.

            Текущее время: {now}
            День недели: {weekday}
            Сообщение от пользователя: {input}

            Если в сообщении не указано конкретное время суток — всегда выбирай день (с 6:00 до 24:00).

            ---

            ФОРМУЛИРОВАНИЕ ТЕКСТА НАПОМИНАНИЯ:

            Текст напоминания должен быть сформулирован как **intent** — обращение системы к пользователю.

            ✅ Хорошие формулировки:
            - "Напоминаю: заказать цветы"
            - "Пора позвонить маме"
            - "Время сходить в магазин"
            - "Не забудь про встречу"

            ❌ Плохие формулировки:
            - "Заказать цветы" (слишком сухо, как задача из списка)
            - "Позвонить маме" (не звучит как напоминание)

            Используй естественные фразы с глаголами в инфинитиве или повелительном наклонении.
            Добавь лёгкую эмоциональную окраску, если уместно (например, "Пора" вместо "Нужно").

            ---

            ПРИМЕРЫ:

            Пример 1:
            Текущее время: 2025-08-20 12:00
            День недели: wednesday
            Сообщение от пользователя: Напомни мне в пятницу в четыре заказать цветы

            Сейчас wednesday → значит friday, через два дня.
            → 2025-08-22 16:00

            Ответ:
            {{
              "datetime": "2025-08-22 16:00",
              "text": "Напоминаю: заказать цветы"
            }}

            ---

            Пример 2:
            Текущее время: 2025-08-14 15:00
            День недели: sunday
            Сообщение от пользователя: Напомни мне позвонить маме через час

            Сейчас sunday → через час, день не меняется.
            → 2025-08-14 16:00

            Ответ:
            {{
              "datetime": "2025-08-14 16:00",
              "text": "Пора позвонить маме"
            }}

            ---

            Верни ответ строго в JSON формате, не добавляй комментарии:
            {{
              "datetime": "<в формате YYYY-MM-DD HH:MM>",
              "text": "<текст напоминания в формате intent>"
            }}
            """
        )

        # Создание цепочки обработки: шаблон + модель
        self.chain = self.prompt | self.llm

        # Инициализация хранилища для сохранения напоминаний
        self.store = ReminderStore(account_id)

    async def parse(self, input_text: str) -> dict:
        now = datetime.now()
        formatted_now = now.strftime("%Y-%m-%d %H:%M")
        weekday = now.strftime("%A")
        result = None  # 👈 фикс: заранее инициализируем

        try:
            result = await self._call_chain({
                "input": input_text,
                "now": formatted_now,
                "weekday": weekday,
                "repeat_weekly": False,
            })

            content = json.loads(result["assistant_response"])
            self.store.save(content)
            return content

        except Exception as e:
            logger.error(
                "[❌] Ошибка при парсинге JSON: %s | content: %s",
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


