# Patient Intake Voice AI Agent

A voice AI agent built with LiveKit Agents framework that collects patient information for medical appointment scheduling.

## Features

✅ Collects patient demographics (name, DOB)  
✅ Gathers insurance information (payer name and ID)  
✅ Records referral information  
✅ Documents chief medical complaint  
✅ Validates mailing address with external validation  
✅ Collects contact information (phone and email)  
✅ Offers available appointment times with providers  

## Architecture

- **Agent**: Python-based voice AI agent using LiveKit Agents framework
- **Voice Pipeline**: 
  - STT: Deepgram
  - LLM: OpenAI GPT-4o-mini
  - TTS: Cartesia
  - VAD: Silero
- **Frontend**: Web-based interface for easy testing (no phone required)
- **Token Server**: Simple FastAPI server for authentication

## Prerequisites

1. **Python 3.9+**
2. **LiveKit Server** (local or cloud)
3. **API Keys**:
   - OpenAI API key
   - Deepgram API key  
   - Cartesia API key

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Additional dependencies for the token server:
```bash
pip install fastapi uvicorn
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```env
# LiveKit Configuration
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# AI Provider Keys
OPENAI_API_KEY=your_openai_api_key_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here
CARTESIA_API_KEY=your_cartesia_api_key_here
```

### 3. Start LiveKit Server (Local Development)

Install and start LiveKit server locally:

```bash
# Using Homebrew (Mac)
brew install livekit

# Or download from https://github.com/livekit/livekit/releases

# Start the server
livekit-server --dev
```

The dev server will run on `ws://localhost:7880` with default credentials:
- API Key: `devkey`
- API Secret: `secret`

### 4. Start the Token Server

In a new terminal:

```bash
python token_server.py
```

This starts the token server on `http://localhost:3000`.

### 5. Start the Voice Agent

In another terminal:

```bash
python agent_direct.py
```

This starts the direct agent which will listen for room join requests on port 5001.

### 6. Open the Frontend

Open `frontend.html` in your web browser (or use a simple HTTP server):

```bash
# Using Python's built-in server
python -m http.server 8080
# Then open http://localhost:8080/frontend.html
```

### 7. Test the Agent

1. Click "Start Voice Session" in the frontend
2. Allow microphone access when prompted
3. Start speaking with the agent!

The agent will guide you through the patient intake process:
1. Name
2. Date of birth
3. Insurance information
4. Referral details
5. Chief complaint
6. Address (with validation)
7. Contact information
8. Available appointments

## Project Structure

```
assort_4/
├── agent_direct.py       # Main voice AI agent (direct connection)
├── token_server.py       # Authentication token server
├── frontend.html         # Web-based testing interface
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (create this)
└── README.md            # This file
```

## How It Works

### Agent Flow

The agent uses a structured conversation flow with function calling:

1. **Greeting**: Agent introduces itself and asks for patient name
2. **Data Collection**: Uses AI callable functions to store each piece of information
3. **Address Validation**: Validates address completeness using external validation logic
4. **Appointment Scheduling**: Generates and offers available appointment times
5. **Completion**: Summarizes collected information

### Tools/Functions

The agent has access to these functions:
- `store_patient_name()` - Records patient name
- `store_date_of_birth()` - Records DOB
- `store_insurance()` - Records insurance details
- `store_referral_info()` - Records referral information
- `store_chief_complaint()` - Records medical complaint
- `store_and_validate_address()` - Validates and stores address
- `store_contact_info()` - Records phone and email
- `get_available_appointments()` - Retrieves available time slots
- `get_patient_summary()` - Returns all collected data

### Address Validation

Currently uses a heuristic-based validation that checks for:
- Street number
- City
- State
- ZIP code

For production, integrate with:
- USPS Address Validation API
- Google Maps Geocoding API
- SmartyStreets
- Melissa Data

## Customization

### Change Voice Providers

Edit `agent.py` to use different providers:

```python
session = AgentSession(
    vad=silero.VAD.load(),
    stt=deepgram.STT(),  # Or: openai.STT(), assemblyai.STT()
    llm=openai.LLM(),     # Or: anthropic.LLM(), groq.LLM()
    tts=cartesia.TTS(),   # Or: elevenlabs.TTS(), openai.TTS()
)
```

### Modify Agent Instructions

Update the `instructions` parameter in `agent_direct.py`:

```python
agent = Agent(
    instructions="Your custom instructions here...",
    tools=tools,
)
```

### Add More Data Fields

1. Add fields to `patient_info` dict in `agent_direct.py`
2. Create a new `@llm.function_tool` method
3. Update agent instructions to collect the new field

## Deployment

### Deploy to LiveKit Cloud

1. Create account at https://cloud.livekit.io
2. Get your production credentials
3. Update `.env` with production values
4. Deploy agent:

```bash
# Build and push agent to LiveKit Cloud
livekit-cli agent deploy
```

### Deploy Token Server

Deploy the token server to:
- Railway
- Render  
- Heroku
- AWS Lambda
- Google Cloud Run

### Deploy Frontend

Host the frontend on:
- Vercel
- Netlify
- GitHub Pages
- Any static hosting service

Update the token server URL in `frontend.html`.

## Converting to Phone Integration

To add phone functionality later:

1. **Telephony Integration**: Use LiveKit's SIP integration or services like Twilio, Vonage
2. **Phone Number**: Configure inbound phone number to route to LiveKit room
3. **Agent Dispatch**: Configure agent to automatically join when phone call connects
4. **DTMF Support**: Add support for phone keypad input if needed

See: https://docs.livekit.io/agents/telephony/

## Troubleshooting

### Agent won't connect
- Ensure LiveKit server is running
- Check that API keys in `.env` are correct
- Verify agent_direct.py is running and listening on port 5001

### No audio
- Check microphone permissions in browser
- Verify audio tracks are being published
- Check browser console for errors

### Token errors  
- Ensure token server is running on port 3000
- Verify LIVEKIT_API_KEY and LIVEKIT_API_SECRET match

### Address validation issues
- Current validation is basic - for production use a real address validation API
- Check the validation logic in `validate_address()` function

## Resources

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/build/)
- [LiveKit Python SDK](https://github.com/livekit/python-sdks)
- [LiveKit Cloud](https://cloud.livekit.io)

## License

MIT

## Support

For issues or questions:
1. Check the LiveKit documentation
2. Visit LiveKit community Slack
3. Review example projects in LiveKit GitHub repos

