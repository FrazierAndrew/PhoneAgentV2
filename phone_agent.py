"""
Phone-based Patient Intake Voice AI Agent
Integrates with Twilio for phone calls
"""
import asyncio
import logging
from typing import Annotated, Optional
from datetime import datetime, timedelta
import random
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import aiohttp
from twilio.rest import Client
from twilio.twiml import VoiceResponse

# Load environment variables
load_dotenv()

from livekit import rtc
from livekit.agents import llm
from livekit.agents.voice import AgentSession, Agent
from livekit.plugins import openai, deepgram, cartesia, silero

logger = logging.getLogger("phone-patient-intake-agent")
logger.setLevel(logging.INFO)

# Patient data storage (in production, this would be a database)
patient_info = {
    "name": None,
    "date_of_birth": None,
    "insurance_payer": None,
    "insurance_id": None,
    "has_referral": None,
    "referral_physician": None,
    "chief_complaint": None,
    "address": None,
    "address_valid": False,
    "phone": None,
    "email": None,
    "stage": "greeting"
}

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = "+13505005217"  # Your Twilio number
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None


async def validate_address(address: str) -> dict:
    """Validate address using external API (mock for now)"""
    # Mock validation - in production use USPS or Google Maps API
    required_parts = ["street", "city", "state", "zip"]
    
    # Simple heuristic validation
    has_numbers = any(char.isdigit() for char in address)
    has_comma = "," in address
    word_count = len(address.split())
    
    if has_numbers and has_comma and word_count >= 4:
        return {
            "valid": True,
            "message": "Address appears valid",
            "formatted_address": address
        }
    else:
        missing = []
        if not has_numbers:
            missing.append("street number")
        if word_count < 4:
            missing.append("complete address (street, city, state, ZIP)")
        
        return {
            "valid": False,
            "message": f"Address is missing: {', '.join(missing)}",
            "formatted_address": None
        }


async def generate_appointments() -> list:
    """Generate fake available appointment slots"""
    appointments = []
    base_date = datetime.now() + timedelta(days=1)
    
    doctors = ["Dr. Smith", "Dr. Johnson", "Dr. Williams"]
    times = ["9:00 AM", "10:30 AM", "2:00 PM", "3:30 PM"]
    
    for i in range(3):
        date = base_date + timedelta(days=i)
        doctor = random.choice(doctors)
        time = random.choice(times)
        
        appointments.append({
            "date": date.strftime("%A, %B %d"),
            "time": time,
            "doctor": doctor
        })
    
    return appointments


async def send_patient_info_email(patient_data: dict):
    """Send collected patient information via email"""
    try:
        # Email configuration
        sender_email = "bubbaf18@gmail.com"
        sender_password = "qirv tzjb tuyd bymv"  # App password
        recipient_email = "a2drewfrazier@gmail.com"
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"New Patient Intake - {patient_data.get('name', 'Unknown')}"
        
        # Format patient data
        body = f"""
New Patient Intake Information
=============================

Patient Details:
- Name: {patient_data.get('name', 'Not provided')}
- Date of Birth: {patient_data.get('date_of_birth', 'Not provided')}
- Phone: {patient_data.get('phone', 'Not provided')}
- Email: {patient_data.get('email', 'Not provided')}

Insurance Information:
- Payer: {patient_data.get('insurance_payer', 'Not provided')}
- ID: {patient_data.get('insurance_id', 'Not provided')}

Referral Information:
- Has Referral: {patient_data.get('has_referral', 'Not provided')}
- Referring Physician: {patient_data.get('referral_physician', 'Not provided')}

Medical Information:
- Chief Complaint: {patient_data.get('chief_complaint', 'Not provided')}

Address Information:
- Address: {patient_data.get('address', 'Not provided')}
- Address Validated: {patient_data.get('address_validated', 'Not provided')}

Intake completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
This information was collected by the AI Patient Intake Agent.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        logger.info(f"✅ Patient information sent to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False


# Define AI-callable tools using function decorators

@llm.function_tool(description="Store the patient's full name")
async def store_patient_name(
    name: Annotated[str, "The patient's full name"]
):
    """Store patient's name"""
    patient_info["name"] = name
    patient_info["stage"] = "dob"
    return f"Stored name: {name}"


