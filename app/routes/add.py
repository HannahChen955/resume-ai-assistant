from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
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
    uuid: str
    note: str

class UpdateResumeData(BaseModel):
    uuid: str
    new_content: str
    filename: Optional[str] = None

# ========== 添加沟通记录（供 GPT 插件调用） ==========
@router.post("/add_note", summary="为候选人追加沟通记录")
def add_note(data: NoteData):
    success = add_note_by_uuid(data.uuid, data.note)
    if success:
        return {"status": "note added", "uuid": data.uuid}
    else:
        raise HTTPException(status_code=500, detail="添加备注失败")

# ========== 更新简历内容（保留沟通记录） ==========
@router.patch("/update_resume_content", summary="更新简历内容（保留原有沟通记录）")
def update_resume_content(data: UpdateResumeData):
    get_url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{data.uuid}"
    res = requests.get(get_url)

    if res.status_code != 200:
        raise HTTPException(status_code=404, detail="未找到候选人")

    obj = res.json()
    props = obj.get("properties", {})
    old_notes = props.get("notes", [])
    if not isinstance(old_notes, list):
        old_notes = []

    update_payload = {
        "properties": {
            "content": data.new_content,
            "notes": old_notes
        }
    }

    if data.filename:
        update_payload["properties"]["filename"] = data.filename

    update_url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{data.uuid}"
    update_res = requests.patch(update_url, json=update_payload)

    if update_res.status_code in [200, 204]:
        return {"status": "resume updated", "uuid": data.uuid}
    else:
        raise HTTPException(status_code=500, detail=f"更新失败: {update_res.text}")

# ========== 新增：供飞书机器人/本地使用的添加笔记函数 ==========
def add_note_by_uuid(uuid: str, note: str) -> bool:
    try:
        get_url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{uuid}"
        res = requests.get(get_url)
        if res.status_code != 200:
            print(f"[❌] 未找到候选人 {uuid}")
            return False

        obj = res.json()
        props = obj.get("properties", {})
        old_notes = props.get("notes", [])
        if not isinstance(old_notes, list):
            old_notes = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_note = f"{timestamp} - {note}"
        updated_notes = old_notes + [new_note]

        update_url = f"{WEAVIATE_URL}/v1/objects/{WEAVIATE_CLASS}/{uuid}"
        update_payload = {
            "properties": {
                "notes": updated_notes
            }
        }

        update_res = requests.patch(update_url, json=update_payload)
        if update_res.status_code in [200, 204]:
            print(f"[✅] 已成功添加沟通记录: {uuid}")
            return True
        else:
            print(f"[❌] 添加失败: {update_res.text}")
            return False
    except Exception as e:
        print(f"[❌] 异常: {e}")
        return False
