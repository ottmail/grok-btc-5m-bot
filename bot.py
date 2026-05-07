import os
import time
import logging
from dotenv import load_dotenv
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import MarketOrderArgs
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from strategy import get_current_market_data, decide_trade
import requests  # for finding active 5m market

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Polymarket client
client = ClobClient(
    host="https://clob.polymarket.com",
    key=os.getenv("POLYGON_PRIVATE_KEY"),
    chain_id=137
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

active_market = None
running = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running
    running = True
    await update.message.reply_text("🚀 Grok BTC 5m Sniper Agent STARTED (DRY_RUN=" + str(DRY_RUN) + ")")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running
    running = False
    await update.message.reply_text("⛔ Bot STOPPED safely.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Status: {'RUNNING' if running else 'STOPPED'}\nDry Run: {DRY_RUN}")

# Main trading loop (runs in background)
def trading_loop():
    global active_market
    while True:
        if not running:
            time.sleep(10)
            continue
            
        try:
            # Find current 5m BTC market
            resp = requests.get("https://gamma-api.polymarket.com/markets", params={"active": True, "limit": 100})
            for m in resp.json():
                if "Bitcoin Up or Down" in m.get("title", "") and "5m" in m.get("title", "").lower():
                    active_market = m
                    break
            
            if not active_market:
                time.sleep(30)
                continue
                
            # Get price data
            df, price = get_current_market_data()
            open_price = float(active_market["tokens"][0]["price"] or 0)  # approximate open
            side, confidence, prob = decide_trade(open_price, price, df)
            
            if confidence > float(os.getenv("MIN_EDGE", 0.55)):
                token_id = active_market["tokens"][0 if side == "UP" else 1]["token_id"]
                size = float(os.getenv("MAX_BET_USDC", 10))
                
                if DRY_RUN:
                    print(f"DRY RUN: Would buy {side} @ confidence {confidence:.2f}")
                else:
                    order = MarketOrderArgs(tokenID=token_id, price=0.99 if side=="UP" else 0.01, size=size)
                    client.create_and_post_order(order)
                    print(f"EXECUTED: {side} trade")
                
                # Send Telegram alert
                # (add your own bot.send_message here if you expand)
                
            time.sleep(30)  # check every 30s
            
        except Exception as e:
            print("Error:", e)
            time.sleep(60)

# Run the bot
if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    
    # Start trading in background thread
    import threading
    threading.Thread(target=trading_loop, daemon=True).start()
    
    print("Telegram bot starting...")
    app.run_polling()
