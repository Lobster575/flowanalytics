from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.collectors import bybit_p2p, binance_p2p
from app.market import fetch_chart, fetch_trending

app = FastAPI(title="Metaflow")

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

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/p2p")
async def p2p(fiat: str = "PLN", crypto: str = "USDT", side: str = "BUY",
              exchange: str = "bybit", sort: str = "price"):
    module = EXCHANGES.get(exchange.lower(), bybit_p2p)
    offers = await module.fetch_p2p_offers(fiat, crypto, side)
    if sort == "volume":
        offers.sort(key=lambda x: x["max_amount"], reverse=True)
    elif sort == "rate":
        offers.sort(key=lambda x: x["completion_rate"], reverse=True)
    else:
        offers.sort(key=lambda x: x["price"], reverse=(side == "SELL"))
    return {"offers": offers, "exchange": exchange}

@app.get("/market/chart")
async def chart(symbol: str = "BTCUSDT", interval: str = "1d"):
    data = await fetch_chart(symbol, interval)
    return {"data": data, "symbol": symbol}

@app.get("/market/trending")
async def trending():
    data = await fetch_trending()
    return {"data": data}