"""
搜索路由模块
处理简历搜索相关的 API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.utils.search_runner import SearchRunner

router = APIRouter()

class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词，如'光学工程师'")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")

@router.post("/search", summary="搜索简历")
async def search_resumes(request: SearchRequest):
    """
    搜索简历接口
    - query: 搜索关键词（如"光学工程师"）
    - top_k: 返回前 top_k 个候选人
    """
    try:
        print(f"搜索关键词: {request.query}")
        search_runner = SearchRunner()
        results = await search_runner.search(request.query, request.top_k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")