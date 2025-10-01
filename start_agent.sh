#!/bin/bash
# Simple script to start the direct agent

echo "🤖 Starting Patient Intake Voice AI Agent (Direct Mode)"
echo "====================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found! Please create it with your API keys."
    echo "See env_template.txt for reference."
    exit 1
fi

# Start the direct agent
echo "🚀 Starting agent_direct.py..."
python agent_direct.py
