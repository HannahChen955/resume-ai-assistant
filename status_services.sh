#!/bin/bash

cd ~/Documents/recruitment_rag_system || exit 1

echo "🔍 检查 Weaviate 容器状态..."
docker compose -f compose.yaml ps weaviate

echo ""
echo "🔍 检查 n8n-custom 容器状态..."
docker compose -f compose.yaml ps n8n-custom

echo ""
echo "🔍 检查 FastAPI 服务 (端口 8001)..."
FASTAPI_PID=$(lsof -ti:8001)
if [ -n "$FASTAPI_PID" ]; then
    echo "✅ FastAPI 正在运行 (PID: $FASTAPI_PID)"
else
    echo "❌ FastAPI 未运行"
fi

echo ""
echo "🔍 检查 Cloudflared Tunnel..."
if [ -f .cloudflared.pid ]; then
    CF_PID=$(cat .cloudflared.pid)
    if ps -p $CF_PID > /dev/null; then
        echo "✅ Cloudflared 正在运行 (PID: $CF_PID)"
    else
        echo "⚠️ Cloudflared PID 文件存在，但进程未运行"
    fi
else
    echo "❌ Cloudflared 未运行"
fi