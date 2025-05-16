from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import os
import uuid
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")

router = APIRouter()

# ========== 数据结构 ==========
class ResumeData(BaseModel):
    filename: str
    content: str
    vector: List[float]

class NoteData(BaseModel):
    filename: str
    note: str

# ========== 添加简历 ==========
@router.post("/add_resume", summary="添加新候选人")
def add_resume(data: ResumeData):
    resume_uuid = str(uuid.uuid5(uuid.UUID("12345678-1234-5678-1234-567812345678"), data.filename))
    payload = {
        "class": WEAVIATE_CLASS,
        "id": resume_uuid,
        "properties": {
            "filename": data.filename,
            "content": data.content,
            "notes": []  # 初始化为空
        },
        "vector": data.vector
    }

    url = f"{WEAVIATE_URL}/v1/objects"
    response = requests.post(url, json=payload)

    if response.status_code in [200, 201]:
        return {"status": "success", "uuid": resume_uuid}
    else:
        raise HTTPException(status_code=500, detail=response.text)

# ========== 添加沟通记录 ==========
@router.post("/add_note", summary="为候选人追加沟通记录")
def add_note(data: NoteData):
    # Step 1: 查询 Weaviate 对象
    query_url = f"{WEAVIATE_URL}/v1/graphql"
    graphql_query = {
        "query": f"""
        {{
          Get {{
            {WEAVIATE_CLASS}(where: {{path: ["filename"], operator: Equal, valueString: "{data.filename}"}}) {{
              _additional {{ id }}
              notes
            }}
          }}
        }}
        """
    }

    res = requests.post(query_url, json=graphql_query)
    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="GraphQL 查询失败")

    results = res.json()["data"]["Get"].get(WEAVIATE_CLASS, [])
    if not results:
        raise HTTPException(status_code=404, detail="未找到候选人")

    obj = results[0]
    obj_id = obj["_additional"]["id"]
    old_notes = obj.get("notes", [])

    # Step 2: 构造结构化 note
    new_note = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": data.note
    }
    updated_notes = old_notes + [new_note]

    update_url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{obj_id}"
    update_payload = {
        "properties": {
            "notes": updated_notes
        }
    }

    update_res = requests.patch(update_url, json=update_payload)

    if update_res.status_code in [200, 204]:
        return {"status": "note added", "uuid": obj_id}
    else:
        print("⚠️ PATCH 更新失败状态码:", update_res.status_code)
        print("⚠️ PATCH 响应内容:", update_res.text)
        raise HTTPException(status_code=500, detail="添加备注失败")
