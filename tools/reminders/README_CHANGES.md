# This file is part of victor_ai_backend.
#
# victor_ai_backend is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# victor_ai_backend is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with victor_ai_backend. If not, see <https://www.gnu.org/licenses/>.

## Как работает обработка напоминалок 

```
Пользователь: "Каждую среду в 18:00 напомни про косметолога"
           ↓
[Этап 1] _call_chain_repeat_type()
    → Промпт: repeat_type_prompt
    → Результат: {"repeat_weekly": true}
    → @track_usage СРАБАТЫВАЕТ ✅
           ↓
[Этап 2] _call_chain()
    → Промпт: reminder_parsing_prompt
    → Результат: {"datetime": "...", "text": "Пора к косметологу"}
    → @track_usage СРАБАТЫВАЕТ ✅
           ↓
[Объединение]
    → Финальный результат: {
        "datetime": "2025-11-27 18:00",
        "text": "Пора к косметологу",
        "repeat_weekly": true  ← Добавлено из этапа 1
      }
           ↓
[Сохранение в БД (таблица reminders)]
```

## Логи при работе

При каждом вызове `parse()` будет:
1. Два лога `usage:` от декоратора @track_usage (один для каждого вызова LLM)
2. Лог `[📅] Тип напоминания определён: repeat_weekly=...`
3. Два обновления в базе данных через `update_model_usage()`

## Проверка работы

Запустите тест (после установки зависимостей):
```bash
python tests/test_reminder_with_yaml.py
```

Или проверьте в основном коде - создайте напоминание и проверьте логи.

## Примеры определения типа

### Одноразовые (repeat_weekly = false):
- "Напомни завтра в 10:00 позвонить маме"
- "Напомни через час про созвон"
- "В пятницу в 16:00 напомни забрать документы"
- "15 ноября в 12:00 напомни про встречу"

### Повторяющиеся (repeat_weekly = true):
- "Каждую среду в 18:00 напоминай про косметолога"
- "Каждый день в 21:30 напомни лечь спать"
- "По понедельникам в 9:00 напомни про планерку"
- "Каждое утро в 7:30 напомни про зарядку"
- "По выходным в 10:00 напомни про уборку"

