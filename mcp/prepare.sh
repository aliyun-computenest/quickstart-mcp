# 安装python
yum install python3.11 -y
# 创建python虚拟环境
python3.11 -m venv venv
# 启动虚拟环境
source venv/bin/activate
# 安装mcpo
pip install mcpo
# 下载nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash
# 配置nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
# 安装node，以node版本22为例
nvm install 22