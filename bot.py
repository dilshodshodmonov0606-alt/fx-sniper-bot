import telebot, requests, time, threading, os

# ===== ENV VARIABLES =====
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_İD")
GOLD_API = os.getenv("GOLD_APİ")

bot = telebot.TeleBot(TOKEN)

trades = []
results = {"tp": 0, "sl": 0}

# ===== BTC DATA =====
def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
    data = requests.get(url).json()

    closes = [float(i[4]) for i in data]
    highs = [float(i[2]) for i in data]
    lows = [float(i[3]) for i in data]
    opens = [float(i[1]) for i in data]

    return closes, highs, lows, opens

# ===== GOLD DATA =====
def get_gold():
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=1min&apikey={GOLD_API}"
    data = requests.get(url).json()

    if "values" not in data:
        return None, None, None, None

    values = data["values"]

    closes = [float(i["close"]) for i in values[::-1]]
    highs = [float(i["high"]) for i in values[::-1]]
    lows = [float(i["low"]) for i in values[::-1]]
    opens = [float(i["open"]) for i in values[::-1]]

    return closes, highs, lows, opens

# ===== EMA =====
def ema(prices, period=50):
    ema_val = prices[0]
    k = 2 / (period + 1)
    for p in prices:
        ema_val = p * k + ema_val * (1 - k)
    return ema_val

# ===== RSI =====
def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    if len(gains) < period or len(losses) < period:
        return 50

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ===== CANDLE =====
def strong_candle(opens, closes):
    body = abs(closes[-1] - opens[-1])
    avg = sum([abs(c - o) for c, o in zip(closes[-20:], opens[-20:])]) / 20
    return body > avg * 1.3

# ===== ICT =====
def ict(highs, lows, price):
    if price > max(highs[-10:]):
        return "BUY"
    if price < min(lows[-10:]):
        return "SELL"
    return None

# ===== SIGNAL =====
def signal(closes, highs, lows, opens):
    price = closes[-1]
    e = ema(closes)
    r = rsi(closes)
    c = strong_candle(opens, closes)
    i = ict(highs, lows, price)

    if price > e and r < 45 and c and i == "BUY":
        return "BUY", price, price - 20, price + 40, price + 80

    if price < e and r > 55 and c and i == "SELL":
        return "SELL", price, price + 20, price - 40, price - 80

    return None, None, None, None, None

# ===== CHECK =====
def check(price):
    for t in trades:
        if t["status"] != "OPEN":
            continue

        if t["type"] == "BUY":
            if price <= t["sl"]:
                t["status"] = "SL"
                results["sl"] += 1
                bot.send_message(CHAT_ID, "❌ SL HIT")
            elif price >= t["tp2"]:
                t["status"] = "TP2"
                results["tp"] += 1
                bot.send_message(CHAT_ID, "🎯 TP2 HIT")

        if t["type"] == "SELL":
            if price >= t["sl"]:
                t["status"] = "SL"
                results["sl"] += 1
                bot.send_message(CHAT_ID, "❌ SL HIT")
            elif price <= t["tp2"]:
                t["status"] = "TP2"
                results["tp"] += 1
                bot.send_message(CHAT_ID, "🎯 TP2 HIT")

# ===== WINRATE =====
def winrate():
    total = results["tp"] + results["sl"]
    return round((results["tp"] / total) * 100, 2) if total else 0

# ===== AUTO =====
def auto():
    while True:
        try:
            # BTC
            closes, highs, lows, opens = get_klines("BTCUSDT")
            s, p, sl, tp1, tp2 = signal(closes, highs, lows, opens)

            if s:
                trades.append({"type": s, "entry": p, "sl": sl, "tp1": tp1, "tp2": tp2, "status": "OPEN"})
                bot.send_message(CHAT_ID, f"🔥 BTC {s}\nEntry: {p}\nSL: {sl}\nTP1: {tp1}\nTP2: {tp2}\nWinrate: {winrate()}%")

            check(closes[-1])

            # GOLD
            g = get_gold()
            if g[0]:
                closes, highs, lows, opens = g
                s, p, sl, tp1, tp2 = signal(closes, highs, lows, opens)

                if s:
                    bot.send_message(CHAT_ID, f"🟡 GOLD {s}\nEntry: {p}\nSL: {sl}\nTP1: {tp1}\nTP2: {tp2}")

        except Exception as e:
            print("ERROR:", e)

        time.sleep(30)

threading.Thread(target=auto).start()
bot.infinity_polling()