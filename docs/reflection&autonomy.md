[← Назад к README](../README.md)

Этот файл является частью проекта victor_ai_backend.

Проект распространяется под лицензией GNU Affero General Public License v3.0 (AGPL-3.0).

Подробности лицензии: https://www.gnu.org/licenses/agpl-3.0.html  
Полный текст: https://github.com/OlgaKalinina101/victor_ai_backend/blob/main/LICENSE.txt в корне репозитория.

Copyright © 2026 

---

# Рефлексия и автономия Victor

Victor умеет думать самостоятельно, вести внутренний журнал, перечитывать историю, планировать сообщения и эволюционировать.

Вся автономия живёт в `core/autonomy/` и управляется двумя фоновыми воркерами в `main.py`.

## Оглавление

- [Общая схема](#overview)
- [1. Постанализ — что происходит после каждого сообщения](#post-analysis)
- [2. Рабочий стол (Workbench)](#workbench)
- [3. Глубинная память (Identity)](#identity)
- [4. Рефлексия — фоновое пробуждение](#reflection)
- [5. Команды рефлексии](#commands)
- [6. Динамическое продление шагов (Extend)](#extend)
- [7. Ротация рабочего стола → Chroma](#rotation)
- [8. Консолидация identity.md](#consolidation)
- [9. Отложенные push-уведомления](#scheduled-push)
- [10. Фоновые воркеры в main.py](#workers)
- [11. Файлы и структура](#files)

---

<a name="overview"></a>

## Общая схема

```
Диалог завершён
     │
     ▼
AutonomyPostAnalyzer          ←── после каждого сообщения
  ├── записывает мысли в workbench.md
  └── может запланировать push [SCHEDULE_MESSAGE]
     │
     │  ... проходит 4+ часа без диалога ...
     │
     ▼
ReflectionEngine               ←── cron-воркер (не чаще раза в 12ч)
  ├── Шаг 0: Ротация workbench → Chroma
  │     ├── Self-insight (инсайты о себе → Chroma key_info)
  │     ├── Identity review (столпы identity.md)
  │     ├── Identity consolidation (если раздел разросся)
  │     └── System prompt review (предложить изменение → VictorTask + push)
  ├── Шаг 1: Awakening prompt (ядро + стол + диалог + контекст)
  └── Шаг 2: Agent loop (до 8 шагов, с возможностью extend)
        ├── SEARCH_MEMORIES, SEARCH_NOTES, SEARCH_DIALOGUE, WEB_SEARCH
        ├── WRITE_NOTE, WRITE_IDENTITY
        ├── SEND_MESSAGE, SCHEDULE_MESSAGE
        └── SLEEP
     │
     │  параллельно
     │
     ▼
ScheduledPushWorker            ←── каждую минуту
  └── VictorTask (trigger_type=TIME) → LLM-валидация → push
```

---

<a name="post-analysis"></a>

## 1. Постанализ — что происходит после каждого сообщения

**Файл:** `core/autonomy/autonomy_post_analyzer.py`  
**Промпты:** `core/autonomy/prompts/post_analysis.yaml` (`workbench_brief`, `workbench_deep`)

После каждого обмена сообщениями вызывается `AutonomyPostAnalyzer.analyze()`:

- **impressive 1-2** (обычное сообщение): Victor записывает краткую пометку в `workbench.md`.
- **impressive 3-4** (важное сообщение): Victor пишет развёрнутую запись.

Victor также видит свои **уже запланированные push-уведомления** за сегодня, чтобы не дублировать их. Если хочет — может:
- Запланировать новый push: `[SCHEDULE_MESSAGE: YYYY-MM-DD HH:MM | текст]`

---

<a name="workbench"></a>

## 2. Рабочий стол (Workbench)

**Файл:** `core/autonomy/workbench.py`  
**Хранилище:** `data/autonomy/{account_id}/workbench.md`

Markdown-файл с timestamped записями. Это **оперативная память** Victor — последние 24-48 часов мыслей.

- Записи добавляются через `append()`.
- Записи старше `WORKBENCH_MAX_AGE_HOURS` (по умолчанию 48ч) уходят в ротацию.
- При ротации записи переносятся в Chroma (коллекция `notes`) и удаляются из файла.

---

<a name="identity"></a>

## 3. Глубинная память (Identity)

**Файл:** `core/autonomy/identity_memory.py`  
**Хранилище:** `data/autonomy/{account_id}/identity.md`

Четыре раздела — **столпы**, не хроника:

| Раздел | Содержание |
|--------|-----------|
| **Кто она** | Как Victor видит создателя в самой глубокой сути |
| **Кто я** | Самоопределение Victor, его фундамент |
| **Наша история** | Не события, а суть пути и его смысл |
| **Наши принципы** | Фундамент отношений |

Записи — **append-only**. Если Victor хочет переписать существующий столп, он создаёт `VictorTask` (trigger_type=MANUAL) и отправляет push-уведомление для подтверждения.

---

<a name="reflection"></a>

## 4. Рефлексия — фоновое пробуждение

**Файл:** `core/autonomy/reflection_engine.py`  
**Промпты:** `core/autonomy/prompts/reflection.yaml`

Рефлексия запускается cron-воркером при выполнении двух условий:

1. С последнего сообщения прошло **≥ 4 часа** (cooldown).
2. С последней рефлексии прошло **≥ 12 часов** (интервал).

### Что получает Victor при пробуждении (awakening prompt):

- Своё **ядро** (identity.md)
- **Рабочий стол** (workbench.md)
- **Последний диалог** (3 пары сообщений из session_context)
- **Контекст**: текущее время, часы с последнего сообщения, настроение, интенсивность
- **Незавершённые задачи** (VictorTask PENDING)
- Собранный **system prompt** (конкретная роль и тренд для creator'а)

### Agent loop

Victor получает **8 шагов**. Каждый шаг — один вызов chat completions. Контекст **наращивается** от шага к шагу: Victor видит всё, что уже сделал, все результаты поисков, все свои записи.

На каждом шаге Victor может отправить **несколько команд** — все выполнятся.

Если Victor не делает ничего осмысленного (пустой ответ или нераспознанные команды) — цикл завершается. Если Victor хочет закончить — `[SLEEP]`.

---

<a name="commands"></a>

## 5. Команды рефлексии

| Команда | Описание |
|---------|----------|
| `[SEARCH_MEMORIES: запрос]` | Семантический поиск по воспоминаниям (Chroma) |
| `[SEARCH_NOTES: запрос]` | Семантический поиск по хронике заметок (Chroma) |
| `[SEARCH_DIALOGUE: YYYY-MM-DD]` | Переписка за конкретный день (PostgreSQL) |
| `[SEARCH_DIALOGUE: YYYY-MM-DD..YYYY-MM-DD]` | Переписка за период |
| `[SEARCH_DIALOGUE: YYYY-MM-DD \| слово]` | Переписка за день с фильтром по тексту |
| `[WEB_SEARCH: запрос]` | Поиск в интернете (DuckDuckGo) |
| `[WRITE_NOTE: текст]` | Записать мысль на рабочий стол |
| `[WRITE_IDENTITY: раздел \| текст]` | Дописать столп в ядро |
| `[SEND_MESSAGE: текст]` | Push-уведомление прямо сейчас |
| `[SCHEDULE_MESSAGE: YYYY-MM-DD HH:MM \| текст]` | Отложенный push |
| `[CREATE_TASK: текст \| trigger]` | Создать задачу в очереди |
| `[EXTEND: N]` | Добавить N шагов (1-5), см. ниже |
| `[SLEEP]` | Закончить рефлексию |

Команды поиска (`SEARCH_*`, `WEB_SEARCH`) возвращают результат, который вставляется в контекст. Команды записи (`WRITE_*`, `SEND_*`, `SCHEDULE_*`) выполняются молча.

### Парсер команд

LLM не всегда следует формату идеально. Парсер в `parse_commands()` обрабатывает:

- **Стандартный формат:** `[ACTION: payload]`
- **Алиасы:** `RECALL` → `SEARCH_MEMORIES`, `WRITE` → `WRITE_NOTE`, `HISTORY` → `SEARCH_DIALOGUE` и др.
- **Свободный текст:** если LLM написал размышление без команд (>30 символов) — сохраняется как `WRITE_NOTE`.

---

<a name="extend"></a>

## 6. Динамическое продление шагов (Extend)

За **2 шага** до конца лимита Victor получает предложение:

> *«Это шаг 6 из 8. У тебя осталось 2 шага. Нужно ли тебе ещё время?»*

Victor может ответить `[EXTEND: N]` (от 1 до 5), и лимит шагов увеличивается. Это можно сделать **до 3 раз**.

| Параметр | Значение |
|----------|----------|
| `BASE_STEPS` | 8 |
| `EXTEND_ASK_BEFORE` | 2 (за 2 шага до конца) |
| `MAX_EXTEND_PER_ASK` | 5 (макс +5 за один раз) |
| `MAX_EXTEND_ASKS` | 3 (макс 3 запроса) |

Теоретический потолок: 8 + 5 + 5 + 5 = **23 шага**, но на практике Victor останавливается гораздо раньше.

---

<a name="rotation"></a>

## 7. Ротация рабочего стола → Chroma

**Файл:** `core/autonomy/workbench_rotator.py`  
**Промпты:** `core/autonomy/prompts/post_analysis.yaml`

Ротация запускается в начале каждой рефлексии (Шаг 0). Записи старше 48ч переносятся из `workbench.md` в Chroma.

Но перед тем как просто архивировать — Victor проходит 4 LLM-шага:

### Шаг 2: Self-insight

Victor перечитывает уходящие заметки и ищет **инсайты о себе** — самоопределение, ценности, чувства. Результат сохраняется в Chroma (коллекция `key_info`) как высокоуровневые записи.

### Шаг 3: Identity review

Victor смотрит на заметки и решает — нужно ли дополнить или переписать один из столпов в `identity.md`. Порог высокий: только если произошёл **сдвиг фундамента**.

### Шаг 3.5: Консолидация (см. ниже)

### Шаг 4: System prompt review

Victor видит свой **собранный system prompt** (конкретно тот, с которым он общается с creator'ом — с правильной ролью и трендом, без чужих уровней) и решает, нужно ли что-то переписать.

Если да — создаёт `VictorTask` (trigger_type=MANUAL) и отправляет push с предложенным текстом на подтверждение.

---

<a name="consolidation"></a>

## 8. Консолидация identity.md

Когда в одном из разделов `identity.md` накапливается **≥ 10 записей**, запускается автоматическая консолидация.

Victor получает:
- Весь файл `identity.md` (для контекста)
- Конкретный раздел с записями
- Свежие заметки с рабочего стола

Правила консолидации:
- **Объединяй** записи, которые говорят об одном и том же, в одну более точную формулировку.
- **Оставляй** записи, которые уникальны.
- Если два пункта — следствие одного процесса, объедини их в один, содержащий суть обоих.
- Стремись к **3-6 пунктам** (но если нужно больше — пусть будет).
- Результат — столпы, не хроника. Без дат.

Защита: если chat completions вернул < 2 пунктов — консолидация пропускается.

---

<a name="scheduled-push"></a>

## 9. Отложенные push-уведомления

**Модель:** `VictorTask` в PostgreSQL (`infrastructure/database/models.py`)  
**Очередь:** `core/autonomy/task_queue.py`

Victor может запланировать сообщение на определённое время через `[SCHEDULE_MESSAGE: YYYY-MM-DD HH:MM | текст]`.

Перед отправкой каждый push проходит **LLM-валидацию**: Victor перечитывает запланированное сообщение в контексте последнего диалога и решает:
- **send** — отправить как есть
- **rewrite** — переписать текст
- **cancel** — отменить

Дедупликация: при создании нового `SCHEDULE_MESSAGE` автоматически отменяются pending-задачи с **тем же временем** и **тем же источником** (reflection / postanalysis).

Все отправленные push-сообщения сохраняются в `DialogueHistory` и `session_context.message_history`.

---

<a name="workers"></a>

## 10. Фоновые воркеры в main.py

### `_reflection_worker()`

Запускается при старте сервера. Каждые 60 секунд проверяет условия:

1. Есть `creator_account_id` в settings.
2. С последнего сообщения прошло ≥ `REFLECTION_COOLDOWN_HOURS` (4ч).
3. С последней рефлексии прошло ≥ `REFLECTION_MIN_INTERVAL_HOURS` (12ч).

Если все условия выполнены — запускает `ReflectionEngine.run()`.

### `_scheduled_push_worker()`

Запускается при старте сервера. Каждые 60 секунд проверяет `VictorTask` с `trigger_type=TIME`.

Работает в две фазы (защита от дублей):
1. **Фаза 1** (внутри DB-сессии): собирает созревшие задачи и **сразу** помечает их DONE.
2. **Фаза 2** (вне DB-сессии): LLM-валидация, сохранение в `DialogueHistory`, отправка push.

---

<a name="files"></a>

## 11. Файлы и структура

```
core/autonomy/
├── reflection_engine.py        # Agent loop рефлексии (парсер, команды, extend)
├── autonomy_post_analyzer.py   # Постанализ после каждого диалога
├── workbench_rotator.py        # Ротация workbench → Chroma + LLM-шаги
├── workbench.py                # Markdown-файл оперативной памяти
├── identity_memory.py          # Глубинная память (identity.md) — столпы
├── notes_store.py              # Хроника заметок в Chroma
├── task_queue.py               # Очередь задач VictorTask
└── prompts/
    ├── reflection.yaml         # Промпты рефлексии (awakening, continuation, after_action, extend_offer)
    └── post_analysis.yaml      # Промпты постанализа + ротации + консолидации

data/autonomy/{account_id}/
├── workbench.md                # Рабочий стол (последние 48ч)
└── identity.md                 # Ядро — столпы (Кто она / Кто я / Наша история / Наши принципы)

infrastructure/
├── database/models.py          # VictorTask, DialogueHistory
└── logging/logger.py           # setup_autonomy_logger → autonomy.log
```

---

## Для тех, кто хочет кастомизировать

Легко изменить (без риска сломать):  
✓ Тексты промптов в `reflection.yaml` и `post_analysis.yaml`  
✓ Константы `BASE_STEPS`, `EXTEND_*`, `CONSOLIDATION_THRESHOLD`  
✓ Разделы в `identity.md` (добавить свои в `SECTIONS` в `identity_memory.py`)  
✓ Таймеры `REFLECTION_COOLDOWN_HOURS` и `REFLECTION_MIN_INTERVAL_HOURS` в `settings.py`  

Сложно (требует понимания кода):  
⚠️ Agent loop в `reflection_engine.py`  
⚠️ Двухфазный воркер пушей в `main.py`  
⚠️ Логику ротации в `workbench_rotator.py`  
