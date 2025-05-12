import weaviate
import json
from pprint import pprint

def connect_to_local():
    return weaviate.Client(
        url="http://localhost:8080",
        additional_headers={}
    )

def main():
    # 连接
    client = connect_to_local()
    print("✅ 连接状态:", client.is_ready())
    print("\n" + "="*50 + "\n")

    # 1. 检查所有集合
    print("📚 所有集合:")
    collections = client.collections.list_all()
    pprint(collections)
    print("\n" + "="*50 + "\n")

    # 2. 检查 Resumes 集合的 schema
    print("📋 Resumes 集合的 Schema:")
    schema = client.schema.get("Resumes")
    pprint(schema)
    print("\n" + "="*50 + "\n")

    # 3. 检查第一个对象的所有字段
    print("🔍 第一个对象的完整数据:")
    result = (
        client.query
        .get("Resumes", ["filename", "content"])
        .with_additional(["vector"])
        .with_limit(1)
        .do()
    )
    pprint(result)
    print("\n" + "="*50 + "\n")

    # 4. 检查向量维度
    if result["data"]["Get"]["Resumes"]:
        obj = result["data"]["Get"]["Resumes"][0]
        vector = obj.get("_additional", {}).get("vector")
        if vector:
            print(f"📊 向量维度: {len(vector)}")
            print(f"📊 向量前5个值: {vector[:5]}")
        else:
            print("❌ 向量不存在")
    else:
        print("❌ 没有找到任何对象")

if __name__ == "__main__":
    main() 