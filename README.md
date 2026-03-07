# Swap Spot

> 실시간 환율 모니터 & 환전 타이밍 추천 대시보드

**Live:** https://swap-spot-jwis.onrender.com

해외여행, 직구, 송금 시 **최적의 환전 시점**을 파악하기 위한 실시간 환율 모니터링 서비스입니다.

![Swap Spot Dashboard](static/images/dashboard.png)

---

## Features

### 실시간 환율 테이블
- 11개 주요 통화(USD, EUR, JPY, GBP, CNH, CHF, CAD, AUD, HKD, SGD, THB) 매매기준율 표시
- WebSocket 기반 실시간 업데이트 (새로고침 불필요)
- 2단 레이아웃으로 한눈에 비교
- 통화 클릭 시 차트/타이밍/예측/알림 섹션 연동 선택

### 환전 타이밍 추천 (3-Signal)
| Signal | Method | Logic |
|--------|--------|-------|
| 이동평균 | 5일 vs 20일 MA 교차 | 단기 MA < 장기 MA × 0.998 → WAIT |
| 백분위 | 90일 분포 내 현재 위치 | 하위 25% → BUY |
| 볼린저 밴드 | 20일 MA ± 2σ | 하단 터치 → BUY |

3개 시그널 투표 → **BUY** / **HOLD** / **WAIT** 추천 + 신뢰도 제공

### 여행 환전 플래너
- 여행지 + 출발일 입력 → D-day 기반 환전 전략 분석
- 남은 기간에 따른 **긴급도 자동 조정** (여유 → 주의 → 긴급 → 즉시)
- **목표 환율** 제시 (HOLD/WAIT 시 얼마에 환전하면 좋을지)
- 분할 환전 비율 추천
- 긴급도별 맞춤형 메시지 및 전략 팁 제공

### 환율 하락 확률 예측
- **Monte Carlo 시뮬레이션** (Historical Block Bootstrap, 5,000회)
- 1주 / 2주 / 3주 단위 실제 날짜 범위로 예측
- 변동성 기반 **동적 목표가** 자동 산출 (0.15σ ~ 1.0σ)
- 목표가별 하락 확률을 시각적 바 차트로 표시
- 예측 분포 백분위(p5/p25/p50/p75/p95) 및 연간 변동성 제공
- 5분 캐시로 빠른 응답

### 환율 추이 차트
- Chart.js 기반 인터랙티브 차트 (1주 / 1개월 / 3개월)
- 마우스 휠 줌, 드래그 팬 지원
- 소스 우선순위 기반 일별 최적 데이터 표시

### 환율 알림
- 목표 환율 도달 시 브라우저 + Telegram 알림
- 조건: 이하 / 이상 / 변동률(%)
- 60분 쿨다운으로 중복 발송 방지
- Telegram 전송 실패 시 지수 백오프 재시도 (최대 3회)

---

## Tech Stack

| Layer | Tech | Why |
|-------|------|-----|
| Backend | FastAPI (Python 3.11+) | Async native, WebSocket 내장 |
| HTTP Client | httpx (async) | 비동기 다중 소스 동시 호출 |
| Scraping | BeautifulSoup4 + lxml | 하나은행 페이지 파싱 |
| Scheduler | APScheduler | 인프로세스 주기적 데이터 수집 |
| Database | SQLite (aiosqlite) / PostgreSQL (asyncpg) | 개발 무설정, 프로덕션 확장 |
| ORM | SQLAlchemy 2.0 (async) | 타입 안전한 DB 접근 |
| Validation | Pydantic v2 + pydantic-settings | 스키마 검증 + 환경변수 관리 |
| Forecast | Monte Carlo (stdlib) | Block Bootstrap 확률 예측 |
| Frontend | Vanilla HTML/CSS/JS | 빌드 불필요, 즉시 배포 |
| Chart | Chart.js + Zoom Plugin | 인터랙티브 시계열 차트 |
| Realtime | WebSocket | 브라우저에 즉시 push |
| Deploy | Render | Web + PostgreSQL 무료 티어 |

---

## Data Sources

| Source | Type | Schedule | Coverage |
|--------|------|----------|----------|
| **한국수출입은행 API** | 공식 환율 (매매기준율, TTB/TTS) | 매일 11:05 KST | 23개 통화 |
| **한국은행 ECOS API** | 과거 데이터 보강 | 매일 18:00 KST | 주요 5개 통화 (USD, EUR, JPY, GBP, CNH) |
| **하나은행 스크래핑** | 장중 실시간 (현찰/송금 환율 포함) | 영업시간(09:00~15:30) 중 2분 간격 | 10개 통화 |

소스 우선순위: koreaexim > hanabank > ecos > demo

---

## Getting Started

### 1. Clone & Install

```bash
git clone https://github.com/hayeong25/Swap-Spot.git
cd Swap-Spot
pip install -e .
```

### 2. API Key 설정

```bash
cp .env.example .env
```

`.env` 파일에 API 키 입력:
```env
KOREAEXIM_API_KEY=your_key_here    # https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2
ECOS_API_KEY=your_key_here         # https://ecos.bok.or.kr/api
```

선택 설정:
```env
TELEGRAM_BOT_TOKEN=                # 텔레그램 알림용 봇 토큰
TELEGRAM_CHAT_ID=                  # 텔레그램 채팅 ID
DATABASE_URL=postgresql://...      # PostgreSQL 사용 시 (기본: SQLite)
ENV=production                     # production 시 로그 WARNING, SSL 검증 활성화
```

### 3. 히스토리 데이터 시드

**실제 데이터** (수출입은행 API 키 필요):
```bash
python scripts/seed_real_history.py
```
> 수출입은행 API에서 90일간 실제 환율 데이터를 가져와 DB에 저장합니다.

