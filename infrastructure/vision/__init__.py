"""
Vision infrastructure package.

Предоставляет инфраструктуру для работы с vision-моделями:
- VisionClient для запросов к vision API
- Утилиты для работы с изображениями
"""

from .client import VisionClient

__all__ = [
    "VisionClient",
]

