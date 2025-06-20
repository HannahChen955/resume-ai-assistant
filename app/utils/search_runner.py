"""
搜索执行器
负责调用 search_candidates.py 执行搜索
"""

import asyncio
import os
import sys
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
root_dir = str(Path(__file__).parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# ✅ 加载 .env
load_dotenv()

from scripts.search_candidates import ResumeSearcher

# ✅ 环境变量配置
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
WEAVIATE_CLASS = os.getenv("WEAVIATE_COLLECTION", "Candidates")
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))

class SearchRunner:
    """搜索执行器类"""

    def __init__(self):
        self.searcher = ResumeSearcher()

    async def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()

        # 在后台线程中运行搜索（非阻塞主线程）
        results = await loop.run_in_executor(
            None,
            self.searcher.search,
            query
        )

        # 截断候选人列表（最多返回 top_k 个）
        if results and "候选人列表" in results:
            results["候选人列表"] = results["候选人列表"][:top_k]
            results["候选人数量"] = len(results["候选人列表"])

        return results