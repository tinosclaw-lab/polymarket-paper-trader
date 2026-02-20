#!/usr/bin/env python3
"""
Polymarket Paper Trading System
Mean Reversion Strategy on 15-minute Bitcoin Markets
Checks NEXT window, runs every 5 minutes
"""

import json
import time
import os
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

CONFIG = {
    "max_position_size": 10.00,
    "buy_threshold": 0.40,
    "sell_threshold": 0.60,
    "circuit_breaker": 3,
    "markets": {
        "btc": {"name": "Bitcoin", "slug_prefix": "btc-updown-15m"},
        "eth": {"name": "Ethereum", "slug_prefix": "eth-updown-15m"}
    }
}

DATA_DIR = os.path.expanduser("~/polymarket-paper-trader")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
LOG_FILE = os.path.join(DATA_DIR, "trading.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def get_next_market_data(asset):
    cfg = CONFIG["markets"].get(asset, CONFIG["markets"]["btc"])
    prefix = cfg["slug_prefix"]
    
    cur = int(time.time())
    rounded = (cur // 900) * 900
    next_ts = rounded + 900
    
    slug = f"{prefix}-{next_ts}"
    url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
    
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("active") and not data.get("closed"):
                prices = json.loads(data.get("outcomePrices", "[]"))
                outcomes = json.loads(data.get("outcomes", "[]"))
                if prices:
                    return {
                        "asset": asset,
                        "name": cfg["name"],
                        "slug": slug,
                        "question": data.get("question", ""),
                        "up_price": float(prices[0]),
                        "down_price": float(prices[1]),
                        "volume": data.get("volumeNum", 0),
                        "liquidity": data.get("liquidityNum", 0),
                        "end_date": data.get("endDate", ""),
                        "timestamp": next_ts
                    }
    except Exception as e:
        log(f"Error {asset}: {e}")
    return None

def load_trades():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            return json.load(f)
    return {"trades": [], "consecutive_losses": 0, "total_pnl": 0.0}

def save_trades(t):
    with open(TRADES_FILE, "w") as f:
        json.dump(t, f, indent=2)

def should_trade(md, trades):
    if trades.get("consecutive_losses", 0) >= CONFIG["circuit_breaker"]:
        return False, "circuit_breaker"
    
    up = md["up_price"]
    if up < CONFIG["buy_threshold"]:
        return True, f"BUY: {up:.2%} < {CONFIG['buy_threshold']:.0%}"
    elif up > CONFIG["sell_threshold"]:
        return True, f"SELL: {up:.2%} > {CONFIG['sell_threshold']:.0%}"
    return False, f"HOLD: {up:.2%}"

def execute(action, md, trades):
    trade = {
        "timestamp": datetime.now().isoformat(),
        "asset": md["asset"],
        "name": md["name"],
        "slug": md["slug"],
        "action": action,
        "price": md["up_price"] if action == "BUY" else md["down_price"],
        "size": CONFIG["max_position_size"],
        "up_price": md["up_price"],
        "down_price": md["down_price"],
        "status": "open",
        "pnl": 0.0
    }
    trades["trades"].append(trade)
    save_trades(trades)
    log(f"TRADE: {action} {md['name']} @ ${trade['price']:.2f}")
    return trade

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    log("=== NEW CYCLE - NEXT WINDOW ===")
    
    trades = load_trades()
    
    for asset in CONFIG["markets"]:
        md = get_next_market_data(asset)
        if not md:
            log(f"{asset.upper()}: No market")
            continue
        
        log(f"{md['name']}: Up ${md['up_price']:.2f} | Down ${md['down_price']:.2f}")
        
        sig, reason = should_trade(md, trades)
        if sig:
            action = "BUY" if "BUY" in reason else "SELL"
            execute(action, md, trades)
        else:
            log(f"  {reason}")
    
    log(f"Total P&L: ${trades.get('total_pnl', 0):.2f}")

if __name__ == "__main__":
    main()
