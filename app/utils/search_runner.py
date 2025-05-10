"""
搜索执行器
负责调用 search_candidates.py 执行搜索
"""

import asyncio
from typing import Dict, Any
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
root_dir = str(Path(__file__).parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from scripts.config import Config
from scripts.search_candidates import ResumeSearcher

class SearchRunner:
    """搜索执行器类"""
    
    def __init__(self):
        """初始化搜索执行器"""
        self.searcher = ResumeSearcher()
    
    async def search(self, query: str, top_k: int = Config.TOP_K_RESULTS) -> Dict[str, Any]:
        """
        异步执行搜索
        
        Args:
            query: 搜索关键词
            top_k: 返回结果数量
            
        Returns:
            搜索结果字典
        """
        # 创建事件循环
        loop = asyncio.get_event_loop()
        
        try:
            # 连接数据库
            self.searcher.connect()
            
            # 在线程池中执行搜索
            results = await loop.run_in_executor(
                None,
                self.searcher.search,
                query
            )
            
            # 限制返回结果数量
            if results and "候选人列表" in results:
                results["候选人列表"] = results["候选人列表"][:top_k]
                results["候选人数量"] = len(results["候选人列表"])
            
            return results
            
        finally:
            # 确保关闭连接
            self.searcher.disconnect() 