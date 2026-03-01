from .collectors import bybit_p2p, binance_p2p
from .market import fetch_chart, fetch_trending
from .cache import cache

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

EXCHANGES = {
    "bybit":   bybit_p2p,
    "binance": binance_p2p,
}

SUPPORTED_FIATS = ["PLN", "EUR", "USD", "GBP", "CZK", "HUF", "CAD", "NGN", "ILS", "JPY"]

@app.get("/health")
async def health():
    return {"status": "ok", "supported_fiats": SUPPORTED_FIATS}

@app.get("/p2p")
async def p2p(
    fiat: str = "PLN",
    crypto: str = "USDT",
    side: str = "BUY",
    exchange: str = "bybit",
    sort: str = "price",
    min_rate: float = 0,
):
    cache_key = f"p2p:{exchange}:{fiat}:{crypto}:{side}"
    offers = cache.get(cache_key)

    if offers is None:
        module = EXCHANGES.get(exchange.lower(), bybit_p2p)
        offers = await module.fetch_p2p_offers(fiat, crypto, side)
        cache.set(cache_key, offers, ttl=25)

    # Filter by completion rate
    if min_rate > 0:
        offers = [o for o in offers if o["completion_rate"] >= min_rate]

    # Sort
    if sort == "volume":
        offers.sort(key=lambda x: x["max_amount"], reverse=True)
    elif sort == "rate":
        offers.sort(key=lambda x: x["completion_rate"], reverse=True)
    else:
        offers.sort(key=lambda x: x["price"], reverse=(side == "SELL"))

    return {"offers": offers, "exchange": exchange}

@app.get("/market/chart")
async def chart(symbol: str = "BTCUSDT", interval: str = "1d"):
    cache_key = f"chart:{symbol}:{interval}"
    data = cache.get(cache_key)
    if data is None:
        data = await fetch_chart(symbol, interval)
        cache.set(cache_key, data, ttl=60)
    return {"data": data, "symbol": symbol}

@app.get("/market/trending")
async def trending():
    data = cache.get("trending")
    if data is None:
        data = await fetch_trending()
        cache.set("trending", data, ttl=60)
    return {"data": data}

@app.get("/p2p/spread")
async def best_spread():
    pairs = [
        ("PLN", "USDT"),
        ("EUR", "USDT"),
        ("USD", "USDT"),
        ("GBP", "USDT"),
    ]

    best_buy = {}
    best_sell = {}

    for fiat, crypto in pairs:
        for ex in ["bybit", "binance"]:
            buy_key = f"p2p:{ex}:{fiat}:{crypto}:BUY"
            sell_key = f"p2p:{ex}:{fiat}:{crypto}:SELL"

            buys = cache.get(buy_key) or []
            sells = cache.get(sell_key) or []

            if buys:
                bp = min(o["price"] for o in buys)
                if fiat not in best_buy or bp < best_buy[fiat]["price"]:
                    best_buy[fiat] = {"price": bp, "exchange": ex}

            if sells:
                sp = max(o["price"] for o in sells)
                if fiat not in best_sell or sp > best_sell[fiat]["price"]:
                    best_sell[fiat] = {"price": sp, "exchange": ex}

    best_spread = None
    best_pct = 0

    for fiat in best_buy:
        if fiat in best_sell:
            buy_p = best_buy[fiat]["price"]
            sell_p = best_sell[fiat]["price"]

            if buy_p > 0:
                pct = (sell_p - buy_p) / buy_p * 100

                if pct > best_pct:
                    best_pct = pct
                    best_spread = {
                        "fiat": fiat,
                        "buy_price": buy_p,
                        "sell_price": sell_p,
                        "spread_pct": round(pct, 2),
                        "buy_exchange": best_buy[fiat]["exchange"],
                        "sell_exchange": best_sell[fiat]["exchange"],
                    }

    return {"spread": best_spread}




