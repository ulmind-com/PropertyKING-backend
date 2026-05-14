import requests
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone

# Connect to MongoDB directly
# First let's find the MongoDB URI from the backend config
import os

# Read .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
mongo_uri = None
with open(env_path, 'r') as f:
    for line in f:
        if line.startswith('MONGODB_URL'):
            mongo_uri = line.split('=', 1)[1].strip().strip('"').strip("'")
            break

if not mongo_uri:
    print("Could not find MongoDB URI in .env")
    # Try alternative key names
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if 'mongo' in line.lower() or 'db' in line.lower():
                print(f"  Found: {line[:60]}...")
    exit()

print(f"MongoDB URI: {mongo_uri[:40]}...")

client = MongoClient(mongo_uri)
db_name = mongo_uri.split('/')[-1].split('?')[0] if '/' in mongo_uri else 'propertyking'
db = client[db_name]

# Approve all pending properties
result = db.properties.update_many(
    {'status': 'pending'},
    {'$set': {
        'status': 'active',
        'listed_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
    }}
)

print(f"Approved: {result.modified_count} pending properties")

# Also make john.smith admin
result2 = db.users.update_one(
    {'email': 'john.smith.pk@gmail.com'},
    {'$set': {'role': 'admin'}}
)
print(f"John Smith set as admin: {result2.modified_count} document(s)")

client.close()
print("Done!")
