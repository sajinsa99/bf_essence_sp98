#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
DB_FILE="$SCRIPT_DIR/prices.json"
PYTHON_SCRIPT="$SCRIPT_DIR/essence_tracker.py"
VENV_DIR="$SCRIPT_DIR/venv"
PORT=9000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${YELLOW}Server is already running (PID: $PID)${NC}"
            return 1
        fi
    fi
    
    # Check if venv exists, create if not
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}Creating Python virtual environment...${NC}"
        python3 -m venv "$VENV_DIR" || {
            echo -e "${RED}✗ Failed to create virtual environment${NC}"
            return 1
        }
    fi
    
    # Activate venv and install dependencies
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        echo -e "${YELLOW}Ensuring Python dependencies are installed...${NC}"
        pip install -q -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || {
            # Fallback: install minimal requirements
            pip install -q Flask==2.3.3 Werkzeug==2.3.7 requests==2.31.0 2>/dev/null || true
        }
    fi
    
    echo -e "${YELLOW}Starting essence tracker server on port $PORT...${NC}"
    cd "$SCRIPT_DIR" || return 1
    
    # Start Python app with venv Python
    nohup "$VENV_DIR/bin/python" "$PYTHON_SCRIPT" > essence_tracker.log 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    
    # Wait a moment for server to start
    sleep 2
    
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        echo -e "${GREEN}✓ Server started (PID: $SERVER_PID)${NC}"
        echo -e "${GREEN}✓ Access at http://localhost:$PORT${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to start server${NC}"
        echo -e "${YELLOW}--- Last 20 lines of log:${NC}"
        tail -20 essence_tracker.log 2>/dev/null || echo "No logs available"
        return 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}Server is not running${NC}"
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${YELLOW}Stopping server (PID: $PID)...${NC}"
        kill "$PID"
        sleep 1
        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ Server stopped${NC}"
        return 0
    else
        echo -e "${YELLOW}Server is not running${NC}"
        rm -f "$PID_FILE"
        return 0
    fi
}

status() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${RED}✗ Server is not running${NC}"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${GREEN}✓ Server is running (PID: $PID)${NC}"
        echo -e "${GREEN}✓ Access at http://localhost:$PORT${NC}"
        if [ -f "$DB_FILE" ]; then
            COUNT=$(jq 'length' "$DB_FILE" 2>/dev/null || echo "0")
            echo -e "${GREEN}✓ Database entries: $COUNT${NC}"
        fi
        return 0
    else
        echo -e "${RED}✗ Server is not running${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

fetch() {
    echo -e "${YELLOW}Fetching current price...${NC}"
    
    # Create venv if it doesn't exist
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}Creating Python virtual environment...${NC}"
        python3 -m venv "$VENV_DIR" || {
            echo -e "${RED}✗ Failed to create virtual environment${NC}"
            return 1
        }
    fi
    
    # Install dependencies
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        pip install -q -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || {
            pip install -q Flask==2.3.3 Werkzeug==2.3.7 requests==2.31.0 2>/dev/null || true
        }
    fi
    
    # Run fetch with venv Python
    cd "$SCRIPT_DIR" || return 1
    "$VENV_DIR/bin/python" "$PYTHON_SCRIPT" --fetch
}

case "${1:-status}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    fetch)
        fetch
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    *)
        echo "Usage: $0 {start|stop|status|fetch|restart}"
        echo ""
        echo "Commands:"
        echo "  start     - Start the HTTP server on port $PORT"
        echo "  stop      - Stop the HTTP server"
        echo "  status    - Show server status"
        echo "  fetch     - Fetch current price and update database"
        echo "  restart   - Restart the server"
        exit 1
        ;;
esac

exit $?
