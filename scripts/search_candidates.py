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
        """连接到 Weaviate 数据库"""
        try:
            self.weaviate_client = get_weaviate_client(self.openai_api_key)
            self.weaviate_client.connect()
            self.collection = self.weaviate_client.collections.get(WEAVIATE_CLASS_NAME)
            logger.info("成功连接到 Weaviate")
        except Exception as e:
            logger.error(f"连接 Weaviate 失败: {e}")
            raise

    def disconnect(self) -> None:
        """断开与 Weaviate 的连接"""
        if self.weaviate_client and self.weaviate_client.is_ready():
            try:
                self.weaviate_client.close()
                logger.info("已断开与 Weaviate 的连接")
            except Exception as e:
                logger.warning(f"断开连接时发生错误: {e}")

    @staticmethod
    def format_summary(content: str) -> str:
        """格式化简历摘要"""
        if not content:
            return ""
        summary = re.sub(r'\s+', ' ', content.strip())[:settings.SUMMARY_LENGTH]
        return summary + "..." if len(content) > settings.SUMMARY_LENGTH else summary

    @staticmethod
    def check_keywords(content: str) -> List[str]:
        """检查关键词匹配"""
        if not content:
            return []
        content_lower = content.lower()
        return [k for k, v in settings.FILTER_KEYWORDS.items() 
                if any(kw.lower() in content_lower for kw in v)]

    @staticmethod
    def parse_filename(filename: str) -> Tuple[str, str]:
        """从文件名解析姓名和职位"""
        name, job_title = "（未提取）", "（未提取）"
        match = re.match(r'(.+?)_(.+?)_', filename)
        if match:
            name = match.group(1)
            job_title = match.group(2)
        return name, job_title

    @staticmethod
    def evaluate_resume_quality(content: str) -> float:
        """评估简历质量（0-1分）"""
        if not content:
            return 0.0
            
        score = 0.0
        # 1. 长度评分 (最高0.3分)
        length = len(content)
        length_score = min(length / 2000, 1.0) * 0.3
        
        # 2. 结构评分 (最高0.4分)
        structure_score = 0.0
        if "教育背景" in content or "教育经历" in content:
            structure_score += 0.1
        if "工作经验" in content or "工作经历" in content:
            structure_score += 0.1
        if "项目经验" in content or "项目经历" in content:
            structure_score += 0.1
        if "技能" in content or "专业技能" in content:
            structure_score += 0.1
            
        # 3. 信息完整度评分 (最高0.3分)
        info_score = 0.0
        if re.search(r'1[3-9]\d{9}', content):  # 手机号
            info_score += 0.1
        if re.search(r'[\w\.-]+@[\w\.-]+', content):  # 邮箱
            info_score += 0.1
        if re.search(r'(本科|学士|硕士|博士|MBA|PhD)', content):  # 学历
            info_score += 0.1
            
        return length_score + structure_score + info_score

    @lru_cache(maxsize=settings.EMBEDDING_CACHE_SIZE)
    def get_embedding(self, text: str) -> List[float]:
        """获取文本的向量表示（带缓存）"""
        try:
            response = self.openai_client.embeddings.create(
                input=[text],
                model=settings.EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"获取向量失败: {e}")
            raise

    def score_candidate(self, candidate: Dict[str, Any], query_keywords: Dict[str, Dict[str, float]]) -> float:
        """计算候选人综合得分"""
        # 1. 向量匹配度分数
        vector_score = float(candidate["匹配度"].rstrip("%")) / 100.0
        
        # 2. 关键词匹配分数
        keyword_score = 0.0
        content_lower = candidate["简历内容"].lower()
        
        # 计算必要词匹配
        essential_matches = []
        if "必要词" in query_keywords:
            for word, weight in query_keywords["必要词"].items():
                if word.lower() in content_lower:
                    essential_matches.append((word, weight))
                    keyword_score += weight
        
        # 计算加分词匹配
        bonus_matches = []
        if "加分词" in query_keywords:
            for word, weight in query_keywords["加分词"].items():
                if word.lower() in content_lower:
                    bonus_matches.append((word, weight))
                    keyword_score += weight
        
        # 归一化关键词得分（除以最大可能得分）
        max_possible_score = sum(query_keywords.get("必要词", {}).values()) + \
                           sum(query_keywords.get("加分词", {}).values())
        keyword_score = keyword_score / max_possible_score if max_possible_score > 0 else 0
        
        # 3. 简历质量分数
        quality_score = self.evaluate_resume_quality(candidate["简历内容"])
        
        # 更新匹配关键词信息
        candidate["匹配关键词"] = {
            "必要词": [{"关键词": word, "权重": weight} for word, weight in essential_matches],
            "加分词": [{"关键词": word, "权重": weight} for word, weight in bonus_matches]
        }
        
        # 计算加权总分
        total_score = (
            vector_score * settings.WEIGHTS["VECTOR_MATCH"] +
            keyword_score * settings.WEIGHTS["KEYWORD_MATCH"] +
            quality_score * settings.WEIGHTS["RESUME_QUALITY"]
        )
        
        return total_score

    def search(self, query: str) -> Dict[str, Any]:
        """执行简历搜索"""
        start_time = time.time()
        logger.info(f"开始处理查询: {query}")

        try:
            # 获取职位相关的关键词配置
            query_keywords = settings.FILTER_KEYWORDS.get(query, {})
            if not query_keywords:
                logger.warning(f"未找到'{query}'的关键词配置，将使用基础向量搜索")
            
            logger.info(f"查询关键词: {query}")
            logger.info(f"必要关键词: {list(query_keywords.get('必要词', {}).keys())}")
            logger.info(f"加分关键词: {list(query_keywords.get('加分词', {}).keys())}")

            # 获取查询向量
            embedding = self.get_embedding(query)
            logger.info(f"已生成查询向量，维度: {len(embedding)}")

            # 执行向量搜索
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

                # 解析文件名获取姓名和职位
                name, job_title = self.parse_filename(filename)

                # 创建候选人信息，将 UUID 转换为字符串
                candidate = {
                    "UUID": str(obj.uuid),  # 确保 UUID 被转换为字符串
                    "姓名": name,
                    "应聘职位": job_title,
                    "文件名": filename,
                    "匹配度": f"{certainty:.1f}%",
                    "简历摘要": self.format_summary(content),
                    "简历内容": content,
                }

                # 计算综合得分
                candidate["综合得分"] = self.score_candidate(candidate, query_keywords)
                candidates.append(candidate)

            # 按综合得分排序
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