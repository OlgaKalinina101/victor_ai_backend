import inspect
from logging import Logger
from typing import Callable, Dict, AsyncGenerator

from core.analysis.preanalysis.preanalysis import analyze_dialogue
from core.router.router_prompts import ROUTER_PROMPT
from infrastructure.llm.client import LLMClient
from infrastructure.logging.logger import setup_logger
from tools.communication.communication_tool import run_communication
from tools.places.places_tool import PlacesContextBuilder
from tools.playlist.playlist_tool import run_playlist_chain
from tools.reminders.reminder_tool import run_reminder_chain
from tools.weather.weather_tool import WeatherContextBuilder

HandlerType = Callable[..., str]  # Тип обработчика может быть sync или async

class MessageTypeManager:
    def __init__(self):
        self.default_route: HandlerType = run_communication
        self.logger: Logger = setup_logger("message_router")

    async def route_message(self, request) -> AsyncGenerator[str | dict, None]:  # ← стримит
        text = request.text.lower().strip()
        account_id = request.session_id
        geo = request.geo

        llm_client = LLMClient(account_id=account_id, mode="foundation")
        result_json = await analyze_dialogue(
            llm_client=llm_client,
            prompt_template=ROUTER_PROMPT,
            user_message=text
        )
        function_call = result_json.get("function call", "None")

        if function_call == "reminder":
            # run_reminder_chain НЕ стримит — собираем в строку
            response = await run_reminder_chain(account_id=account_id, text=text)
            yield response
            return

        # Дефолтный роут
        async for chunk in self._execute_stream(
                self.default_route,
                account_id=account_id,
                text=text,
                function_call=function_call,
                geo=geo,
        ):
            yield chunk

    async def _execute_stream(
            self,
            handler: HandlerType,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        """Выполняет handler и стримит результат."""
        if inspect.isasyncgenfunction(handler):
            # Если handler — async generator
            async for chunk in handler(**kwargs):
                yield chunk
        elif inspect.iscoroutinefunction(handler):
            # Если handler возвращает str
            result = await handler(**kwargs)
            yield result
        else:
            # Синхронный handler
            yield handler(**kwargs)



