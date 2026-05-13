import requests

def test():
    # 1. Login
    res = requests.post("https://propertyking-backend.onrender.com/api/v1/auth/login", json={
        "email": "john.smith.pk@gmail.com",
        "password": "test123456"
    })
    if res.status_code != 200:
        print("Login failed:", res.text)
        return
        
    token = res.json()["access_token"]
    print("Logged in successfully.")
    
    # 2. Call my-listings
    headers = {"Authorization": f"Bearer {token}"}
    res2 = requests.get("https://propertyking-backend.onrender.com/api/v1/properties/my-listings?page=1&limit=5", headers=headers)
    
    print("Status:", res2.status_code)
    try:
        data = res2.json()
        print("Total:", data.get("total"))
        print("Count returned:", len(data.get("properties", [])))
    except Exception as e:
        print("Failed to parse JSON:", res2.text)

if __name__ == "__main__":
    test()
