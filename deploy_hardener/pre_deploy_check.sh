#!/bin/bash
# 部署前环境变量检查脚本

echo "=== 环境变量检查 ==="

REQUIRED_VARS=(
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "POSTGRES_DB"
    "POSTGRES_HOST"
    "POSTGRES_PORT"
    "REDIS_URL"
    "CHROMA_HOST"
    "CHROMA_PORT"
)

OPTIONAL_VARS=(
    "DEEPSEEK_API_KEY"
    "DEEPSEEK_BASE_URL"
    "DEFAULT_MODEL"
    "LOG_LEVEL"
)

MISSING=()
WARNINGS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING+=("$var")
    fi
done

for var in "${OPTIONAL_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        WARNINGS+=("$var")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "❌ 缺少必需环境变量："
    for var in "${MISSING[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "请在 .env 或环境变量中设置以上变量后重试。"
    exit 1
fi

if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo "⚠️ 缺少可选环境变量："
    for var in "${WARNINGS[@]}"; do
        echo "   - $var（使用默认值）"
    done
fi

echo "✅ 必需环境变量检查通过"
exit 0