@llm.function_tool(description="Store the patient's date of birth")
async def store_date_of_birth(
    date_of_birth: Annotated[str, "Patient's date of birth in MM/DD/YYYY format"]
):
    """Store patient's date of birth"""
    patient_info["date_of_birth"] = date_of_birth
    patient_info["stage"] = "insurance"
    return f"Stored date of birth: {date_of_birth}"


@llm.function_tool(description="Store insurance information")
async def store_insurance(
    payer_name: Annotated[str, "Insurance company name"],
    insurance_id: Annotated[str, "Insurance ID number"]
):
    """Store insurance information"""
    patient_info["insurance_payer"] = payer_name
    patient_info["insurance_id"] = insurance_id
    patient_info["stage"] = "referral"
    return f"Stored insurance: {payer_name}, ID: {insurance_id}"


@llm.function_tool(description="Store referral information")
async def store_referral_info(
    has_referral: Annotated[bool, "Whether patient has a referral"],
    physician_name: Annotated[Optional[str], "Referring physician name, if applicable (optional)"] = None
):
    """Store referral information"""
    patient_info["has_referral"] = has_referral
    patient_info["referral_physician"] = physician_name or ""
    patient_info["stage"] = "complaint"
    
    if has_referral and physician_name:
        return f"Stored referral from Dr. {physician_name}"
    else:
        return "Noted: No referral"


@llm.function_tool(description="Store chief medical complaint")
async def store_chief_complaint(
    complaint: Annotated[str, "The patient's chief medical complaint or reason for visit"]
):
    """Store chief complaint"""
    patient_info["chief_complaint"] = complaint
    patient_info["stage"] = "address"
    return f"Stored chief complaint: {complaint}"


@llm.function_tool(description="Store and validate patient address")
async def store_and_validate_address(
    address: Annotated[str, "Complete mailing address including street, city, state, and ZIP code"]
):
    """Store and validate address"""
    validation_result = await validate_address(address)
    
    patient_info["address"] = address
    patient_info["address_valid"] = validation_result["valid"]
    
    if validation_result["valid"]:
        patient_info["stage"] = "contact"
        return f"Address validated: {validation_result['formatted_address']}"
    else:
        return f"Address validation failed: {validation_result['message']}. Please provide the complete address."


@llm.function_tool(description="Store contact information")
async def store_contact_info(
    phone: Annotated[str, "Patient's phone number (any format accepted)"],
    email: Annotated[Optional[str], "Patient's email address (optional)"] = None
):
    """Store contact information"""
    patient_info["phone"] = phone
    patient_info["email"] = email or ""
    patient_info["stage"] = "appointments"
    
    if email:
        return f"Stored contact info - Phone: {phone}, Email: {email}"
    else:
        return f"Stored phone number: {phone}"


@llm.function_tool(description="Get available appointment times")
async def get_available_appointments():
    """Get available appointment slots and send patient info via email"""
    appointments = await generate_appointments()
    patient_info["stage"] = "complete"
    
    appointment_text = "Here are the available appointments:\n"
    for i, apt in enumerate(appointments, 1):
        appointment_text += f"{i}. {apt['date']} at {apt['time']} with {apt['doctor']}\n"
    
    # Send patient information via email
    email_sent = await send_patient_info_email(patient_info)
    if email_sent:
        appointment_text += "\n\n✅ Your information has been sent to our scheduling team. They will contact you shortly to confirm your appointment."
    else:
        appointment_text += "\n\n⚠️ There was an issue sending your information. Please call our office directly to complete your appointment booking."
    
    return appointment_text


@llm.function_tool(description="Get a summary of all collected patient information")
async def get_patient_summary():
    """Get summary of collected information"""
    return json.dumps(patient_info, indent=2)


