import requests
from pprint import pprint

# ✅ 配置
WEAVIATE_URL = "http://localhost:8080"
CLASS_NAME = "ResumesOpenAI"
LIMIT = 10

def check_connection():
    try:
        r = requests.get(f"{WEAVIATE_URL}/v1/.well-known/ready")
        if r.status_code == 200:
            print("✅ Weaviate 连接成功")
        else:
            print(f"⚠️ Weaviate 状态码异常: {r.status_code}")
    except Exception as e:
        print("❌ 无法连接 Weaviate:", e)

def list_collections():
    print("\n📚 当前集合:")
    r = requests.get(f"{WEAVIATE_URL}/v1/schema")
    if r.status_code == 200:
        pprint(r.json())
    else:
        print("❌ 获取 schema 失败")

def check_multiple_object_vectors():
    print(f"\n🔍 查询前 {LIMIT} 个对象及其向量:")
    graphql_query = {
        "query": f"""
        {{
            Get {{
                {CLASS_NAME}(limit: {LIMIT}) {{
                    filename
                    _additional {{
                        vector
                    }}
                }}
            }}
        }}
        """
    }
    try:
        res = requests.post(f"{WEAVIATE_URL}/v1/graphql", json=graphql_query)
        data = res.json()
        objects = data["data"]["Get"].get(CLASS_NAME)
        if not objects:
            print("⚠️ 没有对象数据")
            return

        for idx, obj in enumerate(objects, 1):
            print(f"\n🔹 第 {idx} 个对象:")
            print("📄 文件名:", obj.get("filename", "N/A"))
            vector = obj["_additional"].get("vector")
            if vector:
                print(f"✅ 向量维度: {len(vector)}")
                print(f"✅ 向量前5维: {vector[:5]}")
            else:
                print("❌ 向量不存在")
    except Exception as e:
        print("❌ 查询失败:", e)

def check_object_count():
    print("\n📊 检查集合对象数量:")
    try:
        res = requests.get(f"{WEAVIATE_URL}/v1/objects?class={CLASS_NAME}&limit=0")
        if res.status_code == 200:
            data = res.json()
            print(f"✅ 当前对象总数: {data.get('totalResults', 0)}")
        else:
            print(f"❌ 获取对象数量失败: {res.status_code}")
    except Exception as e:
        print(f"❌ 获取对象数量异常: {e}")

def main():
    check_connection()
    list_collections()
    check_multiple_object_vectors()
    check_object_count()

if __name__ == "__main__":
    main()