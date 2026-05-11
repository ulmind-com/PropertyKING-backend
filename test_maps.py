import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import httpx
from app.config import settings

async def test_geocoding():
    print(f"Testing with API Key: {settings.GOOGLE_MAPS_API_KEY[:10]}...")
    
    address = "1600 Amphitheatre Pkwy"
    city = "Mountain View"
    state = "CA"
    zip_code = "94043"
    full_address = f"{address}, {city}, {state} {zip_code}, USA"
    print(f"\nSearching for: {full_address}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": full_address,
                "key": settings.GOOGLE_MAPS_API_KEY
            }
        )
        data = response.json()
        
        if data.get("status") == "OK" and data.get("results"):
            result = data["results"][0]
            location = result["geometry"]["location"]
            print("\n[OK] SUCCESS! Google Maps API is working!")
            print(f"Latitude: {location['lat']}")
            print(f"Longitude: {location['lng']}")
        else:
            print(f"\n[FAIL] FAILED! Google API returned status: {data.get('status')}")
            print(f"Error Message: {data.get('error_message', 'No error message provided')}")

if __name__ == "__main__":
    asyncio.run(test_geocoding())
