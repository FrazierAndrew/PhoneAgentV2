# Phone-Based Patient Intake System

Automated phone system that collects patient information for medical appointment scheduling using Twilio.

## What It Does

Collects patient information over the phone:
- Name and date of birth
- Insurance (payer name and ID number)
- Referral information
- Chief medical complaint
- Mailing address (with validation)
- Contact information (phone and email)
- Schedules appointments and sends confirmation emails

## Requirements

- Python 3.9+
- Twilio account with phone number
- ngrok (for local development)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```env
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
```

3. Start the server:
```bash
python phone_agent.py
```

4. Expose with ngrok:
```bash
ngrok http 8000
```

5. Configure Twilio webhook to point to: `https://your-ngrok-url/voice/incoming`

## Usage

Call the configured Twilio number. The system will guide you through the intake process, validate your address, and send appointment confirmation emails.

## Configuration

Update email recipients in `send_appointment_confirmation_email()` function in `phone_agent.py`.

## Address Validation

Currently uses basic validation checking for street number, city, state, and ZIP. For production, integrate with USPS or Google Maps API.

## License

MIT