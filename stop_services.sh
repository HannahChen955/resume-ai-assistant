#!/bin/bash

set -e
cd ~/Documents/recruitment_rag_system

# ============================
# 停止 Weaviate + n8n-custom
# ============================
echo "🛑 停止 Weaviate 和 n8n-custom..."
docker compose -f compose.yaml stop weaviate n8n-custom

# ============================
# 停止 FastAPI
# ============================
echo "🛑 停止 FastAPI..."
if [ -f .fastapi.pid ]; then
  kill -9 $(cat .fastapi.pid) 2>/dev/null || true
  rm .fastapi.pid
  echo "✅ FastAPI 已关闭"
else
  echo "⚠️ FastAPI PID 文件不存在"
fi

# ============================
# 停止 MCP Upload Proxy
# ============================
echo "🛑 停止 MCP Upload Proxy..."
if [ -f .mcp_proxy.pid ]; then
  kill -9 $(cat .mcp_proxy.pid) 2>/dev/null || true
  rm .mcp_proxy.pid
  echo "✅ MCP Upload Proxy 已关闭"
else
  echo "⚠️ MCP Upload Proxy PID 文件不存在"
fi

# ============================
# 停止 Cloudflared
# ============================
echo "🛑 停止 Cloudflared..."
if [ -f .cloudflared.pid ]; then
  kill -9 $(cat .cloudflared.pid) 2>/dev/null || true
  rm .cloudflared.pid
  echo "✅ Cloudflared 已关闭"
else
  echo "⚠️ Cloudflared PID 文件不存在"
fi

echo "🧹 所有服务已干净关闭"