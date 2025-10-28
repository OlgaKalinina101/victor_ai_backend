# migrate_sqlite_to_postgres.py
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from infrastructure.database.models import KeyInfo, ChatMeta  # путь может отличаться

# 1. Подключение к SQLite
sqlite_conn = sqlite3.connect("C:/Users/Alien/PycharmProjects/TheOne/core/data/viktor.db", detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
sqlite_cursor = sqlite_conn.cursor()

# 2. Извлечение нужных данных
sqlite_cursor.execute("""
    SELECT trust_level, raw_trust_score, relationship, is_creator, trust_established, trust_test_completed, trust_test_timestamp, last_updated, gender, model
    FROM chat_meta
""")
rows = sqlite_cursor.fetchall()

# 3. Подключение к PostgreSQL
DATABASE_URL = "postgresql+psycopg2://postgres:up2wAzqr2@localhost:5432/victor_db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# 4. Загрузка данных в PostgreSQL
for row in rows:
    trust_level, raw_trust_score, relationship, is_creator, trust_established, trust_test_completed, trust_test_timestamp, last_updated, gender, model = row
    record = ChatMeta(
        account_id="test_user",
        model = model,
        trust_level = trust_level,
        raw_trust_score = raw_trust_score,
        gender = "девушка",
        relationship = relationship,
        is_creator = is_creator,
        trust_established = trust_established,
        trust_test_completed = trust_test_completed,
        trust_test_timestamp = trust_test_timestamp,
        last_updated = last_updated,
    )
    session.merge(record)  # merge — чтобы не дублировать при повторной миграции

session.commit()
session.close()
sqlite_conn.close()

print("✅ Миграция завершена.")

# 2. Выполняем запрос из PostgreSQL
records = session.query(ChatMeta).limit(10).all()

# 3. Печатаем красиво
for record in records:
    print(f"📌 {record.account_id} | {record.model} | {record.trust_level} | {record.raw_trust_score} | {record.gender} | {record.relationship} | {record.is_creator}| {record.trust_established}| {record.trust_test_completed}| {record.trust_test_timestamp}| {record.last_updated}")
