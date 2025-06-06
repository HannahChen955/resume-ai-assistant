#!/bin/bash

set -e
cd ~/Documents/recruitment_rag_system

# ============================
# 启动 Weaviate
# ============================
echo "🔹 启动 Weaviate..."
docker compose -f compose.yaml up -d weaviate

# ============================
# 启动 n8n 自定义服务
# ============================
echo "🔹 启动 n8n-custom..."
docker compose -f compose.yaml up -d n8n-custom

# ============================
# 启动 FastAPI 简历搜索服务
# ============================
echo "🔹 启动 FastAPI 简历搜索服务 (port 8001)..."
mkdir -p logs

# ✅ 清理旧 FastAPI 进程
if [ -f .fastapi.pid ]; then
  kill $(cat .fastapi.pid) 2>/dev/null || true
  rm .fastapi.pid
fi

# ✅ 启动 FastAPI 后台服务
nohup uvicorn app.main:app --host 0.0.0.0 --port 8001 > logs/fastapi.log 2>&1 &
echo $! > .fastapi.pid

# ✅ 健康检查等待 FastAPI 启动
echo -n "⏳ 正在等待 FastAPI 启动"
for i in {1..10}; do
  sleep 1
  if curl -s http://localhost:8001/health | grep -q "healthy"; then
    echo -e "\n✅ FastAPI 启动成功"
    break
  fi
  echo -n "."
done

if ! curl -s http://localhost:8001/health | grep -q "healthy"; then
  echo -e "\n❌ FastAPI 启动失败，请检查 logs/fastapi.log"
fi

# ============================
# 启动 MCP Upload Proxy 服务（port 8010）
# ============================
echo "🔹 启动 MCP Upload Proxy（port 8010）..."

# ✅ 清理旧 proxy 进程
if [ -f .mcp_proxy.pid ]; then
  kill $(cat .mcp_proxy.pid) 2>/dev/null || true
  rm .mcp_proxy.pid
fi

# ✅ 启动 MCP proxy 后台服务（假设脚本放在 scripts/mcp_upload_proxy.py）
nohup uvicorn app.routes.mcp_upload_proxy:app --host 0.0.0.0 --port 8010 > logs/mcp_proxy.log 2>&1 &
echo $! > .mcp_proxy.pid

sleep 1
echo "✅ MCP Upload Proxy 启动完成（日志见 logs/mcp_proxy.log）"

# ============================
# 启动 Cloudflared Tunnel
# ============================
echo "🔹 启动 Cloudflared Tunnel..."
TUNNEL_NAME="resume-tunnel"
CONFIG_PATH="$HOME/.cloudflared/config.yml"

if [ -f .cloudflared.pid ]; then
  kill $(cat .cloudflared.pid) 2>/dev/null || true
  rm .cloudflared.pid
fi

cloudflared tunnel --config "$CONFIG_PATH" run "$TUNNEL_NAME" > logs/cloudflared.log 2>&1 &
echo $! > .cloudflared.pid
echo "✅ Cloudflared 启动完成（使用 config.yml + tunnel name）"