import asyncio
import httpx
from app.trusted import is_trusted

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
}
COMMISSION = 0.0
ROWS_PER_PAGE = 20   # Binance максимум 20 за запрос
PAGES = 3            # итого до 60 офферов


async def _fetch_page(client: httpx.AsyncClient, fiat: str, crypto: str, side: str, page: int) -> list:
    payload = {
        "fiat": fiat, "asset": crypto, "tradeType": side,
        "page": page, "rows": ROWS_PER_PAGE,
        "payTypes": [], "publisherType": None,
    }
    try:
        response = await client.post(BINANCE_P2P_URL, json=payload, headers=HEADERS)
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"Binance P2P page {page} error: {e}")
        return []


async def fetch_p2p_offers(fiat, crypto, side, rows=None):
    offers = []
    seen_ids = set()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Запрашиваем все страницы параллельно
            pages = await asyncio.gather(*[
                _fetch_page(client, fiat, crypto, side, p)
                for p in range(1, PAGES + 1)
            ])

            for page_items in pages:
                for item in page_items:
                    adv        = item.get("adv", {})
                    advertiser = item.get("advertiser", {})

                    advertiser_no = str(advertiser.get("userNo", ""))
                    nick          = advertiser.get("nickName", "")

                    # Дедупликация по ID рекламы
                    adv_id = adv.get("advNo") or advertiser_no
                    if adv_id in seen_ids:
                        continue
                    seen_ids.add(adv_id)

                    trade_count = int(advertiser.get("monthOrderCount", 0))
                    raw_rate    = float(advertiser.get("monthFinishRate", 0))
                    completion_rate = round(
                        min(raw_rate * 100 if raw_rate <= 1.0 else raw_rate, 100.0), 1
                    )

                    offers.append({
                        "exchange":       "Binance",
                        "price":          float(adv.get("price", 0)),
                        "min_amount":     float(adv.get("minSingleTransAmount", 0)),
                        "max_amount":     float(adv.get("maxSingleTransAmount", 0)),
                        "currency":       fiat,
                        "crypto":         crypto,
                        "side":           side,
                        "advertiser":     nick,
                        "advertiser_id":  advertiser_no,
                        "commission":     COMMISSION,
                        "url":            f"https://p2p.binance.com/en/advertiserDetail?advertiserNo={advertiser_no}" if advertiser_no else None,
                        "payment_methods": [p.get("tradeMethodName") for p in adv.get("tradeMethods", [])],
                        "trade_count":    trade_count,
                        "completion_rate": completion_rate,
                        "trusted":        is_trusted("binance", advertiser_no, nick),
                    })

    except Exception as e:
        print(f"Binance P2P error: {e}")

    return offers
