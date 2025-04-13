import weaviate

client = weaviate.Client("http://weaviate:8080")

schema = {
    "class": "Candidates",
    "description": "候选人简历信息", 
    "vectorizer": "none",  # ✅ 禁用自动向量化
    "vectorIndexConfig": {
        "skip": False,      # ✅ 强制启用手动向量上传
        "distance": "cosine"
    },
    "properties": [
        {"name": "name", "dataType": ["text"]},
        {"name": "summary", "dataType": ["text"]},
        {"name": "content", "dataType": ["text"]},
        {"name": "file_type", "dataType": ["text"]},
        {"name": "processed_at", "dataType": ["text"]}
    ]
}

client.schema.create_class(schema)
print("✅ Candidates class 创建成功（手动向量模式）")