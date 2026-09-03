#!/bin/bash
# 在 Docker 的 Ubuntu 容器里构建 .deb（适用于 macOS/Windows 等非 Ubuntu 环境）
# 需要先安装 Docker Desktop；构建镜像和目标系统版本建议一致（改 IMAGE 即可）
# 用法: ./build_deb_docker.sh [版本号]
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="${1:-1.0.0}"
IMAGE="${XCLAWER_BUILD_IMAGE:-ubuntu:22.04}"

echo "==> 在 $IMAGE 容器中构建 xclawer_${VERSION}_amd64.deb ..."
docker run --rm -v "$PROJECT_ROOT":/build -w /build "$IMAGE" bash -c "
    set -e
    apt-get update -qq
    apt-get install -y -qq python3 python3-venv python3-pip rsync dpkg-dev >/dev/null
    bash /build/build_deb.sh $VERSION
"

echo ""
echo "完成: $PROJECT_ROOT/dist/xclawer_${VERSION}_amd64.deb"
echo "安装: sudo dpkg -i dist/xclawer_${VERSION}_amd64.deb"
