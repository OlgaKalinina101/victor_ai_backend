import asyncio

from core.chain.communication import run_communication_pipeline
from infrastructure.embeddings.runner import preload_models


async def test_dialog_loop(account_id: str):
    """
    Простой REPL-цикл для тестирования Victor AI в консоли.
    """
    print("🌿 Victor AI тестовый режим. Напиши 'exit' для выхода.")

    while True:
        user_input = input("\n👤 Ты: ")
        if user_input.strip().lower() in {"exit", "quit"}:
            print("🫡 Завершаю.")
            break

        try:
            assistant_response = await run_communication_pipeline(account_id, user_input)
            print(f"\n🤖 Виктор: {assistant_response}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    import sys
    account_id = sys.argv[1] if len(sys.argv) > 1 else "test_user"
    preload_models()
    asyncio.run(test_dialog_loop(account_id=account_id))

