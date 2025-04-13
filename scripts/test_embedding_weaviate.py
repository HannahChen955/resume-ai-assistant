import weaviate
from dotenv import load_dotenv
import os

# ✅ 加载 .env 文件中的 OpenAI API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# ✅ 初始化 Weaviate 客户端，REST 模式 + text2vec-openai 自动向量化
client = weaviate.Client(
    url="http://weaviate:8080",
    additional_headers={
        "X-OpenAI-Api-Key": openai_api_key
    }
)

# ✅ 插入一条测试文本，观察是否自动生成向量
test_text = "测试向量化是否成功，这是一个来自深圳的薪酬绩效专家。"

properties = {
    "summary": test_text
}

print("🚀 正在插入测试对象...")

client.data_object.create(
    data_object=properties,
    class_name="Candidates"
)

print("✅ 插入完成，请通过以下方式检查是否向量化成功：")
print("🔍 curl http://localhost:8080/v1/objects?class=Candidates")