import os
import uuid
from dotenv import load_dotenv
from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams
from weaviate.classes.init import AdditionalConfig

# 加载环境变量
load_dotenv()

# === 基本路径 ===
RESUMES_DIR = os.getenv("EXTRACTED_DIR", "data/resumes_extract_enhanced")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")

# === Weaviate 参数 ===
WEAVIATE_GRPC_PORT = 50051
WEAVIATE_CLASS_NAME = "Candidates"

# === 向量化与评分参数 ===
NAMESPACE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
MAX_TEXT_LENGTH = 8000
SUMMARY_LENGTH = 300
DEFAULT_CERTAINTY = 0.7
TOP_K_RESULTS = 5

# === 初始化客户端 ===
def get_weaviate_client(api_key: str) -> WeaviateClient:
    return WeaviateClient(
        connection_params=ConnectionParams.from_url(
            url=WEAVIATE_URL,
            grpc_port=WEAVIATE_GRPC_PORT
        ),
        additional_config=AdditionalConfig(
            headers={"Authorization": f"Bearer {api_key}"}
        )
    )