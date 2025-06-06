#!/usr/bin/env python3
# scripts/check_failed_vectors_in_extract.py

import os
import requests
from dotenv import load_dotenv

# ✅ 加载环境变量
load_dotenv()

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")
LOCAL_DIR = "data/resumes_extract_enhanced"
CONTENT_MIN_LENGTH = 200

# ✅ 获取本地所有 .txt 文件名
def get_local_filenames(directory: str):
    return sorted([f for f in os.listdir(directory) if f.endswith(".txt")])

# ✅ 查询 Weaviate 中对象状态 + 向量 + 内容字段
def check_object_status(filename: str) -> dict:
    graphql_query = {
        "query": f"""
        {{
          Get {{
            {WEAVIATE_CLASS}(where: {{
              operator: Equal,
              path: [\"filename\"],
              valueText: \"{filename}\"
            }}) {{
              filename
              content
              _additional {{
                id
                vector
              }}
            }}
          }}
        }}
        """
    }
    try:
        res = requests.post(f"{WEAVIATE_URL}/v1/graphql", json=graphql_query)
        res.raise_for_status()
        result = res.json()["data"]["Get"].get(WEAVIATE_CLASS, [])

        if not result:
            return {"文件名": filename, "状态": "❌ 不存在（未入库）"}

        content = result[0].get("content", "").strip()
        vector = result[0]["_additional"].get("vector")

        if not vector:
            return {"文件名": filename, "状态": "❌ 无向量"}

        if not content or len(content) < CONTENT_MIN_LENGTH:
            return {"文件名": filename, "状态": f"⚠️ 内容不足 ({len(content)} 字)"}

        return {"文件名": filename, "状态": "✅ 向量 + 内容 OK"}
    except Exception as e:
        return {"文件名": filename, "状态": f"❌ 错误: {str(e)}"}

if __name__ == "__main__":
    print("🔍 正在检查 resumes_extract_enhanced 中所有简历是否已有效向量化并入库...\n")
    filenames = get_local_filenames(LOCAL_DIR)
    total = len(filenames)
    abnormal = []

    for name in filenames:
        result = check_object_status(name)
        print(f"{result['文件名']}  →  {result['状态']}")
        if result["状态"] != "✅ 向量 + 内容 OK":
            abnormal.append(result["文件名"])

    print("\n📊 检查完成：")
    print(f"总文件数: {total}")
    print(f"异常数量: {len(abnormal)}")
    if abnormal:
        print("❗️ 以下文件存在问题:")
        for f in abnormal:
            print("  -", f)
