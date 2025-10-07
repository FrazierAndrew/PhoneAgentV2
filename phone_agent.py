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
from twilio.twiml.voice_response import VoiceResponse

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
    """Send appointment confirmation email to all specified recipients"""
    try:
        # Email configuration
        sender_email = "bubbaf18@gmail.com"
        sender_password = "qirv tzjb tuyd bymv"  # App password
        
        # All recipients
        recipients = [
            "bubbaf18@gmail.com",
            "aelsaied@assorthealth.com",
            "connor@assorthealth.com",
            "cole@assorthealth.com",
            "jciminelli@assorthealth.com",
            "drajan@assorthealth.com",
            "nvilimek@assorthealth.com",
            "gwong@assorthealth.com"
        ]
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = f"Appointment Confirmation - {patient_data.get('name', 'Unknown')}"
        
        # Get appointment info
        appointment = patient_data.get('appointment', {})
        
        # Simple appointment confirmation - ONLY date, time, and doctor
        body = f"""
Appointment Confirmation

Appointment Date: {appointment.get('date', 'Not provided')}
Appointment Time: {appointment.get('time', 'Not provided')}
Doctor: {appointment.get('doctor', 'Not provided')}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email to all recipients
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipients, text)
        server.quit()
        
        logger.info(f"Appointment confirmation sent to {len(recipients)} recipients")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send appointment confirmation email: {e}")
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
        appointment_text += "\n\n Your information has been sent to our scheduling team. They will contact you shortly to confirm your appointment."
    else:
        appointment_text += "\n\n There was an issue sending your information. Please call our office directly to complete your appointment booking."
    
    return appointment_text


@llm.function_tool(description="Get a summary of all collected patient information")
async def get_patient_summary():
    """Get summary of collected information"""
    return json.dumps(patient_info, indent=2)


async def run_agent_in_room(room_name: str, caller_phone: str = None):
    """Directly connect agent to a specific room"""
    logger.info(f" Agent directly connecting to room: {room_name}")
    
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
    logger.info(f" Agent connected to room: {room_name}")
    
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

@app.post("/voice/incoming")
async def handle_voice_webhook(request: Request):
    """Handle incoming Twilio voice calls"""
    try:
        form_data = await request.form()
        caller_phone = form_data.get("From")
        call_sid = form_data.get("CallSid")
        
        logger.info(f" Incoming call from {caller_phone}, Call SID: {call_sid}")
        
        # Return TwiML response to start patient intake
        response = VoiceResponse()
        response.say("Hello! Thank you for calling our patient intake system.")
        
        # Use gather to collect voice input for name
        gather = response.gather(
            input="speech",
            action="/voice/collect-name",
            method="POST",
            speech_timeout="auto",
            timeout=10
        )
        gather.say("May I have your full name, please?")
        
        # Fallback if no input - redirect to retry
        response.redirect("/voice/retry-name", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling voice webhook: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-name")
async def collect_name(request: Request):
    """Collect patient name and continue intake process"""
    try:
        form_data = await request.form()
        name = form_data.get("SpeechResult", "").strip()
        caller_phone = form_data.get("From")
        
        logger.info(f"Patient {caller_phone} provided name: {name}")
        
        # Store the name
        patient_info["name"] = name
        patient_info["phone"] = caller_phone
        
        response = VoiceResponse()
        
        if name:
            response.say(f"Thank you, {name}.")
            
            # Collect date of birth
            gather = response.gather(
                input="speech",
                action="/voice/collect-dob",
                method="POST",
                speech_timeout="auto",
                timeout=10
            )
            gather.say("What is your date of birth? Please say the month, day, and year.")
            
            # Fallback - redirect to retry
            response.redirect("/voice/retry-dob", method="POST")
        else:
            # Redirect to retry
            response.redirect("/voice/retry-name", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting name: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-name")
async def retry_name(request: Request):
    """Retry collecting patient name"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch that.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-name",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Could you please tell me your full name one more time?")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-dob")
