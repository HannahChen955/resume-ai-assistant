#!/usr/bin/env python3
"""
简历搜索系统（REST API版）
纯语义向量搜索，使用 Weaviate REST API（GraphQL）接口
"""

import sys
import json
import os
import re
import time
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Tuple
from functools import lru_cache

# 添加项目根目录到 Python 路径
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
from openai import OpenAI
from scripts.config import settings

# 设置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

class ResumeSearcher:
    def __init__(self):
        self.api_key = settings.OPENAI_APIKEY
        if not self.api_key:
            raise ValueError("未设置 OPENAI_APIKEY")
        self.client = OpenAI(api_key=self.api_key)

    @staticmethod
    def format_summary(content: str) -> str:
        if not content:
            return ""
        summary = re.sub(r'\s+', ' ', content.strip())[:settings.SUMMARY_LENGTH]
        return summary + "..." if len(content) > settings.SUMMARY_LENGTH else summary

    @staticmethod
    def parse_filename(filename: str) -> Tuple[str, str]:
        name, job_title = "（未提取）", "（未提取）"
        match = re.match(r'(.+?)_(.+?)_', filename)
        if match:
            name = match.group(1)
            job_title = match.group(2)
        return name, job_title

    @lru_cache(maxsize=settings.EMBEDDING_CACHE_SIZE)
    def get_embedding(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings.create(
                input=[text],
                model=settings.EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"获取向量失败: {e}")
            raise

    def search(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"开始处理查询: {query}")

        try:
            embedding = self.get_embedding(query)
            logger.info(f"已生成查询向量，维度: {len(embedding)}")

            graphql_query = {
                "query": """
                {
                  Get {
                    %s(
                      nearVector: {
                        vector: %s,
                        certainty: %s
                      },
                      limit: %d
                    ) {
                      filename
                      content
                      _additional {
                        id
                        distance
                      }
                    }
                  }
                }
                """ % (
                    settings.WEAVIATE_COLLECTION,
                    json.dumps(embedding),
                    settings.SEARCH_CERTAINTY,
                    settings.DEFAULT_TOP_K
                )
            }

            res = requests.post(
                url=f"{settings.WEAVIATE_URL}/v1/graphql",
                json=graphql_query
            )

            if res.status_code != 200:
                raise Exception(f"GraphQL 请求失败：{res.status_code} - {res.text}")

            results = res.json()["data"]["Get"][settings.WEAVIATE_COLLECTION]

            candidates = []
            for obj in results:
                content = obj.get("content", "")
                filename = obj.get("filename", "")
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
                    "简历内容": content,
                })

            # 匹配度排序
            candidates.sort(key=lambda x: float(x["匹配度"].rstrip("%")), reverse=True)
            elapsed = time.time() - start_time

            return {
                "查询": query,
                "候选人数量": len(candidates),
                "处理时间": f"{elapsed:.2f}秒",
                "候选人列表": candidates
            }

        except Exception as e:
            logger.error(f"搜索失败: {e}")
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