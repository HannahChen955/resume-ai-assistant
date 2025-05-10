"""
配置文件
包含通义千问API和Weaviate的配置信息
"""
import os
from typing import Optional, Dict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """配置类"""
    # 通义千问API配置
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    
    # Weaviate配置
    WEAVIATE_URL: str = os.getenv("WEAVIATE_URL_QIANWEN", "http://localhost:8090")
    WEAVIATE_COLLECTION: str = "ResumesQianwen"
    WEAVIATE_BATCH_SIZE: int = 100
    
    # 文件路径配置
    RESUME_DIR: str = os.getenv("RESUME_DIR", "data/resumes")
    EXTRACTED_DIR: str = os.getenv("EXTRACTED_DIR_QIANWEN", "data/resumes_extract_qianwen")
    
    # 搜索配置
    DEFAULT_TOP_K: int = 5
    SEARCH_CERTAINTY: float = 0.7
    
    # 关键词配置（带权重）
    FILTER_KEYWORDS: Dict = {
        "光学工程师": {
            "必要词": {
                "光学": 1.0,
                "工程师": 0.8,
            },
            "加分词": {
                "光路": 0.6,
                "光机": 0.6,
                "光电": 0.5,
                "光刻": 0.5,
                "光栅": 0.5,
                "光谱": 0.5,
                "激光": 0.5,
                "研发": 0.4,
                "设计": 0.4,
                "optical": 0.4,
                "engineer": 0.4,
            }
        },
        "软件工程师": {
            "必要词": {
                "软件": 1.0,
                "工程师": 0.8,
            },
            "加分词": {
                "开发": 0.6,
                "编程": 0.6,
                "代码": 0.5,
                "算法": 0.5,
                "测试": 0.4,
                "software": 0.4,
                "developer": 0.4,
                "python": 0.4,
                "java": 0.4,
            }
        }
    }
    
    # 评分权重
    WEIGHTS: Dict = {
        "VECTOR_MATCH": 0.4,     # 向量匹配度权重
        "KEYWORD_MATCH": 0.4,    # 关键词匹配权重
        "RESUME_QUALITY": 0.2    # 简历质量权重
    }
    
    # 缓存配置
    EMBEDDING_CACHE_SIZE: int = 100
    
    # 摘要配置
    SUMMARY_LENGTH: int = 200

    class Config:
        """Pydantic配置"""
        env_file = ".env"
        case_sensitive = True

settings = Settings() 