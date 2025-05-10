import os
import uuid
from weaviate.client import WeaviateClient
from weaviate.connect import ConnectionParams
from weaviate.classes.init import AdditionalConfig

# ===================== 路径配置 =====================

def is_running_in_container() -> bool:
    return os.path.exists('/.dockerenv')

RESUMES_DIR = (
    "/home/node/data/resumes_extract_qianwen"
    if is_running_in_container()
    else "../data/resumes_extract_qianwen"
)

MARKDOWN_DIR = "/home/node/data/markdown_uploads"
JSON_OUTPUT_DIR = "/home/node/data/json_outputs"
N8N_FLOWS_DIR = "/home/node/data/n8n_flows"

# ===================== Weaviate 配置 =====================

# ✅ 使用远程公网 Weaviate 地址（云端）
WEAVIATE_HTTP_URL = "https://resume.prime-sources.com"
WEAVIATE_GRPC_PORT = 50051
WEAVIATE_CLASS_NAME = "Candidates"

# ===================== 向量处理相关参数 =====================

NAMESPACE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")

# ✅ 替换为通义千问 embedding 模型名称（用于 log）
EMBEDDING_MODEL = "text-embedding-v1"

MAX_TEXT_LENGTH = 8000
SUMMARY_LENGTH = 300
DEFAULT_CERTAINTY = 0.7
TOP_K_RESULTS = 5

# ===================== 实用函数 =====================

def get_env_variable(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"未找到环境变量: {key}")
    return value

def get_weaviate_client(api_key: str) -> WeaviateClient:
    """
    初始化 Weaviate 客户端，使用通义千问的 DashScope API Key
    """
    return WeaviateClient(
        connection_params=ConnectionParams.from_url(
            url=WEAVIATE_HTTP_URL,
            grpc_port=WEAVIATE_GRPC_PORT
        ),
        additional_config=AdditionalConfig(
            headers={"X-DashScope-Api-Key": api_key}
        )
    )