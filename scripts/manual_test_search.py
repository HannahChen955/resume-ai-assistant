import os
from dotenv import load_dotenv
from openai import OpenAI
import weaviate

# ✅ 加载 OpenAI key
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
openai = OpenAI(api_key=api_key)

# ✅ 初始化 Weaviate 客户端
client = weaviate.Client(
    url="http://weaviate:8080",
    additional_headers={"X-OpenAI-Api-Key": api_key}
)

# ✅ 设置测试关键字
query = "薪酬绩效 深圳"

# ✅ 获取 query 的向量
response = openai.embeddings.create(
    model="text-embedding-ada-002",
    input=query
)
vector = response.data[0].embedding

# ✅ 搜索 Candidates 数据库
results = client.query.get("Candidates", ["name", "summary"]) \
    .with_near_vector({"vector": vector}) \
    .with_limit(5) \
    .do()

# ✅ 打印结果
print("🔍 搜索关键词:", query)
for i, item in enumerate(results["data"]["Get"]["Candidates"]):
    print(f"\n📄 第 {i+1} 个结果：")
    print("Name:", item["name"])
    print("Summary:", item["summary"][:200])