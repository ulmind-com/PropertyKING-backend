import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0')
    db = client['propertyking']
    prop = await db.properties.find_one({'status': {'$ne': 'pending'}})
    if prop:
        prop['_id'] = str(prop['_id'])
        import json
        print(json.dumps(prop, indent=2, default=str))
    else:
        print("No non-pending property found")

asyncio.run(main())
