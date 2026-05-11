"""Update all properties coordinates to Haldia/East Medinipur area for testing."""
import httpx, asyncio

API = "https://propertyking-backend.onrender.com/api/v1"

# Haldia & East Medinipur area coordinates
LOCATIONS = [
    {"lat": 22.0257, "lng": 88.0583, "note": "Haldia Township"},
    {"lat": 22.0667, "lng": 88.0698, "note": "Haldia Dock"},
    {"lat": 22.0450, "lng": 88.0900, "note": "Durgachak, Haldia"},
    {"lat": 22.2833, "lng": 87.8667, "note": "Tamluk, East Medinipur"},
    {"lat": 22.0100, "lng": 88.1200, "note": "Sutahata, East Medinipur"},
    {"lat": 22.0800, "lng": 88.0300, "note": "Haldia Refinery Area"},
]

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API}/auth/login", json={"email": "admin@propertyking.com", "password": "PropertyKING@2026!"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Admin logged in")

        r = await c.get(f"{API}/admin/properties", params={"status": "active", "limit": 50}, headers=headers)
        props = r.json().get("properties", [])
        print(f"Found {len(props)} active properties")

        for i, p in enumerate(props):
            if i >= len(LOCATIONS): break
            loc = LOCATIONS[i]
            # Update via direct DB call through property update endpoint
            update = {"location": {
                "address": p.get("city", "Haldia") + " Road",
                "city": p.get("city", "Haldia"),
                "state": p.get("state", "NY"),
                "zip_code": "10001",
                "coordinates": {"type": "Point", "coordinates": [loc["lng"], loc["lat"]]}
            }}
            r2 = await c.put(f"{API}/properties/{p['id']}", json=update, headers=headers)
            if r2.status_code == 200:
                print(f"[OK] {p['title'][:40]}... -> {loc['note']} ({loc['lat']}, {loc['lng']})")
            else:
                print(f"[FAIL] {p['title'][:40]}: {r2.text[:100]}")

        print("\nDone! All coordinates updated to Haldia/East Medinipur area.")

asyncio.run(main())
