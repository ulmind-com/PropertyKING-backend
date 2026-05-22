"""
PropertyKING — Push Notification Service
Firebase Cloud Messaging integration.
"""

import firebase_admin
from firebase_admin import credentials, messaging
from app.config import settings
from app.database import get_database
from app.utils.helpers import now_utc
from typing import Optional, Dict, List
import os
import httpx

# Initialize Firebase Admin (only if credentials file exists)
_firebase_initialized = False


def init_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_initialized
    if _firebase_initialized:
        return

    cred_path = settings.FIREBASE_CREDENTIALS_PATH
    if os.path.exists(cred_path):
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("[OK] Firebase Admin initialized")
        except Exception as e:
            print(f"[WARN] Firebase init failed: {e}")
    else:
        print("[WARN] Firebase credentials file not found - push notifications disabled")


async def send_push_notification(
    user_id: str,
    title: str,
    body: str,
    notification_type: str = "system",
    data: Optional[Dict] = None,
    image_url: Optional[str] = None
) -> bool:
    """Send a push notification to a specific user and store in DB."""
    db = get_database()

    # Store notification in database
    notification_doc = {
        "user_id": user_id,
        "title": title,
        "body": body,
        "type": notification_type,
        "data": data or {},
        "image_url": image_url,
        "is_read": False,
        "created_at": now_utc()
    }
    await db.notifications.insert_one(notification_doc)

    # Try to send actual push notification if token exists
    user = await db.users.find_one({"_id": __import__("bson").ObjectId(user_id)})
    fcm_token = user.get("fcm_token") if user else None

    if fcm_token:
        print(f"[*] Attempting to send push notification to user {user_id} with token: {fcm_token}")
        if fcm_token.startswith("ExponentPushToken") or fcm_token.startswith("ExpoPushToken"):
            # Use Expo Push API (does not require Firebase to be initialized)
            try:
                async with httpx.AsyncClient() as client:
                    payload = {
                        "to": fcm_token,
                        "title": title,
                        "body": body,
                        "data": { "type": notification_type, **(data or {}) },
                        "sound": "default",
                        "priority": "high",
                        "channelId": "propertyking_channel"
                    }
                    if image_url:
                        payload["image"] = image_url
                    r = await client.post("https://exp.host/--/api/v2/push/send", json=payload)
                    resp_body = r.json() if r.status_code == 200 else {}
                    print(f"[EXPO PUSH] Status: {r.status_code}, Response: {resp_body}")
                    if r.status_code == 200:
                        ticket = resp_body.get("data", {})
                        if ticket.get("status") == "error":
                            print(f"[ERROR] Expo push REJECTED for {user_id}: {ticket.get('message')} | Details: {ticket.get('details')}")
                        else:
                            print(f"[OK] Expo push ticket OK for {user_id}, ticket_id: {ticket.get('id')}")
                        return True
                    else:
                        print(f"[WARN] Expo send failed for {user_id}: {r.text}")
            except Exception as e:
                print(f"[WARN] Expo send error for {user_id}: {e}")
        elif _firebase_initialized:
            # Use Firebase Admin SDK for raw FCM tokens
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                        image=image_url
                    ),
                    data={
                        "type": notification_type,
                        **(data or {})
                    },
                    token=fcm_token,
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            sound="default",
                            channel_id="propertyking_channel",
                            image=image_url
                        )
                    ),
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound="default",
                                badge=1,
                                mutable_content=True
                            )
                        ),
                        fcm_options=messaging.APNSFCMOptions(
                            image=image_url
                        ) if image_url else None
                    )
                )
                messaging.send(message)
                print(f"[OK] FCM push notification sent successfully to {user_id}")
                return True
            except Exception as e:
                print(f"[WARN] FCM send failed for {user_id}: {e}")
                return False
    else:
        print(f"[WARN] No fcm_token found for user {user_id}. Cannot send push notification.")

    return True  # Notification stored in DB even if FCM fails


async def send_bulk_notifications(
    user_ids: List[str],
    title: str,
    body: str,
    notification_type: str = "system",
    data: Optional[Dict] = None,
    image_url: Optional[str] = None
) -> int:
    """Send push notifications to multiple users."""
    success_count = 0
    for user_id in user_ids:
        result = await send_push_notification(user_id, title, body, notification_type, data, image_url)
        if result:
            success_count += 1
    return success_count


async def broadcast_notification(
    title: str,
    body: str,
    notification_type: str = "system",
    data: Optional[Dict] = None,
    target_roles: Optional[List[str]] = None,
    target_states: Optional[List[str]] = None,
    image_url: Optional[str] = None
) -> int:
    """Broadcast notification to all or filtered users."""
    db = get_database()

    query = {"is_active": True}
    if target_roles:
        query["role"] = {"$in": target_roles}
    if target_states:
        query["location.state"] = {"$in": target_states}

    # Get matching users
    cursor = db.users.find(query, {"_id": 1})
    user_ids = [str(doc["_id"]) async for doc in cursor]

    return await send_bulk_notifications(user_ids, title, body, notification_type, data, image_url)
