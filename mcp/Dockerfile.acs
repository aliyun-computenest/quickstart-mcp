FROM python:3.12-slim-bookworm
ENV UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple"

RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple uv

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git curl ca-certificates \
        gcc libc6-dev pkg-config libcairo2-dev \
        nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm config set registry https://registry.npmmirror.com && \
    npm config set cache /tmp/.npm && \
    npm config set audit false && \
    npm config set fund false && \
    npm config set progress false

ENV NPM_CONFIG_CACHE=/tmp/.npm
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
ENV NPM_CONFIG_AUDIT=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_PROGRESS=false

RUN npm install -g supergateway && npm cache clean --force

COPY mcp/ /app/
WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv
RUN uv venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN git clone https://github.com/LYH-RAIN/mcpo.git /app/mcpo
WORKDIR /app/mcpo
RUN uv add --default-index https://mirrors.aliyun.com/pypi/simple requests && \
    uv pip install . && \
    rm -rf ~/.cache

RUN if [ -f "/app/prepare.sh" ]; then \
        mv /app/prepare.sh /app/mcpo && \
        chmod +x prepare.sh && \
        ./prepare.sh; \
    fi

RUN which mcpo && which supergateway

WORKDIR /app
EXPOSE 8080
