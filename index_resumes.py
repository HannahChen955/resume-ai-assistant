import os
import pdfplumber
import docx
import csv
from tqdm import tqdm
from dotenv import load_dotenv
import weaviate
import uuid
import openai
from datetime import datetime

# ✅ 加载 .env 环境变量
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# ✅ 初始化 OpenAI 客户端
openai_client = openai.OpenAI(api_key=openai_api_key)

# ✅ 初始化 Weaviate 客户端
client = weaviate.Client(
    url="http://weaviate:8080",
    additional_headers={"X-OpenAI-Api-Key": openai_api_key}
)

# ✅ 固定命名空间，确保 UUID 一致
NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")

# ✅ 各类简历文件解析
def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages])

def parse_docx(path):
    doc = docx.Document(path)
    return "\n".join([para.text for para in doc.paragraphs])

def parse_csv(path):
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = ["、".join(row) for row in reader]
            return "\n".join(rows)
    except Exception as e:
        print(f"❌ CSV 解析失败: {path}, 错误: {e}")
        return ""

# ✅ 确保 Candidates 集合存在
def ensure_collection_exists():
    try:
        print("⏳ 准备创建/更新集合...")
        
        # ✅ 强制删除现有集合（开发环境中方便调试）
        try:
            if client.schema.exists("Candidates"):
                print("🗑️ 删除现有集合...")
                client.schema.delete_class("Candidates")
                print("✅ 现有集合已删除")
        except Exception as e:
            print(f"⚠️ 删除集合时出错（可能不存在）: {str(e)}")
        
        # ✅ 创建新集合
        class_obj = {
            "class": "Candidates",
            "vectorizer": "none",  # 手动提供向量，禁用自动向量化
            "vectorIndexConfig": {  # 必须设置，否则向量不会被持久化
                "distance": "cosine"  # 使用余弦相似度
            },
            "properties": [
                {
                    "name": "name",
                    "dataType": ["text"],  # 统一使用 text 类型
                    "description": "简历文件名"
                },
                {
                    "name": "summary",
                    "dataType": ["text"],
                    "description": "简历摘要（前300字）"
                },
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "简历全文内容"
                },
                {
                    "name": "file_type",
                    "dataType": ["text"],  # 改为 text
                    "description": "文件类型（pdf/docx等）"
                },
                {
                    "name": "processed_at",
                    "dataType": ["text"],  # 改为 text
                    "description": "处理时间戳"
                }
            ]
        }
        
        client.schema.create_class(class_obj)
        print("✅ 成功创建新集合，配置如下:")
        print(f"  - 向量化方式: 手动")
        print(f"  - 向量索引: 已启用（余弦相似度）")
        print(f"  - 字段数量: {len(class_obj['properties'])}")
                
    except Exception as e:
        print(f"❌ 创建/更新集合失败:")
        print(f"  - 错误类型: {type(e).__name__}")
        print(f"  - 错误信息: {str(e)}")
        raise e

# ✅ 主处理函数
def index_resumes(folder="data/resumes"):
    # 首先确保集合存在
    ensure_collection_exists()
    
    os.makedirs(folder, exist_ok=True)
    file_list = os.listdir(folder)
    print(f"\n✅ 找到 {len(file_list)} 个简历文件，开始处理...")

    success_count = 0
    error_count = 0

    for filename in tqdm(file_list, desc="处理简历"):
        path = os.path.join(folder, filename)
        try:
            # ✅ 文件格式解析
            if filename.endswith(".pdf"):
                text = parse_pdf(path)
            elif filename.endswith(".docx"):
                text = parse_docx(path)
            elif filename.endswith(".txt"):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            elif filename.endswith(".csv"):
                text = parse_csv(path)
            else:
                print(f"❌ 跳过不支持的文件类型: {filename}")
                error_count += 1
                continue

            text = text.strip().replace("\n", " ")
            if len(text) == 0:
                print(f"⚠️ 文件 {filename} 提取文本为空，跳过")
                error_count += 1
                continue
            if len(text) > 8000:
                text = text[:8000]

            # ✅ 手动生成向量
            try:
                embedding_response = openai_client.embeddings.create(
                    input=[text],
                    model="text-embedding-ada-002"
                )
                embedding = embedding_response.data[0].embedding
                print(f"\n✅ 向量生成成功: {filename}")
                print(f"  - 维度: {len(embedding)}")
                print(f"  - 文本长度: {len(text)}")
            except Exception as e:
                print(f"\n❌ 向量生成失败: {filename}")
                print(f"  - 错误类型: {type(e).__name__}")
                print(f"  - 错误信息: {str(e)}")
                error_count += 1
                continue

            # ✅ 为该简历生成固定 UUID（确保更新/覆盖）
            resume_uuid = str(uuid.uuid5(NAMESPACE, filename))

            # ✅ 上传向量对象（使用固定 UUID）
            properties = {
                "name": filename,
                "summary": text[:300],
                "content": text,
                "file_type": os.path.splitext(filename)[1][1:],
                "processed_at": datetime.now().isoformat()
            }

            # ✅ 添加错误处理
            try:
                # 打印向量信息用于调试
                print(f"\n⏳ 准备上传向量数据:")
                print(f"  - 向量类型: {type(embedding)}")
                print(f"  - 向量长度: {len(embedding)}")
                print(f"  - 向量示例: [{embedding[0]:.6f}, {embedding[1]:.6f}, ...]")
                
                # 创建新对象
                result = client.data_object.create(
                    data_object=properties,
                    class_name="Candidates",
                    uuid=resume_uuid,
                    vector=embedding
                )
                
                # 验证上传结果
                print(f"\n✅ Weaviate 响应:")
                print(f"  - 状态: {'成功' if result else '失败'}")
                print(f"  - UUID: {resume_uuid}")
                success_count += 1
            except Exception as e:
                print(f"❌ 上传失败: {filename}")
                print(f"  - 错误类型: {type(e).__name__}")
                print(f"  - 错误信息: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"  - 响应状态: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                    print(f"  - 响应内容: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
                error_count += 1
                continue

        except Exception as e:
            print(f"\n❌ 处理文件 {filename} 时出错:")
            print(f"  - 错误类型: {type(e).__name__}")
            print(f"  - 错误信息: {str(e)}")
            if hasattr(e, 'response'):
                print(f"  - 响应状态: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                print(f"  - 响应内容: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
            error_count += 1

    print("\n🎉 处理完成！")
    print(f"  ✅ 成功: {success_count} 个文件")
    print(f"  ❌ 失败: {error_count} 个文件")
    print(f"  📊 成功率: {success_count/(success_count+error_count)*100:.1f}%")

# ✅ 脚本入口
if __name__ == "__main__":
    index_resumes()
