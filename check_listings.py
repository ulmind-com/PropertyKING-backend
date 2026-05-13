import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGODB_URI = "mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0"
async def check():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.propertyking
    
    user = await db.users.find_one({"email": "john.smith.pk@gmail.com"})
    if not user:
        print("User not found!")
        return
        
    print(f"User ID: {user['_id']}")
    
    # Check properties
    count = await db.properties.count_documents({"listed_by": str(user["_id"])})
    print(f"Properties listed by string ID: {count}")
    
    count_obj = await db.properties.count_documents({"listed_by": user["_id"]})
    print(f"Properties listed by ObjectId: {count_obj}")
    
    if count == 0 and count_obj == 0:
        print("Checking any properties in DB to see what 'listed_by' looks like...")
        prop = await db.properties.find_one()
        if prop:
            print(f"Sample property listed_by: {prop.get('listed_by')} (type: {type(prop.get('listed_by'))})")

if __name__ == "__main__":
    asyncio.run(check())
