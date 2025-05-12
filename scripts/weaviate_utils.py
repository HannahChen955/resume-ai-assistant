import os
import uuid
import requests
from dotenv import load_dotenv
from scripts.config import settings

# ✅ 加载环境变量
load_dotenv()

# === 配置参数 ===
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS_NAME = settings.WEAVIATE_COLLECTION
NAMESPACE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
MAX_TEXT_LENGTH = settings.SUMMARY_LENGTH * 40
SUMMARY_LENGTH = settings.SUMMARY_LENGTH
DEFAULT_CERTAINTY = settings.SEARCH_CERTAINTY
TOP_K_RESULTS = settings.DEFAULT_TOP_K

# ✅ 检查集合是否存在
def class_exists() -> bool:
    res = requests.get(f"{WEAVIATE_URL}/v1/schema")
    if res.status_code == 200:
        classes = res.json().get("classes", [])
        return any(cls["class"] == WEAVIATE_CLASS_NAME for cls in classes)
    return False

# ✅ 创建集合（关闭自动向量化）
def create_class():
    payload = {
        "class": WEAVIATE_CLASS_NAME,
        "vectorizer": "none",
        "vectorIndexType": "hnsw",
        "properties": [
            {
                "name": "filename",
                "dataType": ["text"],
            },
            {
                "name": "content",
                "dataType": ["text"],
            }
        ]
    }
    res = requests.post(f"{WEAVIATE_URL}/v1/schema", json=payload)
    print(f"📦 创建集合状态码: {res.status_code}")
    print(res.json())

# ✅ 写入对象（带向量）
def insert_object(obj_uuid: str, filename: str, content: str, vector: list):
    payload = {
        "class": WEAVIATE_CLASS_NAME,
        "id": obj_uuid,
        "properties": {
            "filename": filename,
            "content": content
        },
        "vector": vector
    }
    res = requests.post(f"{WEAVIATE_URL}/v1/objects", json=payload)
    return res.status_code == 200