# app/routes/feishu_webhook.py

import os
import re
import json
import logging
import requests
from fastapi import APIRouter, Request
from dotenv import load_dotenv
from app.routes.search_async import search_candidates_async
from app.routes.add import add_note_by_uuid

router = APIRouter()
logger = logging.getLogger(__name__)

# ✅ 强制使用 GPT-4o 模型
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = "gpt-4o"

# ✅ 固定提示词（模仿插件人设）
DEFAULT_ASSISTANT_PROMPT = (
    "你是一个招聘知识库助手。\n"
    "当用户输入职位关键词（如'光学工程师', '算法实习'）时，\n"
    "你会调用本地简历数据库搜索匹配的候选人。\n"
    "请将候选人的'姓名, 应聘职位, 匹配度, 简历摘要'用清晰的格式展示给用户。\n"
    "每次回复请合并为一条消息，最多展示5个候选人。"
)

# ✅ 获取 tenant_access_token
def get_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    payload = {
        "app_id": os.getenv("FEISHU_APP_ID"),
        "app_secret": os.getenv("FEISHU_APP_SECRET"),
    }
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json().get("tenant_access_token")

# ✅ 发送消息给用户
def reply_message(open_id: str, text: str):
    url = "https://open.feishu.cn/open-apis/message/v4/send/"
    headers = {
        "Authorization": f"Bearer {get_tenant_token()}",
        "Content-Type": "application/json",
    }
    data = {
        "open_id": open_id,
        "msg_type": "text",
        "content": {
            "text": text
        }
    }
    resp = requests.post(url, headers=headers, json=data)
    logger.info(f"📡 飞书消息投递响应: {resp.status_code} {resp.text}")

# ✅ 格式化候选人信息为单条消息（精简风格，兼容中英文字段名）
def format_candidates(candidates):
    seen_uuids = set()
    unique_candidates = []
    for c in candidates:
        uuid = c.get("uuid") or c.get("UUID") or "无UUID"
        if uuid not in seen_uuids:
            seen_uuids.add(uuid)
            unique_candidates.append(c)

    lines = []
    for idx, c in enumerate(unique_candidates[:5], 1):
        name = c.get("name") or c.get("姓名") or "未知"
        position = c.get("position") or c.get("应聘职位") or "未知职位"
        score = c.get("score") or c.get("匹配度") or "0.00"
        try:
            score_str = f"{float(score):.1f}%"
        except:
            score_str = str(score)
        summary = c.get("summary") or c.get("简历摘要") or "无摘要"

        lines.append(
            f"{idx}. 姓名：{name}  \n"
            f"应聘职位：{position}  \n"
            f"匹配度：{score_str}  \n"
            f"简历摘要：{summary}\n"
        )
    return "\n".join(lines)

# ✅ webhook 路由
@router.post("/feishu/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    logger.info(f"📨 webhook 收到原始请求体: {json.dumps(body, ensure_ascii=False)}")

    try:
        # ✅ Feishu schema v2 兼容逻辑
        event_type = body.get("header", {}).get("event_type", "")
        if event_type == "im.message.receive_v1":
            print("📥 进入 Feishu 消息事件分支")

            event = body.get("event", {})
            message = event.get("message", {})
            content = json.loads(message.get("content", "{}"))
            content_str = content.get("text", "")
            sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "未知用户")

            print(f"📨 content_str: {content_str}")
            print(f"📥 sender_id: {sender_id}")

            # ✅ 判断是否是添加沟通记录请求（UUID + 备注）
            match = re.search(r"([a-f0-9\-]{36})[\s\n\r：:]+(.+)", content_str)
            if match:
                uuid = match.group(1)
                note = match.group(2).strip()
                logger.info(f"📝 识别到 UUID + note 模式，添加沟通记录: {uuid} -> {note}")
                result = add_note_by_uuid(uuid, note)
                reply_message(sender_id, result)
            else:
                # ✅ 只发一次消息：搜索结果或失败提示
                logger.info(f"⚙️ 调用 resume_searcher.search: {content_str}")
                results = await search_candidates_async(content_str, top_k=5)
                candidates = results.get("候选人列表", [])
                logger.info(f"【DEBUG】format_candidates收到的candidates: {candidates}")
                has_valid_result = candidates and any(
                    (c.get("name") or c.get("姓名")) not in [None, "", "未知"] and
                    (c.get("uuid") or c.get("UUID")) not in [None, "", "无UUID"]
                    for c in candidates
                )
                if has_valid_result:
                    reply_text = format_candidates(candidates)
                else:
                    reply_text = "❌ 没有找到匹配的候选人，请尝试其他关键词～"
                reply_message(sender_id, reply_text)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ webhook 处理失败: {e}")
        return {"status": "error", "reason": str(e)}