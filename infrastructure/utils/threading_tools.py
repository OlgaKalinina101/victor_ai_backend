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
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

# Глобальный executor
default_executor = ThreadPoolExecutor(max_workers=5)

async def run_in_executor(func: Callable, *args, executor: ThreadPoolExecutor = default_executor, **kwargs) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

