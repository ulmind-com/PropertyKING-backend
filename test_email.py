import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.email_service import send_welcome_email
from app.config import settings

async def test_email():
    print(f"Testing Brevo Email API...")
    print(f"API Key: {settings.EMAIL_API_KEY[:10]}...")
    print(f"Sender: {settings.FROM_EMAIL}")
    
    test_to = settings.FROM_EMAIL  # Send to yourself to test
    print(f"\nSending test welcome email to: {test_to}")
    
    result = await send_welcome_email(test_to, "Admin Tester")
    
    if result:
        print("\n[OK] SUCCESS! Email sent successfully via Brevo!")
        print("Please check your inbox (and spam folder) to verify.")
    else:
        print("\n[FAIL] FAILED! Could not send email.")

if __name__ == "__main__":
    asyncio.run(test_email())
