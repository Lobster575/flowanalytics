import math, asyncio, time
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

SUPPORTED_FIATS   = ["PLN", "EUR", "USD", "GBP", "CZK", "HUF", "CAD", "NGN", "ILS", "JPY"]
SUPPORTED_CRYPTOS = ["USDT", "BTC", "ETH", "USDC"]

CRYPTO_SET = set(SUPPORTED_CRYPTOS)
FIAT_SET   = set(SUPPORTED_FIATS)


def normalize_pair(fiat: str, crypto: str, side: str):
    fiat_is_crypto = fiat   in CRYPTO_SET
    crypto_is_fiat = crypto in FIAT_SET
    if fiat_is_crypto and crypto_is_fiat:
        flipped_side = "SELL" if side == "BUY" else "BUY"
        return crypto, fiat, flipped_side
    if fiat_is_crypto and crypto in CRYPTO_SET:
        return None, None, None
    return fiat, crypto, side


def compute_rating(completion_rate: float, trade_count: int) -> float:
    """
    Composite score 0–10:
      completion_rate × 0.7  +  log(trade_count + 1) × 0.3
    Normalised so ~10 000 trades at 100% completion ≈ 10.
    """
    cr  = min(max(completion_rate, 0), 100) / 100
    tc  = math.log(max(trade_count, 0) + 1)
    raw = cr * 0.7 + tc * 0.3
    return round(min(raw / 0.287, 10), 2)


@app.get("/health")
async def health():
    return {"status": "ok", "supported_fiats": SUPPORTED_FIATS}


@app.get("/p2p")
async def p2p(
    fiat:      str   = "PLN",
    crypto:    str   = "USDT",
    side:      str   = "BUY",
    exchange:  str   = "bybit",
    sort:      str   = "price",
    min_rate:  float = 0,
    payment:   str   = "",
):
    real_fiat, real_crypto, real_side = normalize_pair(fiat, crypto, side)
    if real_fiat is None:
        return {"offers": [], "exchange": exchange,
                "error": "crypto-to-crypto not supported",
                "server_time": int(time.time()), "ttl": 25}

    cache_key = f"p2p:{exchange}:{real_fiat}:{real_crypto}:{real_side}"
    offers = cache.get(cache_key)
    if offers is None:
        module = EXCHANGES.get(exchange.lower(), bybit_p2p)
        offers = await module.fetch_p2p_offers(real_fiat, real_crypto, real_side)
        cache.set(cache_key, offers, ttl=25)

    # Composite rating score
    for o in offers:
        o["rating_score"] = compute_rating(
            o.get("completion_rate", 0),
            o.get("trade_count", 0),
        )

    # Filters
    if min_rate > 0:
        offers = [o for o in offers if o["completion_rate"] >= min_rate]

    if payment:
        offers = [
            o for o in offers
            if any(payment.lower() in pm.lower()
                   for pm in o.get("payment_methods", []))
        ]

    # Sort
    if sort == "volume":
        offers.sort(key=lambda x: x["max_amount"], reverse=True)
    elif sort == "rate":
        offers.sort(key=lambda x: x["completion_rate"], reverse=True)
    elif sort == "score":
        offers.sort(key=lambda x: x["rating_score"], reverse=True)
    else:
        offers.sort(key=lambda x: x["price"], reverse=(real_side == "SELL"))

    return {
        "offers":      offers,
        "exchange":    exchange,
        "server_time": int(time.time()),
        "ttl":         25,
    }


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


async def _fetch_and_cache(exchange: str, fiat: str, crypto: str, side: str) -> list:
    cache_key = f"p2p:{exchange}:{fiat}:{crypto}:{side}"
    offers = cache.get(cache_key)
    if offers is None:
        try:
            module = EXCHANGES[exchange]
            offers = await module.fetch_p2p_offers(fiat, crypto, side)
            cache.set(cache_key, offers, ttl=25)
        except Exception:
            offers = []
    return offers or []


@app.get("/p2p/spread")
async def best_spread():
    tasks, keys = [], []
    for fiat in SUPPORTED_FIATS:
        for crypto in SUPPORTED_CRYPTOS:
            for ex in EXCHANGES:
                for side in ("BUY", "SELL"):
                    tasks.append(_fetch_and_cache(ex, fiat, crypto, side))
                    keys.append((ex, fiat, crypto, side))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    index = {}
    for (ex, fiat, crypto, side), result in zip(keys, results):
        if isinstance(result, list):
            index[(ex, fiat, crypto, side)] = result

    pair_buy  = {}
    pair_sell = {}

    for (ex, fiat, crypto, side), offers in index.items():
        if not offers:
            continue
        key = (fiat, crypto)
        if side == "BUY":
            best_o = min(offers, key=lambda o: o["price"])
            if key not in pair_buy or best_o["price"] < pair_buy[key]["price"]:
                pair_buy[key] = {
                    "price":      best_o["price"],
                    "exchange":   ex,
                    "advertiser": best_o.get("advertiser", ""),
                    "url":        best_o.get("url", ""),
                }
        else:
            best_o = max(offers, key=lambda o: o["price"])
            if key not in pair_sell or best_o["price"] > pair_sell[key]["price"]:
                pair_sell[key] = {
                    "price":      best_o["price"],
                    "exchange":   ex,
                    "advertiser": best_o.get("advertiser", ""),
                    "url":        best_o.get("url", ""),
                }

    spreads = []
    for key in pair_buy:
        if key not in pair_sell:
            continue
        fiat, crypto = key
        buy  = pair_buy[key]
        sell = pair_sell[key]
        bp, sp = buy["price"], sell["price"]
        if bp <= 0:
            continue
        pct = (sp - bp) / bp * 100
        if not (-50 < pct < 10):
            continue
        spreads.append({
            "fiat":            fiat,
            "crypto":          crypto,
            "buy_price":       round(bp, 6),
            "sell_price":      round(sp, 6),
            "spread_pct":      round(pct, 3),
            "profitable":      pct > 0,
            "buy_exchange":    buy["exchange"],
            "sell_exchange":   sell["exchange"],
            "buy_advertiser":  buy["advertiser"],
            "sell_advertiser": sell["advertiser"],
            "buy_url":         buy["url"],
            "sell_url":        sell["url"],
        })

    spreads.sort(key=lambda x: x["spread_pct"], reverse=True)
    profitable = [s for s in spreads if s["profitable"]]

    return {
        "spread":     spreads[0] if spreads else None,
        "all":        spreads,
        "profitable": profitable,
        "scanned":    len(spreads),
    }
