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

"""Клиент для работы с vision-моделями."""

import asyncio
import base64
import json
import traceback
from typing import Optional, Union, Dict, Any
from logging import Logger

import aiohttp

from infrastructure.llm.usage import track_usage
from infrastructure.logging.logger import setup_logger


class VisionClient:
    """
    Универсальный клиент для работы с vision-моделями.
    
    Поддерживает OpenAI-compatible API для vision-моделей
    (OpenAI GPT-4 Vision, HuggingFace, Novita, etc.)
    """
    
    def __init__(
        self,
        model: str = "Qwen/Qwen3-VL-8B-Instruct:novita",
        api_url: str = "https://router.huggingface.co/v1/chat/completions",
        api_token: Optional[str] = None,
        logger: Optional[Logger] = None,
        timeout: int = 30,
        max_retries: int = 5,
        account_id: str = None,
    ):
        """
        Инициализирует vision client.
        
        Args:
            model: Название vision-модели
            api_url: URL API для vision-модели
            api_token: Токен для API (если None - берется из settings)
            logger: Логгер (если None - создается новый)
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество попыток при ошибках
            account_id: ID аккаунта пользователя для трекинга usage
        """
        self.model = model
        self.api_url = api_url
        self.logger = logger or setup_logger("vision_client")
        self.timeout = timeout
        self.max_retries = max_retries
        self.account_id = account_id
        
        # Настройки для трекинга usage
        self.model_name = "Qwen3-VL-8B-Instruct"
        self.provider = "hugging_face"
        
        # Если токен не передан, берем из settings
        if api_token is None:
            from settings import settings
            api_token = settings.HUGGING_FACE_API_KEY
        
        self.api_token = api_token
    
    def encode_image_bytes(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png"
    ) -> str:
        """
        Кодирует байты изображения в data URL.
        
        Args:
            image_bytes: Байты изображения
            mime_type: MIME-тип изображения (image/png, image/webp, image/jpeg, etc.)
            
        Returns:
            Data URL с base64-кодированным изображением
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"
    
    def encode_image_url(
        self,
        url: str
    ) -> str:
        """
        Возвращает URL изображения как есть (для внешних изображений).
        
        Args:
            url: URL изображения
            
        Returns:
            URL изображения
        """
        return url
    
    @track_usage()
    async def analyze(
        self,
        image: Union[bytes, str],
        prompt: str,
        system_prompt: Optional[str] = None,
        mime_type: str = "image/png",
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Анализирует изображение с помощью vision-модели с максимальной защитой от сетевых ошибок.
        
        Args:
            image: Байты изображения или URL
            prompt: Текстовый промпт для анализа
            system_prompt: Системный промпт (опционально)
            mime_type: MIME-тип изображения (только для bytes)
            temperature: Температура генерации (0.0 - детерминированный)
            response_format: Формат ответа, например {"type": "json_object"}
            **kwargs: Дополнительные параметры для API
            
        Returns:
            dict: Ответ от API с результатами анализа
            
        Raises:
            Exception: При исчерпании всех попыток retry
        """
        self.logger.info(f"[VISION] Начало анализа изображения")
        
        # Определяем тип изображения и кодируем если нужно
        if isinstance(image, bytes):
            image_data = self.encode_image_bytes(image, mime_type)
            self.logger.debug(f"[VISION] Изображение закодировано в base64 ({len(image)} bytes)")
        else:
            image_data = self.encode_image_url(image)
            self.logger.debug(f"[VISION] Используется URL изображения: {image[:100]}")
        
        # Формируем сообщения
        messages = []
        
        # Добавляем системный промпт если есть
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        # Добавляем пользовательское сообщение с изображением
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data}},
            ],
        })
        
        # Формируем payload для API
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        
        # Добавляем response_format если указан
        if response_format:
            payload["response_format"] = response_format
        
        # Вызываем API с retry logic
        last_exception = None
        
        for retry in range(self.max_retries):
            # Экспоненциальный backoff с jitter
            if retry > 0:
                import random
                wait_time = min(2 ** retry + random.uniform(0, 1), 30)  # max 30 секунд
                self.logger.info(f"[VISION][RETRY] Ждём {wait_time:.2f}s перед попыткой {retry + 1}/{self.max_retries}")
                await asyncio.sleep(wait_time)
            
            try:
                # Увеличиваем timeout на каждой попытке
                retry_timeout = aiohttp.ClientTimeout(total=self.timeout + (retry * 20))
                
                async with aiohttp.ClientSession() as session:
                    self.logger.info(f"[VISION] Отправка запроса к {self.api_url}, попытка {retry + 1}/{self.max_retries}")
                    
                    resp = await session.post(
                        self.api_url,
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_token}"},
                        timeout=retry_timeout,
                    )
                    
                    self.logger.info(f"[VISION] Статус ответа API: {resp.status}")
                    
                    # Обработка статусов, требующих retry
                    if resp.status in [429, 500, 502, 503, 504]:
                        error_text = await resp.text()
                        self.logger.warning(f"[VISION][WARN] Статус {resp.status}, retry доступен: {error_text[:200]}")
                        if retry < self.max_retries - 1:
                            continue  # Пробуем снова
                        else:
                            raise Exception(f"API вернул статус {resp.status} после {self.max_retries} попыток: {error_text[:500]}")
                    
                    if resp.status != 200:
                        error_text = await resp.text()
                        self.logger.error(f"[VISION][ERROR] Статус {resp.status}: {error_text[:500]}")
                        raise Exception(f"API вернул статус {resp.status}: {error_text[:500]}")
                    
                    data = await resp.json()
                    self.logger.debug(f"[VISION] Ответ API получен успешно")
                
                # Извлекаем контент из ответа
                if not data.get("choices"):
                    self.logger.error("[VISION][ERROR] В ответе API отсутствуют choices")
                    raise Exception("В ответе API отсутствуют choices")
                
                if not data["choices"][0].get("message") or "content" not in data["choices"][0]["message"]:
                    self.logger.error("[VISION][ERROR] Некорректная структура ответа")
                    raise Exception("Некорректная структура ответа: отсутствует message или content")
                
                raw_content = data["choices"][0]["message"]["content"]
                self.logger.info(f"[VISION] Анализ успешно завершен, длина ответа: {len(raw_content)} символов")
                self.logger.debug(f"[VISION] RAW response: {raw_content[:200]}...")
                
                # Извлекаем usage для трекинга
                usage_data = data.get("usage", {})
                if usage_data:
                    self.logger.debug(f"[VISION] Usage данные: {usage_data}")
                
                return {
                    "content": raw_content,
                    "raw_response": data,
                    "usage": usage_data,  # Для декоратора track_usage
                }
            
            # === SSL ОШИБКИ ===
            except aiohttp.ClientSSLError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] SSL Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[VISION][DEBUG] SSL Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === CONNECTION ОШИБКИ (включая DNS, connection refused, etc.) ===
            except aiohttp.ClientConnectorError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] Connection Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[VISION][DEBUG] Connection details: host={getattr(e, 'host', 'N/A')}, port={getattr(e, 'port', 'N/A')}")
                self.logger.debug(f"[VISION][DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === SERVER DISCONNECTED ===
            except aiohttp.ServerDisconnectedError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] Server Disconnected (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[VISION][DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === CLIENT CONNECTION ERROR ===
            except aiohttp.ClientConnectionError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] Client Connection Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[VISION][DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue

            # === HTTP RESPONSE ERROR (429, 500, etc.) ===
            except aiohttp.ClientResponseError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] ClientResponseError (попытка {retry + 1}/{self.max_retries}): {e}")
                error_body = await e.response.text() if hasattr(e, "response") else "No response body"
                self.logger.error(f"[VISION][DEBUG] Тело ответа: {error_body[:500]}")
                if e.status in [429, 500, 502, 503, 504] and retry < self.max_retries - 1:
                    continue

            # === TIMEOUT ===
            except asyncio.TimeoutError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] Timeout (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[VISION][DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue

            # === OS ERROR (network unreachable, etc.) ===
            except OSError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] OS Error (попытка {retry + 1}/{self.max_retries}): {e}")
                self.logger.debug(f"[VISION][DEBUG] Errno: {e.errno}, Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
                    
            # === JSON DECODE ERROR ===
            except json.JSONDecodeError as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] JSON Decode Error: {e}")
                self.logger.debug(f"[VISION][DEBUG] Traceback: {traceback.format_exc()}")
                # JSON errors не retry-им, сразу выбрасываем
                raise

            # === ВСЕ ОСТАЛЬНЫЕ ОШИБКИ ===
            except Exception as e:
                last_exception = e
                self.logger.error(f"[VISION][ERROR] Неожиданная ошибка (попытка {retry + 1}/{self.max_retries}): {type(e).__name__}: {e}")
                self.logger.debug(f"[VISION][DEBUG] Traceback: {traceback.format_exc()}")
                if retry < self.max_retries - 1:
                    continue
        
        # Если дошли сюда - все попытки провалились
        self.logger.error(f"[VISION][ERROR] Все {self.max_retries} попытки провалились")
        if last_exception:
            raise Exception(f"Vision API недоступен после {self.max_retries} попыток. Последняя ошибка: {type(last_exception).__name__}: {str(last_exception)}") from last_exception
        else:
            raise Exception(f"Vision API недоступен после {self.max_retries} попыток")
    
    async def analyze_json(
        self,
        image: Union[bytes, str],
        prompt: str,
        system_prompt: Optional[str] = None,
        mime_type: str = "image/png",
        temperature: float = 0.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Анализирует изображение и возвращает JSON-ответ.
        
        Удобная обертка над analyze() для случаев, когда ожидается JSON.
        
        Args:
            image: Байты изображения или URL
            prompt: Текстовый промпт для анализа
            system_prompt: Системный промпт (опционально)
            mime_type: MIME-тип изображения (только для bytes)
            temperature: Температура генерации
            **kwargs: Дополнительные параметры для API
            
        Returns:
            dict: Распарсенный JSON из ответа модели
        """
        result = await self.analyze(
            image=image,
            prompt=prompt,
            system_prompt=system_prompt,
            mime_type=mime_type,
            temperature=temperature,
            response_format={"type": "json_object"},
            **kwargs
        )
        
        # Парсим JSON из контента
        try:
            parsed = json.loads(result["content"])
            self.logger.info(f"[VISION] JSON успешно распарсен")
            return parsed
        except json.JSONDecodeError as e:
            self.logger.error(f"[VISION] Ошибка парсинга JSON: {e}")
            self.logger.error(f"[VISION] Контент: {result['content']}")
            raise

