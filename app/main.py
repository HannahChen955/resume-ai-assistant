"""
简历搜索系统 API
FastAPI 应用主入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import search, add, upload, feishu_webhook  # ✅ 加入 feishu_webhook

# 创建 FastAPI 应用
app = FastAPI(
    title="简历搜索系统 API",
    description="基于向量搜索的简历匹配系统 API 接口",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议指定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册功能路由
app.include_router(search.router, tags=["搜索"])
app.include_router(add.router, tags=["数据更新"])
app.include_router(upload.router, tags=["上传简历"])  # ✅ 新增上传模块
app.include_router(feishu_webhook.router, tags=["飞书Bot"])  # ✅ 注册路由

# 健康检查接口
@app.get("/health")
async def health_check():
    return {"status": "healthy"}