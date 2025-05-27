#!/bin/sh

# Set default values
CONFIG_FILE=${CONFIG_FILE:-"/app/config.json"}
PORT=${PORT:-8000}
HOST=${HOST:-"0.0.0.0"}

# Build the command base
CMD_BASE="mcpo --config $CONFIG_FILE --port $PORT --host $HOST"

# Add API key if provided
if [ -n "$API_KEY" ]; then
    CMD_BASE="$CMD_BASE --api-key $API_KEY"
fi

# Execute the command
exec $CMD_BASE
