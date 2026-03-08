import math, asyncio, time, logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.collectors import bybit_p2p, binance_p2p
from app.market import fetch_chart, fetch_trending
from app.cache import cache

logger = logging.getLogger("metaflow")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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


# ─── Rate limiter ────────────────────────────────────────────────────────────
# Minimum seconds between consecutive requests to the same exchange.
# Keeps us well under their undocumented rate limits.
_RATE_INTERVAL = {
    "bybit":   0.8,   # ~75 req/min
    "binance": 0.5,   # ~120 req/min
}
_rate_last:  dict[str, float]         = {}
_rate_locks: dict[str, asyncio.Lock]  = {}


def _exchange_lock(exchange: str) -> asyncio.Lock:
    if exchange not in _rate_locks:
        _rate_locks[exchange] = asyncio.Lock()
    return _rate_locks[exchange]


async def _rate_wait(exchange: str):
    key = exchange.lower()
    async with _exchange_lock(key):
        interval = _RATE_INTERVAL.get(key, 1.0)
        elapsed  = time.time() - _rate_last.get(key, 0)
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)
        _rate_last[key] = time.time()


# ─── Fetch with retry + exponential backoff ──────────────────────────────────
async def _fetch_with_retry(
    exchange: str, fiat: str, crypto: str, side: str,
    max_retries: int = 3,
) -> list:
    module = EXCHANGES.get(exchange.lower(), bybit_p2p)
    for attempt in range(max_retries):
        try:
            await _rate_wait(exchange)
            return await module.fetch_p2p_offers(fiat, crypto, side)
        except Exception as exc:
            wait = 2 ** attempt          # 1 s → 2 s → 4 s
            logger.warning(
                "[%s] attempt %d/%d failed: %s — retry in %ds",
                exchange, attempt + 1, max_retries, exc, wait,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(wait)
    logger.error("[%s] all %d retries failed for %s/%s %s", exchange, max_retries, fiat, crypto, side)
    return []


# ─── Background stale-cache refresh ─────────────────────────────────────────
async def _bg_refresh(cache_key: str, exchange: str, fiat: str, crypto: str, side: str):
    try:
        logger.info("[bg] refreshing %s", cache_key)
        fresh = await _fetch_with_retry(exchange, fiat, crypto, side)
        if fresh:
            cache.set(cache_key, fresh, ttl=25)
            logger.info("[bg] %s refreshed (%d offers)", cache_key, len(fresh))
    except Exception as exc:
        logger.error("[bg] refresh failed %s: %s", cache_key, exc)


# ─── Safety scoring (Bybit-specific) ────────────────────────────────────────
#
# On Bybit P2P, offers with dirty money or scam intent share common signals:
#   • Very few trades (new / throwaway accounts)
#   • Low completion rate (abandon trades after receiving fiat)
#   • Price that deviates suspiciously far from the median (too-good-to-be-true bait)
#   • Abnormally low minimum amount (luring small, cautious buyers)
#
# Binance pre-filters advertisers via its own KYC/compliance layer, so we
# assign a flat baseline score there instead of applying Bybit heuristics.

SAFE_THRESHOLD = 65          # minimum score to be used in safe spread


def compute_safety_score(offer: dict, median_price: float) -> int:
    """Return integer 0–100. Higher = safer."""
    # Binance is platform-filtered — trust their KYC baseline
    if offer.get("exchange", "").lower() == "binance":
        return 85

    score = 100
    tc = offer.get("trade_count", 0)
    cr = offer.get("completion_rate", 0)

    # ── Trade count ──────────────────────────────────────────────────────
    if   tc < 5:    score -= 45   # throwaway / brand-new account
    elif tc < 20:   score -= 30
    elif tc < 50:   score -= 15
    elif tc < 100:  score -= 7

    # ── Completion rate ──────────────────────────────────────────────────
    if   cr < 80:   score -= 30   # abandons >20 % of deals
    elif cr < 90:   score -= 15
    elif cr < 95:   score -= 7

    # ── Price outlier ────────────────────────────────────────────────────
    # A suspiciously better price is a classic scam lure
    if median_price > 0 and offer.get("price", 0) > 0:
        dev = abs(offer["price"] - median_price) / median_price * 100
        if   dev > 8:   score -= 30
        elif dev > 5:   score -= 15
        elif dev > 3:   score -= 5

    # ── Suspiciously low minimum amount ─────────────────────────────────
    if offer.get("min_amount", 0) < 5:
        score -= 10

    return max(0, min(100, score))


def _safety_tier(score: int) -> str:
    if score >= 80: return "safe"
    if score >= 60: return "caution"
    return "risky"


def enrich_safety(offers: list) -> list:
    """Mutates each offer dict in-place; returns same list."""
    if not offers:
        return offers
    prices = sorted(o["price"] for o in offers if o.get("price", 0) > 0)
    median = prices[len(prices) // 2] if prices else 0
    for o in offers:
        sc = compute_safety_score(o, median)
        o["safety_score"] = sc
        o["safety_tier"]  = _safety_tier(sc)
    return offers


# ─── Helpers ─────────────────────────────────────────────────────────────────
def normalize_pair(fiat: str, crypto: str, side: str):
    fiat_is_crypto = fiat   in CRYPTO_SET
    crypto_is_fiat = crypto in FIAT_SET
    if fiat_is_crypto and crypto_is_fiat:
        return crypto, fiat, ("SELL" if side == "BUY" else "BUY")
    if fiat_is_crypto and crypto in CRYPTO_SET:
        return None, None, None
    return fiat, crypto, side


def compute_rating(completion_rate: float, trade_count: int) -> float:
    """Composite score 0–10: completion_rate×0.7 + log(trades+1)×0.3"""
    cr  = min(max(completion_rate, 0), 100) / 100
    tc  = math.log(max(trade_count, 0) + 1)
    raw = cr * 0.7 + tc * 0.3
    return round(min(raw / 0.287, 10), 2)


# ─── Routes ──────────────────────────────────────────────────────────────────
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
    offers    = cache.get(cache_key)
    is_stale  = cache.is_stale(cache_key)

    if offers is None:
        # Nothing in cache — fetch synchronously (first request or expired)
        offers = await _fetch_with_retry(exchange, real_fiat, real_crypto, real_side)
        cache.set(cache_key, offers, ttl=25)
        is_stale = False
    elif is_stale:
        # Serve stale data immediately; refresh in background
        asyncio.create_task(_bg_refresh(cache_key, exchange, real_fiat, real_crypto, real_side))

    # Work on a shallow copy so we don't mutate cached dicts
    offers = [dict(o) for o in offers]
    enrich_safety(offers)

    for o in offers:
        o["rating_score"] = compute_rating(
            o.get("completion_rate", 0),
            o.get("trade_count", 0),
        )

    # ── Filters ──────────────────────────────────────────────────────────
    if min_rate > 0:
        offers = [o for o in offers if o["completion_rate"] >= min_rate]

    if payment:
        offers = [
            o for o in offers
            if any(payment.lower() in pm.lower()
                   for pm in o.get("payment_methods", []))
        ]

    # ── Sort ─────────────────────────────────────────────────────────────
    if sort == "volume":
        offers.sort(key=lambda x: x["max_amount"], reverse=True)
    elif sort == "rate":
        offers.sort(key=lambda x: x["completion_rate"], reverse=True)
    elif sort == "score":
        offers.sort(key=lambda x: x["rating_score"], reverse=True)
    elif sort == "safety":
        offers.sort(key=lambda x: x.get("safety_score", 0), reverse=True)
    else:
        offers.sort(key=lambda x: x["price"], reverse=(real_side == "SELL"))

    return {
        "offers":      offers,
        "exchange":    exchange,
        "is_stale":    is_stale,
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


# ─── Spread ───────────────────────────────────────────────────────────────────
async def _fetch_and_cache(exchange: str, fiat: str, crypto: str, side: str) -> list:
    cache_key = f"p2p:{exchange}:{fiat}:{crypto}:{side}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        fresh = await _fetch_with_retry(exchange, fiat, crypto, side)
        cache.set(cache_key, fresh, ttl=25)
        return fresh
    except Exception:
        return []


@app.get("/p2p/spread")
async def best_spread():
    # Fetch all combinations in parallel
    tasks, keys = [], []
    for fiat in SUPPORTED_FIATS:
        for crypto in SUPPORTED_CRYPTOS:
            for ex in EXCHANGES:
                for side in ("BUY", "SELL"):
                    tasks.append(_fetch_and_cache(ex, fiat, crypto, side))
                    keys.append((ex, fiat, crypto, side))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate raw offers per (fiat, crypto, side) across exchanges
    pair_offers: dict[tuple, dict[str, list]] = {}
    for (ex, fiat, crypto, side), result in zip(keys, results):
        if not isinstance(result, list) or not result:
            continue
        key = (fiat, crypto)
        if key not in pair_offers:
            pair_offers[key] = {"BUY": [], "SELL": []}
        pair_offers[key][side].extend(result)

    pair_buy:  dict[tuple, dict] = {}
    pair_sell: dict[tuple, dict] = {}

    for key, sides in pair_offers.items():
        # Enrich both sides with safety scores before filtering
        buy_all  = enrich_safety([dict(o) for o in sides["BUY"]])
        sell_all = enrich_safety([dict(o) for o in sides["SELL"]])

        # Filter to safe offers; fall back to all if none qualify
        safe_buys  = [o for o in buy_all  if o["safety_score"] >= SAFE_THRESHOLD] or buy_all
        safe_sells = [o for o in sell_all if o["safety_score"] >= SAFE_THRESHOLD] or sell_all

        if safe_buys:
            best = min(safe_buys, key=lambda o: o["price"])
            pair_buy[key] = {
                "price":        best["price"],
                "exchange":     best.get("exchange", ""),
                "advertiser":   best.get("advertiser", ""),
                "url":          best.get("url", ""),
                "safety_score": best["safety_score"],
                "safety_tier":  best["safety_tier"],
            }

        if safe_sells:
            best = max(safe_sells, key=lambda o: o["price"])
            pair_sell[key] = {
                "price":        best["price"],
                "exchange":     best.get("exchange", ""),
                "advertiser":   best.get("advertiser", ""),
                "url":          best.get("url", ""),
                "safety_score": best["safety_score"],
                "safety_tier":  best["safety_tier"],
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
            "fiat":              fiat,
            "crypto":            crypto,
            "buy_price":         round(bp, 6),
            "sell_price":        round(sp, 6),
            "spread_pct":        round(pct, 3),
            "profitable":        pct > 0,
            "buy_exchange":      buy["exchange"],
            "sell_exchange":     sell["exchange"],
            "buy_advertiser":    buy["advertiser"],
            "sell_advertiser":   sell["advertiser"],
            "buy_url":           buy["url"],
            "sell_url":          sell["url"],
            "buy_safety_score":  buy["safety_score"],
            "sell_safety_score": sell["safety_score"],
            "buy_safety_tier":   buy["safety_tier"],
            "sell_safety_tier":  sell["safety_tier"],
            # True when best buy and best sell are on different exchanges
            "cross_exchange":    buy["exchange"].lower() != sell["exchange"].lower(),
        })

    spreads.sort(key=lambda x: x["spread_pct"], reverse=True)
    profitable = [s for s in spreads if s["profitable"]]

    return {
        "spread":     spreads[0] if spreads else None,
        "all":        spreads,
        "profitable": profitable,
        "scanned":    len(spreads),
    }
