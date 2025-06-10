# app/routes/feishu_webhook.py

import os
import re
import json
import logging
import requests
import threading
import httpx
from fastapi import APIRouter, Request
from dotenv import load_dotenv
from app.routes.search_async import search_candidates_async
from app.routes.add import add_note_by_uuid
from app.routes.feishu_gpt_tools import clean_summary_with_gpt, format_candidates
from app.utils.memory import (
    update_session,
    get_last_candidates,
    get_last_candidate_uuid,
    get_session,
    store_last_candidates,
    find_abnormal_names,
    standardize_candidate_fields
)
from openai import OpenAI

# ✅ 加载环境变量（确保在最顶部）
load_dotenv()

# ✅ 标准使用指南
GPT_USAGE_GUIDE = (
    "你好，我是招聘智能助手 😊\n"
    "📌 可用命令：\n"
    "- 搜索候选人：`#search 职位关键词`\n"
    "- 添加沟通记录：`#add_note UUID:备注内容`\n"
    "如有其他问题，欢迎直接提问～"
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Add debug log to verify we're using the async version
logger.info(f"[DEBUG] format_candidates 来自: {format_candidates.__module__}, 类型: {format_candidates}")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = "gpt-4o"

# 每个 open_id 映射到最近查看的候选人 UUID
recent_search_context = {}
# 每个 open_id 映射到最近查看的完整候选人列表
recent_candidates_cache = {}

FEISHU_REPLY_URL = "https://open.feishu.cn/open-apis/im/v1/messages"

processed_message_ids = set()
lock = threading.Lock()

def get_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    payload = {
        "app_id": os.getenv("FEISHU_APP_ID"),
        "app_secret": os.getenv("FEISHU_APP_SECRET"),
    }
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json().get("tenant_access_token")

@router.post("/feishu/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    logger.info(f"📨 webhook 收到原始请求体: {json.dumps(body, ensure_ascii=False)}")
    try:
        event_type = body.get("header", {}).get("event_type", "")
        if event_type == "im.message.receive_v1":
            event = body.get("event", {})
            message = event.get("message", {})
            message_id = message.get("message_id")
            with lock:
                if message_id in processed_message_ids:
                    logger.info(f"[⏭ Feishu] 已忽略重复消息: {message_id}")
                    return {"msg": "Duplicate message ignored."}
                processed_message_ids.add(message_id)
            content = json.loads(message.get("content", "{}"))
            content_str = content.get("text", "")
            sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "未知用户")

            logger.info(f"📨 content_str: {content_str}")

            # ✅ 记录用户消息到会话
            update_session(sender_id, "last_user_message", content_str)

            # ✅ 快速帮助提示
            if content_str.strip().lower() in ["help", "说明", "命令", "怎么用", "帮助"]:
                await reply_feishu(sender_id, GPT_USAGE_GUIDE)
                return {"status": "ok"}

            # 1. 处理 #search 命令
            if content_str.strip().lower().startswith("#search"):
                keyword = content_str.strip()[7:].strip()
                if not keyword:
                    await reply_feishu(sender_id, "请输入搜索关键词，例如：#search 算法工程师")
                    return {"status": "ok"}
                
                # ✅ 记录搜索关键词
                update_session(sender_id, "last_search_query", keyword)
                
                results = await search_candidates_async(keyword, top_k=5)
                logger.info(f"[DEBUG] search_candidates_async 返回类型: {type(results)}")
                logger.info(f"[DEBUG] search_candidates_async 返回值预览: {str(results)[:500]}")
                
                if isinstance(results, dict) and '候选人列表' in results:
                    results = results['候选人列表']
                elif isinstance(results, str):
                    logger.warning(f"[WARNING] 搜索返回字符串，直接回复给用户：{results}")
                    await reply_feishu(sender_id, results)
                    return {"status": "ok"}
                elif not isinstance(results, list):
                    logger.error(f"[ERROR] 搜索结果格式非法，results 类型: {type(results)}")
                    await reply_feishu(sender_id, "搜索结果格式错误，无法展示候选人。请联系管理员或稍后重试。")
                    return {"status": "error", "reason": "invalid result type"}

                # ✅ 清洗字段
                results = standardize_candidate_fields(results)

                if results:
                    # ✅ 使用新的内存管理模块存储候选人列表
                    store_last_candidates(sender_id, results)
                    reply_text = await format_candidates(results)
                else:
                    reply_text = "没有找到匹配的候选人，请试试其他关键词～"

                logger.info(f"[DEFENSE] #search reply_text type: {type(reply_text)}, value: {reply_text}")
                assert isinstance(reply_text, str), f"reply_text is not str: {type(reply_text)}"
                await reply_feishu(sender_id, reply_text)
                return {"status": "ok"}

            # 2. 处理 #add_note 命令
            if content_str.strip().lower().startswith("#add_note"):
                # 尝试从消息中提取 UUID 和备注
                match = re.search(r"([a-f0-9\-]{36})[\s\n\r:：]+(.+)", content_str)
                if match:
                    uuid = match.group(1)
                    note = match.group(2).strip()
                else:
                    # 如果没有明确 UUID，尝试从会话记忆中获取
                    uuid = get_last_candidate_uuid(sender_id)
                    if uuid:
                        logger.info(f"[上下文补全] 使用最近候选人 UUID: {uuid}")
                        note = content_str.strip()[9:].strip()  # 去掉 #add_note 前缀
                    else:
                        await reply_feishu(sender_id, "请提供候选人 UUID 和备注内容，格式：#add_note UUID:备注内容\n或者先搜索候选人，再添加备注。")
                        return {"status": "ok"}

                logger.info(f"[📝 Feishu] 添加备注: {uuid} -> {note}")
                result = add_note_by_uuid(uuid, note)
                logger.info(f"[DEFENSE] #add_note result type: {type(result)}, value: {result}")
                assert isinstance(result, str), f"result is not str: {type(result)}"
                await reply_feishu(sender_id, result)
                return {"status": "ok"}

            # 3. 其他所有消息交给 GPT 处理
            logger.info(f"🤖 GPT 处理自然语言请求: {content_str}")
            
            # 准备最近候选人上下文（若有）
            recent_result_text = None
            candidates = get_last_candidates(sender_id)
            if candidates:
                recent_result_text = f"最近你查看的候选人 UUID 是 {get_last_candidate_uuid(sender_id)}，如需进一步操作可以告诉我～"

            reply_text = await handle_gpt_fusion_intent(content_str, sender_id, previous_results=recent_result_text)
            logger.info(f"[DEFENSE] GPT reply_text type: {type(reply_text)}, value: {reply_text}")
            assert isinstance(reply_text, str), f"reply_text is not str: {type(reply_text)}"
            await reply_feishu(sender_id, reply_text)

        return {"status": "ok"}

    except Exception as e:
        import traceback
        logger.error("❌ webhook 处理失败:\n" + traceback.format_exc())
        return {"status": "error", "reason": str(e)}

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def handle_gpt_fusion_intent(text: str, sender_id: str = None, previous_results: str = None) -> str:
    system_prompt = """
你是一个自然亲切的招聘助手，正在飞书中与用户进行自然语言对话。你理解人类语言，能提供专业的招聘建议，并擅长发现和修正数据问题。

你的核心能力包括：

---
📝 命令引导：
1. 当用户想要搜索候选人时，引导使用 #search 命令
2. 当用户想要添加备注时，引导使用 #add_note 命令
3. 对于其他需求，直接提供帮助和建议

---
🔍 字段检查能力：
1. 自动识别异常姓名：
   - 检查是否包含"简"、"推荐"、"副本"、"表单"、"默认"、"空白"等关键词
   - 识别非人名格式（如"个人推荐"、"默认候选人"等）
   - 发现重复或冗余信息（如"张三简"、"李四副本"等）

2. 提供修正建议：
   - 使用 bullet 风格列出所有异常项
   - 为每个异常项提供具体的修正建议
   - 示例：
     • "吕冬冬简" → "吕冬冬"
     • "个人推荐" → "待命名候选人"
     • "张三副本" → "张三"

---
💡 交互风格：
1. 保持对话自然、亲切
2. 使用 emoji 增加亲和力
3. 主动提供下一步建议
4. 在用户困惑时提供命令示例

---
🤖 标准开场白（首次触发）：
你好，我是招聘智能助手 😊  
若要搜索候选人，请使用命令：`#search 职位关键词`  
若要添加备注，请使用命令：`#add_note UUID:备注内容`

---
🎯 回复要求：
1. 结构清晰：每条建议用 • 开头
2. 语言自然：像真正的招聘同事一样交流
3. 主动关怀：在发现异常时，主动询问是否需要帮助修复
4. 结尾互动：以"是否需要我为这些候选人加上备注？或者帮你一起修复？"等互动性问题结束

---
📚 Few-shot 示例：

1. 自动关联最近候选人：
用户: "给这个候选人加个备注：电话沟通了，很合适"
助手: "好的，我注意到你最近查看过候选人，我会自动关联到最近查看的候选人。
已添加备注：电话沟通了，很合适
需要我帮你做其他事情吗？"

2. 字段修正建议：
用户: "这个候选人的名字看起来不太对"
助手: "我检查了最近查看的候选人列表，发现以下需要修正的姓名：
• "张三简" → "张三"
• "李四副本" → "李四"
需要我帮你修正这些信息吗？"

3. 搜索建议：
用户: "帮我找算法工程师"
助手: "好的，我来帮你搜索算法工程师。
请使用命令：`#search 算法工程师`
这样我可以为你找到最匹配的候选人～"
"""
    try:
        messages = [{"role": "system", "content": system_prompt}]

        # 注入候选人上下文
        candidates = get_last_candidates(sender_id)
        if candidates:
            candidates_table = "\n".join([
                "| 姓名 | 职位 | UUID |",
                "|------|------|------|",
            ] + [
                f"| {c.get('name', '未知')} | {c.get('position', '未知')} | {c.get('uuid', '未知')} |"
                for c in candidates
            ])
            abnormal_bullets = find_abnormal_names(candidates)
            abnormal_text = "\n".join(abnormal_bullets) if abnormal_bullets else "全部规范"

            messages.append({
                "role": "user",
                "content": (
                    f"以下是我最近搜索到的候选人列表，请帮我检查姓名字段是否规范：\n"
                    f"{candidates_table}\n\n"
                    f"后端初步检测结果如下：\n{abnormal_text}\n\n"
                    f"现在我的输入是：{text}\n"
                    f"请结合候选人列表和我的输入内容，判断是否需要修正姓名，并以 bullet 格式输出。"
                )
            })
        else:
            messages.append({"role": "user", "content": text})

        response = openai_client.chat.completions.create(
            model=GPT_MODEL,
            messages=messages,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"❌ GPT融合处理失败: {e}")
        return GPT_USAGE_GUIDE  # fallback

async def reply_feishu(open_id: str, content: str):
    token = get_tenant_token()  # ✅ 改为每次动态获取 tenant_access_token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    body = {
        "receive_id": open_id,
        "content": json.dumps({"text": content}),
        "msg_type": "text",
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{FEISHU_REPLY_URL}?receive_id_type=open_id",
                headers=headers,
                json=body,
                timeout=10,
            )
    except Exception as e:
        logger.error(f"[❌ Feishu 回复失败] {e}")