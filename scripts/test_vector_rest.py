import weaviate
from dotenv import load_dotenv
import os

# ✅ 加载 .env 文件
load_dotenv()

# ✅ 获取 Weaviate 环境变量
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")

# ✅ 初始化客户端
client = weaviate.Client(WEAVIATE_URL)

# ✅ 查询数据
print("🔍 正在查询数据...")
result = (
    client.query
    .get(WEAVIATE_CLASS, ["filename"])
    .with_additional(["vector"])
    .with_limit(5)
    .do()
)

# ✅ 输出结果
objs = result["data"]["Get"].get(WEAVIATE_CLASS, [])
if not objs:
    print("⚠️ 没有找到任何对象")
else:
    for i, obj in enumerate(objs):
        vec = obj["_additional"].get("vector")
        print(f"\n🔹 第{i+1}个对象")
        print("📄 文件名:", obj.get("filename"))
        if vec:
            print("✅ 向量维度:", len(vec))
            print("前5维:", vec[:5])
        else:
            print("❌ 向量不存在")