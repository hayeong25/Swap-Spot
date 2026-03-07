from datetime import date, datetime, time

import pytz

KST = pytz.timezone("Asia/Seoul")
BANK_OPEN = time(9, 0)
BANK_CLOSE = time(15, 30)

# 고정 공휴일 (월/일) - 매년 동일
FIXED_HOLIDAYS = {
    (1, 1),    # 신정
    (3, 1),    # 삼일절
    (5, 5),    # 어린이날
    (6, 6),    # 현충일
    (8, 15),   # 광복절
    (10, 3),   # 개천절
    (10, 9),   # 한글날
    (12, 25),  # 크리스마스
}

# 음력 기반 공휴일 (연도별 양력 날짜) - 설날, 부처님오신날, 추석
LUNAR_HOLIDAYS = {
    2025: {
        date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),  # 설날 연휴
        date(2025, 5, 5),   # 부처님오신날 (어린이날과 겹침)
        date(2025, 10, 5), date(2025, 10, 6), date(2025, 10, 7),  # 추석 연휴
    },
    2026: {
        date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),  # 설날 연휴
        date(2026, 5, 24),  # 부처님오신날
        date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26),  # 추석 연휴
    },
    2027: {
        date(2027, 2, 6), date(2027, 2, 7), date(2027, 2, 8),    # 설날 연휴
        date(2027, 5, 13),  # 부처님오신날
        date(2027, 10, 14), date(2027, 10, 15), date(2027, 10, 16),  # 추석 연휴
    },
    2028: {
        date(2028, 1, 26), date(2028, 1, 27), date(2028, 1, 28),  # 설날 연휴
        date(2028, 5, 2),   # 부처님오신날
        date(2028, 10, 2), date(2028, 10, 3), date(2028, 10, 4),  # 추석 연휴
    },
}


def _is_korean_holiday(d: date) -> bool:
    if (d.month, d.day) in FIXED_HOLIDAYS:
        return True
    year_holidays = LUNAR_HOLIDAYS.get(d.year, set())
    return d in year_holidays


def is_banking_hours() -> bool:
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return False
    if _is_korean_holiday(now.date()):
        return False
    return BANK_OPEN <= now.time() <= BANK_CLOSE
