
# 下载nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
# 配置nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
# 安装node，以node版本22为例
nvm install 22

uv pip install --upgrade pip && \
    uv pip install --no-cache-dir \
        "httpx<0.28" \
        "markdownify>=0.13.1" \
        "mcp>=1.1.3" \
        "protego>=0.3.1" \
        "pydantic>=2.0.0" \
        "readabilipy>=0.2.0" \
        "requests>=2.32.3" \
        "mcp_server_fetch" \
        "mcp-server-time"
