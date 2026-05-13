"""
Redistribute property types more sensibly.
House/Condo/Apartment should dominate as they are most common.
"""
from pymongo import MongoClient

MONGODB_URL = "mongodb+srv://handymanpro1980_db_user:5G2PmKM!%23ZRwpnz@cluster0.k6kdaqb.mongodb.net/propertyking?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(MONGODB_URL)
db = client["propertyking"]

# Fetch types by name so order is deterministic
types_by_name = {t["name"]: t["_id"] for t in db["property_types"].find()}
print("Types loaded:", list(types_by_name.keys()))

# Fetch all properties
properties = list(db["properties"].find({}, {"_id": 1, "title": 1}))
print(f"Total properties: {len(properties)}")

# Sensible distribution for 30 properties
plan = [
    ("House",        8),
    ("Condo",        5),
    ("Apartment",    5),
    ("Townhouse",    4),
    ("Villa",        3),
    ("Multi-Family", 2),
    ("Commercial",   1),
    ("Land",         1),
    ("Mobile Home",  1),
]

# Build assignment list
assignments = []
for type_name, count in plan:
    type_id = types_by_name.get(type_name)
    if type_id:
        assignments.extend([(type_id, type_name)] * count)

# Pad remainder with House if needed
while len(assignments) < len(properties):
    assignments.append((types_by_name["House"], "House"))
assignments = assignments[:len(properties)]

# Update
print("\nUpdating...")
for prop, (type_id, type_name) in zip(properties, assignments):
    db["properties"].update_one(
        {"_id": prop["_id"]},
        {"$set": {"property_type_id": type_id, "property_type_name": type_name}}
    )

print("Done!")

# Final count
print("\nFinal distribution:")
pipeline = [
    {"$group": {"_id": "$property_type_name", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
for r in db["properties"].aggregate(pipeline):
    print(f"  {r['_id']}: {r['count']}")

client.close()
