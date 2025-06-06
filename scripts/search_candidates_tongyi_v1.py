#!/usr/bin/env python3
"""
简历搜索系统（REST API版）通义千问版本
"""

import os
import sys
import json
import re
import time
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Tuple
from functools import lru_cache
from dotenv import load_dotenv

# ✅ 加载 .env
load_dotenv()

import dashscope
from dashscope import TextEmbedding

# ✅ 手动写死通义 API Key（确保替换成你的真实 key）
dashscope.api_key = "sk-1d92a7280052451c84509f57e1b44991"

# ✅ 环境变量
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v1")
TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))
CERTAINTY = float(os.getenv("SEARCH_CERTAINTY", "0.75"))
SUMMARY_LENGTH = int(os.getenv("SUMMARY_LENGTH", "200"))
EMBEDDING_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_SIZE", "100"))

# ✅ 日志设置
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ 通义 embedding 接口封装
def get_tongyi_embedding(text: str, model: str = EMBEDDING_MODEL) -> List[float]:
    try:
        response = TextEmbedding.call(model=model, input=text)
        if response and "output" in response and "embeddings" in response["output"]:
            embedding = response["output"]["embeddings"][0]["embedding"]
            logger.info(f"✅ 通义返回向量长度: {len(embedding)}")
            return embedding
        else:
            logger.error(f"❌ 通义返回结果异常: {response}")
            return []
    except Exception as e:
        logger.error(f"❌ 通义向量生成失败: {e}")
        return []

class ResumeSearcher:
    def __init__(self):
        print(f"🔧 当前使用通义模型: {EMBEDDING_MODEL}")
        logger.info("🔍 初始化 ResumeSearcher")
        self.embedding_model = EMBEDDING_MODEL

    @staticmethod
    def format_summary(content: str) -> str:
        if not content:
            return ""
        summary = re.sub(r'\s+', ' ', content.strip())[:SUMMARY_LENGTH]
        return summary + "..." if len(content) > SUMMARY_LENGTH else summary

    @staticmethod
    def parse_filename(filename: str) -> Tuple[str, str]:
        name, job_title = "（未提取）", "（未提取）"
        match = re.match(r'(.+?)_(.+?)_', filename)
        if match:
            name = match.group(1)
            job_title = match.group(2)
        return name, job_title

    @lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
    def get_embedding(self, text: str) -> List[float]:
        try:
            from dashscope import TextEmbedding
            import dashscope
            dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
            response = TextEmbedding.call(model=self.embedding_model, input=text)
            return response.output["embeddings"][0]["embedding"]
        except Exception as e:
            logger.error(f"❌ 获取向量失败（通义）: {e}")
            raise

    def search(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"开始处理查询: {query}")

        try:
            embedding = self.get_embedding(query)
            logger.info(f"✅ 查询向量维度: {len(embedding)}")

            graphql_query = {
                "query": f"""
                {{
                  Get {{
                    {WEAVIATE_CLASS}(
                      nearVector: {{
                        vector: {json.dumps(embedding)},
                        distance: 0.3
                      }},
                      limit: {TOP_K}
                    ) {{
                      filename
                      content
                      notes
                      _additional {{
                        id
                        distance
                      }}
                    }}
                  }}
                }}
                """
            }

            res = requests.post(f"{WEAVIATE_URL}/v1/graphql", json=graphql_query)
            if res.status_code != 200:
                raise Exception(f"GraphQL 请求失败：{res.status_code} - {res.text}")

            results = res.json()["data"]["Get"][WEAVIATE_CLASS]
            candidates = []
            for obj in results:
                content = obj.get("content", "")
                filename = obj.get("filename", "")
                notes = obj.get("notes", [])
                additional = obj.get("_additional", {})
                distance = additional.get("distance", 1.0)
                certainty = (1 - float(distance)) * 100

                name, job_title = self.parse_filename(filename)
                candidates.append({
                    "UUID": additional.get("id", "未知"),
                    "姓名": name,
                    "应聘职位": job_title,
                    "文件名": filename,
                    "匹配度": f"{certainty:.1f}%",
                    "简历摘要": self.format_summary(content),
                    "沟通记录": notes if notes else [],
                    "简历内容": content,
                })

            candidates.sort(key=lambda x: float(x["匹配度"].rstrip("%")), reverse=True)
            elapsed = time.time() - start_time

            return {
                "查询": query,
                "候选人数量": len(candidates),
                "处理时间": f"{elapsed:.2f}秒",
                "候选人列表": candidates
            }

        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            raise

def main():
    query = ""
    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i] in ["--query", "-q", "--keywords", "-k"] and i + 1 < len(sys.argv):
                query = sys.argv[i + 1].strip()
                break
            elif i == 1:
                query = sys.argv[1].strip()

    if not query:
        print(json.dumps({"候选人列表": [], "查询关键词": "", "状态": "无关键词"}, ensure_ascii=False))
        return

    print(f"搜索关键词: {query}")
    try:
        searcher = ResumeSearcher()
        result = searcher.search(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "候选人列表": [],
            "查询关键词": query,
            "状态": f"系统错误: {str(e)}"
        }, ensure_ascii=False))

if __name__ == "__main__":
    main()