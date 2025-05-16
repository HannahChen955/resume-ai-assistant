"""
简历搜索系统 API
FastAPI 应用主入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import search, add  # ✅ 加入 add

# 创建 FastAPI 应用
app = FastAPI(
    title="简历搜索系统 API",
    description="基于向量搜索的简历匹配系统 API 接口",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(search.router, tags=["搜索"])
app.include_router(add.router, tags=["数据更新"])  # ✅ 新增数据更新接口

# 健康检查接口
@app.get("/health")
async def health_check():
    return {"status": "healthy"}