import asyncio
import json
import traceback
from typing import List, Any, Optional, Dict, Union, AsyncGenerator

import aiohttp

from infrastructure.llm.usage import track_usage, track_usage_stream
from infrastructure.logging.logger import setup_logger
from settings import settings


class LLMClient:
    """Клиент для взаимодействия с LLM API."""

    def __init__(self, account_id: str = "test_user", mode: str = "advanced"):
        self.mode = mode
        self.account_id = account_id
        self.logger = setup_logger("llm_client")
        self.mode_config = {
            "creative": {
                "model": "grok-3-beta",
                "url": "https://api.x.ai/v1/chat/completions",
                "bearer": settings.XAI_API_KEY,
                "temperature": 0.5,
                "max_tokens": 1500,
                "provider": "xai"
            },
            "advanced": {
                "model": "gpt-4o",
                "url": "https://api.openai.com/v1/chat/completions",
                "bearer": settings.OPENAI_API_KEY,
                "temperature": 0.5,
                "max_tokens": 1500,
                "provider": "openai"
            },
            "foundation": {
                "model": "deepseek-chat",
                "url": "https://api.deepseek.com/v1/chat/completions",
                "bearer": settings.DEEPSEEK_API_KEY,
                "temperature": 0.5,
                "max_tokens": 1500,
                "provider": "deepseek"
            }
        }
        if mode not in self.mode_config:
            self.logger.error(f"[ERROR] Неизвестный режим: {mode}")
            raise ValueError(f"Неизвестный режим: {mode}")
        self.model_name = self.mode_config[mode]["model"]
        self.provider = self.mode_config[mode]["provider"]
        self.timeout = aiohttp.ClientTimeout(total=120)
        self.max_retries = 3

    async def get_response(self,
                      system_prompt: str,
                      context_prompt: str,
                      message_history: Optional[List[str]] = None,
                      new_message: Optional[str] = None,
                      temperature: float = 0.5,
                      top_p: Optional[float] = None,
                      max_tokens: int = 1500,
                      stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        """
        Вызывает LLM для генерации ответа.

        Args:
            system_prompt: Системный промпт.
            context_prompt: Контекстный промпт.
            message_history: История сообщений.
            new_message: Новое сообщение пользователя.
            temperature: Температура генерации.
            top_p: Параметр top-p (если указан).
            max_tokens: Максимальное количество токенов.
            stream: Режим стриминга (не поддерживается в текущей версии).

        Returns:
            str: Ответ LLM или сообщение об ошибке.
        """
        self.logger.info(f"[INFO] Запуск LLM в режиме {self.mode}, stream={stream}")

        try:
            messages = self._build_messages(system_prompt, context_prompt, message_history, new_message)
            json_payload = self._build_payload(temperature, top_p, max_tokens, stream)
            json_payload["messages"] = messages

            if stream:
                return self._send_request_stream(json_payload)  # ← generator
            else:
                response = await self._send_request(json_payload)  # ← dict
                return response["assistant_response"]

        except Exception as e:
            self.logger.exception(f"[ERROR] Ошибка при вызове LLM: {e}")
            if stream:
                async def error_generator():
                    yield "Кажется, у нас что-то не то с API или интернетом..."

                return error_generator()
            else:
                return "Кажется, у нас что-то не то с API или интернетом..."

    async def get_response_stream(
            self,
            system_prompt: str,
            context_prompt: str,
            message_history: List[str],
            new_message: str,
            temperature: float = 0.5,
            top_p: Optional[float] = None,
            max_tokens: int = 1500
    ) -> AsyncGenerator[str, None]:
        """Возвращает стрим чанков."""
        self.logger.info(f"[INFO] Запуск LLM в режиме {self.mode}, stream=True")
        try:
            messages = self._build_messages(system_prompt, context_prompt, message_history, new_message)
            json_payload = self._build_payload(temperature, top_p, max_tokens, stream=True)
            json_payload["messages"] = messages

            async for chunk in self._send_request_stream(json_payload):
                yield chunk

        except Exception as e:
            self.logger.exception(f"[ERROR] Ошибка при вызове LLM: {e}")
            yield "Кажется, у нас что-то не то с API или интернетом..."

    def _build_messages(self, system_prompt: str, context_prompt: str, message_history: List[str], new_message: str) -> \
    List[Dict[str, str]]:
        """Формирует список сообщений для API."""
        self.logger.debug("[DEBUG] Формирование списка сообщений")
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_prompt}
            ]
            # История (если есть)
            if message_history:
                parsed_history = []
                for line in message_history:
                    if line.startswith("user:"):
                        parsed_history.append({"role": "user", "content": line[5:].strip()})
                    elif line.startswith("assistant:"):
                        parsed_history.append({"role": "assistant", "content": line[10:].strip()})
                    else:
                        self.logger.warning(f"[WARNING] Неподдерживаемый формат строки в истории: {line}")
                messages.extend(parsed_history)

            # Новое сообщение (если есть)
            if new_message:
                messages.append({"role": "user", "content": new_message})

            self.logger.debug(f"[DEBUG] Сформированные сообщения: {messages}")
            return messages
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при формировании сообщений: {e}")
            raise

    def _build_payload(self, temperature: float, top_p: Optional[float], max_tokens: int, stream: bool) -> Dict[
        str, Any]:
        """Формирует JSON-пayload для API-запроса."""
        self.logger.debug("[DEBUG] Формирование payload")
        try:
            cfg = self.mode_config[self.mode]
            json_payload = {
                "model": cfg["model"],
                "messages": None,  # Будет заполнено в _send_request
                "max_tokens": max_tokens,
                "temperature": temperature if temperature is not None else cfg["temperature"],
                "stream": stream
            }
            if top_p is not None:
                json_payload["top_p"] = top_p
            return json_payload
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при формировании payload: {e}")
            raise

    @track_usage()
    async def _send_request(self, json_payload: Dict[str, Any]) -> dict:
        """Отправляет запрос к LLM API с ретраями."""
        self.logger.debug("[DEBUG] Отправка запроса к LLM API")
        cfg = self.mode_config[self.mode]
        error_msg = "Я настолько задумался, что сломал API... 😏 Давай снизим градус?"

        for retry in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    self.logger.info(f"[DEBUG] Отправка запроса к {cfg['url']}, попытка {retry + 1}/{self.max_retries}")
                    response = await session.post(
                        cfg["url"],
                        json={**json_payload, "messages": json_payload["messages"]},
                        headers={"Authorization": f"Bearer {cfg['bearer']}"},
                        timeout=self.timeout
                    )

                    self.logger.info(f"[DEBUG] Статус ответа API: {response.status}")

                    if response.status != 200:
                        error_body = await response.text()
                        self.logger.error(f"[ERROR] Получен статус {response.status}, тело: {error_body}")
                        return {
                            "assistant_response": error_msg,
                            "usage": {}
                        }

                    response.raise_for_status()
                    data = await response.json()
                    self.logger.debug(f"[DEBUG] Ответ API: {data}")

                    if not data.get("choices"):
                        self.logger.error("[ERROR] В ответе API отсутствуют choices")
                        return {
                            "assistant_response": error_msg,
                            "usage": {}
                        }

                    choice = data["choices"][0]
                    if "message" not in choice or "content" not in choice["message"]:
                        self.logger.error("[ERROR] Некорректная структура ответа: отсутствует message или content")
                        return {
                            "assistant_response": error_msg,
                            "usage": {}
                        }

                    assistant_response = choice["message"]["content"]
                    if assistant_response is None:
                        self.logger.error("[ERROR] Содержимое ответа равно None")
                        return {
                            "assistant_response": error_msg,
                            "usage": {}
                        }

                    self.logger.info(f"[DEBUG] Результат API: {assistant_response[:100]}...")
                    return {
                        "assistant_response": assistant_response.strip(),
                        "usage": data.get("usage", {})
                    }

            except aiohttp.ClientResponseError as e:
                self.logger.error(f"[ERROR] ClientResponseError: {e}")
                error_body = await e.response.text() if hasattr(e, "response") else "No response body"
                self.logger.error(f"[DEBUG] Тело ответа: {error_body}")
                if e.status == 429:
                    self.logger.info(f"[DEBUG] Лимит запросов, повтор через {2 ** retry} секунд")
                    await asyncio.sleep(2 ** retry)
                    continue
                return {
                    "assistant_response": error_msg,
                    "usage": {}
                }

            except asyncio.TimeoutError as e:
                self.logger.error(f"[ERROR] TimeoutError: {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                self.logger.info(f"[DEBUG] Повтор через {2 ** retry} секунд")
                await asyncio.sleep(2 ** retry)
                continue

            except Exception as e:
                self.logger.error(f"[ERROR] Общая ошибка при вызове API: {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                return {
                    "assistant_response": error_msg,
                    "usage": {}
                }

        self.logger.error(f"[ERROR] Все {self.max_retries} попытки провалились")
        return {
            "assistant_response": "Кажется, у нас что-то не то с API или интернетом...",
            "usage": {}
        }

    @track_usage_stream()
    async def _send_request_stream(self, json_payload: Dict[str, Any]) -> AsyncGenerator[Union[str, dict], None]:
        """Отправляет запрос к LLM API в режиме стриминга."""
        self.logger.debug("[DEBUG] Отправка streaming-запроса к LLM API")
        cfg = self.mode_config[self.mode]
        error_msg = "Я настолько задумался, что сломал API... 😏 Давай снизим градус?"
        collected_usage: dict | None = None  # ← сюда сохраним usage

        for retry in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    self.logger.info(f"[DEBUG] Streaming-запрос к {cfg['url']}, попытка {retry + 1}/{self.max_retries}")

                    async with session.post(
                            cfg["url"],
                            json={**json_payload, "stream": True},  # ← явно включаем stream
                            headers={"Authorization": f"Bearer {cfg['bearer']}"},
                            timeout=self.timeout
                    ) as response:

                        if response.status != 200:
                            error_body = await response.text()
                            self.logger.error(f"[ERROR] Статус {response.status}: {error_body}")
                            yield error_msg
                            return

                        # Читаем SSE-поток
                        async for line in response.content:
                            line = line.decode('utf-8').strip()

                            if not line or line == "data: [DONE]":
                                continue

                            if line.startswith("data: "):
                                try:
                                    chunk_data = json.loads(line[6:])  # убираем "data: "

                                    # === ИЩЕМ USAGE ===
                                    if "usage" in chunk_data:
                                        collected_usage = chunk_data["usage"]
                                        self.logger.debug(f"[USAGE] Найдено: {collected_usage}")
                                        # НЕ yield'им usage — только сохраняем

                                    # Парсим chunk (структура зависит от провайдера)
                                    if "choices" in chunk_data and chunk_data["choices"]:
                                        delta = chunk_data["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content

                                except json.JSONDecodeError as e:
                                    self.logger.warning(f"[WARN] Не удалось распарсить chunk: {line[:100]}")
                                    continue

                            # === КОНЕЦ СТРИМА: ОТПРАВЛЯЕМ USAGE ===
                            if collected_usage:
                                self.logger.info(
                                    f"[USAGE] Отправлено в стрим: prompt={collected_usage.get('prompt_tokens')} "
                                    f"output={collected_usage.get('completion_tokens')}")
                                yield {"usage": collected_usage}

                        return  # успешно завершили стрим

            except aiohttp.ClientResponseError as e:
                self.logger.error(f"[ERROR] ClientResponseError: {e}")
                if e.status == 429:
                    self.logger.info(f"[DEBUG] Rate limit, ждём {2 ** retry}с")
                    await asyncio.sleep(2 ** retry)
                    continue
                yield error_msg
                return

            except asyncio.TimeoutError:
                self.logger.error(f"[ERROR] Timeout, ждём {2 ** retry}с")
                await asyncio.sleep(2 ** retry)
                continue

            except Exception as e:
                self.logger.error(f"[ERROR] Ошибка стриминга: {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                yield error_msg
                return

        self.logger.error(f"[ERROR] Все {self.max_retries} попытки провалились")
        yield "Кажется, у нас что-то не то с API или интернетом..."

    def update_config(self, mode: str, **kwargs: Any) -> None:
        """Обновляет конфигурацию для указанного режима."""
        self.logger.debug(f"[DEBUG] Обновление конфигурации для режима {mode}")
        try:
            if mode not in self.mode_config:
                self.logger.error(f"[ERROR] Неизвестный режим: {mode}")
                raise ValueError(f"Неизвестный режим: {mode}")
            self.mode_config[mode].update(kwargs)
            self.logger.info(f"[DEBUG] Конфигурация для {mode} обновлена: {kwargs}")
        except Exception as e:
            self.logger.error(f"[ERROR] Ошибка при обновлении конфигурации: {e}")
            raise




