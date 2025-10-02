#!/bin/bash
# Start the phone-based patient intake agent

echo "📞 Starting Phone-based Patient Intake Voice AI Agent"
echo "===================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found! Please create it with your API keys."
    echo "See env_template.txt for reference."
    exit 1
fi

# Check if Twilio credentials are set
if ! grep -q "TWILIO_ACCOUNT_SID=" .env || grep -q "your_twilio_account_sid_here" .env; then
    echo "⚠️  Twilio credentials not configured in .env file!"
    echo "Please add your TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to .env"
    exit 1
fi

echo "🚀 Starting phone_agent.py..."
echo "📞 Your Twilio number: (350) 500-5217"
echo "🌐 Webhook URL: https://your-domain.com/webhook/voice"
echo ""
echo "Make sure to configure your Twilio webhook to point to this server!"
echo ""

python phone_agent.py
