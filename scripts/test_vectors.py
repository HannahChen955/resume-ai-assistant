import uuid
import random
from weaviate import WeaviateClient
from weaviate.connect import ConnectionParams
from weaviate.classes.config import Property, DataType  # ✅ 使用旧版接口

# === 配置 ===
VECTOR_DIM = 1536
TEST_CLASS_NAME = "TestManualVector"

# === 建立连接 ===
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
print("✅ 连接状态:", client.is_ready())

# === 删除旧的测试集合（如存在）===
if TEST_CLASS_NAME in client.collections.list_all():
    client.collections.delete(TEST_CLASS_NAME)
    print(f"🗑️ 已删除旧集合: {TEST_CLASS_NAME}")

# === 创建新集合（关闭自动向量化）===
client.collections.create(
    name=TEST_CLASS_NAME,
    properties=[
        Property(name="title", data_type=DataType.TEXT),
    ],
    vectorizer_config=None  # ✅ 不使用向量模块
    # ❌ 旧版 SDK 不支持 vector_index_config
)
print(f"📦 新集合已创建: {TEST_CLASS_NAME}")

# === 插入测试数据（手动向量）===
collection = client.collections.get(TEST_CLASS_NAME)
test_uuid = uuid.uuid4()
test_vector = [random.random() for _ in range(VECTOR_DIM)]

collection.data.insert(
    uuid=test_uuid,
    properties={"title": "测试对象"},
    vector=test_vector
)
print("✅ 向量对象已插入")

# === 检查是否成功写入 ===
result = collection.query.fetch_object_by_id(test_uuid)
vec = result.vector if hasattr(result, "vector") else None

print("\n=== 检查结果 ===")
if vec:
    print(f"📊 向量维度: {len(vec)}")
    print(f"📊 向量前5维: {vec[:5]}")
else:
    print("❌ 向量不存在")

client.close()