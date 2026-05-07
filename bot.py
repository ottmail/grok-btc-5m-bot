import os
import time
import logging
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from strategy import get_current_market_data, decide_trade
import requests

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === CONFIG ===
host = "https://clob.polymarket.com"
chain_id = 137

# Safe init with error checking
try:
    private_key = os.getenv("POLYGON_PRIVATE_KEY")
    if not private_key:
        raise ValueError("❌ POLYGON_PRIVATE_KEY is missing!")
    
    # Initialize Polymarket client (official V2 way)
    client = ClobClient(host=host, chain_id=chain_id, key=private_key)
    print("✅ Polymarket client initialized successfully")
except Exception as e:
    print(f"❌ CLIENT INIT FAILED: {e}")
    raise

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

running = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running
    running = True
    await update.message.reply_text(f"🚀 Grok BTC 5m Sniper Agent STARTED\nDry Run: {DRY_RUN}\n✅ Ready to snipe!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running
    running = False
    await update.message.reply_text("⛔ Bot STOPPED safely.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Status: {'RUNNING ✅' if running else 'STOPPED'}\nDry Run: {DRY_RUN}")

def trading_loop():
    global running
    while True:
        if not running:
            time.sleep(10)
            continue
        try:
            # Find active 5m BTC market
            resp = requests.get("https://gamma-api.polymarket.com/markets", params={"active": True, "limit": 100})
            active_market = None
            for m in resp.json():
                title = m.get("title", "").lower()
                if "bitcoin up or down" in title and "5m" in title:
                    active_market = m
                    break
            
            if not active_market:
                time.sleep(30)
                continue

            df, price = get_current_market_data()
            open_price = float(active_market.get("tokens", [{}])[0].get("price", 0.5))

            side, confidence, prob = decide_trade(open_price, price, df)
            
            if confidence > float(os.getenv("MIN_EDGE", 0.55)):
                token_id = active_market["tokens"][0 if side == "UP" else 1]["token_id"]
                size = float(os.getenv("MAX_BET_USDC", 10))
                
                if DRY_RUN:
                    print(f"DRY RUN: Would BUY {side} @ confidence {confidence:.2f} | Price: {price}")
                else:
                    # TODO: Add real order creation once we confirm it works in dry-run
                    print(f"✅ LIVE TRADE: Would execute {side} order")
                
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(60)
        time.sleep(30)

if __name__ == "__main__":
    print("🚀 Starting Telegram + Trading bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    
    import threading
    threading.Thread(target=trading_loop, daemon=True).start()
    
    print("✅ Bot is now running! Send /start in Telegram")
    app.run_polling()
