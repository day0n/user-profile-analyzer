#!/bin/bash
# 用户画像分析系统 - 服务器部署脚本
# 使用方法: sudo bash deploy.sh

set -e

APP_NAME="user-profile-analyzer"
APP_DIR="/opt/$APP_NAME"
SERVICE_FILE="$APP_NAME.service"

echo "=========================================="
echo "  用户画像分析系统 - 部署脚本"
echo "=========================================="

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 1. 安装系统依赖
echo ""
echo "[1/6] 安装系统依赖..."
apt-get update
apt-get install -y python3.12 python3.12-venv python3-pip nginx

# 2. 创建应用目录
echo ""
echo "[2/6] 创建应用目录..."
mkdir -p $APP_DIR
cp -r src $APP_DIR/
cp requirements.txt $APP_DIR/
cp .env.prod $APP_DIR/

# 3. 创建虚拟环境并安装依赖
echo ""
echo "[3/6] 创建虚拟环境并安装依赖..."
cd $APP_DIR
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. 设置权限
echo ""
echo "[4/6] 设置权限..."
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# 5. 安装 systemd 服务
echo ""
echo "[5/6] 安装 systemd 服务..."
cp deploy/$SERVICE_FILE /etc/systemd/system/
systemctl daemon-reload
systemctl enable $APP_NAME
systemctl start $APP_NAME

# 6. 配置 Nginx (可选)
echo ""
echo "[6/6] 检查服务状态..."
sleep 3
systemctl status $APP_NAME --no-pager

echo ""
echo "=========================================="
echo "  部署完成!"
echo "=========================================="
echo ""
echo "服务管理命令:"
echo "  查看状态: sudo systemctl status $APP_NAME"
echo "  启动服务: sudo systemctl start $APP_NAME"
echo "  停止服务: sudo systemctl stop $APP_NAME"
echo "  重启服务: sudo systemctl restart $APP_NAME"
echo "  查看日志: sudo journalctl -u $APP_NAME -f"
echo ""
echo "访问地址: http://服务器IP:7860"
echo ""
