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
client = ClobClient(host=host, chain_id=chain_id, key=os.getenv("POLYGON_PRIVATE_KEY"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
MIN_EDGE = float(os.getenv("MIN_EDGE", 0.55))
MAX_BET_USDC = float(os.getenv("MAX_BET_USDC", 1))

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
    logging.info("=== TRADING LOOP STARTED - WILL PRINT EVERY 30 SECONDS ===")
    
    while True:
        if not running:
            time.sleep(10)
            continue

        try:
            logging.info("=== TRADING LOOP CYCLE STARTED ===")
            
            # Find active 5m BTC market (improved detection)
            resp = requests.get("https://gamma-api.polymarket.com/markets", params={"active": True, "limit": 100})
            active_market = None
            for m in resp.json():
                title = m.get("title", "").lower()
                if "bitcoin up or down" in title:
                    active_market = m
                    logging.info(f"✅ FOUND MARKET: {m.get('title')}")
                    break

            if not active_market:
                logging.info("No active 5m BTC market found yet - waiting for next window...")
                time.sleep(30)
                continue

            # Get price + TA data
            df, price = get_current_market_data()
            open_price = float(active_market.get("tokens", [{}])[0].get("price", 0.5))

            logging.info(f"Price data -> Open: {open_price:.2f} | Current: {price:.2f}")

            side, confidence, prob = decide_trade(open_price, price, df, seconds_remaining=90)
            logging.info(f"DECISION: {side} | Confidence: {confidence} | Prob: {prob}")

            if confidence >= MIN_EDGE:
                token_id = active_market["tokens"][0 if side == "UP" else 1]["token_id"]
                size = MAX_BET_USDC
                
                if DRY_RUN:
                    logging.info(f"🔥 DRY RUN: Would BUY {side} @ confidence {confidence} | Size: ${size}")
                else:
                    logging.info(f"✅ LIVE TRADE: {side} | Size: ${size}")
            else:
                logging.info(f"No strong edge yet (confidence {confidence} < {MIN_EDGE})")

        except Exception as e:
            logging.error(f"Loop error: {e}")
        
        time.sleep(30)

if __name__ == "__main__":
    logging.info("🚀 Starting Telegram + Trading bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    
    import threading
    threading.Thread(target=trading_loop, daemon=True).start()
    
    logging.info("✅ Bot is now running! Send /start in Telegram")
    app.run_polling()
