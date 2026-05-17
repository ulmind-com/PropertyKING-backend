import asyncio
import os
import sys
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    load_dotenv()
    uri = os.getenv('MONGODB_URL')
    if not uri:
        print("MONGODB_URL not found")
        sys.exit(1)
        
    client = AsyncIOMotorClient(uri)
    db = client.get_database(os.getenv('DATABASE_NAME', 'propertyking'))
    
    # Update user role to admin
    user = await db.users.find_one_and_update(
        {'email': 'john.smith.pk@gmail.com'}, 
        {'$set': {'role': 'admin'}}
    )
    
    if user:
        print(f"Updated user role to admin for: {user.get('email')}")
    else:
        print("User not found")
        
    # Approve pending properties
    result = await db.properties.update_many(
        {'status': 'pending'}, 
        {'$set': {'status': 'active'}}
    )
    
    print(f"Approved {result.modified_count} pending properties.")
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
