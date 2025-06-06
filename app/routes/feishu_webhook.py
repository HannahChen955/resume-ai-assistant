# app/routes/feishu_webhook.py

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os
import logging
import json
import re
import requests
from dotenv import load_dotenv
from openai import OpenAI
from scripts.search_candidates import ResumeSearcher
from app.routes.add import add_note_by_uuid

load_dotenv()

router = APIRouter()

# ✅ 初始化 OpenAI 和模型配置
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")

# ✅ 初始化 ResumeSearcher
resume_searcher = ResumeSearcher(
    weaviate_url=os.getenv("WEAVIATE_URL", "http://localhost:8080"),
    weaviate_class=os.getenv("WEAVIATE_COLLECTION", "Candidates"),
    openai_client=openai_client,
    embedding_model=embedding_model
)

# ✅ 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")


def get_access_token():
    resp = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    })
    return resp.json().get("tenant_access_token", "")


def reply(text: str, user_id: str):
    print(f"📤 正在给 {user_id} 回复: {text}")
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "receive_id": user_id,
        "content": json.dumps({"text": text}),
        "msg_type": "text"
    }
    r = requests.post(
        url="https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers=headers,
        json=body
    )
    logging.info(f"[📤 回复飞书用户] 状态: {r.status_code} | 内容: {r.text}")
    return JSONResponse(content={"text": text})


@router.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    body = await request.json()

    # 校验 URL
    if body.get("type") == "url_verification":
        return JSONResponse(content={"challenge": body.get("challenge")})

    if body.get("type") == "event_callback":
        event = body.get("event", {})
        content_str = event.get("message", {}).get("content", "")
        sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "未知用户")

        print(f"📥 content_str: {content_str}")
        print(f"📥 sender_id: {sender_id}")

        try:
            content = json.loads(content_str).get("text", "")
        except Exception:
            content = content_str

        # 判断是否是 UUID + 备注格式（用于添加沟通记录）
        uuid_match = re.search(r"([a-fA-F0-9\-]{36})", content)
        note_match = re.search(r"[:：](.+)$", content)

        if uuid_match and note_match:
            uuid = uuid_match.group(1)
            note = note_match.group(1).strip()
            success = add_note_by_uuid(uuid, note)
            if success:
                return reply(f"✅ 已为候选人 {uuid[:6]} 添加沟通记录：{note}", sender_id)
            else:
                return reply(f"❌ 添加沟通记录失败（可能 UUID 不存在）", sender_id)

        # 默认走搜索逻辑
        try:
            result = resume_searcher.search(content)
            candidates = result.get("候选人列表", [])

            if not candidates:
                return reply("❌ 未找到匹配候选人。", sender_id)

            lines = ["🎯 匹配候选人："]
            for idx, candidate in enumerate(candidates[:3]):
                name = candidate.get("姓名", "未知")
                position = candidate.get("应聘职位", "")
                uuid = candidate.get("UUID", "")
                notes = candidate.get("沟通记录", [])
                notes_str = " / ".join(notes[-2:]) if notes else "暂无沟通记录"
                lines.append(f"{idx + 1}. {name}（{position}）\nUUID: {uuid}\n备注: {notes_str}\n")

            return reply("\n".join(lines), sender_id)

        except Exception as e:
            logging.exception("❌ 查询失败")
            return reply(f"⚠️ 查询失败：{str(e)}", sender_id)

    return {"code": 0}