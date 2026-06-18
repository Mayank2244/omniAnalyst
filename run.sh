#!/bin/bash
# ═══════════════════════════════════════════════
#  OmniRoute Analytics — One-Command Startup
#  Usage: ./run.sh
# ═══════════════════════════════════════════════

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "═══════════════════════════════════════════════"
echo "  🚀 OmniRoute Analytics — Starting Up"
echo "═══════════════════════════════════════════════"

# ── 1. Check Python venv ──
if [ ! -f "$BACKEND_DIR/venv/bin/python" ]; then
    echo "📦 Creating Python virtual environment..."
    python3.11 -m venv "$BACKEND_DIR/venv"
    "$BACKEND_DIR/venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
fi

PYTHON="$BACKEND_DIR/venv/bin/python"

# ── 2. Seed database ──
echo ""
echo "🗄️  Seeding database..."
cd "$ROOT_DIR"
$PYTHON scripts/seed_data.py

# ── 3. Start backend ──
echo ""
echo "🔌 Starting FastAPI backend..."
cd "$BACKEND_DIR"
$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "   Waiting for backend..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "   ✅ Backend ready!"
        break
    fi
    sleep 2
done

# ── 4. Start frontend ──
echo ""
echo "🎨 Starting React frontend..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ OmniRoute Analytics is running!"
echo ""
echo "  🔌 Backend:  http://localhost:8000"
echo "  📖 API Docs: http://localhost:8000/docs"
echo "  🎨 Frontend: http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "═══════════════════════════════════════════════"

# Cleanup on exit
trap "echo ''; echo '👋 Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Wait for either process to exit
wait
