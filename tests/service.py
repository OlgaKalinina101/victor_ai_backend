import psycopg2
import pandas as pd

conn = psycopg2.connect(
    dbname="victor_db",
    user="postgres",
    password="up2wAzqr2",
    host="localhost",
    port="5432"
)

df = pd.read_sql("SELECT id, role, mood, message_type, text FROM dialogue_history ORDER BY id", conn)
print(df.head(290))  # или df.to_csv('output.csv', index=False)
