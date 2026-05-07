import os
import time
import logging
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient, MarketOrderArgs
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from strategy import get_current_market_data, decide_trade
import requests

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Polymarket client (V2)
host = "https://clob.polymarket.com"
chain_id = 137
client = ClobClient(host=host, chain_id=chain_id, key=os.getenv("POLYGON_PRIVATE_KEY"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

running = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running
    running = True
    await update.message.reply_text(f"🚀 Grok BTC 5m Sniper Agent STARTED\nDry Run: {DRY_RUN}")

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
            # Find current 5m BTC market
            resp = requests.get("https://gamma-api.polymarket.com/markets", params={"active": True, "limit": 100})
            active_market = None
            for m in resp.json():
                if "Bitcoin Up or Down" in m.get("title", "") and "5m" in m.get("title", "").lower():
                    active_market = m
                    break
            
            if not active_market:
                time.sleep(30)
                continue

            # Get price data
            df, price = get_current_market_data()
            # Approximate open price from market
            open_price = float(active_market.get("tokens", [{}])[0].get("price", 0.5))

            side, confidence, prob = decide_trade(open_price, price, df)
            
            if confidence > float(os.getenv("MIN_EDGE", 0.55)):
                token_id = active_market["tokens"][0 if side == "UP" else 1]["token_id"]
                size = float(os.getenv("MAX_BET_USDC", 10))
                
                if DRY_RUN:
                    print(f"DRY RUN: Would buy {side} @ confidence {confidence:.2f}")
                else:
                    order = MarketOrderArgs(token_id=token_id, amount=size, side="BUY")
                    client.create_and_post_market_order(order)
                    print(f"EXECUTED: {side} trade")
                
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)
        time.sleep(30)

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    
    import threading
    threading.Thread(target=trading_loop, daemon=True).start()
    
    print("Telegram bot starting...")
    app.run_polling()
