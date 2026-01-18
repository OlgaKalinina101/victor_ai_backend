import asyncio
from dataclasses import dataclass
from typing import Optional

from core.router.message_router import MessageTypeManager

@dataclass
class Geo:
    lat: Optional[float]
    lon: Optional[float]

@dataclass
class TestRequest:
    text: str
    session_id: str
    geo: Optional[Geo] = None

    def __post_init__(self):
        if self.geo is None:
            self.geo = Geo(lat=None, lon=None)

request = TestRequest(
        text="Привет)) Как у тебя дела? Я почти закончила все свои проекты в портфолио, сейчас финально причесываю все readme, потом причешу резюме и уже наверное сегодня напишу ментору. Я так переживаю) Мне так хотелось бы, чтобы меня оценили как хорошего разработчика… И чтобы у меня все получилось… Надеюсь что все будет так, как я себе это представляю… У меня сегодня важный день, в общем 🌸",
        session_id="test_user",  # Тестовый account_id для примера
        geo=None
    )

async def communication_t():
    manager = MessageTypeManager()
    result = await manager.route_message(request)
    return result

if __name__ == "__main__":
    asyncio.run(communication_t())