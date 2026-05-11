"""Fix geo index directly on MongoDB."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URL = "mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0"

async def main():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client["propertyking"]
    
    # List current indexes
    indexes = await db.properties.index_information()
    print("Current indexes:")
    for name, info in indexes.items():
        print(f"  {name}: {info['key']}")
    
    # Drop any geo indexes
    for name in indexes:
        if "2dsphere" in name:
            print(f"\nDropping index: {name}")
            try:
                await db.properties.drop_index(name)
                print(f"  Dropped!")
            except Exception as e:
                print(f"  Error: {e}")
    
    # Create correct index
    print("\nCreating correct index: location.coordinates 2dsphere")
    await db.properties.create_index([("location.coordinates", "2dsphere")])
    print("Done!")
    
    # Verify
    indexes = await db.properties.index_information()
    print("\nNew indexes:")
    for name, info in indexes.items():
        print(f"  {name}: {info['key']}")
    
    # Test query
    print("\nTesting nearby query (Haldia)...")
    count = await db.properties.count_documents({
        "status": "active",
        "location.coordinates": {
            "$nearSphere": {
                "$geometry": {"type": "Point", "coordinates": [88.0583, 22.0257]},
                "$maxDistance": 20000
            }
        }
    })
    print(f"Found {count} properties near Haldia!")
    
    client.close()

asyncio.run(main())
