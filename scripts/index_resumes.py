"""
简历索引脚本
用于将简历文本提取并索引到 Weaviate 数据库
"""
import os
import sys
import uuid
import time
from pathlib import Path
from typing import List

import pdfplumber
import docx
from tqdm import tqdm
from dotenv import load_dotenv

# ✅ 加载 .env 文件（确保能获取 EXTRACTED_DIR）
load_dotenv()

# 添加父目录以导入工具模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.weaviate_utils import (
    get_weaviate_client, WEAVIATE_CLASS_NAME,
    NAMESPACE_UUID, MAX_TEXT_LENGTH
)
from scripts.config import settings

from openai import OpenAI
from weaviate.classes.config import Property, DataType
from weaviate import WeaviateClient

# === 初始化 OpenAI 客户端 ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ✅ 读取简历目录路径（来自 .env）
RESUMES_DIR = settings.EXTRACTED_DIR

# === 获取向量 ===
def get_embedding(text: str) -> List[float]:
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

# === 加载文本 ===
def load_resume_text(file_path: str) -> str:
    if file_path.endswith(".txt"):
        with open(file_path, 'r', encoding="utf-8") as f:
            text = f.read()
            return text[:MAX_TEXT_LENGTH]
    return ""

# === 创建集合 ===
def ensure_collection_exists(client: WeaviateClient) -> bool:
    try:
        if not client.collections.exists(WEAVIATE_CLASS_NAME):
            print("📦 创建集合...")
            client.collections.create(
                name=WEAVIATE_CLASS_NAME,
                properties=[
                    Property(name="filename", data_type=DataType.TEXT),
                    Property(name="content", data_type=DataType.TEXT)
                ],
                vectorizer_config=None  # 手动向量化
            )
        else:
            print("✅ 集合已存在")
        return True
    except Exception as e:
        print(f"❌ 创建集合失败: {e}")
        return False

# === 主函数 ===
def index_resumes():
    client = get_weaviate_client(api_key=OPENAI_API_KEY)
    client.connect()

    if not ensure_collection_exists(client):
        return

    if not os.path.exists(RESUMES_DIR):
        print(f"❌ 错误：简历目录 {RESUMES_DIR} 不存在。")
        return

    files = [f for f in os.listdir(RESUMES_DIR) if f.endswith(".txt")]
    if not files:
        print("⚠️ 没有找到简历文件。")
        return

    collection = client.collections.get(WEAVIATE_CLASS_NAME)
    print("处理简历:")

    for filename in tqdm(files):
        file_path = os.path.join(RESUMES_DIR, filename)
        content = load_resume_text(file_path)

        if not content.strip():
            print(f"⚠️ 空文件: {filename}")
            continue

        resume_uuid = str(uuid.uuid5(NAMESPACE_UUID, filename))

        # 检查是否已存在
        existing = collection.query.fetch_object_by_id(resume_uuid)
        if existing is not None:
            print(f"⏩ 已存在: {filename}")
            continue

        try:
            vector = get_embedding(content)

            collection.data.insert(
                uuid=resume_uuid,
                properties={
                    "filename": filename,
                    "content": content
                },
                vector=vector
            )

            time.sleep(0.3)  # 减缓速率

        except Exception as e:
            print(f"❌ 上传失败: {filename} 错误: {e}")

    client.close()
    print("✅ 向量上传完成！")

if __name__ == "__main__":
    index_resumes()
