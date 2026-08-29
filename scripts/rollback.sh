#!/bin/bash
# 回滚脚本：快速回滚到上一个稳定版本

set -e

IMAGE_NAME="toolkit-app"
PREV_VERSION_FILE=".release_prev_version"

if [ ! -f "${PREV_VERSION_FILE}" ]; then
    echo "❌ 找不到回滚版本文件 ${PREV_VERSION_FILE}"
    exit 1
fi

PREV_VERSION=$(cat "${PREV_VERSION_FILE}")
CURRENT_VERSION="${1:-unknown}"

echo "=== 回滚开始 ==="
echo "当前版本: ${CURRENT_VERSION}"
echo "回滚到: ${PREV_VERSION}"

# 1. 检查上一版本镜像是否存在
if ! docker image inspect "${IMAGE_NAME}:${PREV_VERSION}" > /dev/null 2>&1; then
    echo "❌ 镜像 ${IMAGE_NAME}:${PREV_VERSION} 不存在"
    exit 1
fi

# 2. 切换 latest 标签
docker tag "${IMAGE_NAME}:${PREV_VERSION}" "${IMAGE_NAME}:latest"
echo "✅ latest 已切换到 ${PREV_VERSION}"

# 3. 更新回滚记录
echo "${PREV_VERSION}" > "${PREV_VERSION_FILE}"
echo "✅ 回滚完成"
echo ""
echo "⚠️ 请验证服务恢复正常，并记录回滚原因。"