# ✨ 用 GPT-4o 清洗简历摘要
import os
import logging
import re
import asyncio
from openai import OpenAI
from typing import Optional

# ✅ 常量配置
MAX_TEXT_LENGTH = 1500  # 防止 prompt 太长
MAX_SUMMARY_POINTS = 5  # 最多展示的摘要条数
GPT_MODEL = "gpt-4o"

# ✅ 初始化
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logger = logging.getLogger(__name__)

def is_structured(text: str) -> bool:
    """判断文本是否为结构化格式，需要清洗"""
    if not text:
        return True
    text = text.strip()
    return (
        text.startswith("{") or
        "字段信息" in text or
        "===" in text or
        "【字段信息】" in text or
        "【模块结构分类】" in text
    )

def clean_raw_text(text: str) -> str:
    """清理原始文本，移除特殊标记"""
    if not text:
        return ""
    text = text.strip()
    # 移除特殊标记
    text = text.replace("【字段信息】", "")
    text = text.replace("【模块结构分类】", "")
    text = text.replace("【原文补充】", "")
    # 限制长度
    return text[:MAX_TEXT_LENGTH]

# ✅ 异步格式化候选人信息（适配 GPT 清洗）
async def format_candidates(candidates):
    if not candidates:
        logger.warning("[format_candidates] 候选人列表为空")
        return "未找到匹配的候选人。"
    
    seen_uuids = set()
    unique_candidates = []
    for c in candidates:
        if isinstance(c, str):
            continue
        uuid = c.get("uuid") or c.get("UUID") or "无UUID"
        if uuid not in seen_uuids:
            seen_uuids.add(uuid)
            unique_candidates.append(c)

    lines = []
    for idx, c in enumerate(unique_candidates[:MAX_SUMMARY_POINTS], 1):
        name = c.get("name") or c.get("姓名") or "未知"
        position = c.get("position") or c.get("应聘职位") or "未知职位"
        score = c.get("score") or c.get("匹配度") or "0.0"
        try:
            score_str = f"{float(score):.1f}%"
        except:
            score_str = str(score)

        # ✅ 调用 GPT 清洗摘要
        summary_raw = c.get("summary") or c.get("简历摘要") or ""
        if is_structured(summary_raw):
            summary_raw = c.get("content", "").strip()
            summary_raw = clean_raw_text(summary_raw)

        try:
            summary_clean = await clean_summary_with_gpt(summary_raw)
        except Exception as e:
            logger.warning(f"[format_candidates] 调用 GPT 清洗失败: {e}")
            summary_clean = summary_raw
            
        summary_points = [s.strip() for s in re.split(r"[。；;\n]", summary_clean) if s.strip()]
        summary_points = summary_points[:MAX_SUMMARY_POINTS]
        summary_bullets = "\n".join([f"• {s}" for s in summary_points]) if summary_points else "• 无摘要"

        notes = c.get("notes", [])
        note_str = notes[-1] if notes else "暂无沟通记录"

        lines.append(
            f"{idx}. 姓名：{name}  \n"
            f"应聘职位：{position}  \n"
            f"匹配度：{score_str}  \n"
            f"UUID：{uuid}  \n"
            f"简历摘要：\n{summary_bullets}\n"
            f"备注：{note_str}\n"
        )

    return "\n".join(lines)

# ✅ 用 GPT-4o 清洗简历摘要
async def clean_summary_with_gpt(text: str) -> str:
    """使用 GPT 清洗简历摘要，返回格式化的要点"""
    if not text:
        return "无简历内容"
        
    try:
        prompt = (
            "以下是一段简历内容，请将其精简为 3-5 条 bullet point，总结候选人的核心经历和能力，语言保持简洁专业：\n\n"
            f"{text.strip()}\n\n"
            "请直接输出 bullet point 格式，每条以 • 开头。"
        )
        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "你是一个专业的招聘助手，擅长提炼候选人简历内容为要点摘要。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        try:
            content = response.choices[0].message.content.strip()
            logger.debug(f"[GPT清洗后摘要] {content}")
            if content:
                return content
        except Exception as e:
            logger.warning(f"[GPT返回格式异常] {e}")
    except Exception as e:
        logger.warning(f"[GPT清洗失败] {e}")
    return text  # fallback

# ✅ 测试入口
if __name__ == "__main__":
    async def test_clean_summary():
        sample = """张三，男，28岁，本科毕业于北京大学计算机系。
        工作经历：
        1. 2020-2022 字节跳动 高级算法工程师
        - 负责推荐系统核心算法优化
        - 主导了多个A/B测试项目
        2. 2018-2020 百度 算法工程师
        - 参与搜索排序算法开发
        - 优化了搜索性能提升30%
        技能：Python, TensorFlow, 推荐系统, 机器学习"""
        
        print("测试 GPT 清洗摘要:")
        result = await clean_summary_with_gpt(sample)
        print("\n清洗结果:")
        print(result)
        
        print("\n测试完整格式化:")
        candidates = [{
            "name": "张三",
            "position": "算法工程师",
            "score": "95.5",
            "summary": sample,
            "notes": ["电话沟通了，很合适"]
        }]
        result = await format_candidates(candidates)
        print("\n格式化结果:")
        print(result)

    # 运行测试
    asyncio.run(test_clean_summary())