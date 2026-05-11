"""Quick approve all pending properties."""
import httpx, asyncio

API = "https://propertyking-backend.onrender.com/api/v1"

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        # Login as admin
        r = await c.post(f"{API}/auth/login", json={"email": "admin@propertyking.com", "password": "PropertyKING@2026!"})
        if r.status_code != 200:
            print(f"Admin login failed: {r.text}")
            return
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Admin logged in")

        # Get pending properties
        r = await c.get(f"{API}/admin/properties", params={"status": "pending", "limit": 50}, headers=headers)
        props = r.json().get("properties", [])
        print(f"Found {len(props)} pending properties")

        for p in props:
            r = await c.put(f"{API}/admin/properties/{p['id']}/approve", headers=headers)
            if r.status_code == 200:
                print(f"[OK] Approved: {p['title'][:50]}")
            else:
                print(f"[FAIL] {p['title'][:50]}: {r.text[:80]}")

        print("Done! All properties approved.")

asyncio.run(main())
