#!/bin/bash

# 自动加载 .env 中的环境变量（忽略注释行）
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  echo "✅ 环境变量已成功加载。"
else
  echo "❌ 未找到 .env 文件。请确保你在项目根目录下运行此脚本。"
fi
