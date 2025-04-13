import os
import sys
import re
import weaviate
from dotenv import load_dotenv
from openai import OpenAI

# ✅ 加载 .env 中的环境变量
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# ✅ 初始化新版 OpenAI 客户端
openai = OpenAI(api_key=api_key)

# ✅ 查询关键词（从命令行参数获取）
if len(sys.argv) < 2:
    print("❗请输入关键词，例如：python3 search_candidates.py '薪酬绩效 深圳'")
    sys.exit(1)

query_text = sys.argv[1]

# ✅ 初始化 Weaviate 客户端
client = weaviate.Client(
    url="http://weaviate:8080",
    additional_headers={"X-OpenAI-Api-Key": api_key}
)

# ✅ 提取候选人结构化摘要（辅助展示去重）
def extract_candidate_info(summary):
    name = re.search(r"姓名[:：]?\s*([\u4e00-\u9fa5]{2,4})", summary)
    gender = re.search(r"性别[:：]?\s*(男|女)", summary)
    age = re.search(r"年龄[:：]?\s*(\d{2})", summary)
    location = re.search(r"(位置|现居|所在地)[:：]?\s*([\u4e00-\u9fa5]+)", summary)

    return {
        "name": name.group(1) if name else "",
        "gender": gender.group(1) if gender else "",
        "age": age.group(1) if age else "",
        "location": location.group(2) if location else ""
    }

# ✅ GPT 生成推荐理由（新版 ChatCompletion 调用）
def generate_recommendation(query, summary):
    prompt = f"""你是招聘助手，现在有一个岗位需求是：{query}
请你基于以下候选人简历摘要，判断是否匹配，并给出推荐理由：
摘要内容：
{summary}
请用一句话回复推荐理由，如果不匹配也请指出原因。"""

    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ✅ 执行语义搜索并输出
def search_candidates(query_text, top_k=5):
    # Step 1: 获取 query 向量（新版 embedding 调用）
    embed_response = openai.embeddings.create(
        input=query_text,
        model="text-embedding-ada-002"
    )
    query_vector = embed_response.data[0].embedding

    # Step 2: 查询 Weaviate
    result = client.query.get("candidates", ["name", "summary"]) \
        .with_near_vector({"vector": query_vector}) \
        .with_limit(top_k) \
        .do()

    candidates = result.get("data", {}).get("Get", {}).get("candidates", [])

    # Step 3: 输出
    print(f"\n🔍 搜索关键词: {query_text}（Top {top_k}）")
    if not candidates:
        print("❗未找到匹配候选人。")
        return

    seen = set()
    for i, c in enumerate(candidates, start=1):
        name = c.get("name", "未知")
        summary = c.get("summary", "")

        info = extract_candidate_info(summary)
        unique_key = f"{info['name']}-{info['gender']}-{info['age']}-{info['location']}"
        if unique_key in seen:
            continue
        seen.add(unique_key)

        reason = generate_recommendation(query_text, summary)

        print(f"\n📄 [{i}] {name}")
        print(f"   摘要: {summary[:80]}...")
        print(f"   推荐理由: {reason}")

# ✅ 脚本入口
if __name__ == "__main__":
    search_candidates(query_text)