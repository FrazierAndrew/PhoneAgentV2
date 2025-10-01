# Quick Start Guide

Get up and running in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Create Environment File

Create a `.env` file with your API keys:

```bash
cat > .env << 'EOF'
# LiveKit Configuration (for local dev)
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# AI Provider Keys - GET THESE FROM:
# OpenAI: https://platform.openai.com/api-keys
# Deepgram: https://console.deepgram.com/
# Cartesia: https://cartesia.ai/

OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
DEEPGRAM_API_KEY=YOUR_KEY_HERE
CARTESIA_API_KEY=YOUR_KEY_HERE
EOF
```

**🔑 You need to get API keys from:**
- **OpenAI**: https://platform.openai.com/api-keys
- **Deepgram**: https://console.deepgram.com/
- **Cartesia**: https://cartesia.ai/

## Step 3: Install & Start LiveKit Server

```bash
# Install LiveKit (Mac)
brew install livekit

# OR download from: https://github.com/livekit/livekit/releases

# Start in dev mode
livekit-server --dev
```

Keep this terminal open. The server runs on `ws://localhost:7880`.

## Step 4: Run Everything

Open a new terminal and run:

```bash
./run_all.sh
```

This starts:
- ✅ Token server (port 3000)
- ✅ Voice agent
- ✅ Web frontend (port 8080)

## Step 5: Test!

1. Open browser to: **http://localhost:8080/frontend.html**
2. Click "**Start Voice Session**"
3. Allow microphone access
4. **Start talking!**

The agent will guide you through patient intake.

## Alternative: Run Manually

If you prefer to run services individually:

**Terminal 1 - LiveKit Server:**
```bash
livekit-server --dev
```

**Terminal 2 - Token Server:**
```bash
python token_server.py
```

**Terminal 3 - Voice Agent:**
```bash
python agent.py dev
```

**Terminal 4 - Web Server:**
```bash
python -m http.server 8080
```

Then open: http://localhost:8080/frontend.html

## Troubleshooting

### "Connection failed"
- Make sure all 3 services are running (LiveKit, token server, agent)
- Check terminal logs for errors

### "Token server not available"
- Ensure `token_server.py` is running on port 3000
- Check if another service is using port 3000

### No audio / Agent not responding
- Check that agent.py shows "Connected to room" in terminal
- Verify microphone permissions in browser
- Look at browser console (F12) for errors

### API Key Errors
- Verify all API keys are set in `.env`
- Make sure keys are valid and have credit/quota
- Check terminal logs for specific error messages

## What the Agent Does

The agent will collect:
1. ✅ Patient name
2. ✅ Date of birth
3. ✅ Insurance (payer name and ID)
4. ✅ Referral information
5. ✅ Chief medical complaint
6. ✅ Mailing address (with validation!)
7. ✅ Contact info (phone + email)
8. ✅ Available appointment times

## Next Steps

- Check `README.md` for detailed documentation
- Modify agent instructions in `agent.py`
- Customize the conversation flow
- Add more validation logic
- Deploy to production (see README)

## Getting API Keys

### OpenAI ($)
1. Go to https://platform.openai.com/
2. Sign up / Log in
3. Go to API Keys section
4. Create new key
5. Add credits to your account

### Deepgram (Free tier available)
1. Go to https://console.deepgram.com/
2. Sign up
3. Get your API key from dashboard
4. Free tier: 45,000 minutes

### Cartesia (Free tier available)
1. Go to https://cartesia.ai/
2. Sign up for early access
3. Get API key from dashboard

**Alternative TTS (if Cartesia not available):**
Edit `agent.py` and change:
```python
from livekit.plugins import elevenlabs  # or openai

tts=elevenlabs.TTS(),  # or openai.TTS()
```

---

**Need help?** Check the full README.md or LiveKit docs: https://docs.livekit.io/agents/

