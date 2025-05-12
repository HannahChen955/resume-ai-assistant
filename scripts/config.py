import os
from pydantic_settings import BaseSettings
from pydantic import Extra


class Settings(BaseSettings):
    """
    全局配置类：控制 API Key、文件路径、搜索参数、日志等级等
    """

    # ✅ API Keys
    OPENAI_APIKEY: str = os.getenv("OPENAI_APIKEY", "")
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # ✅ Weaviate 服务地址
    WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    WEAVIATE_URL_QIANWEN: str = os.getenv("WEAVIATE_URL_QIANWEN", "http://localhost:8090")
    WEAVIATE_COLLECTION: str = "ResumesOpenAI"
    WEAVIATE_BATCH_SIZE: int = 100  # 向量上传批次大小

    # ✅ 文件路径配置
    RESUME_DIR: str = os.getenv("RESUME_DIR", "data/resumes")
    EXTRACTED_DIR: str = os.getenv("EXTRACTED_DIR", "data/resumes_extract_enhanced")
    EXTRACTED_DIR_QIANWEN: str = os.getenv("EXTRACTED_DIR_QIANWEN", "data/resumes_extract_qianwen")

    # ✅ 搜索配置（REST GraphQL 专用）
    DEFAULT_TOP_K: int = 5
    SEARCH_CERTAINTY: float = 0.75
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    EMBEDDING_CACHE_SIZE: int = 100
    SUMMARY_LENGTH: int = 200

    # ✅ 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(levelname)s - %(message)s"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = Extra.allow


# 实例化配置
settings = Settings()