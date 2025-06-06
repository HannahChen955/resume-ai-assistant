#!/usr/bin/env python3
"""
简历搜索系统（REST API版）支持 OpenAI / 通义千问 / DeepSeek
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

# ✅ 环境变量
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))
CERTAINTY = float(os.getenv("SEARCH_CERTAINTY", "0.75"))
SUMMARY_LENGTH = int(os.getenv("SUMMARY_LENGTH", "200"))
EMBEDDING_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_SIZE", "100"))

# ✅ 日志设置
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ✅ OpenAI Client
from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def is_uuid_like(s: str) -> bool:
    return re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", s) is not None

class ResumeSearcher:
    def __init__(self, weaviate_url, weaviate_class, openai_client, embedding_model):
        self.weaviate_url = weaviate_url
        self.weaviate_class = weaviate_class
        self.openai_client = openai_client
        self.embedding_model = embedding_model
        print(f"🔧 当前使用 OpenAI 模型: {self.embedding_model}")
        logger.info("🔍 初始化 ResumeSearcher")

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
            response = self.openai_client.embeddings.create(
                input=[text],
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"❌ 获取向量失败: {e}")
            raise

    def search(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"开始处理查询: {query}")

        try:
            # ✅ 如果是 UUID 直接用 REST API 查询
            if is_uuid_like(query):
                logger.info("⚡️ 检测为 UUID，执行精确查找")
                url = f"{self.weaviate_url}/v1/objects/{self.weaviate_class}/{query}"
                res = requests.get(url)
                if res.status_code == 200:
                    obj = res.json().get("properties", {})
                    name, job_title = self.parse_filename(obj.get("filename", ""))
                    elapsed = time.time() - start_time
                    return {
                        "查询": query,
                        "候选人数量": 1,
                        "处理时间": f"{elapsed:.2f}秒",
                        "候选人列表": [{
                            "UUID": query,
                            "姓名": name,
                            "应聘职位": job_title,
                            "文件名": obj.get("filename", ""),
                            "匹配度": "100.0%",
                            "简历摘要": self.format_summary(obj.get("content", "")),
                            "沟通记录": obj.get("notes", []),
                            "简历内容": obj.get("content", ""),
                        }]
                    }
                else:
                    return {"查询": query, "候选人数量": 0, "候选人列表": []}

            # ✅ 否则执行向量搜索
            embedding = self.get_embedding(query)
            graphql_query = {
                "query": f"""
                {{
                  Get {{
                    {self.weaviate_class}(
                      nearVector: {{
                        vector: {json.dumps(embedding)},
                        certainty: {CERTAINTY}
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

            res = requests.post(f"{self.weaviate_url}/v1/graphql", json=graphql_query)
            if res.status_code != 200:
                raise Exception(f"GraphQL 请求失败：{res.status_code} - {res.text}")

            results = res.json()["data"]["Get"][self.weaviate_class]
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
        searcher = ResumeSearcher(WEAVIATE_URL, WEAVIATE_CLASS, openai_client, EMBEDDING_MODEL)
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