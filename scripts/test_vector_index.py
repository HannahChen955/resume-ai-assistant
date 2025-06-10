#!/usr/bin/env python3

import json
import requests
from dashscope import TextEmbedding

# ✅ 用你写死的 DashScope Key
embedding_model = "text-embedding-v1"
dashscope_api_key = "sk-1d92a7280052451c84509f57e1b44991"
test_text = "吕冬冬 男 29 岁 本科 AI工程师 深圳"

# ✅ 获取向量
def get_embedding(text):
    import dashscope
    dashscope.api_key = dashscope_api_key
    resp = TextEmbedding.call(model=embedding_model, input=text)
    return resp.output["embeddings"][0]["embedding"]

# ✅ 发 GraphQL 查询
def search_with_vector(vector):
    graphql_query = {
        "query": f"""
        {{
          Get {{
            Candidates(
              nearVector: {{
                vector: {json.dumps(vector)}
              }},
              limit: 5
            ) {{
              filename
              _additional {{
                id
                distance
              }}
            }}
          }}
        }}
        """
    }
    res = requests.post("http://localhost:8080/v1/graphql", json=graphql_query)
    return res.json()

if __name__ == "__main__":
    vector = get_embedding(test_text)
    print("✅ 向量长度:", len(vector))
    result = search_with_vector(vector)
    print(json.dumps(result, indent=2, ensure_ascii=False))