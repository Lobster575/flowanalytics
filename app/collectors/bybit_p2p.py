import httpx

BYBIT_P2P_URL = "https://api2.bybit.com/fiat/otc/item/online"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
PAYMENT_METHODS = {
    "14": "Bank Transfer", "9": "Revolut", "133": "Wise", "139": "PayPal",
    "154": "SEPA", "159": "Faster Payments", "355": "BLIK", "357": "Paysend",
    "174": "Skrill", "147": "Neteller", "292": "Crypto.com", "22": "WebMoney",
    "416": "MB WAY", "77": "Payoneer", "234": "Neosurf",
}
COMMISSION = 0.0

async def fetch_p2p_offers(fiat, crypto, side, rows=15):
    payload = {
        "tokenId": crypto, "currencyId": fiat,
        "side": "1" if side == "BUY" else "0",
        "size": str(rows), "page": "1", "amount": "", "paymentMethod": []
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(BYBIT_P2P_URL, json=payload, headers=HEADERS)
        data = response.json()
        offers = []
        for item in data.get("result", {}).get("items", []):
            user_id = item.get("userId", "")
            raw_payments = item.get("payments", [])
            payment_names = [PAYMENT_METHODS.get(str(p), f"#{p}") for p in raw_payments]
            trade_count = int(item.get("recentOrderNum", 0))
            raw_rate = float(item.get("recentExecuteRate", 0))
            completion_rate = raw_rate * 100 if raw_rate <= 1.0 else raw_rate
            completion_rate = min(completion_rate, 100.0)
            offers.append({
                "exchange": "Bybit",
                "price": float(item.get("price", 0)),
                "min_amount": float(item.get("minAmount", 0)),
                "max_amount": float(item.get("maxAmount", 0)),
                "currency": fiat, "crypto": crypto, "side": side,
                "advertiser": item.get("nickName"),
                "commission": COMMISSION,
                "url": f"https://www.bybit.com/fiat/trade/otc/profile/{user_id}" if user_id else None,
                "payment_methods": payment_names,
                "trade_count": trade_count,
                "completion_rate": round(completion_rate, 1),
                "trusted": trade_count > 300 and completion_rate > 95
            })
        return offers