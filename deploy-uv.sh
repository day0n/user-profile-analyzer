#!/bin/bash
# 用户画像分析系统 - 服务器部署脚本 (使用 uv)
# 使用方法: sudo bash deploy-uv.sh

set -e

APP_NAME="user-profile-analyzer"
APP_DIR="/opt/$APP_NAME"
SERVICE_FILE="$APP_NAME.service"

echo "=========================================="
echo "  用户画像分析系统 - 部署脚本 (uv)"
echo "=========================================="

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 1. 安装 uv (如果没有)
echo ""
echo "[1/5] 检查/安装 uv..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv 版本: $(uv --version)"

# 2. 创建应用目录
echo ""
echo "[2/5] 创建应用目录..."
mkdir -p $APP_DIR
cp -r src $APP_DIR/
cp pyproject.toml $APP_DIR/
cp .env.prod $APP_DIR/

# 3. 使用 uv 创建虚拟环境并安装依赖
echo ""
echo "[3/5] 使用 uv 创建虚拟环境并安装依赖..."
cd $APP_DIR
uv venv .venv --python 3.12
uv pip install -r pyproject.toml --python .venv/bin/python

# 4. 设置权限
echo ""
echo "[4/5] 设置权限..."
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# 5. 安装并启动 systemd 服务
echo ""
echo "[5/5] 安装 systemd 服务..."
cat > /etc/systemd/system/$SERVICE_FILE << 'EOF'
[Unit]
Description=User Profile Analyzer Web UI
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/user-profile-analyzer
Environment="PYTHONPATH=/opt/user-profile-analyzer/src"
Environment="APP_ENV=prod"
ExecStart=/opt/user-profile-analyzer/.venv/bin/python -m user_profile_analyzer.web_ui
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $APP_NAME
systemctl start $APP_NAME

sleep 3
systemctl status $APP_NAME --no-pager

echo ""
echo "=========================================="
echo "  部署完成!"
echo "=========================================="
echo ""
echo "访问地址: http://服务器IP:7860"
echo ""
echo "服务管理:"
echo "  sudo systemctl status $APP_NAME"
echo "  sudo systemctl restart $APP_NAME"
echo "  sudo journalctl -u $APP_NAME -f"
echo ""
