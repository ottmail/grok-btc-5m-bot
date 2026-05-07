import pandas as pd
import pandas_ta as ta
import ccxt
import time

exchange = ccxt.binance()

def get_current_market_data():
    # Get latest BTC price and recent candles for TA
    ticker = exchange.fetch_ticker('BTC/USDT')
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1m', limit=60)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['rsi'] = ta.rsi(df['close'])
    df['macd'] = ta.macd(df['close'])['MACD_12_26_9']
    df['ema_fast'] = ta.ema(df['close'], length=8)
    df['ema_slow'] = ta.ema(df['close'], length=21)
    return df, ticker['last']

def decide_trade(open_price, current_price, df):
    # Window delta is KING (from real bot research)
    delta = (current_price - open_price) / open_price
    rsi = df['rsi'].iloc[-1]
    macd = df['macd'].iloc[-1]
    momentum = 1 if delta > 0 else -1
    
    # Composite score (weighted like proven strategies)
    score = (delta * 5) + (momentum * 2) + (1 if rsi < 70 else -1) + (1 if macd > 0 else -1)
    prob_up = 0.5 + (score / 10)
    prob_up = max(0.1, min(0.9, prob_up))  # clamp
    
    side = "UP" if prob_up > 0.55 else "DOWN"
    confidence = abs(prob_up - 0.5) * 2
    return side, confidence, prob_up
