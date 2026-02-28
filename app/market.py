import httpx

BINANCE_BASE = "https://api.binance.com/api/v3"

def calc_ma(data, period):
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            avg = sum(d["close"] for d in data[i-period+1:i+1]) / period
            result.append(round(avg, 2))
    return result

async def fetch_chart(symbol: str = "BTCUSDT", interval: str = "1d", limit: int = 90):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BINANCE_BASE}/klines", params={"symbol": symbol, "interval": interval, "limit": limit})
            raw = r.json()
            data = [{"time": k[0], "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in raw]
            ma7  = calc_ma(data, 7)
            ma25 = calc_ma(data, 25)
            ma99 = calc_ma(data, 99)
            for i, d in enumerate(data):
                d["ma7"]  = ma7[i]
                d["ma25"] = ma25[i]
                d["ma99"] = ma99[i]
            return data
    except Exception as e:
        print(f"Chart error: {e}")
        return []

async def fetch_trending(limit: int = 20):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BINANCE_BASE}/ticker/24hr")
            data = r.json()
            usdt_pairs = [t for t in data if t["symbol"].endswith("USDT") and float(t.get("quoteVolume", 0)) > 1_000_000]
            sorted_pairs = sorted(usdt_pairs, key=lambda x: abs(float(x["priceChangePercent"])), reverse=True)
            return [{
                "symbol": t["symbol"].replace("USDT", ""),
                "price": float(t["lastPrice"]),
                "change": float(t["priceChangePercent"]),
                "volume": float(t["quoteVolume"]),
                "high": float(t["highPrice"]),
                "low": float(t["lowPrice"]),
            } for t in sorted_pairs[:limit]]
    except Exception as e:
        print(f"Trending error: {e}")
        return []