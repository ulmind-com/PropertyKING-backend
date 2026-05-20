import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0')
    db = client['propertyking']
    result = await db.users.update_one({'email': 'nandigram@test.com'}, {'$set': {'role': 'user'}})
    print(f"Fixed: {result.modified_count} user updated to role 'user'")

    # Also fix any other users with role 'lister'
    result2 = await db.users.update_many({'role': 'lister'}, {'$set': {'role': 'user'}})
    print(f"Fixed: {result2.modified_count} total lister roles changed to user")

asyncio.run(main())
