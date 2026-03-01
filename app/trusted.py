# Whitelist trusted advertisers by exchange + advertiser name or ID
# Format: { "exchange": { "id_or_name": "display_reason" } }

TRUSTED = {
    "bybit": {
        # "123456789": "verified partner",
    },
    "binance": {
       "BXNEXCHANGE"
    },
}

def is_trusted(exchange: str, advertiser_id: str, advertiser_name: str) -> bool:
    ex = TRUSTED.get(exchange.lower(), {})

    return advertiser_id in ex or advertiser_name in ex
