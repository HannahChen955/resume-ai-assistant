"""
搜索路由模块
处理简历搜索相关的 API 路由
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.utils.search_runner import SearchRunner

router = APIRouter()

class SearchRequest(BaseModel):
    """搜索请求模型"""
    query: Optional[str] = Field(None, description="搜索关键词，如'光学工程师'")
    keywords: Optional[str] = Field(None, description="搜索关键词（兼容旧版本）")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="返回结果数量")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "光学工程师",
                "top_k": 5
            }
        }

@router.post("/search", summary="搜索简历")
async def search_resumes(request: SearchRequest):
    """
    搜索简历接口
    
    - **query**: 搜索关键词，如"光学工程师"（优先使用）
    - **keywords**: 搜索关键词（兼容旧版本）
    - **top_k**: 返回结果数量，默认为5
    
    返回匹配度最高的简历列表
    """
    try:
        # 获取搜索关键词
        search_keywords = request.query or request.keywords
        if not search_keywords:
            raise HTTPException(
                status_code=400,
                detail="缺少搜索关键词，请提供 'query' 或 'keywords' 字段"
            )
            
        print(f"搜索关键词: {search_keywords}")  # 打印搜索关键词
        
        search_runner = SearchRunner()
        results = await search_runner.search(search_keywords, request.top_k)
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"搜索失败: {str(e)}"
        ) 