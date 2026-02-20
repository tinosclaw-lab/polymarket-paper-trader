#!/usr/bin/env python3
"""
Polymarket Paper Trading System
Mean Reversion Strategy on 15-minute Bitcoin Markets

Author: Axion
For: Tino (Architect)
"""

import json
import time
import os
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

# Configuration
CONFIG = {
    "max_position_size": 10.00,  # $10 max per trade
    "buy_threshold": 0.40,       # Buy when YES price < 0.40
    "sell_threshold": 0.60,     # Sell when YES price > 0.60
    "circuit_breaker": 3,        # Stop after 3 consecutive losses
    "markets": {
        "btc": {
            "name": "Bitcoin",
            "slug_prefix": "btc-updown-15m"
        },
        "eth": {
            "name": "Ethereum", 
            "slug_prefix": "eth-updown-15m"
        }
    }
}

DATA_DIR = os.path.expanduser("~/polymarket-paper-trader")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
LOG_FILE = os.path.join(DATA_DIR, "trading.log")

def log(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")

def get_market_data(asset="btc"):
    """Fetch current 15-minute market data from Polymarket"""
    market_config = CONFIG["markets"].get(asset, CONFIG["markets"]["btc"])
    slug_prefix = market_config["slug_prefix"]
    
    # Get current 15-minute timestamp
    current_time = int(time.time())
    rounded_time = (current_time // 900) * 900  # Round down to 15 min
    
    # Try current window and next window
    for offset in [0, 900]:
        timestamp = rounded_time + offset
        slug = f"{slug_prefix}-{timestamp}"
        
        url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
        
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                if data.get("active") and not data.get("closed"):
                    # Parse prices
                    outcome_prices = json.loads(data.get("outcomePrices", "[]"))
                    outcomes = json.loads(data.get("outcomes", "[]"))
                    
                    if len(outcome_prices) >= 2:
                        return {
                            "asset": asset,
                            "name": market_config["name"],
                            "slug": slug,
                            "question": data.get("question", ""),
                            "outcomes": outcomes,
                            "prices": outcome_prices,
                            "up_price": float(outcome_prices[0]) if "Up" in outcomes[0] else float(outcome_prices[1]),
                            "down_price": float(outcome_prices[1]) if "Down" in outcomes[1] else float(outcome_prices[0]),
                            "volume": data.get("volumeNum", 0),
                            "liquidity": data.get("liquidityNum", 0),
                            "end_date": data.get("endDate", ""),
                            "timestamp": timestamp
                        }
        except Exception as e:
            log(f"Error fetching {slug}: {e}")
            continue
    
    return None

def load_trades():
    """Load trades from JSON file"""
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            return json.load(f)
    return {"trades": [], "consecutive_losses": 0, "total_pnl": 0.0}

def save_trades(trades):
    """Save trades to JSON file"""
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def should_trade(market_data, trades):
    """Determine if we should trade based on mean reversion strategy"""
    config = CONFIG
    
    # Check circuit breaker
    if trades.get("consecutive_losses", 0) >= config["circuit_breaker"]:
        log(f"🚫 CIRCUIT BREAKER: {trades['consecutive_losses']} consecutive losses. Stopping.")
        return False, "circuit_breaker"
    
    up_price = market_data["up_price"]
    
    # Mean reversion signals
    if up_price < config["buy_threshold"]:
        return True, f"BUY signal: Up price {up_price:.2%} < {config['buy_threshold']:.0%}"
    elif up_price > config["sell_threshold"]:
        return True, f"SELL signal: Up price {up_price:.2%} > {config['sell_threshold']:.0%}"
    else:
        return False, f"HOLD: Up price {up_price:.2%} in neutral zone"

def execute_trade(action, market_data, trades):
    """Execute a paper trade"""
    config = CONFIG
    position_size = config["max_position_size"]
    
    trade = {
        "timestamp": datetime.now().isoformat(),
        "asset": market_data["asset"],
        "name": market_data["name"],
        "slug": market_data["slug"],
        "action": action,
        "price": market_data["up_price"] if action == "BUY" else market_data["down_price"],
        "size": position_size,
        "up_price": market_data["up_price"],
        "down_price": market_data["down_price"],
        "volume": market_data["volume"],
        "status": "open",
        "pnl": 0.0
    }
    
    trades["trades"].append(trade)
    save_trades(trades)
    
    log(f"✅ EXECUTED: {action} {market_data['name']} @ ${trade['price']:.2f} (${position_size})")
    
    return trade

def check_closed_positions(trades):
    """Check if any positions can be closed (market ended)"""
    current_time = int(time.time())
    closed_count = 0
    
    for trade in trades["trades"]:
        if trade.get("status") == "open":
            # Extract timestamp from slug (btc-updown-15m-1771616700)
            slug_parts = trade["slug"].split("-")
            if len(slug_parts) >= 4:
                market_end_time = int(slug_parts[-1]) + 900  # 15 min after start
                
                if current_time > market_end_time:
                    # Market closed - assume 50/50 resolution for paper trading
                    # In reality, you'd check the resolution
                    trade["status"] = "closed"
                    
                    # Calculate P&L (simplified)
                    if trade["action"] == "BUY":
                        # Bought "Up" at entry price
                        # If resolved "Up", win; else lose
                        resolved_up = True  # Placeholder - real impl would check API
                        if resolved_up:
                            trade["pnl"] = trade["size"] * (1 - trade["price"])  # Win
                            trades["consecutive_losses"] = 0
                        else:
                            trade["pnl"] = -trade["size"] * trade["price"]  # Lose
                            trades["consecutive_losses"] += 1
                    else:
                        # Sold "Down" 
                        resolved_down = False  # Placeholder
                        if resolved_down:
                            trade["pnl"] = trade["size"] * (1 - trade["price"])
                            trades["consecutive_losses"] = 0
                        else:
                            trade["pnl"] = -trade["size"] * trade["price"]
                            trades["consecutive_losses"] += 1
                    
                    trades["total_pnl"] += trade["pnl"]
                    closed_count += 1
                    log(f"📊 CLOSED: {trade['action']} {trade['name']} - P&L: ${trade['pnl']:.2f}")
    
    if closed_count > 0:
        save_trades(trades)
    
    return closed_count

def run_trading_cycle():
    """Run one trading cycle"""
    log("=" * 50)
    log("STARTING TRADING CYCLE")
    
    # Load existing trades
    trades = load_trades()
    
    # Check for closed positions
    check_closed_positions(trades)
    
    # Fetch market data for each asset
    for asset in CONFIG["markets"].keys():
        log(f"\n--- Checking {asset.upper()} ---")
        
        market_data = get_market_data(asset)
        
        if not market_data:
            log(f"No active market found for {asset}")
            continue
        
        log(f"Market: {market_data['question']}")
        log(f"Prices: Up ${market_data['up_price']:.2f} | Down ${market_data['down_price']:.2f}")
        log(f"Volume: ${market_data['volume']:,.2f} | Liquidity: ${market_data['liquidity']:,.2f}")
        
        # Check if we should trade
        trade_signal, reason = should_trade(market_data, trades)
        
        if trade_signal:
            action = "BUY" if "BUY" in reason else "SELL"
            execute_trade(action, market_data, trades)
        else:
            log(f"💤 {reason}")
    
    # Print summary
    log("\n--- SUMMARY ---")
    log(f"Total Trades: {len(trades['trades'])}")
    log(f"Consecutive Losses: {trades.get('consecutive_losses', 0)}")
    log(f"Total P&L: ${trades.get('total_pnl', 0):.2f}")
    log("=" * 50)

def main():
    """Main entry point"""
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    log("Polymarket Paper Trading System Started")
    
    # Run one cycle
    run_trading_cycle()

if __name__ == "__main__":
    main()
