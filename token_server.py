"""
Simple token server for LiveKit
This generates access tokens for testing the frontend
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")


@app.post("/token")
async def get_token(request: Request):
    """Generate a token for joining a room"""
    print(f"\n=== TOKEN REQUEST ===")
    body = await request.json()
    print(f"Request body: {body}")
    room_name = body.get("roomName")
    identity = body.get("identity", "guest")
    print(f"Generating token for room: {room_name}, identity: {identity}")
    
    if not room_name:
        print(f"ERROR: No room name provided")
        return {"error": "roomName is required"}, 400
    
    # Create access token
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    token.with_identity(identity).with_name(identity).with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )
    )
    
    print(f"Token generated successfully for {identity}")
    print(f"=== END TOKEN REQUEST ===\n")
    return {"token": token.to_jwt()}


@app.post("/create-room")
async def create_room(request: Request):
    """Create a room and dispatch an agent to it"""
    print(f"\n=== CREATE ROOM REQUEST ===")
    import aiohttp
    
    body = await request.json()
    print(f"Request body: {body}")
    room_name = body.get("roomName")
    print(f"Creating room: {room_name}")
    
    if not room_name:
        print(f"ERROR: No room name provided")
        return {"error": "roomName is required"}, 400
    
    try:
        # Get LiveKit server URL
        livekit_url = os.getenv("LIVEKIT_URL", "").replace("wss://", "https://").replace("ws://", "http://")
        print(f"LiveKit URL: {livekit_url}")
        
        # Create admin JWT with proper video grants for API access
        admin_token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        admin_token.with_grants(api.VideoGrants(
            room_create=True,
            room_admin=True,
        ))
        admin_jwt = admin_token.to_jwt()
        print(f"Generated admin JWT token")
        
        # Step 1: Create the room using REST API
        print(f"Step 1: Creating room via REST API...")
        create_room_url = f"{livekit_url}/twirp/livekit.RoomService/CreateRoom"
        print(f"Create room URL: {create_room_url}")
        
        create_room_payload = {
            "name": room_name,
            "empty_timeout": 300,
            "max_participants": 10,
            "metadata": '{"agent_name":"patient-intake-agent"}'
        }
        
        headers = {
            "Authorization": f"Bearer {admin_jwt}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            # Create room
            async with session.post(create_room_url, headers=headers, json=create_room_payload) as response:
                create_response = await response.text()
                print(f"Create room response status: {response.status}")
                print(f"Create room response body: {create_response}")
                
                if response.status == 200 or response.status == 409:  # 409 = room already exists
                    print(f"✅ Room created/verified: {room_name}")
                else:
                    print(f"⚠️  Room creation returned {response.status}, continuing anyway")
            
            # Notify our direct agent to join the room
            print(f"Step 2: Notifying agent to join room...")
            agent_url = "http://localhost:5001/join-room"
            async with session.post(agent_url, json={"roomName": room_name}) as response:
                if response.status == 200:
                    print(f"✅ Agent notified successfully!")
                else:
                    print(f"⚠️  Could not notify agent (status {response.status})")
        
        print(f"=== END CREATE ROOM REQUEST ===\n")
        return {"success": True, "room": room_name}
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"=== END CREATE ROOM REQUEST (ERROR) ===\n")
        return {"success": False, "error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3001
    print(f"Token server starting on http://localhost:{port}")
    print("📝 Make sure LIVEKIT_API_KEY and LIVEKIT_API_SECRET are set in .env")
    uvicorn.run(app, host="0.0.0.0", port=port)

