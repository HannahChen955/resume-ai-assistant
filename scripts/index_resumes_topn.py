#!/usr/bin/env python3

import os
import sys
import uuid
import time
import json
import requests
from typing import List
import re
import pdfplumber
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

# ✅ 加载 .env 文件
load_dotenv()

# ✅ 环境变量配置
RESUMES_DIR = os.getenv("EXTRACTED_DIR", "data/resumes_extract_enhanced")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
NAMESPACE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
TOP_N = 5
MAX_CHUNK_LENGTH = 300

# ✅ 初始化 OpenAI 客户端
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ✅ 获取向量
def get_embedding(text: str) -> List[float]:
    response = openai_client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding

# ✅ GPT 分段打分
def score_chunk(query: str, chunk: str) -> float:
    prompt = f"请根据与 {query} 岗位的相关性，对以下文本打分（满分100分），只返回数字：\n\n{chunk}"
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    try:
        return float(response.choices[0].message.content.strip().split()[0])
    except:
        return 0.0

# ✅ 切分文本段落
def chunk_text(text: str, max_length: int) -> List[str]:
    sentences = re.split(r'[\n。！？!？]', text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) < max_length:
            current += sentence + "。"
        else:
            if current:
                chunks.append(current.strip())
            current = sentence + "。"
    if current:
        chunks.append(current.strip())
    return [c for c in chunks if len(c) > 10]

# ✅ 读取简历文本
def load_resume_text(file_path: str) -> str:
    if file_path.endswith(".txt"):
        with open(file_path, 'r', encoding="utf-8") as f:
            return f.read()
    return ""

# ✅ 检查 Weaviate 是否已有该对象
def object_exists(resume_uuid: str) -> bool:
    url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{resume_uuid}"
    response = requests.get(url)
    return response.status_code == 200

# ✅ 上传到 Weaviate
def upload_resume(filename: str, content: str, vector: List[float], resume_uuid: str):
    payload = {
        "class": WEAVIATE_CLASS,
        "id": resume_uuid,
        "properties": {
            "filename": filename,
            "content": content,
            "notes": []  # ✅ 初始化 notes 字段
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

# ✅ 主逻辑
def index_resumes_topn():
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
        full_text = load_resume_text(file_path)
        if not full_text.strip():
            print(f"⚠️ 跳过空文件: {filename}")
            continue

        chunks = chunk_text(full_text, MAX_CHUNK_LENGTH)
        scored = [(chunk, score_chunk("光学工程师", chunk)) for chunk in chunks]
        sorted_chunks = sorted(scored, key=lambda x: x[1], reverse=True)
        selected_chunks = [chunk for chunk, _ in sorted_chunks[:TOP_N]]

        if not selected_chunks:
            print(f"⚠️ 无有效段落: {filename}")
            continue

        final_text = "\n".join(selected_chunks)
        resume_uuid = str(uuid.uuid5(NAMESPACE_UUID, filename))

        if object_exists(resume_uuid):
            print(f"⏩ 已存在: {filename}")
            continue

        try:
            vector = get_embedding(final_text)
            upload_resume(filename, final_text, vector, resume_uuid)
            time.sleep(0.3)
        except Exception as e:
            import traceback
            print(f"❌ 上传失败: {filename}")
            traceback.print_exc()

    print("✅ 所有简历处理完成！")

if __name__ == "__main__":
    index_resumes_topn()
