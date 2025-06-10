# memory.py: 会话上下文记忆模块
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# 使用 defaultdict 自动处理新用户
session_memory = defaultdict(dict)

def update_session(open_id: str, key: str, value):
    """更新用户会话中的指定键值"""
    try:
        session_memory[open_id][key] = value
        logger.debug(f"[Memory] 更新会话: {open_id} -> {key}")
    except Exception as e:
        logger.error(f"[Memory] 更新会话失败: {e}")

def get_session(open_id: str, key: str):
    """获取用户会话中的指定键值"""
    try:
        return session_memory[open_id].get(key)
    except Exception as e:
        logger.error(f"[Memory] 获取会话失败: {e}")
        return None

def get_last_candidates(user_id):
    """获取用户最近查看的候选人列表"""
    return session_memory[user_id].get("last_candidates", [])

def get_last_candidate_uuid(open_id: str):
    """获取用户最近查看的候选人 UUID"""
    try:
        candidates = get_last_candidates(open_id)
        if candidates:
            return candidates[0].get("uuid")
        return None
    except Exception as e:
        logger.error(f"[Memory] 获取候选人 UUID 失败: {e}")
        return None

def clear_session(open_id: str):
    """清除用户的所有会话数据"""
    try:
        if open_id in session_memory:
            del session_memory[open_id]
            logger.debug(f"[Memory] 清除会话: {open_id}")
    except Exception as e:
        logger.error(f"[Memory] 清除会话失败: {e}")

def store_last_candidates(user_id, candidates):
    session_memory[user_id]["last_candidates"] = candidates

def find_abnormal_names(candidates):
    # ✅ 增强关键词规则
    keywords = ["简", "推荐", "副本", "表单", "默认", "空白", "无", "待命", "unknown", "Unnamed", "个人", "示例", "测试"]
    abnormal = []
    for c in candidates:
        name = c.get("name", "").strip()
        for k in keywords:
            if k in name:
                fixed = name
                for k2 in keywords:
                    fixed = fixed.replace(k2, "")
                fixed = fixed or "待命名候选人"
                abnormal.append(f'• 姓名"{name}" 不规范，建议修改为 "{fixed}"')
                break
    return abnormal

def standardize_candidate_fields(candidates: list) -> list:
    return [
        {
            "name": c.get("name") or c.get("姓名", ""),
            "position": c.get("position") or c.get("应聘职位", ""),
            "uuid": c.get("uuid") or c.get("UUID", ""),
            "summary": c.get("summary") or c.get("简历摘要", ""),
        }
        for c in candidates
    ] 