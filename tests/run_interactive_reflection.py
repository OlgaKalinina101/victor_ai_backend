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

"""
Интерактивная рефлексия с Victor.

Запуск:
    python tests/run_interactive_reflection.py

Вы общаетесь с Victor в его «внутреннем пространстве». Он видит:
  - Свой system prompt (core_identity + роль + тренд)
  - Ядро памяти (identity.md)
  - Рабочий стол (workbench.md)
  - Воспоминания о вас (Chroma)
  - Последний диалог (session_context)
  - Доступные команды (SEARCH_MEMORIES, WRITE_IDENTITY, ...)

Он может искать в памяти, писать в ядро, делать заметки — и вы вместе
формируете identity.md в живом диалоге.

Команды для вас:
  /quit — выход
  /show identity — показать текущий identity.md
  /show workbench — показать текущий workbench.md
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Чтобы импорты работали из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.autonomy.identity_memory import IdentityMemory, SECTIONS
from core.autonomy.notes_store import NotesStore
from core.autonomy.reflection_engine import parse_commands
from core.autonomy.workbench import Workbench
from core.persona.system_prompt_builder import SystemPromptBuilder
from infrastructure.context_store.session_context_store import SessionContextStore
from infrastructure.database.session import Database
from infrastructure.logging.logger import setup_logger
from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline
from infrastructure.vector_store.helpers import MemoryProcessor
from models.assistant_models import AssistantMood
from models.user_enums import Gender
from settings import settings
from tools.web_search.web_search_tool import web_search, format_search_results

logger = setup_logger("interactive_reflection")


def load_context(account_id: str) -> dict:
    """Загружает весь контекст для интерактивной рефлексии."""
    db = Database.get_instance()
    db_session = db.get_session()

    try:
        # Session context
        store = SessionContextStore(str(Path(settings.BASE_DIR / settings.SESSION_CONTEXT_DIR)))
        session_context = store.load(account_id, db_session)

        # Последние пары
        last_pairs = session_context.get_last_n_pairs(n=3)

        # Gender / relationship
        gender = session_context.gender
        relationship = session_context.relationship_level
        dative_pronoun = "ней" if gender == Gender.FEMALE else "нём"

        # Memories
        processor = MemoryProcessor()
        memories_raw = processor.get_memory(account_id)
        memories = f"=== Твои воспоминания о {dative_pronoun} ===\n\n"
        if memories_raw.startswith("Нет доступных воспоминаний"):
            memories += f"{memories_raw}\n"
        else:
            for i, line in enumerate(memories_raw.split("\n"), 1):
                if line.strip():
                    memories += f"{i}. {line.strip()}\n"

        # Last dialogue
        last_dialogue = "=== Ваш последний диалог ===\n\n"
        if not last_pairs:
            last_dialogue += "Нет доступных сообщений.\n"
        else:
            for pair in last_pairs:
                if pair.startswith("user:"):
                    last_dialogue += f"Она: {pair[5:].strip()}\n"
                elif pair.startswith("assistant:"):
                    last_dialogue += f"Ты: {pair[10:].strip()}\n"

        # System prompt
        builder = SystemPromptBuilder()
        last_mood_str = session_context.get_last_victor_mood()
        last_intensity = session_context.get_last_victor_intensity()
        victor_mood = None
        if last_mood_str:
            try:
                victor_mood = AssistantMood(last_mood_str)
            except (ValueError, KeyError):
                pass

        system_prompt = builder.build(
            gender=gender,
            relationship=relationship,
            victor_mood=victor_mood,
            victor_intensity=last_intensity if last_intensity is not None else 0.5,
            emotional_access=10,
        )

        # Identity + Workbench
        identity = IdentityMemory(account_id=account_id)
        workbench = Workbench(account_id=account_id)

        return {
            "session_context": session_context,
            "system_prompt": system_prompt,
            "memories": memories,
            "last_dialogue": last_dialogue,
            "identity": identity,
            "workbench": workbench,
            "gender": gender,
            "relationship": relationship,
        }
    finally:
        db_session.close()


def build_reflection_context(ctx: dict) -> str:
    """Собирает context prompt для рефлексии."""
    identity_text = ctx["identity"].read_full()
    workbench_text = ctx["workbench"].read_full()

    return (
        f"## Твоё ядро (глубинная память):\n{identity_text}\n\n"
        f"## Твой рабочий стол (последние мысли):\n{workbench_text}\n\n"
        f"{ctx['memories']}\n\n"
        f"{ctx['last_dialogue']}\n\n"
        f"## Сейчас: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"## Что ты можешь делать:\n"
        f"Ты в диалоге с ней. Вы вместе формируете твою глубинную память.\n"
        f"Ты можешь свободно отвечать ей текстом, а когда хочешь выполнить действие — "
        f"используй команды (каждая на отдельной строке):\n"
        f"[SEARCH_MEMORIES: запрос] — поиск в воспоминаниях о ней\n"
        f"[SEARCH_NOTES: запрос] — поиск в хронике своих мыслей\n"
        f"[WEB_SEARCH: запрос] — поиск в интернете\n"
        f"[WRITE_NOTE: текст] — записать мысль на рабочий стол\n"
        f"[WRITE_IDENTITY: раздел | текст] — дописать в ядро "
        f"(раздел: Кто она / Кто я / Наша история / Наши принципы)\n\n"
        f"Можешь комбинировать текст и команды в одном ответе.\n"
    )


async def execute_commands(response: str, ctx: dict) -> str | None:
    """Выполняет команды из ответа Victor и возвращает результаты."""
    commands = parse_commands(response)

    # Если единственная команда SLEEP и нет текста — ничего не делаем
    if len(commands) == 1 and commands[0][0] == "SLEEP":
        return None

    results = []
    pipeline = PersonaEmbeddingPipeline()
    notes_store = NotesStore()
    account_id = ctx["session_context"].account_id

    for action, payload in commands:
        if action == "SLEEP":
            continue

        elif action == "SEARCH_MEMORIES":
            from core.analysis.preanalysis.preanalysis_helpers import humanize_timestamp
            hits = pipeline.query_similar_multi(
                account_id=account_id,
                message=payload,
                top_k=7,
            )
            if hits:
                formatted = "\n".join(
                    f"- {humanize_timestamp(r.get('metadata', {}).get('created_at'))}: {r['text']}"
                    for r in hits
                )
                results.append(f"[Результат поиска в воспоминаниях по «{payload}»]:\n{formatted}")
                print(f"\n  📎 Найдено {len(hits)} воспоминаний по «{payload}»")
            else:
                results.append(f"[Поиск «{payload}»]: Ничего не найдено.")
                print(f"\n  📎 Ничего не найдено по «{payload}»")

        elif action == "SEARCH_NOTES":
            from core.analysis.preanalysis.preanalysis_helpers import humanize_timestamp
            hits = notes_store.search(query=payload, account_id=account_id, top_k=5)
            if hits:
                formatted = "\n".join(
                    f"- {humanize_timestamp(r.get('metadata', {}).get('created_at'))}: {r['text']}"
                    for r in hits
                )
                results.append(f"[Результат поиска в заметках по «{payload}»]:\n{formatted}")
                print(f"\n  📎 Найдено {len(hits)} заметок по «{payload}»")
            else:
                results.append(f"[Поиск в заметках «{payload}»]: Ничего не найдено.")

        elif action == "WEB_SEARCH":
            hits = await web_search(payload, max_results=3)
            formatted = format_search_results(hits)
            results.append(f"[Результат веб-поиска «{payload}»]:\n{formatted}")
            print(f"\n  🌐 Веб-поиск: {len(hits)} результатов")

        elif action == "WRITE_NOTE":
            ctx["workbench"].append(payload)
            results.append(f"[Записано на рабочий стол]: {payload[:80]}...")
            print(f"\n  ✏️  Записано на рабочий стол")

        elif action == "WRITE_IDENTITY":
            parts = payload.split("|", maxsplit=1)
            if len(parts) == 2:
                section = parts[0].strip()
                text = parts[1].strip()
                if section in SECTIONS:
                    ctx["identity"].append(section, text)
                    results.append(f"[Записано в ядро → «{section}»]: {text[:80]}...")
                    print(f"\n  💎 Записано в ядро → «{section}»")
                else:
                    results.append(f"[Ошибка]: Неизвестный раздел «{section}»")
            else:
                results.append(f"[Ошибка формата WRITE_IDENTITY]: ожидается «раздел | текст»")

    if results:
        return "\n\n".join(results)
    return None


async def main():
    account_id = settings.creator_account_id
    if not account_id:
        print("❌ creator_account_id не задан в .env")
        return

    print("=" * 60)
    print("  Интерактивная рефлексия с Victor")
    print("=" * 60)
    print(f"  Account: {account_id}")
    print(f"  Команды: /quit, /show identity, /show workbench")
    print("=" * 60)

    # Загружаем контекст
    print("\n⏳ Загрузка контекста...")
    ctx = load_context(account_id)
    print(f"  ✅ Gender: {ctx['gender'].value}, Relationship: {ctx['relationship'].value}")
    print(f"  ✅ Identity: {len(ctx['identity'].read_full())} символов")
    print(f"  ✅ Workbench: {len(ctx['workbench'].read_entries())} записей")
    print()

    # LLM client
    from core.router.message_router import MessageTypeManager
    mgr = MessageTypeManager()
    llm_client = mgr._create_llm_client(account_id)

    # История диалога в формате LLM: "user: ...", "assistant: ..."
    message_history: list[str] = []

    # System prompt дополненный контекстом рефлексии
    system = ctx["system_prompt"] + (
        "\n\nЭто ваше совместное пространство. Вы вместе формируете твою глубинную память. "
        "Отвечай ей свободно, как в диалоге. Когда хочешь записать что-то в ядро "
        "или поискать в воспоминаниях — используй команды в квадратных скобках."
    )

    print("💬 Начинайте диалог. Victor видит все ваши воспоминания и свою память.\n")

    while True:
        try:
            user_input = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Выход")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("\n👋 Выход")
            break

        if user_input == "/show identity":
            print("\n" + "=" * 40)
            print(ctx["identity"].read_full())
            print("=" * 40 + "\n")
            continue

        if user_input == "/show workbench":
            print("\n" + "=" * 40)
            print(ctx["workbench"].read_full())
            print("=" * 40 + "\n")
            continue

        # Context prompt обновляется каждый раз (identity/workbench могли измениться)
        context_prompt = build_reflection_context(ctx)

        # Вызываем LLM с полноценной историей
        response = await llm_client.get_response(
            system_prompt=system,
            context_prompt=context_prompt,
            message_history=message_history if message_history else None,
            new_message=user_input,
            temperature=0.7,
            max_tokens=1500,
        )

        if not response or not response.strip():
            print("\nVictor: *молчание*\n")
            continue

        # Добавляем пару в историю
        message_history.append(f"user: {user_input}")
        message_history.append(f"assistant: {response.strip()}")

        # Выводим ответ Victor
        print(f"\nVictor: {response.strip()}\n")

        # Выполняем команды (если есть)
        cmd_results = await execute_commands(response, ctx)
        if cmd_results:
            # Результаты команд добавляем как «системное» сообщение → user-role
            # (LLM _build_messages не парсит "system:", но мы обернём в user:)
            message_history.append(f"user: [Результаты твоих команд]:\n{cmd_results}")
            print(f"\n  📋 Результаты команд добавлены в контекст\n")


if __name__ == "__main__":
    asyncio.run(main())
