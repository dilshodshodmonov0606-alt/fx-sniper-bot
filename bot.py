import telebot, requests, time, threading

TOKEN = "8284811491:AAG6vih0p4_38t4MTxqRtj-zW4xBkSi5Kkk"
CHAT_ID = "wodmonovfx7"
GOLD_API = "ada8d9fc15d744bc8484dd96ee8f4ca0"

bot = telebot.TeleBot(TOKEN)

trades = []
results = {"tp":0, "sl":0}

# ===== BTC DATA =====
def get_btc():
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=100"
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

    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 0

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

# ===== ORDER BLOCK (oddiy) =====
def order_block(highs, lows):
    return max(highs[-20:]), min(lows[-20:])

# ===== TP/SL =====
def tp_sl(price, direction):
    if direction == "BUY":
        return price - 20, price + 40, price + 80
    else:
        return price + 20, price - 40, price - 80

# ===== WINRATE =====
def winrate():
    total = results["tp"] + results["sl"]
    if total == 0:
        return 0
    return round(results["tp"] / total * 100, 2)

# ===== SIGNAL =====
def signal(closes, highs, lows, opens):
    price = closes[-1]
    e = ema(closes)
    r = rsi(closes)
    c = strong_candle(opens, closes)
    i = ict(highs, lows, price)

    ob_high, ob_low = order_block(highs, lows)

    # SNIPER FILTER
    if abs(price - e) < 5:
        return None, None, None, None, None

    # BUY
    if price > e and r < 45 and c and i == "BUY" and ob_low < price < ob_high:
        sl, tp1, tp2 = tp_sl(price, "BUY")
        return "BUY", price, sl, tp1, tp2

    # SELL
    if price < e and r > 55 and c and i == "SELL" and ob_low < price < ob_high:
        sl, tp1, tp2 = tp_sl(price, "SELL")
        return "SELL", price, sl, tp1, tp2

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
            elif price >= t["tp1"]:
                bot.send_message(CHAT_ID, "🎯 TP1 HIT")

        if t["type"] == "SELL":
            if price >= t["sl"]:
                t["status"] = "SL"
                results["sl"] += 1
                bot.send_message(CHAT_ID, "❌ SL HIT")
            elif price <= t["tp2"]:
                t["status"] = "TP2"
                results["tp"] += 1
                bot.send_message(CHAT_ID, "🎯 TP2 HIT")
            elif price <= t["tp1"]:
                bot.send_message(CHAT_ID, "🎯 TP1 HIT")

# ===== AUTO =====
def auto():
    while True:
        try:
            # BTC
            closes, highs, lows, opens = get_btc()
            s, p, sl, tp1, tp2 = signal(closes, highs, lows, opens)

            if s:
                trades.append({
                    "type": s,
                    "entry": p,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "status": "OPEN"
                })

                bot.send_message(
                    CHAT_ID,
                    f"🔥 BTC {s}\nEntry: {p}\nSL: {sl}\nTP1: {tp1}\nTP2: {tp2}\nWinrate: {winrate()}%"
                )

            check(closes[-1])

            # GOLD
            closes, highs, lows, opens = get_gold()
            s, p, sl, tp1, tp2 = signal(closes, highs, lows, opens)

            if s:
                bot.send_message(
                    CHAT_ID,
                    f"🟡 GOLD {s}\nEntry: {p}\nSL: {sl}\nTP1: {tp1}\nTP2: {tp2}"
                )

        except Exception as e:
            print(e)

        time.sleep(30)

threading.Thread(target=auto).start()
bot.infinity_polling()
