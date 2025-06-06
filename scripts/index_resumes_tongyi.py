#!/usr/bin/env python3

import os
import uuid
import time
import json
import logging
import hashlib
import re
from typing import List
from tqdm import tqdm
from dotenv import load_dotenv
import dashscope
from dashscope import TextEmbedding
import requests

# ✅ 加载 .env 文件
load_dotenv()
dashscope.api_key = "sk-1d92a7280052451c84509f57e1b44991"

# ✅ 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ 环境变量配置
RESUMES_DIR = os.getenv("EXTRACTED_DIR", "data/resumes_extract_enhanced")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v1")
NAMESPACE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
TOP_N = 5
MAX_CHUNK_LENGTH = 300

# ✅ 获取向量（通义 DashScope 正确接口）
def get_embedding(text: str) -> list[float]:
    logger.info(f"🔍 向量化文本长度: {len(text)}")
    try:
        response = TextEmbedding.call(
            model=DASHSCOPE_EMBEDDING_MODEL,
            input=text
        )
        # 检查 response 结构
        if response and hasattr(response, "output") and response.output:
            embedding = response.output.get("embeddings", [{}])[0].get("embedding")
            if embedding:
                logger.info("✅ 向量化成功！前5维向量为: %s", embedding[:5])
                return embedding
        logger.error(f"❌ 通义返回结果异常: {response}")
        return []
    except Exception as e:
        logger.error(f"❌ 获取向量失败: {str(e)}")
        return []

# ✅ 安全截断文本
def safe_truncate(text: str, max_length: int = 1000) -> str:
    return text[:max_length] if len(text) > max_length else text

# ✅ 切分文本段落
def chunk_text(text: str, max_length: int) -> List[str]:
    sentences = re.split(r'[\n\u3002\uff01\uff1f!\?]', text)
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

# ✅ 从 .txt 中提取结构字段、模块内容和原文部分
def split_txt_sections(full_text: str):
    pattern = r"===\s*字段提取结果\s*===\n(.*?)\n+===\s*模块结构分类结果\s*===\n(.*?)\n+===\s*原始简历文本\s*===\n(.*)"
    match = re.search(pattern, full_text, re.DOTALL)
    if match:
        fields_str, sections_str, raw_text = match.groups()
        return fields_str.strip(), sections_str.strip(), raw_text.strip()
    else:
        return "", "", full_text.strip()

# ✅ 拼接结构信息与原文文本用于向量化
def build_vector_text(fields_str: str, sections_str: str, raw_text: str) -> str:
    return f"""【字段信息】\n{fields_str}\n\n【模块结构分类】\n{sections_str}\n\n【原文补充】\n{raw_text}"""

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
    if vector is None or not isinstance(vector, list):
        raise ValueError("❌ 向量为空或格式错误！")

    payload = {
        "class": WEAVIATE_CLASS,
        "id": resume_uuid,
        "properties": {
            "filename": filename,
            "content": content,
            "notes": []
        },
        "vector": vector
    }

    logger.debug("📦 上传对象 payload: \n%s", json.dumps(payload, indent=2, ensure_ascii=False))

    url = f"{WEAVIATE_URL}/v1/objects"
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("✅ 插入成功: %s", filename)
    else:
        logger.error("❌ 插入失败: %s", filename)
        logger.error("状态码: %d", response.status_code)
        try:
            logger.error("错误信息: %s", response.json())
        except:
            logger.warning("⚠️ 响应体解析失败")

# ✅ 根据文件名和内容生成 UUID
def generate_uuid_from_file(filename: str, content: str) -> str:
    hash_val = hashlib.sha256(content.encode('utf-8')).hexdigest()
    return str(uuid.uuid5(NAMESPACE_UUID, filename + hash_val))

# ✅ 主逻辑
def index_resumes_topn():
    logger.info("🔧 当前使用通义模型: %s", DASHSCOPE_EMBEDDING_MODEL)
    if not os.path.exists(RESUMES_DIR):
        logger.error("❌ 简历目录不存在: %s", RESUMES_DIR)
        return

    files = [f for f in os.listdir(RESUMES_DIR) if f.endswith(".txt")]
    if not files:
        logger.warning("⚠️ 没有发现简历文件")
        return

    logger.info("📄 开始处理简历:")
    start = time.time()

    for filename in tqdm(files):
        file_path = os.path.join(RESUMES_DIR, filename)
        full_text = load_resume_text(file_path)
        if not full_text.strip():
            logger.warning("⚠️ 跳过空文件: %s", filename)
            continue

        fields, sections, raw = split_txt_sections(full_text)
        merged_text = build_vector_text(fields, sections, raw)
        chunks = chunk_text(merged_text, MAX_CHUNK_LENGTH)
        selected_chunks = chunks[:TOP_N]

        if not selected_chunks:
            logger.warning("⚠️ 无有效段落: %s", filename)
            continue

        final_text = safe_truncate("\n".join(selected_chunks))
        resume_uuid = generate_uuid_from_file(filename, final_text)

        if object_exists(resume_uuid):
            logger.info("⏩ 已存在: %s", filename)
            continue

        try:
            vector = get_embedding(final_text)
            upload_resume(filename, final_text, vector, resume_uuid)
            time.sleep(0.3)
        except Exception as e:
            logger.exception("❌ 上传失败: %s", filename)

    elapsed = time.time() - start
    logger.info("✅ 所有简历处理完成！总耗时 %.2fs", elapsed)

if __name__ == "__main__":
    index_resumes_topn()