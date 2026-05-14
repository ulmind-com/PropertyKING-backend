import requests
r = requests.get('https://propertyking-backend.onrender.com/api/v1/properties', params={'limit':50,'city':'Austin'})
data = r.json()
props = data.get('properties',[])
print(f'Total: {len(props)} properties in Austin, TX\n')
for i, p in enumerate(props):
    title = p.get('title','?')
    price = p.get('price',0)
    lt = p.get('listing_type','?')
    beds = p.get('details',{}).get('bedrooms',0)
    baths = p.get('details',{}).get('bathrooms',0)
    sqft = p.get('details',{}).get('total_sqft','N/A')
    print(f"  {i+1}. {title}")
    print(f"     ${price:,.0f} ({lt}) | {beds}bd/{baths}ba | {sqft} sqft")
