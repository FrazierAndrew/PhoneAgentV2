"""
Patient Intake Voice AI Agent
Collects patient information for medical appointment scheduling
"""

import asyncio
import logging
from typing import Annotated
from datetime import datetime, timedelta
import random
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice import AgentSession, Agent
from livekit.plugins import openai, deepgram, cartesia, silero

logger = logging.getLogger("patient-intake-agent")
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


async def validate_address(address: str) -> dict:
    """
    Validate address using an external API
    For demo purposes, we'll use a simple validation that checks for completeness
    In production, integrate with USPS, Google Maps, or similar services
    """
    # Simple validation: check if address has required components
    address_lower = address.lower()
    
    # Basic heuristic checks
    has_numbers = any(char.isdigit() for char in address)
    has_state = any(state in address_lower for state in [
        'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
        'alabama', 'alaska', 'arizona', 'california', 'colorado', 'florida',
        'ny', 'new york', 'tx', 'texas', 'il', 'illinois'
    ])
    has_zip = len([word for word in address.split() if word.isdigit() and len(word) == 5]) > 0
    
    parts = address.split(',')
    has_city = len(parts) >= 2
    
    missing_fields = []
    if not has_numbers:
        missing_fields.append("street number")
    if not has_city:
        missing_fields.append("city")
    if not has_state:
        missing_fields.append("state")
    if not has_zip:
        missing_fields.append("ZIP code")
    
    is_valid = len(missing_fields) == 0
    
    return {
        "valid": is_valid,
        "missing_fields": missing_fields,
        "formatted_address": address if is_valid else None,
        "message": "Address is valid" if is_valid else f"Address is missing: {', '.join(missing_fields)}"
    }


# Mock database of available providers and time slots
AVAILABLE_PROVIDERS = [
    {"name": "Dr. Sarah Johnson", "specialty": "Family Medicine", "location": "Main Office"},
    {"name": "Dr. Michael Chen", "specialty": "Internal Medicine", "location": "Downtown Clinic"},
    {"name": "Dr. Emily Rodriguez", "specialty": "Pediatrics", "location": "Children's Center"},
    {"name": "Dr. James Williams", "specialty": "Family Medicine", "location": "Main Office"},
]


def generate_available_times(num_slots=3):
    """Generate fake available appointment times"""
    times = []
    base_date = datetime.now() + timedelta(days=1)
    
    for i in range(num_slots):
        day_offset = random.randint(1, 7)
        hour = random.choice([9, 10, 11, 14, 15, 16])
        minute = random.choice([0, 30])
        
        appointment_time = base_date + timedelta(days=day_offset)
        appointment_time = appointment_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        times.append(appointment_time)
    
    return sorted(times)


# Define tools using the function_tool decorator
@llm.function_tool(description="Store the patient's name. Call this when the patient provides their full name.")
async def store_patient_name(
    name: Annotated[str, "The patient's full name"]
):
    """Store patient name"""
    patient_info["name"] = name
    patient_info["stage"] = "dob"
    logger.info(f"Stored patient name: {name}")
    return f"Thank you, {name}. I have recorded your name."


@llm.function_tool(description="Store the patient's date of birth. Call this when the patient provides their DOB.")
async def store_date_of_birth(
    date_of_birth: Annotated[str, "Patient's date of birth in MM/DD/YYYY format"]
):
    """Store patient date of birth"""
    patient_info["date_of_birth"] = date_of_birth
    patient_info["stage"] = "insurance"
    logger.info(f"Stored DOB: {date_of_birth}")
    return "Date of birth recorded. Now let's collect your insurance information."


@llm.function_tool(description="Store insurance information including payer name and ID number")
async def store_insurance(
    payer_name: Annotated[str, "Insurance payer/company name"],
    insurance_id: Annotated[str, "Insurance ID or member number"]
):
    """Store insurance information"""
    patient_info["insurance_payer"] = payer_name
    patient_info["insurance_id"] = insurance_id
    patient_info["stage"] = "referral"
    logger.info(f"Stored insurance: {payer_name}, ID: {insurance_id}")
    return "Insurance information saved."


