"""
PropertyKING — Geocoding Service
Geocoding and reverse geocoding using Google Maps API.
"""

import httpx
from app.config import settings
from typing import Optional, Dict


async def geocode_address(address: str, city: str, state: str, zip_code: str) -> Optional[Dict]:
    """Convert address to coordinates using Google Maps Geocoding API."""
    full_address = f"{address}, {city}, {state} {zip_code}, USA"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "address": full_address,
                    "key": settings.GOOGLE_MAPS_API_KEY
                }
            )

            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                location = result["geometry"]["location"]

                return {
                    "lat": location["lat"],
                    "lng": location["lng"],
                    "formatted_address": result.get("formatted_address", full_address)
                }

    except Exception as e:
        print(f"[WARN] Geocoding failed: {e}")

    return None


async def reverse_geocode(lat: float, lng: float) -> Optional[Dict]:
    """Convert coordinates to address using Google Maps."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={
                    "latlng": f"{lat},{lng}",
                    "key": settings.GOOGLE_MAPS_API_KEY
                }
            )

            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                components = {c["types"][0]: c["long_name"]
                              for c in result.get("address_components", [])
                              if c.get("types")}

                return {
                    "formatted_address": result.get("formatted_address"),
                    "city": components.get("locality", ""),
                    "state": components.get("administrative_area_level_1", ""),
                    "state_short": next(
                        (c["short_name"] for c in result.get("address_components", [])
                         if "administrative_area_level_1" in c.get("types", [])),
                        ""
                    ),
                    "zip_code": components.get("postal_code", ""),
                    "county": components.get("administrative_area_level_2", ""),
                    "country": components.get("country", "USA")
                }

    except Exception as e:
        print(f"[WARN] Reverse geocoding failed: {e}")

    return None
