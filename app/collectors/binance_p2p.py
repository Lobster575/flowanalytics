import httpx

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
}
COMMISSION = 0.0

async def fetch_p2p_offers(fiat, crypto, side, rows=15):
    payload = {
        "fiat": fiat, "asset": crypto, "tradeType": side,
        "page": 1, "rows": rows, "payTypes": [], "publisherType": None
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(BINANCE_P2P_URL, json=payload, headers=HEADERS)
            data = response.json()
            offers = []
            for item in data.get("data", []):
                adv = item.get("adv", {})
                advertiser = item.get("advertiser", {})
                advertiser_no = advertiser.get("userNo", "")
                trade_count = int(advertiser.get("monthOrderCount", 0))
                raw_rate = float(advertiser.get("monthFinishRate", 0))
                completion_rate = raw_rate * 100 if raw_rate <= 1.0 else raw_rate
                completion_rate = min(completion_rate, 100.0)
                offers.append({
                    "exchange": "Binance",
                    "price": float(adv.get("price", 0)),
                    "min_amount": float(adv.get("minSingleTransAmount", 0)),
                    "max_amount": float(adv.get("maxSingleTransAmount", 0)),
                    "currency": fiat, "crypto": crypto, "side": side,
                    "advertiser": advertiser.get("nickName"),
                    "commission": COMMISSION,
                    "url": f"https://p2p.binance.com/en/advertiserDetail?advertiserNo={advertiser_no}" if advertiser_no else None,
                    "payment_methods": [p.get("tradeMethodName") for p in adv.get("tradeMethods", [])],
                    "trade_count": trade_count,
                    "completion_rate": round(completion_rate, 1),
                    "trusted": trade_count > 300 and completion_rate > 95
                })
            return offers
    except Exception as e:
        print(f"Binance P2P error: {e}")
        return []