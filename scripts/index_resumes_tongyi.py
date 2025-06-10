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
import weaviate

# ✅ 强制加载环境变量（备用）
load_dotenv()

# ✅ DashScope API Key（hardcoded，用户指定保留）
dashscope.api_key = "sk-1d92a7280052451c84509f57e1b44991"

# ✅ 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ 环境变量配置
RESUMES_DIR = os.getenv("EXTRACTED_DIR", "data/resumes_extract_enhanced")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")
DASHSCOPE_EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v1")
NAMESPACE_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
TOP_N = 5
MAX_CHUNK_LENGTH = 300

# ✅ 自动注册 class（vectorizer=none）
def ensure_class_exists():
    url = f"{WEAVIATE_URL}/v1/schema"
    resp = requests.get(url)
    schema = resp.json()
    classes = [c['class'] for c in schema.get('classes', [])]
    if WEAVIATE_CLASS not in classes:
        logger.info("📚 Weaviate 中未找到 %s，准备自动注册...", WEAVIATE_CLASS)
        payload = {
            "class": WEAVIATE_CLASS,
            "vectorizer": "none",
            "properties": [
                {"name": "filename", "dataType": ["text"]},
                {"name": "content", "dataType": ["text"]},
                {"name": "name", "dataType": ["text"]},
                {"name": "position", "dataType": ["text"]},
                {"name": "notes", "dataType": ["text[]"]},
            ]
        }
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            logger.info("✅ 已自动注册 Weaviate class: %s", WEAVIATE_CLASS)
        else:
            logger.error("❌ 注册 class 失败: %s", resp.text)

# ✅ 向量前文本清洗（不截断，仅去重空行）
def clean_text_for_embedding(text: str) -> str:
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()

# ✅ 获取向量（通义 DashScope 强健版本）
def get_embedding(text: str) -> list[float]:
    text = clean_text_for_embedding(text)
    logger.info(f"🔍 向量化文本长度: {len(text)}")
    try:
        response = TextEmbedding.call(
            model=DASHSCOPE_EMBEDDING_MODEL,
            input=text
        )
        logger.info(f"[DEBUG] DashScope 原始响应: {response}")

        if isinstance(response, dict):
            embeddings = response.get("output", {}).get("embeddings", [])
            if embeddings and isinstance(embeddings[0], dict):
                vector = embeddings[0].get("embedding")
                logger.info(f"[DEBUG] 向量维度: {len(vector) if isinstance(vector, list) else 'N/A'}")
                logger.info(f"[DEBUG] 向量类型: {type(vector)}")
                logger.info(f"[DEBUG] 向量预览: {vector[:5] if isinstance(vector, list) else vector}")
                if vector and isinstance(vector, list) and all(isinstance(x, (float, int)) for x in vector):
                    logger.info("✅ 向量化成功，前5维: %s", vector[:5])
                    return vector

        logger.error(f"❌ 向量提取失败，结构异常: {response}")
        return []
    except Exception as e:
        logger.exception(f"❌ DashScope 异常: {e}")
        return []

# ✅ 文本分段
def chunk_text(text: str, max_length: int) -> List[str]:
    sentences = re.split(r'[\n。！？!\?]', text)
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

# ✅ 拆分结构
def split_txt_sections(full_text: str):
    pattern = r"===\s*字段提取结果\s*===\n(.*?)\n+===\s*模块结构分类结果\s*===\n(.*?)\n+===\s*原始简历文本\s*===\n(.*)"
    match = re.search(pattern, full_text, re.DOTALL)
    if match:
        fields_str, sections_str, raw_text = match.groups()
        return fields_str.strip(), sections_str.strip(), raw_text.strip()
    else:
        return "", "", full_text.strip()

# ✅ 拼接文本用于向量化
def build_vector_text(fields_str: str, sections_str: str, raw_text: str) -> str:
    return f"""【字段信息】\n{fields_str}\n\n【模块结构分类】\n{sections_str}\n\n【原文补充】\n{raw_text}"""

# ✅ 检查对象是否存在
def object_exists(resume_uuid: str) -> bool:
    url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{resume_uuid}"
    response = requests.get(url)
    return response.status_code == 200

# ✅ 上传对象
def upload_resume(filename: str, content: str, vector: List[float], resume_uuid: str, name: str = "", position: str = ""):
    logger.info(f"[DEBUG] upload_resume: filename={filename}, name={name}, position={position}, vector前5维={vector[:5] if vector else vector}")
    if not vector:
        logger.warning("⚠️ 向量为空，跳过上传: %s", filename)
        return

    payload = {
        "class": WEAVIATE_CLASS,
        "id": resume_uuid,
        "properties": {
            "filename": filename,
            "content": content,
            "name": name,
            "position": position,
            "notes": []
        },
        "vector": vector
    }

    logger.info("🧾 准备插入对象 payload:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))

    url = f"{WEAVIATE_URL}/v1/objects"
    response = requests.post(url, json=payload)
    logger.info(f"[DEBUG] Weaviate 响应状态: {response.status_code}, 响应体: {response.text}")
    if response.status_code == 200:
        logger.info("✅ 插入成功: %s", filename)
    else:
        logger.error("❌ 插入失败: %s，状态码: %d", filename, response.status_code)
        try:
            logger.error("错误信息: %s", response.json())
        except:
            logger.warning("⚠️ 响应体解析失败")

# ✅ 生成 UUID
def generate_uuid_from_file(filename: str, content: str) -> str:
    hash_val = hashlib.sha256(content.encode('utf-8')).hexdigest()
    return str(uuid.uuid5(NAMESPACE_UUID, filename + hash_val))

# ✅ 主函数
def index_resumes_topn():
    logger.info("🔧 当前使用通义模型: %s", DASHSCOPE_EMBEDDING_MODEL)
    ensure_class_exists()

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
        name_match = re.search(r"姓名[:：]\s*(.*)", fields)
        position_match = re.search(r"(目标职位|职位)[:：]\s*(.*)", fields)
        name = name_match.group(1).strip() if name_match else ""
        position = position_match.group(2).strip() if position_match else ""
        logger.info(f"[DEBUG] 解析到 name: {name}, position: {position}, file: {filename}")

        merged_text = build_vector_text(fields, sections, raw)
        chunks = chunk_text(merged_text, MAX_CHUNK_LENGTH)
        selected_chunks = chunks[:TOP_N]
        if not selected_chunks:
            logger.warning("⚠️ 无有效段落: %s", filename)
            continue

        final_text = "\n".join(selected_chunks)
        resume_uuid = generate_uuid_from_file(filename, final_text)

        if object_exists(resume_uuid):
            logger.info("⏩ 已存在: %s", filename)
            continue

        try:
            vector = get_embedding(final_text)
            logger.info(f"📐 最终向量前5维: {vector[:5] if vector else '空向量'}")
            upload_resume(filename, final_text, vector, resume_uuid, name, position)
            time.sleep(0.3)
        except Exception as e:
            logger.exception("❌ 上传失败: %s", filename)

    elapsed = time.time() - start
    logger.info("✅ 所有简历处理完成，总耗时 %.2fs", elapsed)

if __name__ == "__main__":
    index_resumes_topn()