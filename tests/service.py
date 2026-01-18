import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

# ВАЖНО: Этот файл для тестирования. Используйте переменные окружения!
# Создайте .env файл с DATABASE_URL или установите переменные окружения
db_url = os.getenv("DATABASE_URL", "postgresql://postgres:YOUR_PASSWORD@localhost:5432/victor_db")

# Парсинг URL для psycopg2
from urllib.parse import urlparse
parsed = urlparse(db_url)

conn = psycopg2.connect(
    dbname=parsed.path[1:],  # убираем первый слеш
    user=parsed.username,
    password=parsed.password,
    host=parsed.hostname,
    port=parsed.port or "5432"
)

df = pd.read_sql("SELECT id, role, mood, message_type, text FROM dialogue_history ORDER BY id", conn)
print(df.head(290))  # или df.to_csv('output.csv', index=False)
