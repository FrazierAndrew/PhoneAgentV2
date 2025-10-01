#!/bin/bash
# Convenience script to run all services for development

set -e

echo "🏥 Starting Patient Intake Voice AI Agent"
echo "=========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found! Creating from example..."
    cat > .env << EOF
# LiveKit Configuration
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# AI Provider Keys - REPLACE THESE WITH YOUR KEYS
OPENAI_API_KEY=your_openai_api_key_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here
CARTESIA_API_KEY=your_cartesia_api_key_here
EOF
    echo "📝 Created .env file - please edit it with your API keys"
    exit 1
fi

# Check if using LiveKit Cloud or local server
if grep -q "livekit.cloud" .env 2>/dev/null; then
    echo "✅ Using LiveKit Cloud (from .env)"
else
    # Check if local LiveKit server is running
    if ! nc -z localhost 7880 2>/dev/null; then
        echo "⚠️  LiveKit server not detected on localhost:7880"
        echo "Please start LiveKit server first:"
        echo "  brew install livekit"
        echo "  livekit-server --dev"
        exit 1
    fi
    echo "✅ Local LiveKit server detected"
fi

# Start token server in background
echo "🔑 Starting token server..."
python token_server.py &
TOKEN_SERVER_PID=$!
sleep 2

# Start agent in background  
echo "🤖 Starting voice agent..."
python agent.py dev &
AGENT_PID=$!
sleep 2

# Start simple HTTP server for frontend
echo "🌐 Starting web frontend..."
python -m http.server 8080 &
WEB_SERVER_PID=$!

echo ""
echo "=========================================="
echo "✅ All services started!"
echo "=========================================="
echo ""
echo "📱 Open your browser to: http://localhost:8080/frontend.html"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    kill $TOKEN_SERVER_PID 2>/dev/null || true
    kill $AGENT_PID 2>/dev/null || true
    kill $WEB_SERVER_PID 2>/dev/null || true
    echo "✅ All services stopped"
    exit 0
}

trap cleanup INT TERM

# Wait for any process to exit
wait

