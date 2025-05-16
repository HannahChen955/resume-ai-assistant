#!/usr/bin/env python3
import os
import psycopg2
from dotenv import load_dotenv

# ✅ 加载 .env 配置
load_dotenv()

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
PG_USER = os.getenv("POSTGRES_USER", "nocodb")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "nocodb_pw")
PG_DB = os.getenv("POSTGRES_DB", "recruitment_db")

try:
    print(f"🔍 正在尝试连接 PostgreSQL {PG_HOST}:{PG_PORT} ...")
    conn = psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT
    )
    print("✅ PostgreSQL 连接成功！")
    conn.close()
except Exception as e:
    print(f"❌ PostgreSQL 连接失败: {e}")