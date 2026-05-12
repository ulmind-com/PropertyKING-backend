"""
Seed Script: Register a test user and add 6 sample US properties.
Run: python seed_properties.py
"""
import httpx, asyncio

API = "https://propertyking-backend.onrender.com/api/v1"

USER = {"full_name": "John Smith", "email": "john.smith.pk@gmail.com", "password": "test123456"}

PROPERTIES = [
    {
        "title": "Luxury 4BR Brownstone in Brooklyn Heights",
        "description": "Stunning renovated brownstone featuring 4 spacious bedrooms, original hardwood floors, a chef's kitchen with marble countertops, and a private garden. Walking distance to Brooklyn Bridge Park and all major transit.",
        "listing_type": "sale", "price": 2450000, "price_unit": "total",
        "details": {"bedrooms": 4, "bathrooms": 3.5, "total_sqft": 3200, "year_built": 1890, "stories": 3, "heating": "Central", "cooling": "Central AC"},
        "location": {"address": "128 Willow Street", "city": "Brooklyn", "state": "NY", "zip_code": "11201", "county": "Kings County",
                     "coordinates": {"type": "Point", "coordinates": [-73.9957, 40.6975]}},
        "images": [{"url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800", "is_primary": True, "order": 0},
                   {"url": "https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=800", "is_primary": False, "order": 1},
                   {"url": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800", "is_primary": False, "order": 2},
                   {"url": "https://images.unsplash.com/photo-1600573472550-8090b5e0745e?w=800", "is_primary": False, "order": 3},
                   {"url": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=800", "is_primary": False, "order": 4}],
        "video_url": "https://www.youtube.com/watch?v=y9j-BL5ocW8",
        "floor_plan_urls": [
            "https://images.unsplash.com/photo-1574359173348-71e1e5c6b48c?w=800",
            "https://images.unsplash.com/photo-1503387837-b154d5074bd2?w=800"
        ]
    },
    {
        "title": "Modern 2BR Condo with Bay Views in Miami",
        "description": "Experience waterfront living in this sleek 2-bedroom condo with panoramic Biscayne Bay views. Features floor-to-ceiling windows, Italian porcelain floors, and resort-style amenities including pool and gym.",
        "listing_type": "rent", "price": 4200, "price_unit": "per_month",
        "details": {"bedrooms": 2, "bathrooms": 2, "total_sqft": 1350, "year_built": 2021, "stories": 1},
        "location": {"address": "501 NE 31st Street", "city": "Miami", "state": "FL", "zip_code": "33137", "county": "Miami-Dade County",
                     "coordinates": {"type": "Point", "coordinates": [-80.1867, 25.8095]}},
        "images": [{"url": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800", "is_primary": True, "order": 0},
                   {"url": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800", "is_primary": False, "order": 1},
                   {"url": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800", "is_primary": False, "order": 2},
                   {"url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800", "is_primary": False, "order": 3}],
        "video_url": "https://www.youtube.com/watch?v=MP9AHOxICnU",
        "floor_plan_urls": [
            "https://images.unsplash.com/photo-1574359173348-71e1e5c6b48c?w=800"
        ]
    },
    {
        "title": "Charming 3BR Ranch Home in Austin",
        "description": "Beautifully updated single-story ranch in the heart of Austin. Open floor plan with vaulted ceilings, updated kitchen with quartz counters, large backyard with mature trees. Great neighborhood near hiking trails.",
        "listing_type": "sale", "price": 575000, "price_unit": "total",
        "details": {"bedrooms": 3, "bathrooms": 2, "total_sqft": 1800, "year_built": 1975, "garage_spaces": 2, "parking_type": "attached_garage"},
        "location": {"address": "2415 Barton Hills Drive", "city": "Austin", "state": "TX", "zip_code": "78704", "county": "Travis County",
                     "coordinates": {"type": "Point", "coordinates": [-97.7729, 30.2421]}},
        "images": [{"url": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800", "is_primary": True, "order": 0},
                   {"url": "https://images.unsplash.com/photo-1583608205776-bfd35f0d9f83?w=800", "is_primary": False, "order": 1},
                   {"url": "https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde?w=800", "is_primary": False, "order": 2},
                   {"url": "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=800", "is_primary": False, "order": 3}],
        "floor_plan_urls": [
            "https://images.unsplash.com/photo-1503387837-b154d5074bd2?w=800",
            "https://images.unsplash.com/photo-1574359173348-71e1e5c6b48c?w=800"
        ]
    },
    {
        "title": "Spacious 5BR Family Home in Naperville",
        "description": "Gorgeous 5-bedroom colonial on a quiet cul-de-sac in top-rated school district. Features a gourmet kitchen, finished basement with home theater, and professionally landscaped yard with in-ground pool.",
        "listing_type": "sale", "price": 825000, "price_unit": "total",
        "details": {"bedrooms": 5, "bathrooms": 4, "total_sqft": 4200, "year_built": 2005, "garage_spaces": 3, "basement": "finished", "stories": 2},
        "location": {"address": "1847 Clover Lane", "city": "Naperville", "state": "IL", "zip_code": "60540", "county": "DuPage County",
                     "coordinates": {"type": "Point", "coordinates": [-88.1535, 41.7508]}},
        "images": [{"url": "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=800", "is_primary": True, "order": 0},
                   {"url": "https://images.unsplash.com/photo-1600573472550-8090b5e0745e?w=800", "is_primary": False, "order": 1},
                   {"url": "https://images.unsplash.com/photo-1600607686527-6fb886090705?w=800", "is_primary": False, "order": 2},
                   {"url": "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800", "is_primary": False, "order": 3},
                   {"url": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800", "is_primary": False, "order": 4}],
        "video_url": "https://www.youtube.com/watch?v=dCKvFb2HTGY",
        "floor_plan_urls": [
            "https://images.unsplash.com/photo-1574359173348-71e1e5c6b48c?w=800",
            "https://images.unsplash.com/photo-1503387837-b154d5074bd2?w=800"
        ]
    },
    {
        "title": "Downtown LA Loft with Rooftop Access",
        "description": "Industrial-chic loft in the Arts District with 16-foot ceilings, exposed brick walls, and polished concrete floors. Building features rooftop pool, co-working space, and 24/7 concierge. Walk to restaurants and galleries.",
        "listing_type": "rent", "price": 3500, "price_unit": "per_month",
        "details": {"bedrooms": 1, "bathrooms": 1, "total_sqft": 950, "year_built": 2019},
        "location": {"address": "825 E 4th Street", "city": "Los Angeles", "state": "CA", "zip_code": "90013", "county": "Los Angeles County",
                     "coordinates": {"type": "Point", "coordinates": [-118.2330, 34.0407]}},
        "images": [{"url": "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800", "is_primary": True, "order": 0},
                   {"url": "https://images.unsplash.com/photo-1536376072261-38c75010e6c9?w=800", "is_primary": False, "order": 1},
                   {"url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800", "is_primary": False, "order": 2},
                   {"url": "https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=800", "is_primary": False, "order": 3}],
        "floor_plan_urls": [
            "https://images.unsplash.com/photo-1503387837-b154d5074bd2?w=800"
        ]
    },
    {
        "title": "Waterfront 3BR Townhouse in Seattle",
        "description": "Stunning three-level townhouse on the waterfront in West Seattle with breathtaking Puget Sound and Olympic Mountain views. Features a chef's kitchen, gas fireplace, private deck, and 2-car garage.",
        "listing_type": "sale", "price": 1150000, "price_unit": "total",
        "details": {"bedrooms": 3, "bathrooms": 2.5, "total_sqft": 2400, "year_built": 2018, "garage_spaces": 2, "stories": 3, "heating": "Forced Air", "cooling": "Heat Pump"},
        "location": {"address": "3210 Harbor Avenue SW", "city": "Seattle", "state": "WA", "zip_code": "98126", "county": "King County",
                     "coordinates": {"type": "Point", "coordinates": [-122.3755, 47.5745]}},
        "images": [{"url": "https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde?w=800", "is_primary": True, "order": 0},
                   {"url": "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800", "is_primary": False, "order": 1},
                   {"url": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=800", "is_primary": False, "order": 2},
                   {"url": "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=800", "is_primary": False, "order": 3},
                   {"url": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800", "is_primary": False, "order": 4}],
        "video_url": "https://www.youtube.com/watch?v=y9j-BL5ocW8",
        "floor_plan_urls": [
            "https://images.unsplash.com/photo-1574359173348-71e1e5c6b48c?w=800",
            "https://images.unsplash.com/photo-1503387837-b154d5074bd2?w=800"
        ]
    },
]

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # Register user
        print("Registering test user...")
        r = await c.post(f"{API}/auth/register", json=USER)
        if r.status_code == 201:
            token = r.json()["access_token"]
            print(f"✅ User registered: {USER['email']}")
        elif r.status_code == 409:
            print("User exists, logging in...")
            r = await c.post(f"{API}/auth/login", json={"email": USER["email"], "password": USER["password"]})
            token = r.json()["access_token"]
            print(f"✅ Logged in: {USER['email']}")
        else:
            print(f"❌ Registration failed: {r.text}")
            return

        headers = {"Authorization": f"Bearer {token}"}

        # Get property types
        r = await c.get(f"{API}/property-types", headers=headers)
        types = r.json()
        if not types:
            print("❌ No property types found. Add some from admin first.")
            return
        type_id = types[0]["id"]
        print(f"Using property type: {types[0]['name']} ({type_id})")

        # Create properties
        for i, prop in enumerate(PROPERTIES):
            prop["property_type_id"] = type_id
            r = await c.post(f"{API}/properties", json=prop, headers=headers)
            if r.status_code == 201:
                print(f"✅ Property {i+1}/6: {prop['title'][:40]}...")
            else:
                print(f"❌ Property {i+1} failed: {r.text[:100]}")

        print("\n🎉 Done! 6 properties seeded.")
        print("Note: Properties are in 'pending' status. Approve them from Admin panel to make visible.")

asyncio.run(main())
