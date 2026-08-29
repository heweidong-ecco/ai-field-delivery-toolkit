#!/bin/bash
# 发布脚本：执行检查、构建镜像、打标签、保存回滚信息

set -e

VERSION="${1:-0.1.0}"
IMAGE_NAME="toolkit-app"
PREV_VERSION_FILE=".release_prev_version"

echo "=== AI 项目现场交付工具包 发布 v${VERSION} ==="

# 1. 运行测试
echo "1. 运行测试..."
if ! pytest tests/ -q --tb=short; then
    echo "❌ 测试未通过，禁止发布"
    exit 1
fi
echo "✅ 测试通过"

# 2. 保存当前版本为回滚版本（如果存在）
if [ -f "${PREV_VERSION_FILE}" ]; then
    PREV_VERSION=$(cat "${PREV_VERSION_FILE}")
    echo "2. 当前回滚版本: ${PREV_VERSION}"
else
    PREV_VERSION="none"
    echo "2. 无上一版本（首次发布）"
fi

# 3. 构建镜像
echo "3. 构建 Docker 镜像..."
docker build -t "${IMAGE_NAME}:${VERSION}" .
echo "✅ 镜像构建成功"

# 4. 打标签
echo "4. 打标签 ${IMAGE_NAME}:latest"
docker tag "${IMAGE_NAME}:${VERSION}" "${IMAGE_NAME}:latest"
echo "✅ 标签完成"

# 5. 保存回滚信息
echo "${VERSION}" > "${PREV_VERSION_FILE}"
echo "5. 已保存回滚信息到 ${PREV_VERSION_FILE}"

# 6. 输出发布信息
echo ""
echo "=== 发布完成 ==="
echo "镜像: ${IMAGE_NAME}:${VERSION}"
echo "最新标签: ${IMAGE_NAME}:latest"
echo "回滚版本: ${PREV_VERSION}"
echo ""
echo "下一步："
echo "  1. 通知团队"
echo "  2. 安排培训"
echo "  3. 更新文档"