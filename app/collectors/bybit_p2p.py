import httpx
from app.trusted import is_trusted

BYBIT_P2P_URL = "https://api2.bybit.com/fiat/otc/item/online"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
BYBIT_PAYMENT_NAMES = {
    "14":  "BLIK",
    "15":  "Revolut",
    "64":  "Paysend",
    "65":  "WebMoney",
    "75":  "Wise",
    "328": "Faster Payments",
    "377": "SEPA",
    "382": "Bank Transfer",
    "591": "Neteller",
    "592": "Skrill",
    "3":   "Bank Transfer",
}

# при формировании оффера:
"payment_methods": [
    BYBIT_PAYMENT_NAMES.get(str(pm["paymentType"]), pm.get("paymentName", str(pm["paymentType"])))
    for pm in item["payments"]
]

COMMISSION = 0.0

async def fetch_p2p_offers(fiat, crypto, side, rows=20):
    payload = {
        "tokenId": crypto, "currencyId": fiat,
        "side": "1" if side == "BUY" else "0",
        "size": str(rows), "page": "1", "amount": "", "paymentMethod": []
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(BYBIT_P2P_URL, json=payload, headers=HEADERS)
        data = response.json()
        offers = []
        for item in data.get("result", {}).get("items", []):
            user_id = str(item.get("userId", ""))
            nick = item.get("nickName", "")
            raw_payments = item.get("payments", [])
            payment_names = [PAYMENT_METHODS.get(str(p), f"#{p}") for p in raw_payments]
            trade_count = int(item.get("recentOrderNum", 0))
            raw_rate = float(item.get("recentExecuteRate", 0))
            completion_rate = round(min(raw_rate * 100 if raw_rate <= 1.0 else raw_rate, 100.0), 1)
            offers.append({
                "exchange": "Bybit",
                "price": float(item.get("price", 0)),
                "min_amount": float(item.get("minAmount", 0)),
                "max_amount": float(item.get("maxAmount", 0)),
                "currency": fiat, "crypto": crypto, "side": side,
                "advertiser": nick,
                "advertiser_id": user_id,
                "commission": COMMISSION,
                "url": f"https://www.bybit.com/fiat/trade/otc/profile/{user_id}" if user_id else None,
                "payment_methods": payment_names,
                "trade_count": trade_count,
                "completion_rate": completion_rate,
                "trusted": is_trusted("bybit", user_id, nick),
            })
        return offers
