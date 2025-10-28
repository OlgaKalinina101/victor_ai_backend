import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

# Глобальный executor
default_executor = ThreadPoolExecutor(max_workers=5)

async def run_in_executor(func: Callable, *args, executor: ThreadPoolExecutor = default_executor, **kwargs) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

