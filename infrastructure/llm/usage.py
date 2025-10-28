import functools
import logging
from typing import Callable, Optional, Awaitable

from infrastructure.database.repositories import update_model_usage
from infrastructure.llm.helpers import extract_usage_info
from infrastructure.utils.threading_tools import run_in_executor


def track_usage(
    logger: Optional[logging.Logger] = None,
    account_id: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None
):
    """
        Асинхронный декоратор для отслеживания использования LLM-моделей.

        Перехватывает все вызовы LLM, извлекает информацию об использовании токенов
        (input_tokens, output_tokens) из ответа, логирует её и сохраняет в базу данных.

        Декоратор работает с асинхронными функциями, возвращающими словарь с ответом LLM.
        Поддерживает fallback-логику: если параметры не переданы в декораторе,
        пытается получить их из экземпляра класса (self.logger, self.model_name, self.provider).

        Пример использования:

        @track_usage(logger=my_logger, model_name="gpt-4o", provider="openai")
        async def generate_response(self, prompt: str) -> dict:
            # вызов LLM
            return await self.llm_client.generate(prompt)

        Или без параметров (fallback к self.* атрибутам):

        @track_usage()
        async def generate_response(self, prompt: str) -> dict:
            # вызов LLM
            return await self.llm_client.generate(prompt)

        Args:
            logger: Логгер для записи usage-информации.
                    Если None, используется self.logger из первого аргумента функции.
            account_id: Имя аккаунта пользователя.
            model_name: Название модели (например, "gpt-4", "claude-3").
                        Если None, используется self.model_name.
            provider: Провайдер LLM (например, "openai", "anthropic").
                      Если None, используется self.provider.

        Returns:
            Декорированная функция, которая возвращает тот же результат, что и оригинальная.

        Raises:
            ValueError: Если не удалось определить model_name или provider из параметров
                        или атрибутов экземпляра.

        Notes:
            - Ошибки в декораторе логируются как WARNING, но не прерывают выполнение основной функции.
            - Использует extract_usage_info() для парсинга usage из ответа LLM.
            - Сохранение в БД происходит синхронно через run_in_executor() с функцией update_model_usage().
        """
    def decorator(func: Callable[..., Awaitable[dict]]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)

            try:
                # Получаем логгер (из аргументов декоратора или из экземпляра класса)
                _logger = logger or getattr(args[0], "logger", None)

                _account_id = account_id or getattr(args[0], "account_id", None)

                # Извлекаем usage
                usage = extract_usage_info(_logger, response)

                if _logger:
                    _logger.info(f"usage: {usage}")

                if usage is None:
                    return response

                input_tokens, output_tokens = usage

                # Получаем модель и провайдера
                _model_name = model_name or getattr(args[0], "model_name", None)
                _provider = provider or getattr(args[0], "provider", None)

                if not _model_name or not _provider:
                    raise ValueError("track_usage: Не удалось определить model_name или provider.")

                # Отправим usage в базу
                await run_in_executor(
                    update_model_usage,
                    _account_id,
                    _model_name,
                    _provider,
                    input_tokens,
                    output_tokens
                )

            except Exception as e:
                if _logger:
                    _logger.warning(f"[track_usage] Ошибка в декораторе: {e}")

            return response
        return wrapper
    return decorator


def track_usage_stream(
    logger: Optional[logging.Logger] = None,
    account_id: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            _logger = logger or getattr(args[0], "logger", None)
            _account_id = account_id or getattr(args[0], "account_id", None)
            _model_name = model_name or getattr(args[0], "model_name", None)
            _provider = provider or getattr(args[0], "provider", None)

            usage_data = None

            async for chunk in func(*args, **kwargs):
                # === ВАРИАНТ 1: OpenAI-формат (chunk — dict) ===
                if isinstance(chunk, dict):
                    # Ловим usage в последнем chunk
                    if "usage" in chunk:
                        usage_data = chunk["usage"]
                    # Или в choices[0].usage (зависит от провайдера)
                    elif (
                        "choices" in chunk
                        and chunk["choices"]
                        and "usage" in chunk["choices"][0]
                    ):
                        usage_data = chunk["choices"][0]["usage"]

                # === ВАРИАНТ 2: Твой кастомный формат: {"usage": {...}} ===
                elif isinstance(chunk, dict) and "usage" in chunk:
                    usage_data = chunk["usage"]

                # Пробрасываем chunk дальше
                yield chunk

            # === После стрима — сохраняем ===
            if usage_data and _logger:
                input_tokens = usage_data.get("prompt_tokens") or usage_data.get("input_tokens", 0)
                output_tokens = usage_data.get("completion_tokens") or usage_data.get("output_tokens", 0)

                _logger.info(
                    f"[USAGE] account={_account_id} model={_model_name} "
                    f"provider={_provider} input={input_tokens} output={output_tokens}"
                )

                if _account_id and _model_name:
                    await run_in_executor(
                        update_model_usage,
                        _account_id,
                        _model_name,
                        _provider,
                        input_tokens,
                        output_tokens,
                    )

        return wrapper
    return decorator


