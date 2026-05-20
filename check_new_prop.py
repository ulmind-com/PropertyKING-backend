import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0')
    db = client['propertyking']
    # Get any property that has video or floor plan
    async for prop in db.properties.find().sort("updated_at", -1).limit(5):
        prop['_id'] = str(prop['_id'])
        import json
        print(f"--- {prop.get('title')} (status: {prop.get('status')}) ---")
        for k in ['video_url', 'floor_plan_url', 'floor_plan_urls', 'images']:
            val = prop.get(k)
            if val:
                print(f"  {k}: {json.dumps(val, indent=4, default=str)}")
        print()

asyncio.run(main())
