# Whitelist trusted advertisers by exchange.
# Format: { "exchange": { "id_or_nick": "reason" } }
# Add user IDs (strings) or nicknames — both are checked.

TRUSTED: dict[str, dict[str, str]] = {
    "bybit": {
        # "123456789": "verified partner",
    },
    "binance": {
        "BXNEXCHANGE": "verified exchange",
    },
}


def is_trusted(exchange: str, advertiser_id: str, advertiser_name: str) -> bool:
    ex = TRUSTED.get(exchange.lower(), {})
    return advertiser_id in ex or advertiser_name in ex
