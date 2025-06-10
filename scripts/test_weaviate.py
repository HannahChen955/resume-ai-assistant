import requests
import json
from typing import List

url = "http://localhost:8080/v1/objects"
payload = {
    "class": "Candidates",
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "properties": {
        "filename": "test.txt",
        "content": "向量插入测试",
        "name": "测试用户",
        "position": "AI工程师",
        "notes": []
    },
    "vector": [0.1] * 1536  # 生成 1536 维的向量
}

response = requests.post(url, json=payload)
print(f"Status code: {response.status_code}")
print(f"Response: {response.text}")

def upload_resume(filename: str, content: str, vector: List[float], resume_uuid: str, name: str = "", position: str = ""):
    # 1. 检查向量
    logger.info("🔍 正准备插入对象: %s", filename)
    logger.info("📐 向量维度: %s", len(vector) if vector else "❌ 无向量")
    logger.info("📦 向量预览: %s", vector[:5] if vector else None)
    
    if not vector:
        logger.warning("⚠️ 向量为空，跳过上传: %s", filename)
        return

    # 2. 构建 payload
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

    # 3. 打印完整 payload
    logger.info("🧾 准备插入对象 payload:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))

    # 4. 发送请求
    url = f"{WEAVIATE_URL}/v1/objects"
    response = requests.post(url, json=payload)
    
    # 5. 检查响应
    logger.info(f"[DEBUG] Weaviate 响应状态: {response.status_code}")
    logger.info(f"[DEBUG] Weaviate 响应体: {response.text}")
    
    if response.status_code == 200:
        logger.info("✅ 插入成功: %s", filename)
        # 6. 立即验证
        verify_url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{resume_uuid}?include=vector"
        verify_response = requests.get(verify_url)
        if verify_response.status_code == 200:
            verify_data = verify_response.json()
            logger.info("🔍 验证结果 - 向量状态: %s", 
                       "✅ 有向量" if verify_data.get("vector") else "❌ 无向量")
            logger.info("🔍 验证结果 - 向量维度: %s", 
                       len(verify_data.get("vector", [])) if verify_data.get("vector") else "N/A")
    else:
        logger.error("❌ 插入失败: %s，状态码: %d", filename, response.status_code)
        try:
            logger.error("错误信息: %s", response.json())
        except:
            logger.warning("⚠️ 响应体解析失败")

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