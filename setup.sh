#!/bin/bash
# 初始化脚本 - 自动完成所有设置步骤

set -e

echo "=================================="
echo "X.com Tweet Scraper - 初始化脚本"
echo "=================================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未找到，请先安装 Python 3.8 或更新版本"
    exit 1
fi

echo "✓ Python3 已安装: $(python3 --version)"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo ""
    echo "创建虚拟环境..."
    python3 -m venv venv
    echo "✓ 虚拟环境已创建"
else
    echo "✓ 虚拟环境已存在"
fi

# 激活虚拟环境
source venv/bin/activate

echo ""
echo "升级 pip..."
pip install --upgrade pip &> /dev/null

echo "安装依赖..."
pip install -r requirements.txt &> /dev/null
echo "✓ Python 依赖已安装"

echo "安装 Playwright..."
playwright install &> /dev/null
echo "✓ Playwright 已安装"

# 创建必要的目录
mkdir -p logs
mkdir -p browser_state
mkdir -p debug_screenshots

echo "✓ 创建了必要的目录"

# 设置权限
chmod +x cron_job.sh main.py setup.sh

echo ""
echo "=================================="
echo "✓ 初始化完成！"
echo "=================================="
echo ""
echo "下一步："
echo "1. 登录 X.com:"
echo "   python3 main.py --login"
echo ""
echo "2. 运行首次采集:"
echo "   python3 main.py --collect"
echo ""
echo "3. 查看数据统计:"
echo "   python3 main.py --stats"
echo ""
echo "4. 设置定时采集:"
echo "   ./cron_job.sh"
echo ""
echo "更多信息请查看 README.md 或 QUICKSTART.md"
echo ""
