import os
from dotenv import load_dotenv
from openai import OpenAI

# ✅ 加载环境变量
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# ✅ 初始化 OpenAI 客户端（新版）
openai_client = OpenAI(api_key=openai_api_key)

# ✅ 测试向量生成
if __name__ == "__main__":
    print("📡 正在测试 OpenAI 向量化...")
    try:
        test_text = "薪酬绩效 深圳"
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=[test_text]
        )
        embedding = response.data[0].embedding

        if embedding and isinstance(embedding, list):
            print("✅ 成功获取向量，维度：", len(embedding))
        else:
            print("⚠️ 未能成功获取向量。返回：", embedding)

    except Exception as e:
        print("❌ 失败，错误信息：\n")
        print(e)
