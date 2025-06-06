#!/usr/bin/env python3
"""
列出 Weaviate 中 Candidates 类的所有简历数据（兼容 v4 + gRPC，最终稳定版）
"""

from weaviate import WeaviateClient
from weaviate.connect import ConnectionParams
from dotenv import load_dotenv
import os
import pandas as pd

load_dotenv()
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")

# ✅ 初始化客户端并连接
client = WeaviateClient(ConnectionParams.from_url(WEAVIATE_URL, grpc_port=50051))
client.connect()

# ✅ 获取集合对象
collection = client.collections.get(WEAVIATE_CLASS)

# ✅ 获取字段名（properties 是 list[Property])
properties = [prop.name for prop in collection.config.properties]

# ✅ 拉取数据
objs = collection.query.fetch_objects(limit=100, return_properties=properties)

# ✅ 结构化为 DataFrame
records = []
for obj in objs.objects:
    data = obj.properties
    data["uuid"] = obj.uuid
    records.append(data)

df = pd.DataFrame(records)
print(f"✅ 共找到 {len(df)} 条记录")
print(df.head(10))

# ✅ 导出 CSV（可选）
df.to_csv("weaviate_candidates_full.csv", index=False)
print("✅ 已导出为 weaviate_candidates_full.csv")

# ✅ 安全关闭连接
client.close()