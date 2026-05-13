import requests

# 1. Fresh login
res = requests.post("https://propertyking-backend.onrender.com/api/v1/auth/login", json={
    "email": "john.smith.pk@gmail.com",
    "password": "test123456"
})
print("Login status:", res.status_code)
if res.status_code != 200:
    print("Login failed:", res.text)
    exit()

data = res.json()
token = data["access_token"]
print("Token (first 30 chars):", token[:30])

# 2. Test /users/me
headers = {"Authorization": f"Bearer {token}"}
me = requests.get("https://propertyking-backend.onrender.com/api/v1/users/me", headers=headers)
print("\n/users/me status:", me.status_code)
if me.status_code == 200:
    u = me.json()
    print("User ID:", u.get("id"))
    print("Listings count:", u.get("listings_count"))
else:
    print("Error:", me.text)

# 3. Test /my-listings
ml = requests.get("https://propertyking-backend.onrender.com/api/v1/properties/my-listings?page=1&limit=5", headers=headers)
print("\n/my-listings status:", ml.status_code)
if ml.status_code == 200:
    d = ml.json()
    print("Total:", d.get("total"))
    print("Count:", len(d.get("properties", [])))
    print("Total pages:", d.get("total_pages"))
else:
    print("Error:", ml.text)
