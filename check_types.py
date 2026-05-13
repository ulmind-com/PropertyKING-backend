import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = "mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0"

async def check():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.propertyking
    
    p = await db.properties.find_one({})
    print("Property ID:", p["_id"], type(p["_id"]))
    print("listed_by:", p.get("listed_by"), type(p.get("listed_by")))

if __name__ == "__main__":
    asyncio.run(check())
