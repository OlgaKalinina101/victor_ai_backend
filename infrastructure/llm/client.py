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

import asyncio
import base64
import json
import traceback
from pathlib import Path
from typing import List, Any, Optional, Dict, Union, AsyncGenerator

import aiohttp

from infrastructure.llm.usage import track_usage, track_usage_stream
from infrastructure.logging.logger import setup_logger
from settings import settings


class LLMClient:
    """Клиент для взаимодействия с LLM API."""

    def __init__(self, account_id: str, mode: str = "advanced"):
        self.mode = mode
        self.account_id = account_id
        self.logger = setup_logger("llm_client")
        self.mode_config = {
            "creative": {
                "model": "grok-4-1-fast-non-reasoning-latest",
                "url": "https://api.x.ai/v1/chat/completions",
                "bearer": settings.XAI_API_KEY,
                "temperature": 0.5,
                "max_tokens": 3000,
                "provider": "xai",
                "supports_vision": False
            },
            "advanced": {
                "model": "gpt-4o",
                "url": "https://api.openai.com/v1/chat/completions",
                "bearer": settings.OPENAI_API_KEY,
                "temperature": 0.5,
                "max_tokens": 3000,
                "provider": "openai",
                "supports_vision": True
            },
            "foundation": {
                "model": "deepseek-chat",
                "url": "https://api.deepseek.com/v1/chat/completions",
                "bearer": settings.DEEPSEEK_API_KEY,
                "temperature": 0.5,
                "max_tokens": 3000,
                "provider": "deepseek",
                "supports_vision": False
            }
        }
        if mode not in self.mode_config:
            self.logger.error(f"[ERROR] Неизвестный режим: {mode}")
            raise ValueError(f"Неизвестный режим: {mode}")
        self.model_name = self.mode_config[mode]["model"]
        self.provider = self.mode_config[mode]["provider"]
        self.timeout = aiohttp.ClientTimeout(total=180)
        self.max_retries = 5  # Увеличили с 3 до 5 для надежности

    async def get_response(self,
                      system_prompt: str,
                      context_prompt: str,
                      message_history: Optional[List[str]] = None,
                      new_message: Optional[str] = None,
                      temperature: float = 0.5,
                      top_p: Optional[float] = None,
                      max_tokens: int = 3000,
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
            max_tokens: int = 3000
    ) -> AsyncGenerator[str, None]:
        """Возвращает стрим чанков."""
        self.logger.info(f"[INFO] Запуск LLM в режиме {self.mode}, stream=True")
        try:
            # ДОБАВЬ В НАЧАЛО:
            self.logger.info(f"[DEBUG_STREAM] new_message: {new_message[:200]}...")
            self.logger.info(
                f"[DEBUG_STREAM] message_history последнее: {message_history[-1][:200] if message_history else 'пусто'}...")
            messages = self._build_messages(system_prompt, context_prompt, message_history, new_message)
            json_payload = self._build_payload(temperature, top_p, max_tokens, stream=True)
            json_payload["messages"] = messages
            # ДОБАВЬ ПОСЛЕ:
            self.logger.info(f"[DEBUG_STREAM] Всего messages: {len(messages)}")
            self.logger.info(
                f"[DEBUG_STREAM] Последнее user message: {messages[-1]['content'][:200] if messages else 'нет'}...")

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
        """Отправляет запрос к LLM API с ретраями и максимальной защитой от сетевых ошибок."""
        self.logger.debug("[DEBUG] Отправка запроса к LLM API")
        cfg = self.mode_config[self.mode]
        error_msg = "Я настолько задумался, что сломал API... 😏 Давай снизим градус?"

        for retry in range(self.max_retries):
            # Экспоненциальный backoff с jitter
            if retry > 0:
                import random
                wait_time = min(2 ** retry + random.uniform(0, 1), 30)  # max 30 секунд
                self.logger.info(f"[RETRY] Ждём {wait_time:.2f}s перед попыткой {retry + 1}/{self.max_retries}")
                await asyncio.sleep(wait_time)
            
            try:
                # Увеличиваем timeout на каждой попытке
                retry_timeout = aiohttp.ClientTimeout(total=120 + (retry * 30))
                
                async with aiohttp.ClientSession() as session:
                    self.logger.info(f"[DEBUG] Отправка запроса к {cfg['url']}, попытка {retry + 1}/{self.max_retries}")
                    response = await session.post(
                        cfg["url"],
                        json={**json_payload, "messages": json_payload["messages"]},
                        headers={"Authorization": f"Bearer {cfg['bearer']}"},
                        timeout=retry_timeout
                    )

                    self.logger.info(f"[DEBUG] Статус ответа API: {response.status}")

                    # Обработка статусов, требующих retry
                    if response.status in [429, 500, 502, 503, 504]:
                        error_body = await response.text()
                        self.logger.warning(f"[WARN] Статус {response.status}, retry доступен: {error_body[:200]}")
                        continue  # Пробуем снова
                    
                    if response.status != 200:
                        error_body = await response.text()
                        self.logger.error(f"[ERROR] Получен статус {response.status}, тело: {error_body[:500]}")
                        # Для других ошибок не делаем retry
                        return {
                            "assistant_response": error_msg,
                            "usage": {}
                        }

                    response.raise_for_status()
                    data = await response.json()
                    self.logger.debug(f"[DEBUG] Ответ API получен успешно")

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

            # === SSL ОШИБКИ ===
            except aiohttp.ClientSSLError as e:
                self.logger.error(f"[ERROR] SSL Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] SSL Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === CONNECTION ОШИБКИ (включая DNS, connection refused, etc.) ===
            except aiohttp.ClientConnectorError as e:
                self.logger.error(f"[ERROR] Connection Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Connection details: host={getattr(e, 'host', 'N/A')}, port={getattr(e, 'port', 'N/A')}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === SERVER DISCONNECTED ===
            except aiohttp.ServerDisconnectedError as e:
                self.logger.error(f"[ERROR] Server Disconnected (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === CLIENT CONNECTION ERROR ===
            except aiohttp.ClientConnectionError as e:
                self.logger.error(f"[ERROR] Client Connection Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue

            # === HTTP RESPONSE ERROR (429, 500, etc.) ===
            except aiohttp.ClientResponseError as e:
                self.logger.error(f"[ERROR] ClientResponseError (попытка {retry + 1}/{self.max_retries}): {e}")
                error_body = await e.response.text() if hasattr(e, "response") else "No response body"
                self.logger.error(f"[DEBUG] Тело ответа: {error_body[:500]}")
                if e.status in [429, 500, 502, 503, 504] and retry < self.max_retries - 1:
                    continue
                # Для других статусов не делаем retry
                return {
                    "assistant_response": error_msg,
                    "usage": {}
                }

            # === TIMEOUT ===
            except asyncio.TimeoutError as e:
                self.logger.error(f"[ERROR] Timeout (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue

            # === OS ERROR (network unreachable, etc.) ===
            except OSError as e:
                self.logger.error(f"[ERROR] OS Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Errno: {e.errno}, Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === JSON DECODE ERROR ===
            except json.JSONDecodeError as e:
                self.logger.error(f"[ERROR] JSON Decode Error: {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                return {
                    "assistant_response": error_msg,
                    "usage": {}
                }

            # === ВСЕ ОСТАЛЬНЫЕ ОШИБКИ ===
            except Exception as e:
                self.logger.error(f"[ERROR] Неожиданная ошибка (попытка {retry + 1}/{self.max_retries}): {type(e).__name__}: {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
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
    async def _send_request_stream(self, json_payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Отправляет запрос к LLM API в режиме стриминга с максимальной защитой от сетевых ошибок."""
        self.logger.debug("[DEBUG] Отправка streaming-запроса к LLM API")
        cfg = self.mode_config[self.mode]
        error_msg = "Я настолько задумался, что сломал API... 😏 Давай снизим градус?"
        collected_usage: dict | None = None  # ← сюда сохраним usage

        for retry in range(self.max_retries):
            # Экспоненциальный backoff с jitter перед retry
            if retry > 0:
                import random
                wait_time = min(2 ** retry + random.uniform(0, 1), 30)  # max 30 секунд
                self.logger.info(f"[RETRY] Ждём {wait_time:.2f}s перед попыткой стрима {retry + 1}/{self.max_retries}")
                await asyncio.sleep(wait_time)
            
            try:
                # Увеличиваем timeout на каждой попытке для стриминга
                retry_timeout = aiohttp.ClientTimeout(total=120 + (retry * 30), sock_read=60 + (retry * 15))
                
                async with aiohttp.ClientSession() as session:
                    self.logger.info(f"[DEBUG] Streaming-запрос к {cfg['url']}, попытка {retry + 1}/{self.max_retries}")

                    async with session.post(
                            cfg["url"],
                            json={**json_payload, "stream": True},  # ← явно включаем stream
                            headers={"Authorization": f"Bearer {cfg['bearer']}"},
                            timeout=retry_timeout
                    ) as response:

                        # Обработка статусов, требующих retry
                        if response.status in [429, 500, 502, 503, 504]:
                            error_body = await response.text()
                            self.logger.warning(f"[WARN] Статус {response.status} в стриме, retry доступен: {error_body[:200]}")
                            if retry < self.max_retries - 1:
                                continue  # Пробуем снова
                        
                        if response.status != 200:
                            error_body = await response.text()
                            self.logger.error(f"[ERROR] Статус {response.status}: {error_body[:500]}")
                            yield error_msg
                            return

                        # Читаем SSE-поток
                        chunk_count = 0
                        try:
                            async for line in response.content:
                                line = line.decode('utf-8').strip()
                                chunk_count += 1

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
                        
                        except aiohttp.ClientPayloadError as e:
                            self.logger.error(f"[ERROR] Payload error во время чтения стрима: {e}")
                            if chunk_count > 0:
                                # Если получили хоть что-то, логируем usage и завершаем
                                self.logger.info(f"[INFO] Получено {chunk_count} чанков до ошибки, завершаем")
                                if collected_usage:
                                    self.logger.info(
                                        f"[USAGE] prompt={collected_usage.get('prompt_tokens')} "
                                        f"output={collected_usage.get('completion_tokens')}")
                                return
                            # Если ничего не получили, пробуем retry
                            if retry < self.max_retries - 1:
                                continue

                        # === КОНЕЦ СТРИМА: ЛОГИРУЕМ USAGE ===
                        if collected_usage:
                            self.logger.info(
                                f"[USAGE] Стрим завершён: prompt={collected_usage.get('prompt_tokens')} "
                                f"output={collected_usage.get('completion_tokens')}")

                        self.logger.info(f"[INFO] Стрим успешно завершен, получено {chunk_count} чанков")
                        return  # успешно завершили стрим

            # === SSL ОШИБКИ ===
            except aiohttp.ClientSSLError as e:
                self.logger.error(f"[ERROR] SSL Error в стриме (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] SSL Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                yield error_msg
                return
                    
            # === CONNECTION ОШИБКИ (включая DNS, connection refused, etc.) ===
            except aiohttp.ClientConnectorError as e:
                self.logger.error(f"[ERROR] Connection Error в стриме (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Connection details: host={getattr(e, 'host', 'N/A')}, port={getattr(e, 'port', 'N/A')}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                yield error_msg
                return
                    
            # === SERVER DISCONNECTED ===
            except aiohttp.ServerDisconnectedError as e:
                self.logger.error(f"[ERROR] Server Disconnected в стриме (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                yield error_msg
                return
                    
            # === CLIENT CONNECTION ERROR ===
            except aiohttp.ClientConnectionError as e:
                self.logger.error(f"[ERROR] Client Connection Error в стриме (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                yield error_msg
                return

            # === HTTP RESPONSE ERROR (429, 500, etc.) ===
            except aiohttp.ClientResponseError as e:
                self.logger.error(f"[ERROR] ClientResponseError в стриме (попытка {retry + 1}/{self.max_retries}): {e}")
                error_body = await e.response.text() if hasattr(e, "response") else "No response body"
                self.logger.error(f"[DEBUG] Тело ответа: {error_body[:500]}")
                if e.status in [429, 500, 502, 503, 504] and retry < self.max_retries - 1:
                    continue
                yield error_msg
                return

            # === TIMEOUT ===
            except asyncio.TimeoutError as e:
                self.logger.error(f"[ERROR] Timeout в стриме (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                yield error_msg
                return

            # === OS ERROR (network unreachable, etc.) ===
            except OSError as e:
                self.logger.error(f"[ERROR] OS Error в стриме (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[DEBUG] Errno: {e.errno}, Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                yield error_msg
                return

            # === ВСЕ ОСТАЛЬНЫЕ ОШИБКИ ===
            except Exception as e:
                self.logger.error(f"[ERROR] Неожиданная ошибка в стриме (попытка {retry + 1}/{self.max_retries}): {type(e).__name__}: {e}")
                self.logger.debug(f"[DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                yield error_msg
                return

        self.logger.error(f"[ERROR] Все {self.max_retries} попытки стрима провалились")
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
