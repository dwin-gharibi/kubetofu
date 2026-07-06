#!/bin/bash
# Kube-Tofu Development Server Startup Script
# This script starts both the backend API server and frontend development server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}           Kube-Tofu Development Server${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}Done!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "\n${YELLOW}Checking dependencies...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed!${NC}"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is not installed!${NC}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}npm is not installed!${NC}"
    exit 1
fi

echo -e "${GREEN}All dependencies found!${NC}"

echo -e "\n${YELLOW}Setting up backend...${NC}"
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

pip install -q fastapi uvicorn python-multipart 2>/dev/null || true

echo -e "${GREEN}Starting backend API server on port 8000...${NC}"
cd "$PROJECT_ROOT/backend"
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

sleep 2

echo -e "\n${YELLOW}Setting up frontend...${NC}"
cd "$PROJECT_ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo -e "${GREEN}Starting frontend development server on port 3000...${NC}"
npm run dev &
FRONTEND_PID=$!

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Servers started successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "\n${YELLOW}Services:${NC}"
echo -e "  Frontend: ${GREEN}http://localhost:3000${NC}"
echo -e "  Backend API: ${GREEN}http://localhost:8000${NC}"
echo -e "  API Docs: ${GREEN}http://localhost:8000/api/docs${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop all servers${NC}\n"

wait $BACKEND_PID $FRONTEND_PID
