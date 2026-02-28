import httpx

BINANCE_BASE = "https://data-api.binance.vision/api/v3"

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
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{BINANCE_BASE}/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
        print("BINANCE STATUS:", r.status_code)
        print("BINANCE TEXT:", r.text[:300])
        if r.status_code != 200:
            return []
        raw = r.json()
        if not isinstance(raw, list):
            return []
        ...

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
