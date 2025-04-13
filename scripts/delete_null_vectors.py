import weaviate
import os
from dotenv import load_dotenv

# ✅ 加载环境变量
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# ✅ 初始化 Weaviate 客户端
client = weaviate.Client(
    url="http://weaviate:8080",
    additional_headers={"X-OpenAI-Api-Key": openai_api_key}
)

def delete_null_vectors():
    try:
        # 获取所有向量为空的对象
        result = client.query.get(
            "Candidates", ["_additional {id}"]) \
            .with_additional(["vector"]) \
            .do()

        objects = result["data"]["Get"]["Candidates"]
        null_vector_count = 0

        print(f"\n⏳ 开始检查空向量...")
        print(f"✅ 总共找到 {len(objects)} 个对象")

        # 删除向量为空的对象
        for obj in objects:
            if "_additional" in obj and "vector" not in obj["_additional"]:
                try:
                    object_id = obj["_additional"]["id"]
                    client.data_object.delete(
                        uuid=object_id,
                        class_name="Candidates"
                    )
                    null_vector_count += 1
                    print(f"  ✅ 删除空向量对象: {object_id}")
                except Exception as e:
                    print(f"  ❌ 删除失败: {object_id}")
                    print(f"    - 错误: {str(e)}")

        print(f"\n🎉 清理完成!")
        print(f"  ✅ 删除了 {null_vector_count} 个空向量对象")
        print(f"  ✅ 剩余 {len(objects) - null_vector_count} 个有效对象")

    except Exception as e:
        print(f"❌ 执行清理时出错:")
        print(f"  - 错误类型: {type(e).__name__}")
        print(f"  - 错误信息: {str(e)}")

if __name__ == "__main__":
    delete_null_vectors()