async def collect_dob(request: Request):
    """Collect date of birth and continue intake process"""
    try:
        form_data = await request.form()
        dob = form_data.get("SpeechResult", "").strip()
        
        logger.info(f"Patient provided DOB: {dob}")
        
        # Store the DOB
        patient_info["date_of_birth"] = dob
        
        response = VoiceResponse()
        
        if dob:
            response.say(f"Thank you. I have your date of birth as {dob}.")
            
            # Collect insurance
            gather = response.gather(
                input="speech",
                action="/voice/collect-insurance",
                method="POST",
                speech_timeout="auto",
                timeout=10
            )
            gather.say("What insurance company do you have?")
            
            # Fallback - redirect to retry
            response.redirect("/voice/retry-insurance", method="POST")
        else:
            # Redirect to retry
            response.redirect("/voice/retry-dob", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting DOB: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-dob")
async def retry_dob(request: Request):
    """Retry collecting date of birth"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't hear your date of birth.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-dob",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Please tell me your date of birth again. Say the month, day, and year.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-insurance")
async def collect_insurance(request: Request):
    """Collect insurance payer name"""
    try:
        form_data = await request.form()
        insurance = form_data.get("SpeechResult", "").strip()
        
        logger.info(f"Patient provided insurance: {insurance}")
        
        # Store the insurance payer
        patient_info["insurance_payer"] = insurance
        
        response = VoiceResponse()
        
        if insurance:
            response.say(f"Thank you. I have your insurance as {insurance}.")
            
            # Collect insurance ID
            gather = response.gather(
                input="speech dtmf",
                action="/voice/collect-insurance-id",
                method="POST",
                speech_timeout="auto",
                timeout=10
            )
            gather.say("What is your insurance ID number?")
            
            # Fallback - redirect to retry
            response.redirect("/voice/retry-insurance-id", method="POST")
        else:
            # Redirect to retry
            response.redirect("/voice/retry-insurance", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting insurance: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-insurance")
async def retry_insurance(request: Request):
    """Retry collecting insurance"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch your insurance company name.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-insurance",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Please tell me your insurance company name again.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-insurance-id")
async def collect_insurance_id(request: Request):
    """Collect insurance ID number"""
    try:
        form_data = await request.form()
        insurance_id = form_data.get("SpeechResult") or form_data.get("Digits", "")
        insurance_id = insurance_id.strip()
        
        logger.info(f"Patient provided insurance ID: {insurance_id}")
        
        # Store the insurance ID
        patient_info["insurance_id"] = insurance_id
        
        response = VoiceResponse()
        
        if insurance_id:
            response.say(f"Thank you. I have your insurance ID.")
            
            # Ask about referral
            gather = response.gather(
                input="speech",
                action="/voice/collect-referral",
                method="POST",
                speech_timeout="auto",
                timeout=10
            )
            gather.say("Do you have a referral from another physician?")
            
            # Fallback - redirect to retry
            response.redirect("/voice/retry-referral", method="POST")
        else:
            # Redirect to retry
            response.redirect("/voice/retry-insurance-id", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting insurance ID: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-insurance-id")
async def retry_insurance_id(request: Request):
    """Retry collecting insurance ID"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch your insurance ID number.")
    
    gather = response.gather(
        input="speech dtmf",
        action="/voice/collect-insurance-id",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Please tell me your insurance ID number again.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-referral")
async def collect_referral(request: Request):
    """Collect referral information"""
    try:
        form_data = await request.form()
        referral_response = form_data.get("SpeechResult", "").strip().lower()
        
        logger.info(f"Patient referral response: {referral_response}")
        
        response = VoiceResponse()
        
        if referral_response:
            # Check if they said yes/no
            has_referral = any(word in referral_response for word in ["yes", "yeah", "yep", "have", "got"])
            
            if has_referral:
                patient_info["has_referral"] = True
                response.say("Great.")
                
                # Ask for physician name
                gather = response.gather(
                    input="speech",
                    action="/voice/collect-physician",
                    method="POST",
                    speech_timeout="auto",
                    timeout=10
                )
                gather.say("Which physician referred you?")
                
                response.redirect("/voice/retry-physician", method="POST")
            else:
                patient_info["has_referral"] = False
                patient_info["referral_physician"] = ""
                response.say("Okay, no problem.")
                
                # Move to chief complaint
                gather = response.gather(
                    input="speech",
                    action="/voice/collect-complaint",
                    method="POST",
                    speech_timeout="auto",
                    timeout=15
                )
                gather.say("What is the main reason for your visit today?")
                
                response.redirect("/voice/retry-complaint", method="POST")
        else:
            response.redirect("/voice/retry-referral", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting referral: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-referral")
async def retry_referral(request: Request):
    """Retry collecting referral"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch that.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-referral",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Do you have a referral from another physician? Please say yes or no.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-physician")
async def collect_physician(request: Request):
    """Collect referring physician name"""
    try:
        form_data = await request.form()
        physician = form_data.get("SpeechResult", "").strip()
        
        logger.info(f"Patient provided physician: {physician}")
        
        # Store the physician
        patient_info["referral_physician"] = physician
        
        response = VoiceResponse()
        
        if physician:
            response.say(f"Thank you. I have the referral from Doctor {physician}.")
            
            # Move to chief complaint
            gather = response.gather(
                input="speech",
                action="/voice/collect-complaint",
                method="POST",
                speech_timeout="auto",
                timeout=15
            )
            gather.say("What is the main reason for your visit today?")
            
            response.redirect("/voice/retry-complaint", method="POST")
        else:
            response.redirect("/voice/retry-physician", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting physician: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-physician")
async def retry_physician(request: Request):
    """Retry collecting physician"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch the physician's name.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-physician",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Which physician referred you? Please tell me their name.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-complaint")
async def collect_complaint(request: Request):
    """Collect chief complaint"""
    try:
        form_data = await request.form()
        complaint = form_data.get("SpeechResult", "").strip()
        
        logger.info(f"Patient provided complaint: {complaint}")
        
        response = VoiceResponse()
        
        if complaint:
            # Store the complaint
            patient_info["chief_complaint"] = complaint
            
            response.say(f"Thank you. I have your reason for the visit as {complaint}.")
            
            # Collect address
            gather = response.gather(
                input="speech",
                action="/voice/collect-address",
                method="POST",
                speech_timeout="auto",
                timeout=15
            )
            gather.say("What is your complete mailing address? Please include street, city, state, and ZIP code.")
            
            response.redirect("/voice/retry-address", method="POST")
        else:
            # Redirect to retry
            response.redirect("/voice/retry-complaint", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting complaint: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-complaint")
async def retry_complaint(request: Request):
    """Retry collecting chief complaint"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch that.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-complaint",
        method="POST",
        speech_timeout="auto",
        timeout=15
    )
    gather.say("Please tell me the main reason for your visit one more time.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-address")
async def collect_address(request: Request):
    """Collect and validate patient address"""
    try:
        form_data = await request.form()
        address = form_data.get("SpeechResult", "").strip()
        
        logger.info(f"Patient provided address: {address}")
        
        response = VoiceResponse()
        
        if address:
            # Validate the address
            validation_result = await validate_address(address)
            patient_info["address"] = address
            patient_info["address_valid"] = validation_result["valid"]
            
            if validation_result["valid"]:
                response.say("Thank you. I have your address.")
                
                # Collect phone number
                gather = response.gather(
                    input="speech dtmf",
                    action="/voice/collect-contact",
                    method="POST",
                    speech_timeout="auto",
                    timeout=10
                )
                gather.say("What is the best phone number to reach you?")
                
                response.redirect("/voice/retry-contact", method="POST")
            else:
                # Address validation failed
                response.say(f"I'm sorry, but {validation_result['message']}")
                response.say("Let me ask for your address again.")
                
                gather = response.gather(
                    input="speech",
                    action="/voice/collect-address",
                    method="POST",
                    speech_timeout="auto",
                    timeout=15
                )
                gather.say("Please provide your complete mailing address including street number, city, state, and ZIP code.")
                
                response.redirect("/voice/retry-address", method="POST")
        else:
            response.redirect("/voice/retry-address", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting address: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-address")
async def retry_address(request: Request):
    """Retry collecting address"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch your complete address.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-address",
        method="POST",
        speech_timeout="auto",
        timeout=15
    )
    gather.say("Please tell me your mailing address again, including street, city, state, and ZIP code.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-contact")
async def collect_contact(request: Request):
    """Collect contact phone number"""
    try:
        form_data = await request.form()
        phone = form_data.get("SpeechResult") or form_data.get("Digits", "")
        phone = phone.strip()
        caller_phone = form_data.get("From")
        
        logger.info(f"Patient provided contact phone: {phone}")
        
        response = VoiceResponse()
        
        if phone:
            # Store phone (or use caller ID if not provided)
            patient_info["phone"] = phone if phone else caller_phone
            
            response.say("Thank you.")
            
            # Ask for email
            gather = response.gather(
                input="speech",
                action="/voice/collect-email",
                method="POST",
                speech_timeout="auto",
                timeout=10
            )
            gather.say("Would you like to provide an email address? Say your email or say no.")
            
            response.redirect("/voice/retry-email", method="POST")
        else:
            response.redirect("/voice/retry-contact", method="POST")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting contact: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-contact")
async def retry_contact(request: Request):
    """Retry collecting contact phone"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch your phone number.")
    
    gather = response.gather(
        input="speech dtmf",
        action="/voice/collect-contact",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Please tell me your phone number again.")
    
    # Final fallback - end call
    response.say("I'm having trouble hearing you. Please try calling back when you have a better connection. Goodbye.")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/collect-email")
async def collect_email(request: Request):
    """Collect email address (optional)"""
    try:
        form_data = await request.form()
        email_response = form_data.get("SpeechResult", "").strip().lower()
        
        logger.info(f"Patient email response: {email_response}")
        
        response = VoiceResponse()
        
        # Check if they declined
        if any(word in email_response for word in ["no", "nope", "don't", "skip"]):
            patient_info["email"] = ""
            response.say("No problem.")
        elif "@" in email_response or "at" in email_response:
            # They provided an email (roughly)
            patient_info["email"] = email_response
            response.say("Thank you. I have your email.")
        else:
            patient_info["email"] = email_response
            response.say("Got it.")
        
        # Now show appointments and complete
        appointments = await generate_appointments()
        patient_info["stage"] = "complete"
        
        response.say("Great! Let me show you our available appointments.")
        
        appointment_text = "We have the following times available: "
        for i, apt in enumerate(appointments, 1):
            appointment_text += f"Option {i}: {apt['date']} at {apt['time']} with {apt['doctor']}. "
        
        response.say(appointment_text)
        
        # Select the first appointment as default
        selected_appointment = appointments[0]
        patient_info["appointment"] = selected_appointment
        
        response.say(f"I've scheduled you for {selected_appointment['date']} at {selected_appointment['time']} with {selected_appointment['doctor']}.")
        response.say("Our scheduling team will contact you shortly to confirm your appointment.")
        
        # Send appointment confirmation email
        confirmation_sent = await send_patient_info_email(patient_info)
        
        if confirmation_sent:
            response.say("Your appointment confirmation has been sent.")
        
        response.say("Thank you for calling. We look forward to seeing you. Goodbye.")
        
        return PlainTextResponse(str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error collecting email: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, there was an error. Please try again later.")
        return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/voice/retry-email")
async def retry_email(request: Request):
    """Retry collecting email"""
    response = VoiceResponse()
    response.say("I'm sorry, I didn't catch that.")
    
    gather = response.gather(
        input="speech",
        action="/voice/collect-email",
        method="POST",
        speech_timeout="auto",
        timeout=10
    )
    gather.say("Would you like to provide an email address? Say your email or say no.")
    
    # Final fallback - skip email and go to appointments
    response.redirect("/voice/collect-email", method="POST")
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/webhook/voice")
async def handle_webhook_voice(request: Request):
    """Handle incoming calls from old webhook path - redirect to /voice/incoming"""
    logger.info(" Call received at /webhook/voice - redirecting to /voice/incoming handler")
    return await handle_voice_webhook(request)


@app.post("/voice")
async def handle_voice_root(request: Request):
    """Handle incoming calls from /voice path - redirect to /voice/incoming"""
    logger.info(" Call received at /voice - redirecting to /voice/incoming handler")
    return await handle_voice_webhook(request)




@app.post("/webhook/status")
async def handle_status_webhook(request: Request):
    """Handle call status updates"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    
    logger.info(f" Call {call_sid} status: {call_status}")
    
    return {"status": "ok"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "twilio_number": TWILIO_PHONE_NUMBER}


if __name__ == "__main__":
    print(f" Phone-based Patient Intake Agent")
    print(f" Twilio Number: {TWILIO_PHONE_NUMBER}")
    print(f" Webhook URL: https://your-domain.com/webhook/voice")
    print(f" Starting server on port 8000...")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
