#!/usr/bin/env python3
# scripts/check_weaviate_count_http.py

import os
import requests
from dotenv import load_dotenv

load_dotenv()

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")

# ✅ 构造 GraphQL 查询语句
graphql_query = {
    "query": f"""
    {{
      Aggregate {{
        {WEAVIATE_CLASS} {{
          meta {{
            count
          }}
        }}
      }}
    }}
    """
}

try:
    # ✅ 发出 GraphQL 请求
    response = requests.post(f"{WEAVIATE_URL}/v1/graphql", json=graphql_query)
    response.raise_for_status()
    result = response.json()

    count = result["data"]["Aggregate"][WEAVIATE_CLASS][0]["meta"]["count"]
    print(f"📊 Weaviate 中对象数量: {count}")
except Exception as e:
    print(f"❌ 查询失败: {e}")