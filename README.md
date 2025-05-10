# 简历搜索系统 API

基于 FastAPI 的简历搜索系统 API 接口，支持向量搜索和关键词匹配。

## 功能特点

- 支持向量搜索和关键词匹配的混合搜索
- 支持职位相关的关键词权重配置
- 提供 RESTful API 接口
- 支持异步处理
- 自动 API 文档

## 安装

1. 确保已安装 Python 3.8+
2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 运行

1. 启动 API 服务：

```bash
uvicorn app.main:app --reload
```

2. 访问 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 使用

### 搜索简历

**请求**：

```bash
POST /search
Content-Type: application/json

{
    "query": "光学工程师",
    "top_k": 5
}
```

**响应**：

```json
{
    "查询": "光学工程师",
    "候选人数量": 5,
    "关键词配置": {
        "必要词数量": 2,
        "加分词数量": 11
    },
    "处理时间": "0.52秒",
    "候选人列表": [...]
}
```

## 环境变量

请确保设置以下环境变量：

- `OPENAI_API_KEY`: OpenAI API 密钥
- 其他 Weaviate 相关配置（见 .env.example）

## 注意事项

1. 生产环境部署时请修改 CORS 配置
2. 建议配置适当的速率限制
3. 注意保护 API 密钥和敏感信息 