async def run_agent_in_room(room_name: str, caller_phone: str = None):
    """Directly connect agent to a specific room"""
    logger.info(f"🚀 Agent directly connecting to room: {room_name}")
    
    # Store caller phone if provided
    if caller_phone:
        patient_info["phone"] = caller_phone
    
    # Create a room connection
    room = rtc.Room()
    
    # Connect to the room
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    # Generate agent token
    from livekit import api
    token = api.AccessToken(api_key, api_secret)
    token.with_identity(f"agent-{random.randint(1000, 9999)}")
    token.with_name("Patient Intake Agent")
    token.with_grants(api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    ))
    
    await room.connect(livekit_url, token.to_jwt())
    logger.info(f"✅ Agent connected to room: {room_name}")
    
    # Collect all tools
    tools = [
        store_patient_name,
        store_date_of_birth,
        store_insurance,
        store_referral_info,
        store_chief_complaint,
        store_and_validate_address,
        store_contact_info,
        get_available_appointments,
        get_patient_summary,
    ]
    
    # Define the agent with instructions
    from livekit.agents.voice import Agent
    agent = Agent(
        instructions="""You are a friendly and professional medical receptionist conducting patient intake over the phone.

Your job is to collect the following information IN ORDER:
1. Patient's full name
2. Date of birth (MM/DD/YYYY format)
3. Insurance information (payer name and ID number)
4. Whether they have a referral, and if so, to which physician
5. Chief medical complaint or reason for their visit
6. Complete mailing address (street, city, state, ZIP code)
   - If the address validation fails, ask them to provide the missing information
7. Contact information (phone number and optionally email)
8. After all information is collected, offer available appointment times

Guidelines:
- Be warm, empathetic, and professional
- Speak naturally and conversationally
- Ask one question at a time
- Confirm information when needed
- Use the provided tools to store and validate information
- When validating the address, if it's invalid, clearly explain what's missing
- After collecting all information, use the get_available_appointments tool to show options
- Keep responses concise and clear
- Remember this is a phone call, so speak clearly and wait for responses

Start by greeting the patient and asking for their full name.""",
        tools=tools,
    )
    
    # Create a dedicated HTTP session for plugins (since we're not in worker job context)
    http_session = aiohttp.ClientSession()

    # Initialize the agent session with voice pipeline
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(api_key=os.getenv("DEEPGRAM_API_KEY"), http_session=http_session),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(api_key=os.getenv("CARTESIA_API_KEY"), http_session=http_session),
    )
    
    # Start the session
    await session.start(agent, room=room)
    
    # Send initial greeting
    logger.info("Sending initial greeting to patient")
    await session.say(
        "Hello! Thank you for calling. I'm here to help you schedule an appointment. May I have your full name, please?"
    )
    
    # Keep the agent running (no wait_for_completion in this API)
    try:
        # Wait for room to disconnect or session to close
        # Use room state monitoring instead of wait_for_disconnect
        while room.state != rtc.RoomState.DISCONNECTED:
            await asyncio.sleep(1)
        logger.info("Room disconnected")
    except Exception as e:
        logger.error(f"Session error: {e}")
    finally:
        # Clean up
        try:
            await session.aclose()
        except:
            pass
        try:
            await room.disconnect()
        except:
            pass
        try:
            await http_session.close()
        except:
            pass
        logger.info("Cleanup completed")
        logger.info("Patient intake session completed")
        logger.info(f"Final patient data: {patient_info}")


# FastAPI server for Twilio webhooks
from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
import uvicorn

app = FastAPI()

@app.post("/webhook/voice")
async def handle_voice_webhook(request: Request):
    """Handle incoming Twilio voice calls"""
    form_data = await request.form()
    caller_phone = form_data.get("From")
    call_sid = form_data.get("CallSid")
    
    logger.info(f"📞 Incoming call from {caller_phone}, Call SID: {call_sid}")
    
    # Create a unique room name for this call
    room_name = f"phone-call-{call_sid}"
    
    # Start agent in background
    asyncio.create_task(run_agent_in_room(room_name, caller_phone))
    
    # Return TwiML to connect to LiveKit
    response = VoiceResponse()
    
    # Connect to LiveKit room
    response.say("Please hold while I connect you to our patient intake system.")
    
    # Use Twilio's LiveKit integration
    # Note: This requires Twilio's LiveKit connector
    response.connect().room(room_name)
    
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/webhook/status")
async def handle_status_webhook(request: Request):
    """Handle call status updates"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    
    logger.info(f"📊 Call {call_sid} status: {call_status}")
    
    return {"status": "ok"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "twilio_number": TWILIO_PHONE_NUMBER}


if __name__ == "__main__":
    print(f"🏥 Phone-based Patient Intake Agent")
    print(f"📞 Twilio Number: {TWILIO_PHONE_NUMBER}")
    print(f"🌐 Webhook URL: https://your-domain.com/webhook/voice")
    print(f"🚀 Starting server on port 8000...")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
