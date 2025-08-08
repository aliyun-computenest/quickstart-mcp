#!/bin/sh

# Set default values
CONFIG_FILE=${CONFIG_FILE:-"/app/config.json"}
PORT=${PORT:-8000}
HOST=${HOST:-"0.0.0.0"}
WORKERS=${WORKERS:-4}
LOG_FILE="/app/logs/mcpo.log"

# 创建日志目录
mkdir -p /app/logs

# Build the command base
CMD_BASE="mcpo --config $CONFIG_FILE --port $PORT --host $HOST --workers $WORKERS"

# Add API key if provided
if [ -n "$API_KEY" ]; then
    CMD_BASE="$CMD_BASE --api-key $API_KEY"
fi

# Execute the command and redirect output to log file
exec $CMD_BASE >> $LOG_FILE 2>&1