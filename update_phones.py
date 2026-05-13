"""
Script to add phone numbers to all users in the PropertyKING database.
Also ensures the inquiry and viewer phone fields are populated.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = "mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0"

async def update_phones():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.propertyking

    # 1. List all users and add phone numbers if missing
    users = []
    async for user in db.users.find({}):
        users.append(user)

    print(f"Total users: {len(users)}")

    phone_counter = 0
    for user in users:
        current_phone = user.get("phone")
        if not current_phone:
            # Generate a realistic US phone number based on user index
            phone_counter += 1
            phone = f"+1555{str(phone_counter).zfill(7)}"
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"phone": phone}}
            )
            print(f"  Updated {user.get('full_name', user.get('email', 'Unknown'))} -> {phone}")
        else:
            print(f"  {user.get('full_name', user.get('email', 'Unknown'))} already has phone: {current_phone}")

    # 2. Refresh all property_views with correct user phone numbers
    views = []
    async for v in db.property_views.find({}):
        views.append(v)
    
    print(f"\nTotal property views: {len(views)}")
    for v in views:
        user_id = v.get("user_id")
        if user_id:
            try:
                from bson import ObjectId
                try:
                    user = await db.users.find_one({"_id": ObjectId(user_id)})
                except:
                    user = await db.users.find_one({"_id": user_id})
                
                if user and user.get("phone"):
                    await db.property_views.update_one(
                        {"_id": v["_id"]},
                        {"$set": {
                            "user_phone": user.get("phone"),
                            "user_name": user.get("full_name"),
                            "user_email": user.get("email"),
                            "user_avatar": user.get("avatar"),
                        }}
                    )
                    print(f"  View updated for {user.get('full_name')} -> phone: {user.get('phone')}")
            except Exception as e:
                print(f"  Error updating view: {e}")

    # 3. Refresh all inquiries with correct user phone/email
    inqs = []
    async for inq in db.inquiries.find({}):
        inqs.append(inq)
    
    print(f"\nTotal inquiries: {len(inqs)}")
    for inq in inqs:
        user_id = inq.get("user_id")
        if user_id:
            try:
                from bson import ObjectId
                try:
                    user = await db.users.find_one({"_id": ObjectId(user_id)})
                except:
                    user = await db.users.find_one({"_id": user_id})
                
                if user:
                    update = {}
                    if not inq.get("contact_phone") and user.get("phone"):
                        update["contact_phone"] = user["phone"]
                    if user.get("phone"):
                        update["user_phone"] = user["phone"]
                    
                    if update:
                        await db.inquiries.update_one(
                            {"_id": inq["_id"]},
                            {"$set": update}
                        )
                        print(f"  Inquiry updated: {user.get('full_name')} -> phone: {user.get('phone')}")
            except Exception as e:
                print(f"  Error updating inquiry: {e}")

    print("\nDone! All users, views, and inquiries updated with phone numbers.")
    client.close()

asyncio.run(update_phones())
