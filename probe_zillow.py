"""
PropertyKING — RapidAPI Zillow probe

Run this after putting RAPIDAPI_KEY in .env and subscribing to the API. It
checks, against the live service:

  * whether the key is subscribed to a Zillow API at all (and which one)
  * how much monthly quota is left
  * that a real search returns listings
  * the exact response field names, so the adapter's mapping can be verified

It never prints the API key, and spends 2-3 requests.

    python probe_zillow.py
"""

import asyncio
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("RAPIDAPI_KEY", "").strip()
HOST = os.getenv("ZILLOW_RAPIDAPI_HOST", "zillow-real-estate-data-api.p.rapidapi.com").strip()

SUBSCRIBE_URL = "https://rapidapi.com/ReefAPI/api/zillow-real-estate-data-api/pricing"

# Zillow listing APIs we know how to talk to. A RapidAPI key only works on APIs
# the account has actually subscribed to, so we try each and report which answer.
KNOWN_HOSTS = [
    ("zillow-real-estate-data-api.p.rapidapi.com", "/zillow/v1/search", "POST"),
    ("real-time-zillow-data.p.rapidapi.com",       "/search",           "GET"),
    ("zillow-working-api.p.rapidapi.com",          "/search/byaddress", "GET"),
    ("zillow56.p.rapidapi.com",                    "/search",           "GET"),
]

G, R, Y, D = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def quota(resp):
    h = resp.headers
    left = h.get("x-ratelimit-requests-remaining")
    limit = h.get("x-ratelimit-requests-limit")
    return f"{left}/{limit}" if left else "unknown"


def extract_items(payload):
    """The listing array has lived under several keys across versions."""
    if isinstance(payload, list):
        return [i for i in payload if isinstance(i, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "listings", "properties", "props", "data", "items"):
        v = payload.get(key)
        if isinstance(v, list):
            return [i for i in v if isinstance(i, dict)]
        if isinstance(v, dict):
            for inner in ("items", "results", "listings", "properties"):
                if isinstance(v.get(inner), list):
                    return [i for i in v[inner] if isinstance(i, dict)]
    return []


async def discover(key):
    print("\n\033[1m1. Which Zillow API is this key subscribed to?\033[0m")
    found = []
    async with httpx.AsyncClient(timeout=45.0) as c:
        for host, path, method in KNOWN_HOSTS:
            headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": host,
                       "Content-Type": "application/json"}
            try:
                if method == "POST":
                    r = await c.post(f"https://{host}{path}", headers=headers,
                                     json={"location": "Houston, TX", "max_results": 3})
                else:
                    r = await c.get(f"https://{host}{path}", headers=headers,
                                    params={"location": "Houston, TX"})
            except Exception as exc:
                print(f"  {Y}?{D} {host:44} {str(exc)[:40]}")
                continue

            body = (r.text or "")[:120]
            if r.status_code == 404 and "doesn't exist" in body:
                print(f"  {R}✗{D} {host:44} not subscribed")
            elif r.status_code in (401, 403):
                print(f"  {R}✗{D} {host:44} {r.status_code} key rejected")
            else:
                n = len(extract_items(r.json())) if "json" in r.headers.get("content-type", "") else 0
                print(f"  {G}✓{D} {host:44} HTTP {r.status_code}, {n} listing(s)  [quota {quota(r)}]")
                found.append((host, path, method, r))
            await asyncio.sleep(0.6)
    return found


async def main():
    print("\n\033[1m### RapidAPI Zillow probe\033[0m")
    print(f"  host : {HOST}")
    print(f"  key  : {'set (' + str(len(KEY)) + ' chars)' if KEY else R + 'MISSING' + D}")

    if not KEY:
        print(f"\n{R}RAPIDAPI_KEY is not set.{D} Add it to PropertyKING-backend/.env\n")
        return 1

    found = await discover(KEY)
    if not found:
        print(f"\n{R}This key is not subscribed to any Zillow API.{D}")
        print("  A RapidAPI key alone is not enough — you must subscribe to the")
        print("  specific API. Open this page and pick the free Basic plan:\n")
        print(f"    {SUBSCRIBE_URL}\n")
        return 1

    host, path, method, first = found[0]
    if host != HOST:
        print(f"\n{Y}ZILLOW_RAPIDAPI_HOST in .env is '{HOST}' but that one is not subscribed.{D}")
        print(f"  Change it to: {host}\n")

    print("\n\033[1m2. Real search — Houston, TX, for sale\033[0m")
    headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": host,
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=90.0, headers=headers) as c:
        r = await c.post(f"https://{host}{path}",
                         json={"location": "Houston, TX", "status": "for_sale",
                               "max_results": 25})
        if r.status_code >= 400:
            print(f"  {R}✗{D} HTTP {r.status_code} — {r.text[:200]}")
            return 1
        payload = r.json()
        items = extract_items(payload)
        print(f"  {G}✓{D} {len(items)} listing(s) returned  [quota left {quota(r)}]")
        if isinstance(payload, dict):
            print(f"     top-level keys: {list(payload.keys())[:10]}")

        if not items:
            print(f"  {Y}No listings in the response — dumping it so the mapping can be fixed:{D}")
            print(json.dumps(payload, indent=2)[:1500])
            return 1

        print("\n\033[1m3. Fields on a listing\033[0m")
        sample = items[0]
        for k in sorted(sample):
            v = sample[k]
            shown = v[:58] if isinstance(v, str) else json.dumps(v, default=str)[:58]
            print(f"     {k:24} {shown}")

        print("\n\033[1m4. Fields the adapter maps\033[0m")
        wanted = ["zpid", "url", "list_price_usd", "status", "property_type", "beds",
                  "baths", "sqft", "lot_sqft", "zestimate_usd", "rent_zestimate_usd",
                  "address_line", "latitude", "longitude", "photo_url"]
        missing = [w for w in wanted if w not in sample]
        for w in wanted:
            print(f"     {w:20} {G + 'present' + D if w in sample else Y + 'ABSENT' + D}")

        print("\n\033[1m### Result\033[0m")
        if missing:
            print(f"  {Y}Missing: {', '.join(missing)}{D}")
            print("  → Give Claude this output and the adapter mapping gets corrected.")
        else:
            print(f"  {G}Every mapped field is present — the adapter should work as-is.{D}")
        print("  Provider to select in the admin panel: \033[1mZillow via ReefAPI\033[0m")
        print()

    return 0


sys.exit(asyncio.run(main()))
