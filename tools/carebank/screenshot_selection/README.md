# Screenshot Selection Module

Модуль для выбора позиций из скриншотов доставки еды/продуктов.

## Архитектура

### 1. `VisionAnalyzer`
Анализирует скриншот через vision-модель (Qwen3-VL) и извлекает информацию о доступных позициях.

**Вход:** 
- Байты изображения скриншота
- Поисковый запрос пользователя

**Выход:**
```json
{
  "options": [
    {"id": 1, "name": "Блинчики с творогом", "state": "готовое блюдо"},
    {"id": 2, "name": "Блинчики с яблоком", "state": "готовое блюдо"}
  ]
}
```

### 2. `ItemSelector`
Выбирает наиболее подходящую позицию на основе контекста диалога с пользователем.

**Вход:**
- Байты скриншота
- Поисковый запрос
- Account ID (для загрузки контекста)

**Выход:**
```json
{
  "id": "1",
  "selected_item": "Блинчики с творогом",
  "match_type": "exact",
  "user_message": "Нашел блинчики с творогом. ✨"
}
```

## Использование

```python
from tools.carebank.screenshot_selection import ItemSelector

# Инициализация
selector = ItemSelector(account_id="user_123")

# Выбор позиции
result = await selector.select_item(
    screenshot_bytes=image_bytes,
    search_query="блинчики с творогом",
    mime_type="image/png",
    db_session=db_session
)

print(result["user_message"])  # "Нашел блинчики с творогом. ✨"
```

## Конфигурация

- **Vision-модель:** Qwen/Qwen3-VL-8B-Instruct:novita (Hugging Face)
- **LLM для выбора:** Из контекста пользователя (SessionContext.model)
- **Промпты:** `carebank_choice_prompts.yaml`

## Дебаг

Последний обработанный скриншот сохраняется в `debug_screenshots/last_screenshot.*` для отладки.

