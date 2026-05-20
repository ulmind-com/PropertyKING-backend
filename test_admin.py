import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Login
        res = await client.post("https://propertyking-backend.onrender.com/api/v1/auth/login", json={"email": "admin@propertyking.com", "password": "PropertyKING@2026!"})
        print("Login:", res.status_code, res.text)
        if res.status_code == 200:
            token = res.json()["access_token"]
            # Fetch properties
            res2 = await client.get("https://propertyking-backend.onrender.com/api/v1/admin/properties?page=1&limit=10&status=pending", headers={"Authorization": f"Bearer {token}"})
            print("Properties:", res2.status_code, res2.text)

asyncio.run(main())
