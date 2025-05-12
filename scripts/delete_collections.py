"""
删除 Weaviate 中的指定集合（如 Candidates、ResumesOpenAI、TestManualVector）。
支持命令行传参，也有默认值。兼容 Weaviate Python Client v4。
用法示例：
    python scripts/delete_collections.py
    python scripts/delete_collections.py ResumesOpenAI TestManualVector
"""

import sys
from weaviate import WeaviateClient
from weaviate.connect import ConnectionParams

# === 连接本地 Weaviate ===
client = WeaviateClient(
    connection_params=ConnectionParams.from_params(
        http_host="localhost",
        http_port=8080,
        http_secure=False,
        grpc_host="localhost",
        grpc_port=50051,
        grpc_secure=False,
    )
)
client.connect()

# === 获取要删除的集合（来自参数或默认值）
default_collections = ["Candidates", "ResumesOpenAI", "TestManualVector"]
collections_to_delete = sys.argv[1:] if len(sys.argv) > 1 else default_collections

# === 删除逻辑
existing_collections = client.collections.list_all().keys()

for name in collections_to_delete:
    if name in existing_collections:
        client.collections.delete(name)
        print(f"✅ 已删除集合: {name}")
    else:
        print(f"⚠️ 集合 {name} 不存在，跳过")

client.close()