@llm.function_tool(description="Record whether patient has a referral and the referring physician name if applicable")
async def store_referral_info(
    has_referral: Annotated[bool, "Whether the patient has a referral"],
    physician_name: Annotated[str | None, "Name of referring physician if they have a referral"] = None
):
    """Store referral information"""
    patient_info["has_referral"] = has_referral
    patient_info["referral_physician"] = physician_name if has_referral else None
    patient_info["stage"] = "complaint"
    logger.info(f"Stored referral: {has_referral}, Physician: {physician_name}")
    return "Referral information recorded."


@llm.function_tool(description="Store the patient's chief medical complaint or reason for visit")
async def store_chief_complaint(
    complaint: Annotated[str, "The patient's medical complaint or reason for visit"]
):
    """Store chief complaint"""
    patient_info["chief_complaint"] = complaint
    patient_info["stage"] = "address"
    logger.info(f"Stored complaint: {complaint}")
    return "Chief complaint recorded. Now I need your address."


@llm.function_tool(description="Validate and store the patient's mailing address. This will check if the address is valid and complete.")
async def store_and_validate_address(
    address: Annotated[str, "Complete mailing address including street, city, state, and ZIP"]
):
    """Store and validate address using external API"""
    validation_result = await validate_address(address)
    
    patient_info["address"] = address
    patient_info["address_valid"] = validation_result["valid"]
    
    logger.info(f"Address validation: {validation_result}")
    
    if validation_result["valid"]:
        patient_info["stage"] = "contact"
        return "Address verified and saved."
    else:
        return f"I'm sorry, but the address appears to be incomplete or invalid. {validation_result['message']}. Please provide the complete address."


@llm.function_tool(description="Store patient contact information including phone and optional email")
async def store_contact_info(
    phone: Annotated[str, "Patient's phone number"],
    email: Annotated[str | None, "Patient's email address (optional)"] = None
):
    """Store contact information"""
    patient_info["phone"] = phone
    patient_info["email"] = email
    patient_info["stage"] = "scheduling"
    logger.info(f"Stored contact: phone={phone}, email={email}")
    return "Contact information saved. Now let me find available appointment times for you."


@llm.function_tool(description="Get available providers and appointment times to offer the patient")
async def get_available_appointments():
    """Get available appointments"""
    # Select random providers
    num_providers = min(2, len(AVAILABLE_PROVIDERS))
    selected_providers = random.sample(AVAILABLE_PROVIDERS, num_providers)
    
    appointments = []
    for provider in selected_providers:
        times = generate_available_times(2)
        for time in times:
            appointments.append({
                "provider": provider["name"],
                "specialty": provider["specialty"],
                "location": provider["location"],
                "datetime": time.strftime("%A, %B %d at %I:%M %p")
            })
    
    patient_info["stage"] = "complete"
    logger.info(f"Generated appointments: {appointments}")
    
    # Format for the agent to read
    formatted = "Here are the available appointments:\n"
    for i, apt in enumerate(appointments, 1):
        formatted += f"{i}. {apt['provider']} ({apt['specialty']}) at {apt['location']} - {apt['datetime']}\n"
    
    return formatted


@llm.function_tool(description="Get a summary of all collected patient information")
async def get_patient_summary():
    """Get summary of collected information"""
    return json.dumps(patient_info, indent=2)


async def entrypoint(ctx: JobContext):
    """Main entrypoint for the agent"""
    
    logger.info(f"Starting patient intake agent for room: {ctx.room.name}")
    
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
    
    # Initialize the agent session with voice pipeline
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
    )
    
    # Define the agent with instructions
    agent = Agent(
        instructions="""You are a friendly and professional medical receptionist conducting patient intake.

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

Start by greeting the patient and asking for their full name.""",
        tools=tools,
    )
    
    # Start the session
    await session.start(
        ctx.room,
        agent=agent,
    )
    
    # Send initial greeting
    logger.info("Sending initial greeting to patient")
    await session.say(
        "Hello! Thank you for calling. I'm here to help you schedule an appointment. May I have your full name, please?"
    )
    
    # Keep the agent running
    await session.wait_for_completion()
    
    logger.info("Patient intake session completed")
    logger.info(f"Final patient data: {patient_info}")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="patient-intake-agent",
            # Auto-join any room that gets created
            ws_url=os.getenv("LIVEKIT_URL"),
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        ),
    )
