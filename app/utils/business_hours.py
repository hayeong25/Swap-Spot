from datetime import date, datetime, time

import pytz

KST = pytz.timezone("Asia/Seoul")
BANK_OPEN = time(9, 0)
BANK_CLOSE = time(15, 30)

KOREAN_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # 신정
    date(2026, 2, 16),  # 설날 연휴
    date(2026, 2, 17),  # 설날
    date(2026, 2, 18),  # 설날 연휴
    date(2026, 3, 1),   # 삼일절
    date(2026, 5, 5),   # 어린이날
    date(2026, 5, 24),  # 부처님오신날
    date(2026, 6, 6),   # 현충일
    date(2026, 8, 15),  # 광복절
    date(2026, 9, 24),  # 추석 연휴
    date(2026, 9, 25),  # 추석
    date(2026, 9, 26),  # 추석 연휴
    date(2026, 10, 3),  # 개천절
    date(2026, 10, 9),  # 한글날
    date(2026, 12, 25), # 크리스마스
}


def is_banking_hours() -> bool:
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return False
    if now.date() in KOREAN_HOLIDAYS_2026:
        return False
    return BANK_OPEN <= now.time() <= BANK_CLOSE
