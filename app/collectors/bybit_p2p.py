import httpx
from app.trusted import is_trusted

BYBIT_P2P_URL = "https://api2.bybit.com/fiat/otc/item/online"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
PAYMENT_METHODS = {
    # Bank / Wire
    "14":  "Bank Transfer",
    "64":  "Bank Transfer",
    "65":  "Bank Transfer",
    "328": "Bank Transfer",
    "382": "Bank Transfer",
    # Cards & wallets
    "9":   "Revolut",
    "15":  "Revolut",
    "133": "Wise",
    "75":  "Wise",
    "139": "PayPal",
    "174": "Skrill",
    "147": "Neteller",
    "77":  "Payoneer",
    "292": "Crypto.com",
    "234": "Neosurf",
    "416": "MB WAY",
    "591": "Neteller",
    "592": "Skrill",
    # Regional
    "154": "SEPA",
    "377": "SEPA",
    "159": "Faster Payments",
    "355": "BLIK",
    "357": "Paysend",
    "22":  "WebMoney",
}
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
            # Resolve name from map, fallback to paymentName field, then #ID
            payment_names = []
            for p in raw_payments:
                pid = str(p)
                if pid in PAYMENT_METHODS:
                    payment_names.append(PAYMENT_METHODS[pid])
                else:
                    # Try to get name from object if it's a dict
                    if isinstance(p, dict):
                        name = p.get("paymentName") or PAYMENT_METHODS.get(str(p.get("id", ""))) or f"#{p.get('id', p)}"
                    else:
                        name = f"#{pid}"
                    payment_names.append(name)
            # Deduplicate while preserving order
            seen = set()
            payment_names = [x for x in payment_names if not (x in seen or seen.add(x))]

            trade_count = int(item.get("recentOrderNum", 0))
            raw_rate = float(item.get("recentExecuteRate", 0))
            completion_rate = round(min(raw_rate * 100 if raw_rate <= 1.0 else raw_rate, 100.0), 1)
            offers.append({
                "exchange":      "Bybit",
                "price":         float(item.get("price", 0)),
                "min_amount":    float(item.get("minAmount", 0)),
                "max_amount":    float(item.get("maxAmount", 0)),
                "currency":      fiat,
                "crypto":        crypto,
                "side":          side,
                "advertiser":    nick,
                "advertiser_id": user_id,
                "commission":    COMMISSION,
                "url":           f"https://www.bybit.com/fiat/trade/otc/profile/{user_id}" if user_id else None,
                "payment_methods": payment_names,
                "trade_count":   trade_count,
                "completion_rate": completion_rate,
                "trusted":       is_trusted("bybit", user_id, nick),
            })
        return offers
