import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from datetime import datetime, timezone
from bson import ObjectId

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def main():
    client = AsyncIOMotorClient('mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0')
    db = client['propertyking']

    email = 'nandigram@test.com'
    password = 'Password123!'

    # Create User
    existing = await db.users.find_one({'email': email})
    if existing:
        await db.users.delete_one({'_id': existing['_id']})
    
    user_id = ObjectId()
    now_utc = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    user_doc = {
        '_id': user_id,
        'full_name': 'Nandigram Agent',
        'email': email,
        'phone': '9876543210',
        'password_hash': pwd_context.hash(password),
        'role': 'lister',
        'is_active': True,
        'verified': True,
        'created_at': now_utc,
        'updated_at': now_utc
    }
    await db.users.insert_one(user_doc)
    print(f'User created: {email} / {password}')

    # Create Property
    prop_doc = {
        'title': 'Beautiful Riverside Villa in Nandigram',
        'description': 'A gorgeous 3BHK villa located right near the Haldi river in Nandigram. Perfect for a peaceful retreat with amazing sunset views.',
        'property_type': 'Villa',
        'listing_type': 'For Sale',
        'price': 4500000,
        'currency': 'INR',
        'address': 'Nandigram River Drive, Block 1',
        'city': 'Nandigram',
        'state': 'West Bengal',
        'zip_code': '721631',
        'country': 'India',
        'latitude': 21.9961,
        'longitude': 87.9786,
        'bedrooms': 3,
        'bathrooms': 2,
        'area_sqft': 1500,
        'year_built': 2024,
        'amenities': ['Garden', 'River View', 'Parking', 'WiFi'],
        'images': ['https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80'],
        'lister_id': str(user_id),
        'lister_name': 'Nandigram Agent',
        'contact_email': email,
        'contact_phone': '9876543210',
        'status': 'pending',
        'views': 0,
        'favorites': 0,
        'inquiries': 0,
        'created_at': now_utc,
        'updated_at': now_utc
    }
    await db.properties.insert_one(prop_doc)
    print('Property created successfully with pending status.')

if __name__ == '__main__':
    asyncio.run(main())
