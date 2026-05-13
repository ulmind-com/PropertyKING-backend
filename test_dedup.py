import requests

def test_dedup():
    print("Testing deduplication issue...")
    
    # Let's get the properties from live APIs
    print("Fetching APIs...")
    res_nearby = requests.get("https://propertyking-backend.onrender.com/api/v1/properties/nearby?lat=37.7749&lng=-122.4194&radius_miles=5000&limit=15")
    res_feat = requests.get("https://propertyking-backend.onrender.com/api/v1/properties/recommendations?limit=15")
    res_top = requests.get("https://propertyking-backend.onrender.com/api/v1/properties/top-viewed?limit=15")
    
    nearbyProps = res_nearby.json().get("properties", []) if res_nearby.status_code == 200 else []
    featuredProps = res_feat.json().get("properties", []) if res_feat.status_code == 200 else []
    topViewedProps = res_top.json().get("properties", []) if res_top.status_code == 200 else []
    
    print(f"Nearby count: {len(nearbyProps)}")
    print(f"Featured count: {len(featuredProps)}")
    print(f"TopViewed count: {len(topViewedProps)}")
    
    # Simulate frontend dedup
    finalNearby = nearbyProps[:5]
    nearbyIds = {p["id"] for p in finalNearby}
    
    finalFeatured = [p for p in featuredProps if p["id"] not in nearbyIds][:5]
    featuredIds = {p["id"] for p in finalFeatured}
    
    finalTopViewed = [p for p in topViewedProps if p["id"] not in nearbyIds and p["id"] not in featuredIds][:5]
    
    print(f"\nFinal Nearby count: {len(finalNearby)}")
    print(f"Final Featured count: {len(finalFeatured)}")
    print(f"Final TopViewed count: {len(finalTopViewed)}")
    
    print("\nIf any count is 0, that section will not show in the app!")

if __name__ == "__main__":
    test_dedup()
