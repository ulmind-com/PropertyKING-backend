import requests

res = requests.options(
    "https://propertyking-backend.onrender.com/api/v1/properties/my-listings?page=1&limit=50",
    headers={
        "Origin": "http://localhost:8081",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"
    }
)
print("Status:", res.status_code)
print("Headers:")
for k, v in res.headers.items():
    print(f"{k}: {v}")
