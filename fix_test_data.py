import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0')
    db = client['propertyking']
    
    # Find the bad property
    prop = await db.properties.find_one({'contact_email': 'nandigram@test.com'})
    if prop and 'images' in prop:
        fixed_images = []
        for img in prop['images']:
            if isinstance(img, str):
                fixed_images.append({'url': img, 'is_primary': True})
            else:
                fixed_images.append(img)
        
        await db.properties.update_one({'_id': prop['_id']}, {'$set': {'images': fixed_images}})
        print("Fixed images in property")
    else:
        print("Property not found or no images")

asyncio.run(main())
