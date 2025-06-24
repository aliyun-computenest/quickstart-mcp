#!/bin/sh

echo "🚀 启动 MCP Hub..."

# 设置默认值
export PUBLIC_IP=${PUBLIC_IP:-}
export PRIVATE_IP=${PRIVATE_IP:-}
export PUBLIC_TOKEN=${PUBLIC_TOKEN:-${API_KEY:-}}
export PRIVATE_TOKEN=${PRIVATE_TOKEN:-${API_KEY:-}}
export USE_PUBLIC_IP=${USE_PUBLIC_IP:-"true"}

# 确保配置目录存在
mkdir -p /app/dist/config

# 生成服务器配置文件到 dist/config 目录
echo "📝 生成服务器配置文件..."
cat > /app/dist/server-config.json << EOF
{
  "publicIp": "${PUBLIC_IP}",
  "privateIp": "${PRIVATE_IP}",
  "publicToken": "${PUBLIC_TOKEN}",
  "privateToken": "${PRIVATE_TOKEN}",
  "usePublicIp": ${USE_PUBLIC_IP}
}
EOF

echo "✅ 服务器配置已生成到 /app/dist/config/server-config.json"
cat /app/dist/server-config.json

# 检查挂载的配置文件（在 dist 根目录）
if [ -f "/app/dist/config.json" ]; then
    echo "📋 发现 MCP 配置文件: config.json"
else
    echo "⚠️  未找到 config.json"
fi

if [ -f "/app/dist/config_detail.json" ]; then
    echo "📋 发现 MCP 详细配置文件: config_detail.json"
else
    echo "⚠️  未找到 config_detail.json"
fi

echo "🌟 启动服务..."
exec "$@"
