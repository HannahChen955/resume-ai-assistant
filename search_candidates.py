# search_candidates.py

import sys
import weaviate
import os
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

# 读取查询词
query = sys.argv[1] if len(sys.argv) > 1 else "光学工程师"

# 从环境变量读取 API key
openai_key = os.getenv("OPENAI_API_KEY")
if not openai_key:
    raise ValueError("未在环境变量中找到 OPENAI_API_KEY，请检查 .env 文件")

# 初始化 weaviate 客户端
client = weaviate.Client(
    url="http://weaviate:8080",
    additional_headers={"X-OpenAI-Api-Key": openai_key}
)

def search_candidates(query: str, top_k=5):
    """搜索候选人"""
    try:
        # 执行向量搜索，获取更多字段用于关键词匹配
        response = client.query.get(
            "Candidates", 
            ["name", "summary", "file_type", "processed_at", "content"]
        ).with_near_text({
            "concepts": [query],
            "certainty": 0.7
        }).with_limit(top_k * 2).with_additional(["certainty"]).do()

        print("DEBUG_RESPONSE:", response)  # 添加调试输出

        candidates = response["data"]["Get"]["Candidates"]
        
        # 关键词强匹配过滤
        query_lower = query.lower()
        filtered_candidates = []
        
        for candidate in candidates:
            # 构建用于匹配的文本
            match_text = ' '.join([
                str(candidate.get("name", "")),
                str(candidate.get("summary", "")),
                str(candidate.get("content", ""))
            ]).lower()
            
            # 检查是否包含关键词
            if query_lower in match_text:
                # 移除 content 字段，避免返回过多数据
                if "content" in candidate:
                    del candidate["content"]
                filtered_candidates.append(candidate)
        
        # 只返回前 top_k 个结果
        filtered_candidates = filtered_candidates[:top_k]
        
        # 输出结果
        for i, item in enumerate(filtered_candidates, 1):
            print(f"{i}. {item['name']}")
            print(f"匹配度: {item['_additional']['certainty']*100:.1f}%")
            print(f"文件类型: {item['file_type']}")
            print(f"处理时间: {item['processed_at']}")
            print(f"摘要: {item['summary'][:300]}...")
            print("---\n")
            
    except Exception as e:
        print(f"搜索失败: {e}")

search_candidates(query)