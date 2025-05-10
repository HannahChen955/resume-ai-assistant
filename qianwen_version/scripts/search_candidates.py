#!/usr/bin/env python3

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
from dashscope import Embedding
import dashscope

from scripts.weaviate_utils import (
    get_weaviate_client, WEAVIATE_CLASS_NAME, TOP_K_RESULTS
)
from scripts.config import Config
from weaviate.classes.query import MetadataQuery

# 设置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()
QIANWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY")
dashscope.api_key = QIANWEN_API_KEY


class ResumeSearcher:
    def __init__(self):
        if not QIANWEN_API_KEY:
            raise ValueError("未找到 QIANWEN_API_KEY 或 DASHSCOPE_API_KEY 环境变量")

        self.weaviate_client = None
        self.collection = None

    def connect(self) -> None:
        try:
            self.weaviate_client = get_weaviate_client(api_key=QIANWEN_API_KEY)
            self.weaviate_client.connect()
            self.collection = self.weaviate_client.collections.get(WEAVIATE_CLASS_NAME)
            logger.info("✅ 成功连接 Weaviate")
        except Exception as e:
            logger.error(f"❌ 连接 Weaviate 失败: {e}")
            raise

    def disconnect(self) -> None:
        if self.weaviate_client and self.weaviate_client.is_ready():
            try:
                self.weaviate_client.close()
                logger.info("🔌 已断开 Weaviate")
            except Exception as e:
                logger.warning(f"⚠️ 断开错误: {e}")

    @staticmethod
    def format_summary(content: str) -> str:
        if not content:
            return ""
        summary = re.sub(r'\s+', ' ', content.strip())[:Config.SUMMARY_LENGTH]
        return summary + "..." if len(content) > Config.SUMMARY_LENGTH else summary

    @staticmethod
    def check_keywords(content: str) -> List[str]:
        if not content:
            return []
        content_lower = content.lower()
        return [k for k, v in Config.FILTER_KEYWORDS.items() 
                if any(kw.lower() in content_lower for kw in v)]

    @staticmethod
    def parse_filename(filename: str) -> Tuple[str, str]:
        name, job_title = "（未提取）", "（未提取）"
        match = re.match(r'(.+?)_(.+?)_', filename)
        if match:
            name = match.group(1)
            job_title = match.group(2)
        return name, job_title

    @staticmethod
    def evaluate_resume_quality(content: str) -> float:
        if not content:
            return 0.0
        score = 0.0
        length_score = min(len(content) / 2000, 1.0) * 0.3
        structure_score = 0.0
        if "教育背景" in content or "教育经历" in content:
            structure_score += 0.1
        if "工作经验" in content or "工作经历" in content:
            structure_score += 0.1
        if "项目经验" in content or "项目经历" in content:
            structure_score += 0.1
        if "技能" in content or "专业技能" in content:
            structure_score += 0.1
        info_score = 0.0
        if re.search(r'1[3-9]\d{9}', content):
            info_score += 0.1
        if re.search(r'[\w\.-]+@[\w\.-]+', content):
            info_score += 0.1
        if re.search(r'(本科|硕士|博士|MBA|PhD)', content):
            info_score += 0.1
        return length_score + structure_score + info_score

    @lru_cache(maxsize=Config.EMBEDDING_CACHE_SIZE)
    def get_embedding(self, text: str) -> List[float]:
        try:
            response = Embedding.call(
                model="text-embedding-v1",
                input=text
            )
            return response["output"]["embeddings"][0]["embedding"]
        except Exception as e:
            logger.error(f"❌ 向量生成失败: {e}")
            raise

    def score_candidate(self, candidate: Dict[str, Any], query_keywords: Dict[str, Dict[str, float]]) -> float:
        vector_score = float(candidate["匹配度"].rstrip("%")) / 100.0
        keyword_score = 0.0
        content_lower = candidate["简历内容"].lower()

        essential_matches = []
        if "必要词" in query_keywords:
            for word, weight in query_keywords["必要词"].items():
                if word.lower() in content_lower:
                    essential_matches.append((word, weight))
                    keyword_score += weight

        bonus_matches = []
        if "加分词" in query_keywords:
            for word, weight in query_keywords["加分词"].items():
                if word.lower() in content_lower:
                    bonus_matches.append((word, weight))
                    keyword_score += weight

        max_possible_score = sum(query_keywords.get("必要词", {}).values()) + \
                             sum(query_keywords.get("加分词", {}).values())
        keyword_score = keyword_score / max_possible_score if max_possible_score > 0 else 0

        quality_score = self.evaluate_resume_quality(candidate["简历内容"])

        candidate["匹配关键词"] = {
            "必要词": [{"关键词": word, "权重": weight} for word, weight in essential_matches],
            "加分词": [{"关键词": word, "权重": weight} for word, weight in bonus_matches]
        }

        total_score = (
            vector_score * Config.WEIGHTS["VECTOR_MATCH"] +
            keyword_score * Config.WEIGHTS["KEYWORD_MATCH"] +
            quality_score * Config.WEIGHTS["RESUME_QUALITY"]
        )
        return total_score

    def search(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"开始处理查询: {query}")

        try:
            query_keywords = Config.FILTER_KEYWORDS.get(query, {})
            logger.info(f"查询关键词: {query_keywords}")

            embedding = self.get_embedding(query)
            logger.info(f"✅ 查询向量生成完成，维度: {len(embedding)}")

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

                candidate["综合得分"] = self.score_candidate(candidate, query_keywords)
                candidates.append(candidate)

            candidates.sort(key=lambda x: x["综合得分"], reverse=True)
            search_time = time.time() - start_time

            return {
                "查询": query,
                "候选人数量": len(candidates),
                "关键词配置": {
                    "必要词数量": len(query_keywords.get("必要词", {})),
                    "加分词数量": len(query_keywords.get("加分词", {}))
                },
                "处理时间": f"{search_time:.2f}秒",
                "候选人列表": candidates
            }

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            raise

def main():
    query = ""
    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i] in ["--query", "-q"] and i + 1 < len(sys.argv):
                query = sys.argv[i + 1].strip()
                break
            elif sys.argv[i] not in ["--query", "-q"]:
                query = sys.argv[i].strip()
                break

    if not query:
        print(json.dumps({"候选人列表": [], "查询关键词": "", "状态": "无关键词"}, ensure_ascii=False))
        return

    print(f"搜索关键词: {query}")
    try:
        searcher = ResumeSearcher()
        searcher.connect()
        result = searcher.search(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"执行失败: {e}")
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