**데모 데이터** (API 키 없이 체험):
```bash
python -m scripts.seed_demo
```
> 11개 통화의 90일간 랜덤 워크 데이터를 생성합니다.

### 4. 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`http://localhost:8000` 접속

---

## Project Structure

```
app/
├── main.py                    # FastAPI 앱 진입점 + lifespan 관리
├── config.py                  # 환경변수 설정 (Pydantic Settings)
├── models/                    # SQLAlchemy ORM
│   ├── database.py            # async 엔진 + 세션 팩토리
│   ├── exchange_rate.py       # 환율 테이블 (currency_code+rate_date 복합 인덱스)
│   └── alert.py               # 알림 설정 테이블 (is_active 인덱스)
├── sources/                   # 데이터 수집 (Strategy 패턴)
│   ├── base.py                # ExchangeRateSource 추상 클래스
│   ├── koreaexim.py           # 수출입은행 API (7일 역추적, CNY→CNH 통일)
│   ├── ecos.py                # 한국은행 ECOS API (일별 + 히스토리 조회)
│   ├── hanabank.py            # 하나은행 스크래퍼 (POST/GET 폴백)
│   └── aggregator.py          # 다중 소스 통합 + 우선순위 병합
├── services/                  # 비즈니스 로직
│   ├── rate_service.py        # 환율 캐시 (asyncio.Lock) + DB 저장 + WebSocket broadcast
│   ├── timing_engine.py       # 3-Signal 타이밍 + 여행 플래너 (긴급도별 전략)
│   ├── forecast_engine.py     # Monte Carlo 확률 예측 (Block Bootstrap, 5분 캐시)
│   ├── alert_service.py       # 알림 평가 + 쿨다운 + Telegram 재시도
│   └── scheduler.py           # 소스별 분리 스케줄링 (APScheduler)
├── api/                       # 엔드포인트
│   ├── routes_rates.py        # 환율 + 타이밍 + 예측 REST API
│   ├── routes_alerts.py       # 알림 CRUD API
│   └── websocket.py           # 실시간 WebSocket (자동 정리)
├── schemas/                   # Pydantic 스키마
│   ├── rate.py                # RateData, RateResponse, HistoricalRateResponse, TimingResponse
│   └── alert.py               # AlertCreate (조건 검증), AlertResponse
└── utils/                     # 유틸리티
    ├── currency.py            # 11개 주요 통화 정의 + 포맷터
    └── business_hours.py      # 은행 영업시간 + 한국 공휴일 판별 (2025~2028)

static/                        # 프론트엔드
├── index.html                 # SPA 대시보드 (접근성 aria 속성 포함)
├── css/style.css              # 다크 테마 스타일 (반응형)
├── js/app.js                  # 메인 로직 (WS 지수 백오프, 디바운스, Toast)
└── images/                    # 스크린샷

scripts/                       # 유틸리티 스크립트
├── seed_real_history.py       # 수출입은행 API 90일 히스토리 시딩
├── seed_demo.py               # API 키 없이 데모 데이터 생성
└── full_test.py               # 서버 가동 상태에서 종합 테스트

tests/                         # 테스트 코드 (pytest + pytest-asyncio)
├── conftest.py                # 테스트 픽스처
├── test_api.py                # API 엔드포인트 테스트
├── test_schemas.py            # Pydantic 스키마 검증 테스트
├── test_utils.py              # 유틸리티 테스트
├── test_sources/              # 데이터 소스 테스트
│   └── test_aggregator.py
└── test_services/             # 서비스 로직 테스트
    ├── test_timing_engine.py
    ├── test_forecast_engine.py
    └── test_rate_service.py

render.yaml                    # Render 배포 설정 (Web + PostgreSQL)
pyproject.toml                 # 패키지 설정 + 의존성
.env.example                   # 환경변수 템플릿
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/rates/latest` | 주요 11개 통화 최신 환율 |
| `GET` | `/api/rates/timing/{currency}` | 환전 타이밍 분석 (3-Signal) |
| `GET` | `/api/rates/travel-timing/{currency}?travel_date=` | 여행 환전 플래너 |
| `GET` | `/api/rates/forecast/{currency}` | 환율 하락 확률 예측 (Monte Carlo) |
| `GET` | `/api/rates/health/sources` | 데이터 소스 헬스체크 |
| `GET` | `/api/rates/{currency}?days=30` | 환율 히스토리 (1~365일) |
| `GET` | `/api/alerts/` | 활성 알림 목록 |
| `POST` | `/api/alerts/` | 알림 추가 (below/above/percent_change) |
| `DELETE` | `/api/alerts/{id}` | 알림 삭제 (soft delete) |
| `WS` | `/ws/rates` | 실시간 환율 스트림 (snapshot + update) |
| `GET` | `/docs` | Swagger UI |

---

## Testing

```bash
# 단위 + 통합 테스트 (pytest)
pip install -e ".[dev]"
pytest

# 서버 종합 테스트 (서버 가동 필요)
python scripts/full_test.py
```

---

## Deployment

### Render

`render.yaml`로 원클릭 배포:
- Web Service (Python) + PostgreSQL 자동 구성
- 환경변수 `DATABASE_URL` 자동 연결
- `pip install -e ".[postgres]"`로 asyncpg 포함 빌드

### 수동 배포

```bash
pip install -e ".[postgres]"
export DATABASE_URL=postgresql://user:pass@host:5432/swap_spot
export ENV=production
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Disclaimer

본 서비스의 환전 타이밍 추천 및 확률 예측은 **통계적 분석 도구**이며, 투자 또는 환전에 대한 전문적인 금융 조언이 아닙니다. 환율은 다양한 거시경제적 요인에 의해 변동되며, 과거 데이터가 미래 결과를 보장하지 않습니다.
