import asyncio
from app.database import get_database
from app.routes.admin import admin_list_properties
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0')
    import app.database
    app.database.client = client
    app.database.db = client['propertyking']
    try:
        res = await admin_list_properties(page=1, limit=10, status_filter='pending', search=None, admin={})
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
