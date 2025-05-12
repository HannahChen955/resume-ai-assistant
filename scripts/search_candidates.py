#!/usr/bin/env python3
"""
简历搜索系统
支持向量搜索和关键词匹配的混合搜索系统，带评分机制
"""

import sys
import json
import os
import re
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from pathlib import Path

# 添加项目根目录到 Python 路径
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
from openai import OpenAI
from scripts.weaviate_utils import (
    get_weaviate_client, WEAVIATE_CLASS_NAME,
    TOP_K_RESULTS
)
from scripts.config import settings
from weaviate.classes.query import MetadataQuery

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
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("未找到 OPENAI_API_KEY 环境变量")
        
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.weaviate_client = None
        self.collection = None

    def connect(self) -> None:
        try:
            self.weaviate_client = get_weaviate_client(self.openai_api_key)
            self.weaviate_client.connect()
            self.collection = self.weaviate_client.collections.get(WEAVIATE_CLASS_NAME)
            logger.info("成功连接到 Weaviate")
        except Exception as e:
            logger.error(f"连接 Weaviate 失败: {e}")
            raise

    def disconnect(self) -> None:
        if self.weaviate_client and self.weaviate_client.is_ready():
            try:
                self.weaviate_client.close()
                logger.info("已断开与 Weaviate 的连接")
            except Exception as e:
                logger.warning(f"断开连接时发生错误: {e}")

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
            response = self.openai_client.embeddings.create(
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
            # 获取查询向量
            embedding = self.get_embedding(query)
            logger.info(f"已生成查询向量，维度: {len(embedding)}")

            response = self.collection.query.near_vector(
                near_vector=embedding,
                target_vector="default",
                limit=TOP_K_RESULTS,
                return_metadata=["distance"]
            )

            candidates = []
            for obj in response.objects:
                distance = obj.metadata.distance
                if distance is None:
                    continue

                certainty = (1 - float(distance)) * 100
                content = obj.properties.get("content", "")
                filename = obj.properties.get("filename", "")
                name, job_title = self.parse_filename(filename)

                candidate = {
                    "UUID": str(obj.uuid),
                    "姓名": name,
                    "应聘职位": job_title,
                    "文件名": filename,
                    "匹配度": f"{certainty:.1f}%",
                    "简历摘要": self.format_summary(content),
                    "简历内容": content,
                }
                candidates.append(candidate)

            # 用匹配度排序（向量相似度）
            candidates.sort(key=lambda x: float(x["匹配度"].rstrip("%")), reverse=True)
            search_time = time.time() - start_time

            return {
                "查询": query,
                "候选人数量": len(candidates),
                "处理时间": f"{search_time:.2f}秒",
                "候选人列表": candidates
            }

        except Exception as e:
            logger.error(f"搜索过程中发生错误: {e}")
            raise

def main():
    """主函数"""
    # 获取查询词
    query = ""
    if len(sys.argv) > 1:
        # 尝试从 --query 或 --keywords 参数获取搜索词
        for i in range(1, len(sys.argv)):
            if sys.argv[i] in ["--query", "-q"] and i + 1 < len(sys.argv):
                query = sys.argv[i + 1].strip()
                break
            elif sys.argv[i] in ["--keywords", "-k"] and i + 1 < len(sys.argv):
                query = sys.argv[i + 1].strip()
                break
            elif i == 1:  # 如果没有指定参数名，使用第一个参数
                query = sys.argv[1].strip()

    if not query:
        print(json.dumps({"候选人列表": [], "查询关键词": "", "状态": "无关键词"}, ensure_ascii=False))
        return

    print(f"搜索关键词: {query}")  # 打印搜索关键词

    try:
        searcher = ResumeSearcher()
        searcher.connect()
        result = searcher.search(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        print(json.dumps({
            "候选人列表": [],
            "查询关键词": query,
            "状态": f"系统错误: {str(e)}"
        }, ensure_ascii=False))
    finally:
        if searcher:
            searcher.disconnect()

if __name__ == "__main__":
    main()