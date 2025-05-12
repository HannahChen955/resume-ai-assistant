import requests
import uuid
import random
import json

# ✅ 配置
CLASS_NAME = "TestManualVector"
VECTOR_DIM = 1536
test_uuid = str(uuid.uuid4())

# ✅ 构造请求体（手动向量）
payload = {
    "class": CLASS_NAME,
    "id": test_uuid,
    "properties": {
        "title": "测试对象 - REST 写入"
    },
    "vector": [random.random() for _ in range(VECTOR_DIM)]
}

# ✅ 写入对象
print("🚀 正在写入对象...")
res = requests.post("http://localhost:8080/v1/objects", json=payload)
print("状态码:", res.status_code)
try:
    print("响应:", res.json())
except Exception as e:
    print("响应内容解析失败:", e)

# ✅ 查询向量（需要使用 GraphQL 才能返回 vector）
print("\n🔍 使用 GraphQL 查询对象是否写入成功...")
graphql_url = "http://localhost:8080/v1/graphql"
query = {
    "query": f"""
    {{
      Get {{
        {CLASS_NAME}(where: {{path: ["id"], operator: Equal, valueString: "{test_uuid}"}}) {{
          title
          _additional {{
            id
            vector
          }}
        }}
      }}
    }}
    """
}
res_query = requests.post(graphql_url, json=query)
try:
    result = res_query.json()
    objs = result.get("data", {}).get("Get", {}).get(CLASS_NAME, [])
    if not objs:
        print("❌ 没有找到对象")
    else:
        vector = objs[0].get("_additional", {}).get("vector")
        if vector:
            print(f"✅ 向量维度: {len(vector)}")
            print(f"✅ 向量前5维: {vector[:5]}")
        else:
            print("❌ 向量字段不存在")
except Exception as e:
    print("❌ 查询失败:", e)