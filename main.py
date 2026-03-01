import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.collectors import bybit_p2p, binance_p2p
from app.market import fetch_chart, fetch_trending
from app.cache import cache

app = FastAPI(title="Metaflow")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

EXCHANGES = {"bybit": bybit_p2p, "binance": binance_p2p}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/p2p")
async def p2p(fiat="PLN", crypto="USDT", side="BUY", exchange="bybit", sort="price", min_rate: float=0):
    cache_key = f"p2p:{exchange}:{fiat}:{crypto}:{side}"
    offers = cache.get(cache_key)
    if offers is None:
        module = EXCHANGES.get(exchange.lower(), bybit_p2p)
        offers = await module.fetch_p2p_offers(fiat, crypto, side)
        cache.set(cache_key, offers, ttl=25)
    if min_rate > 0:
        offers = [o for o in offers if o["completion_rate"] >= min_rate]
    if sort == "volume":
        offers.sort(key=lambda x: x["max_amount"], reverse=True)
    elif sort == "rate":
        offers.sort(key=lambda x: x["completion_rate"], reverse=True)
    else:
        offers.sort(key=lambda x: x["price"], reverse=(side == "SELL"))
    return {"offers": offers, "exchange": exchange}

@app.get("/market/chart")
async def chart(symbol="BTCUSDT", interval="1d"):
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
333
@app.get("/p2p/spread")
async def best_spread():
    pairs = [("PLN","USDT"),("EUR","USDT"),("USD","USDT"),("GBP","USDT")]
    best_buy, best_sell = {}, {}
    for fiat, crypto in pairs:
        for ex in ["bybit","binance"]:
            buys = cache.get(f"p2p:{ex}:{fiat}:{crypto}:BUY") or []
            sells = cache.get(f"p2p:{ex}:{fiat}:{crypto}:SELL") or []
            if buys:
                bp = min(o["price"] for o in buys)
                if fiat not in best_buy or bp < best_buy[fiat]["price"]:
                    best_buy[fiat] = {"price": bp, "exchange": ex}
            if sells:
                sp = max(o["price"] for o in sells)
                if fiat not in best_sell or sp > best_sell[fiat]["price"]:
                    best_sell[fiat] = {"price": sp, "exchange": ex}
    best, best_pct = None, 0
    for fiat in best_buy:
        if fiat in best_sell:
            bp, sp = best_buy[fiat]["price"], best_sell[fiat]["price"]
            if bp > 0:
                pct = (sp - bp) / bp * 100
                if pct > best_pct:
                    best_pct = pct
                    best = {"fiat": fiat, "buy_price": bp, "sell_price": sp, "spread_pct": round(pct,2)}
    return {"spread": best}
