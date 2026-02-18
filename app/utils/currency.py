MAJOR_CURRENCIES = {
    "USD": {"name": "미국 달러", "symbol": "$", "unit": 1},
    "EUR": {"name": "유로", "symbol": "€", "unit": 1},
    "JPY": {"name": "일본 엔", "symbol": "¥", "unit": 100},
    "GBP": {"name": "영국 파운드", "symbol": "£", "unit": 1},
    "CNY": {"name": "중국 위안", "symbol": "¥", "unit": 1},
    "CNH": {"name": "중국 위안(역외)", "symbol": "¥", "unit": 1},
    "CHF": {"name": "스위스 프랑", "symbol": "Fr", "unit": 1},
    "CAD": {"name": "캐나다 달러", "symbol": "C$", "unit": 1},
    "AUD": {"name": "호주 달러", "symbol": "A$", "unit": 1},
    "HKD": {"name": "홍콩 달러", "symbol": "HK$", "unit": 1},
    "SGD": {"name": "싱가포르 달러", "symbol": "S$", "unit": 1},
    "THB": {"name": "태국 바트", "symbol": "฿", "unit": 1},
}


def format_rate(rate: float, currency_code: str) -> str:
    unit = MAJOR_CURRENCIES.get(currency_code, {}).get("unit", 1)
    if unit > 1:
        return f"{rate:,.2f} (/{unit})"
    return f"{rate:,.2f}"
