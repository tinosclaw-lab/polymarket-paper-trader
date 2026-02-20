#!/usr/bin/env python3
"""
Polymarket Paper Trading - Market Discovery
Step 1: Find active crypto 15-minute markets
"""

import requests
import json
import time

# API Base URL
BASE_URL = "https://gamma-api.polymarket.com"

def get_markets(asset=None, limit=50):
    """Fetch markets from Polymarket API"""
    params = {"limit": limit}
    if asset:
        params["asset"] = asset
        
    try:
        response = requests.get(f"{BASE_URL}/markets", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return []

def get_events(category=None, group_slug=None, limit=20):
    """Fetch events from Polymarket API"""
    params = {"limit": limit}
    if category:
        params["category"] = category
    if group_slug:
        params["groupSlug"] = group_slug
        
    try:
        response = requests.get(f"{BASE_URL}/events", params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []

def find_crypto_15m_markets():
    """Find active crypto 15-minute up/down markets"""
    print("=" * 60)
    print("POLYMARKET MARKET DISCOVERY")
    print("=" * 60)
    
    # Try different approaches to find crypto markets
    print("\n[1] Fetching crypto events...")
    crypto_events = get_events(category="Crypto")
    print(f"    Found {len(crypto_events)} crypto events")
    
    # Try group slug for 15-minute markets
    print("\n[2] Trying 15-minute market groups...")
    for group in ["btc-15m", "btc-5m", "crypto-15m", "crypto-5m"]:
        events = get_events(group_slug=group)
        if events:
            print(f"    Found {len(events)} events for group: {group}")
            for event in events[:3]:
                print(f"      - {event.get('title', 'N/A')[:60]}")
    
    # Fetch all markets and filter
    print("\n[3] Fetching all active markets...")
    all_markets = get_markets(limit=200)
    
    # Filter for crypto markets
    crypto_markets = []
    up_down_markets = []
    
    for market in all_markets:
        if not market.get("active", True):
            continue
            
        question = market.get("question", "").lower()
        
        # Look for crypto markets
        if any(x in question for x in ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp"]):
            crypto_markets.append(market)
            
        # Look for up/down markets (15min, 5min)
        if "up" in question or "down" in question:
            if "min" in question or "minute" in question:
                up_down_markets.append(market)
    
    print(f"\n    Total active markets: {len(all_markets)}")
    print(f"    Crypto markets: {len(crypto_markets)}")
    print(f"    Up/Down minute markets: {len(up_down_markets)}")
    
    # Print sample markets
    print("\n[4] Sample Crypto Markets:")
    for m in crypto_markets[:10]:
        print(f"    - {m.get('question', 'N/A')[:70]}")
        print(f"      Volume: ${m.get('volumeNum', 0):,.2f} | Active: {m.get('active')}")
        
    print("\n[5] Sample Up/Down Markets:")
    for m in up_down_markets[:10]:
        print(f"    - {m.get('question', 'N/A')[:70]}")
        
    # Try CLOB API for prices
    print("\n[6] Testing CLOB API for prices...")
    test_token = "53135072462907880191400140706440867753044989936304433583131786753949599718775"
    try:
        resp = requests.get(f"https://clob.polymarket.com/markets/{test_token}", timeout=5)
        print(f"    CLOB response: {resp.status_code}")
    except Exception as e:
        print(f"    CLOB error: {e}")
    
    return {
        "all_markets": all_markets,
        "crypto_markets": crypto_markets,
        "up_down_markets": up_down_markets
    }

if __name__ == "__main__":
    results = find_crypto_15m_markets()
    
    # Save results
    with open("discovered_markets.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Saved results to discovered_markets.json")
