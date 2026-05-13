import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

MONGODB_URI = "mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0"

async def check():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.propertyking
    
    user = await db.users.find_one({"email": "john.smith.pk@gmail.com"})
    print(f"User ID: {user['_id']}")
    
    query = {"listed_by": {"$in": [str(user["_id"]), user["_id"]]}}
    
    # Check properties
    count = await db.properties.count_documents(query)
    print(f"Properties found with $in query: {count}")
    
    if count > 0:
        cursor = db.properties.find(query).limit(1)
        async for p in cursor:
            print("Property ID:", p["_id"])
            print("Status:", p.get("status"))

if __name__ == "__main__":
    asyncio.run(check())
