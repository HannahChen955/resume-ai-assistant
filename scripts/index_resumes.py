import os
import sys
import uuid
import time
import json
import requests
from typing import List

import pdfplumber
import docx
from tqdm import tqdm

# 添加父目录以导入 config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.config import settings

RESUMES_DIR = settings.EXTRACTED_DIR
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS_NAME = settings.WEAVIATE_COLLECTION
NAMESPACE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
MAX_TEXT_LENGTH = settings.SUMMARY_LENGTH * 40

# ✅ 初始化 OpenAI 客户端
from openai import OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def get_embedding(text: str) -> List[float]:
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    vector = response.data[0].embedding
    print(f"[DEBUG] 向量维度: {len(vector)}，前5维: {vector[:5]}")
    return vector

def load_resume_text(file_path: str) -> str:
    if file_path.endswith(".txt"):
        with open(file_path, 'r', encoding="utf-8") as f:
            text = f.read()
            return text[:MAX_TEXT_LENGTH]
    return ""

def object_exists(resume_uuid: str) -> bool:
    url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS_NAME}/{resume_uuid}"
    response = requests.get(url)
    return response.status_code == 200

def upload_resume(filename: str, content: str, vector: List[float], resume_uuid: str):
    payload = {
        "class": WEAVIATE_CLASS_NAME,
        "id": resume_uuid,
        "properties": {
            "filename": filename,
            "content": content
        },
        "vector": vector
    }

    url = f"{WEAVIATE_URL}/v1/objects"
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"✅ 插入成功: {filename}")
    else:
        print(f"❌ 插入失败: {filename}")
        print("状态码:", response.status_code)
        try:
            print("错误信息:", response.json())
        except:
            print("⚠️ 响应体解析失败")

def index_resumes():
    if not os.path.exists(RESUMES_DIR):
        print(f"❌ 简历目录不存在: {RESUMES_DIR}")
        return

    files = [f for f in os.listdir(RESUMES_DIR) if f.endswith(".txt")]
    if not files:
        print("⚠️ 没有发现简历文件")
        return

    print("📄 开始处理简历:")

    for filename in tqdm(files):
        file_path = os.path.join(RESUMES_DIR, filename)
        content = load_resume_text(file_path)

        if not content.strip():
            print(f"⚠️ 跳过空文件: {filename}")
            continue

        resume_uuid = str(uuid.uuid5(NAMESPACE_UUID, filename))

        if object_exists(resume_uuid):
            print(f"⏩ 已存在: {filename}")
            continue

        try:
            vector = get_embedding(content)
            upload_resume(filename, content, vector, resume_uuid)
            time.sleep(0.3)  # 限流
        except Exception as e:
            import traceback
            print(f"❌ 上传失败: {filename}")
            traceback.print_exc()

    print("✅ 所有简历处理完成！")

if __name__ == "__main__":
    index_resumes()