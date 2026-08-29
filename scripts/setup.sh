#!/bin/bash
# 项目初始化脚本：一键完成环境搭建

set -e

echo "=== AI 项目现场交付工具包 初始化 ==="
echo ""

# 1. 检查 Python 版本
echo "1. 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python 版本: $python_version"

# 2. 检查 Docker
echo "2. 检查 Docker..."
if command -v docker &> /dev/null; then
    echo "   Docker 已安装"
else
    echo "   ❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 3. 创建 .env
echo "3. 创建 .env..."
if [ -f .env ]; then
    echo "   .env 已存在，跳过"
else
    cp .env.example .env
    echo "   .env 已创建（从 .env.example 复制），请编辑填写 API Key"
fi

# 4. 安装依赖
echo "4. 安装 Python 依赖..."
pip install -r requirements.txt -q
echo "   依赖安装完成"

# 5. 启动基础设施
echo "5. 启动基础设施（PostgreSQL, Redis, ChromaDB）..."
docker compose up -d
echo "   基础设施已启动"

# 6. 健康检查
echo "6. 健康检查..."
sleep 5
docker compose ps

echo ""
echo "=== 初始化完成 ==="
echo "下一步："
echo "  1. 编辑 .env 文件，填写 DEEPSEEK_API_KEY"
echo "  2. 执行 'make check' 验证环境"
echo "  3. 执行 'make init-db' 初始化数据库"