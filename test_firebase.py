import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.push_notification import init_firebase

def test_firebase():
    print("Testing Firebase Admin Initialization...")
    
    # Force re-initialization to see the logs
    init_firebase()
    
    from firebase_admin import get_app
    try:
        app = get_app()
        print(f"\n[OK] SUCCESS! Firebase App Initialized: {app.name}")
        print("Push notifications are ready to be sent to devices!")
    except ValueError as e:
        print(f"\n[FAIL] FAILED! Firebase not initialized: {e}")

if __name__ == "__main__":
    test_firebase()
