import os
from typing import Dict
from pydantic_settings import BaseSettings
from pydantic import Extra


class Settings(BaseSettings):
    """配置类：从 .env 加载 API Key、本地路径、Weaviate 地址等"""

    # ✅ API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # ✅ Weaviate 云端地址（通过 .env 控制是否连接公网）
    WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    WEAVIATE_URL_QIANWEN: str = os.getenv("WEAVIATE_URL_QIANWEN", "http://localhost:8090")
    WEAVIATE_COLLECTION: str = "ResumesOpenAI"
    WEAVIATE_BATCH_SIZE: int = 100

    # ✅ 文件路径（用于本地简历管理）
    RESUME_DIR: str = os.getenv("RESUME_DIR", "data/resumes")
    EXTRACTED_DIR: str = os.getenv("EXTRACTED_DIR", "data/resumes_extract_enhanced")
    EXTRACTED_DIR_QIANWEN: str = os.getenv("EXTRACTED_DIR_QIANWEN", "data/resumes_extract_qianwen")

    # ✅ 搜索配置
    DEFAULT_TOP_K: int = 5
    SEARCH_CERTAINTY: float = 0.7

    # ✅ 简历关键词配置
    FILTER_KEYWORDS: Dict = {
        "光学工程师": {
            "必要词": {"光学": 1.0, "工程师": 0.8},
            "加分词": {
                "光路": 0.6, "光机": 0.6, "光电": 0.5, "光刻": 0.5,
                "光栅": 0.5, "光谱": 0.5, "激光": 0.5, "研发": 0.4,
                "设计": 0.4, "optical": 0.4, "engineer": 0.4
            },
        },
        "软件工程师": {
            "必要词": {"软件": 1.0, "工程师": 0.8},
            "加分词": {
                "开发": 0.6, "编程": 0.6, "代码": 0.5, "算法": 0.5,
                "测试": 0.4, "software": 0.4, "developer": 0.4,
                "python": 0.4, "java": 0.4
            },
        },
    }

    # ✅ 打分权重
    WEIGHTS: Dict = {
        "VECTOR_MATCH": 0.4,
        "KEYWORD_MATCH": 0.4,
        "RESUME_QUALITY": 0.2,
    }

    # ✅ 其它参数
    EMBEDDING_CACHE_SIZE: int = 100
    SUMMARY_LENGTH: int = 200

    # ✅ 向量模型名称
    EMBEDDING_MODEL: str = "text-embedding-ada-002"

    # ✅ 日志配置（用于 search_candidates）
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(levelname)s - %(message)s"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = Extra.allow  # 避免"extra forbidden"报错

# 实例化配置
settings = Settings()