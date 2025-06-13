FROM python:3.12-slim-bookworm
ENV UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"

# Install uv (from official binary)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Use faster mirror and install system dependencies
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git curl ca-certificates \
        gcc libc6-dev pkg-config libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Verify Node.js installation
RUN node -v && npm -v

# Configure npm with only valid options
RUN npm config set registry https://registry.npmmirror.com
RUN npm config set cache /tmp/.npm
RUN npm config set audit false
RUN npm config set fund false
RUN npm config set progress false

# Set npm environment variables
ENV NPM_CONFIG_CACHE=/tmp/.npm
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
ENV NPM_CONFIG_AUDIT=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_PROGRESS=false

# Clean npm cache
RUN npm cache clean --force

# Copy source code
COPY . /app
WORKDIR /app

# Create virtual environment
ENV VIRTUAL_ENV=/app/.venv
RUN uv venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Clone and setup mcpo
RUN git clone https://github.com/LYH-RAIN/mcpo.git
WORKDIR /app/mcpo

# Install Python dependencies
RUN uv add --default-index https://pypi.tuna.tsinghua.edu.cn/simple requests
RUN uv pip install .
RUN rm -rf ~/.cache

# Setup prepare script if it exists
RUN if [ -f "/app/prepare.sh" ]; then \
        mv /app/prepare.sh /app/mcpo && \
        chmod +x prepare.sh && \
        ./prepare.sh; \
    fi

# Verify mcpo installation
RUN which mcpo

# Copy and set up entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Use the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]