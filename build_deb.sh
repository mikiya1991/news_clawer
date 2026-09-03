#!/bin/bash
# 构建 Ubuntu .deb 安装包
#   需在 Ubuntu 上执行（需要 dpkg-deb、python3-venv、rsync）
#   用法: ./build_deb.sh [版本号]    默认 1.0.0
set -e

VERSION="${1:-1.0.0}"
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
STAGING="$(mktemp -d)"
APP_DIR="$STAGING/usr/lib/xclawer"
mkdir -p "$APP_DIR"   # rsync 3.1.3 不会自动创建多级不存在的目标目录

echo "==> 1/5 拷贝项目文件..."
rsync -a --exclude '.git' --exclude 'venv' --exclude 'browser_state' \
    --exclude 'logs' --exclude 'debug_screenshots' --exclude '__pycache__' \
    --exclude '*.db' --exclude '.env' --exclude 'packaging' \
    --exclude 'build_deb.sh' --exclude 'dist' \
    "$PROJECT_ROOT/" "$APP_DIR/"

echo "==> 2/5 创建 venv 并安装依赖（打进包内，安装时无需联网）..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet \
    -r "$APP_DIR/requirements.txt" \
    -r "$APP_DIR/web/requirements.txt"

# venv 入口脚本的 shebang 指向暂存目录,改成安装后的实际路径
find "$APP_DIR/venv/bin" -maxdepth 1 -type f -exec sed -i "s|$APP_DIR|/usr/lib/xclawer|g" {} +

echo "==> 3/5 组装 DEBIAN 控制文件..."
mkdir -p "$STAGING/DEBIAN"
cp "$PROJECT_ROOT/packaging/debian/DEBIAN/control" "$STAGING/DEBIAN/control"
cp "$PROJECT_ROOT/packaging/debian/DEBIAN/postinst" "$STAGING/DEBIAN/postinst"
cp "$PROJECT_ROOT/packaging/debian/DEBIAN/prerm" "$STAGING/DEBIAN/prerm"
chmod 755 "$STAGING/DEBIAN/postinst" "$STAGING/DEBIAN/prerm"
sed -i "s/^Version: .*/Version: $VERSION/" "$STAGING/DEBIAN/control"

echo "==> 4/5 放入 systemd 服务..."
mkdir -p "$STAGING/lib/systemd/system"
cp "$PROJECT_ROOT/packaging/debian/lib/systemd/system/xclawer.service" \
    "$STAGING/lib/systemd/system/"

echo "==> 5/5 打包..."
OUT="$PROJECT_ROOT/dist"
mkdir -p "$OUT"
dpkg-deb --build --root-owner-group "$STAGING" "$OUT/xclawer_${VERSION}_amd64.deb"
rm -rf "$STAGING"

echo ""
echo "完成: $OUT/xclawer_${VERSION}_amd64.deb"
echo "安装: sudo dpkg -i $OUT/xclawer_${VERSION}_amd64.deb"
