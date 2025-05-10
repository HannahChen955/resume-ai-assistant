# 简历搜索系统（通义千问版本）

这是一个使用通义千问 API 进行向量化的简历搜索系统。相比 OpenAI 版本，它具有以下优势：
- 使用通义千问 API，成本更低
- 在中国大陆访问更稳定
- 支持中文场景优化

## 环境要求
- Python 3.8+
- Weaviate 数据库
- 通义千问 API Key

## 安装步骤

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量：
创建 `.env` 文件并添加以下配置：
```env
DASHSCOPE_API_KEY=your_api_key_here
WEAVIATE_URL=http://localhost:8080
RESUME_DIR=data/resumes
EXTRACTED_DIR=data/extracted
```

## 使用方法

1. 启动 Weaviate：
```bash
docker-compose up -d weaviate
```

2. 索引简历：
```bash
python -m scripts.index_resumes
```

3. 搜索简历：
```bash
# 使用 query 参数
python -m scripts.search_candidates --query "光学工程师"

# 使用 keywords 参数（兼容旧版本）
python -m scripts.search_candidates --keywords "光学工程师"

# 直接使用关键词
python -m scripts.search_candidates "光学工程师"
```

## API 服务

启动 FastAPI 服务：
```bash
uvicorn app.main:app --reload
```

API 端点：
- POST /search：搜索简历
  - 请求体：
    ```json
    {
      "query": "光学工程师",
      "top_k": 5
    }
    ```
  - 响应：
    ```json
    {
      "候选人列表": [...],
      "查询关键词": "光学工程师",
      "状态": "成功"
    }
    ```

## 注意事项
1. 确保已获取通义千问 API Key
2. 文件名格式要求：姓名_职位.pdf
3. 建议先小批量测试系统功能再大规模使用 