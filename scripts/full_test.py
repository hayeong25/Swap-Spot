"""Swap Spot 전체 종합 테스트"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0
WARN = 0


def result(test_name, passed, detail=""):
    global PASS, FAIL
    if passed:
        PASS += 1
        print(f"  [PASS] {test_name}" + (f" - {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {test_name}" + (f" - {detail}" if detail else ""))


def warn(test_name, detail=""):
    global WARN
    WARN += 1
    print(f"  [WARN] {test_name}" + (f" - {detail}" if detail else ""))


async def main():
    global PASS, FAIL, WARN

    async with httpx.AsyncClient(base_url=BASE, timeout=15.0) as client:

        # ============================================================
        print("\n" + "=" * 70)
        print("  SWAP SPOT 종합 테스트")
        print("=" * 70)

        # ============================================================
        # TEST 1: 전체 통화 데이터 검증
        # ============================================================
        print("\n[1] 전체 통화 환율 데이터 검증")
        print("-" * 50)

        resp = await client.get("/api/rates/latest")
        result("API /api/rates/latest 응답", resp.status_code == 200, f"HTTP {resp.status_code}")
        rates = resp.json()
        result("환율 데이터 존재", len(rates) > 0, f"{len(rates)}개 통화")

        # 수출입은행 실제 데이터 검증
        koreaexim_rates = [r for r in rates if r["source"] == "koreaexim"]
        demo_rates = [r for r in rates if r["source"] == "demo"]
        result("수출입은행 실제 데이터 수신", len(koreaexim_rates) > 0, f"{len(koreaexim_rates)}개 통화")

        # 주요 통화 존재 확인
        currency_codes = {r["currency_code"] for r in rates}
        major_currencies = ["USD", "EUR", "JPY", "GBP", "CNH", "CHF", "CAD", "AUD", "HKD", "SGD", "THB"]
        for cur in major_currencies:
            present = cur in currency_codes
            if present:
                rate_obj = next(r for r in rates if r["currency_code"] == cur)
                result(f"  {cur} 데이터 확인", True, f"{rate_obj['rate']:,.2f}원 (source: {rate_obj['source']})")
            else:
                warn(f"  {cur} 데이터 없음")

        # 환율값 유효성 검증
        print("\n[2] 환율값 유효성 검증")
        print("-" * 50)

        # 합리적 범위 체크 (2026년 2월 기준)
        EXPECTED_RANGES = {
            "USD": (1200, 1600),
            "EUR": (1300, 1900),
            "JPY": (700, 1200),  # 100엔당
            "GBP": (1500, 2200),
            "CHF": (1400, 2000),
            "CAD": (800, 1300),
            "AUD": (700, 1200),
            "HKD": (140, 220),
            "SGD": (900, 1300),
        }

        for cur, (low, high) in EXPECTED_RANGES.items():
            rate_obj = next((r for r in rates if r["currency_code"] == cur), None)
            if rate_obj:
                in_range = low <= rate_obj["rate"] <= high
                result(
                    f"  {cur} 범위 검증 ({low:,}~{high:,})",
                    in_range,
                    f"{rate_obj['rate']:,.2f}원" + ("" if in_range else " [범위 초과!]")
                )
            else:
                warn(f"  {cur} 범위 검증 스킵 (데이터 없음)")

        # 0 이하 환율 체크
        zero_rates = [r for r in rates if r["rate"] <= 0]
        result("0 이하 환율 없음", len(zero_rates) == 0, f"{len(zero_rates)}건 발견" if zero_rates else "정상")

        # ============================================================
        # TEST 3: 히스토리 데이터 검증
        # ============================================================
        print("\n[3] 히스토리 데이터 검증")
        print("-" * 50)

        for period, days in [("7일", 7), ("30일", 30), ("90일", 90)]:
            resp = await client.get(f"/api/rates/USD?days={days}")
            data = resp.json()
            count = len(data.get("rates", []))
            # 영업일만 있으므로 대략 days * 5/7
            expected_min = int(days * 0.5)
            result(f"  USD {period} 히스토리", count >= expected_min, f"{count}건 (최소 {expected_min}건 기대)")

        # 날짜 순서 검증
        resp = await client.get("/api/rates/USD?days=90")
        history = resp.json().get("rates", [])
        dates = [r["date"] for r in history]
        is_sorted = dates == sorted(dates)
        result("  날짜 오름차순 정렬", is_sorted)

        # 연속성 검증 (큰 갭 없는지)
        if len(history) > 1:
            from datetime import datetime, timedelta
            max_gap = 0
            for i in range(1, len(history)):
                d1 = datetime.fromisoformat(history[i-1]["date"])
                d2 = datetime.fromisoformat(history[i]["date"])
                gap = (d2 - d1).days
                max_gap = max(max_gap, gap)
            result("  데이터 연속성", max_gap <= 4, f"최대 갭: {max_gap}일" + (" (주말+공휴일 고려 정상)" if max_gap <= 4 else ""))

        # 다중 통화 히스토리
        for cur in ["EUR", "JPY", "GBP"]:
            resp = await client.get(f"/api/rates/{cur}?days=30")
            count = len(resp.json().get("rates", []))
            result(f"  {cur} 30일 히스토리", count > 0, f"{count}건")

        # ============================================================
        # TEST 4: 환전 타이밍 엔진 전체 테스트
        # ============================================================
        print("\n[4] 환전 타이밍 엔진 검증")
        print("-" * 50)

        timing_currencies = ["USD", "EUR", "JPY", "GBP", "CAD", "AUD", "CHF", "HKD", "SGD", "CNH"]

        for cur in timing_currencies:
            resp = await client.get(f"/api/rates/timing/{cur}")
            if resp.status_code != 200:
                result(f"  {cur} 타이밍 분석", False, f"HTTP {resp.status_code}")
                continue

            data = resp.json()

            # 필수 필드 검증
            required_fields = ["recommendation", "confidence", "current_rate", "signals", "percentile_90d", "ma_short", "ma_long"]
            missing = [f for f in required_fields if f not in data]
            result(f"  {cur} 필수 필드", len(missing) == 0, f"누락: {missing}" if missing else "전체 존재")

            # recommendation 값 검증
            rec = data.get("recommendation", "")
            valid_rec = rec in ("BUY", "HOLD", "WAIT")
            result(f"  {cur} 추천값 유효성", valid_rec, f"{rec}")

            # confidence 범위 검증
            conf = data.get("confidence", -1)
            valid_conf = 0 <= conf <= 1
            result(f"  {cur} 신뢰도 범위", valid_conf, f"{conf:.2f}")

            # 시그널 검증
            signals = data.get("signals", {})
            expected_signals = ["moving_average", "percentile", "bollinger"]
            for sig_name in expected_signals:
                sig_val = signals.get(sig_name, "")
                valid_sig = sig_val in ("BUY", "HOLD", "WAIT")
                if not valid_sig:
                    result(f"  {cur} {sig_name} 시그널", False, f"'{sig_val}'")

            # 시그널과 최종 추천의 일관성 검증
            sig_values = list(signals.values())
            buy_count = sig_values.count("BUY")
            wait_count = sig_values.count("WAIT")

            if rec == "BUY":
                consistent = buy_count >= 2
            elif rec == "WAIT":
                consistent = wait_count >= 2
            else:  # HOLD
                consistent = buy_count < 2 and wait_count < 2

            result(
                f"  {cur} 시그널-추천 일관성",
                consistent,
                f"{rec} (BUY:{buy_count} HOLD:{sig_values.count('HOLD')} WAIT:{wait_count})"
            )

            # MA 크로스오버 로직 검증
            ma_short = data.get("ma_short", 0)
            ma_long = data.get("ma_long", 0)
            if ma_short > 0 and ma_long > 0:
                ma_sig = signals.get("moving_average", "")
                if ma_short > ma_long * 1.002 and ma_sig != "BUY":
                    warn(f"  {cur} MA 크로스: short({ma_short:.2f}) > long({ma_long:.2f}) but signal={ma_sig}")
                elif ma_short < ma_long * 0.998 and ma_sig != "WAIT":
                    warn(f"  {cur} MA 크로스: short({ma_short:.2f}) < long({ma_long:.2f}) but signal={ma_sig}")

            # 백분위 로직 검증
            pct = data.get("percentile_90d", 50)
            pct_sig = signals.get("percentile", "")
            if pct <= 25 and pct_sig != "BUY":
                warn(f"  {cur} 백분위 {pct}% but signal={pct_sig}")
            elif pct >= 75 and pct_sig != "WAIT":
                warn(f"  {cur} 백분위 {pct}% but signal={pct_sig}")

        # ============================================================
        # TEST 5: 알림 시스템 CRUD 테스트
        # ============================================================
        print("\n[5] 알림 시스템 CRUD 테스트")
        print("-" * 50)

        # 알림 생성
        alert_data = {"currency_code": "USD", "condition": "below", "threshold": 1400.0}
        resp = await client.post("/api/alerts/", json=alert_data)
        result("알림 생성", resp.status_code == 200, f"HTTP {resp.status_code}")
        created = resp.json()
        alert_id = created.get("id")
        result("알림 ID 할당", alert_id is not None, f"ID={alert_id}")
        result("알림 필드 일치", created.get("currency_code") == "USD" and created.get("threshold") == 1400.0)

        # 두 번째 알림 생성
        alert_data2 = {"currency_code": "EUR", "condition": "above", "threshold": 1800.0}
        resp = await client.post("/api/alerts/", json=alert_data2)
        result("두 번째 알림 생성", resp.status_code == 200)

        # 변동률 알림 생성
        alert_data3 = {"currency_code": "JPY", "condition": "percent_change", "threshold": 1.5}
        resp = await client.post("/api/alerts/", json=alert_data3)
        result("변동률 알림 생성", resp.status_code == 200)

        # 목록 조회
        resp = await client.get("/api/alerts/")
        alerts = resp.json()
        result("알림 목록 조회", len(alerts) >= 3, f"{len(alerts)}건")

        # 알림 삭제
        resp = await client.delete(f"/api/alerts/{alert_id}")
        result("알림 삭제", resp.json().get("ok") == True)

        # 삭제 후 목록 확인
        resp = await client.get("/api/alerts/")
        alerts_after = resp.json()
        result("삭제 후 목록 감소", len(alerts_after) == len(alerts) - 1, f"{len(alerts_after)}건")

        # 없는 알림 삭제
        resp = await client.delete("/api/alerts/99999")
        result("없는 알림 삭제 처리", resp.status_code == 404, f"HTTP {resp.status_code}")

        # ============================================================
        # TEST 6: WebSocket 연결 테스트
        # ============================================================
        print("\n[6] WebSocket 연결 테스트")
        print("-" * 50)

        import websockets
        try:
            async with websockets.connect("ws://localhost:8000/ws/rates", close_timeout=3) as ws:
                # 연결 즉시 snapshot 수신해야 함
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                result("WebSocket 연결 성공", True)
                result("초기 스냅샷 수신", data.get("type") == "snapshot", f"type={data.get('type')}")
                ws_currencies = list(data.get("data", {}).keys())
                result("스냅샷 데이터 포함", len(ws_currencies) > 0, f"{len(ws_currencies)}개 통화")
        except ImportError:
            warn("WebSocket 테스트 스킵 (websockets 패키지 미설치)")
        except Exception as e:
            result("WebSocket 연결", False, str(e))

        # ============================================================
        # TEST 7: 소스 헬스체크
        # ============================================================
        print("\n[7] 데이터 소스 헬스체크")
        print("-" * 50)

        resp = await client.get("/api/rates/health/sources")
        health = resp.json()
        result("헬스체크 API 응답", resp.status_code == 200)
        for source, status in health.items():
            if status:
                result(f"  {source} 상태", True, "정상")
            else:
                warn(f"  {source} 상태: 비정상 (API 키 미설정 또는 접속 불가)")

        # ============================================================
        # TEST 8: Swagger 문서
        # ============================================================
        print("\n[8] API 문서 검증")
        print("-" * 50)

        resp = await client.get("/docs")
        result("Swagger UI 접근", resp.status_code == 200)

        resp = await client.get("/openapi.json")
        result("OpenAPI 스펙 접근", resp.status_code == 200)
        openapi = resp.json()
        paths = list(openapi.get("paths", {}).keys())
        result("API 엔드포인트 등록", len(paths) >= 5, f"{len(paths)}개 경로: {paths}")

        # ============================================================
        # TEST 9: 프론트엔드 정적 파일
        # ============================================================
        print("\n[9] 프론트엔드 정적 파일 검증")
        print("-" * 50)

        for path, name in [("/", "index.html"), ("/css/style.css", "CSS"), ("/js/app.js", "JavaScript")]:
            resp = await client.get(path)
            result(f"  {name} 로드", resp.status_code == 200, f"{len(resp.text):,} bytes")

        # HTML + JS에 핵심 요소 확인
        resp = await client.get("/")
        html = resp.text
        resp_js = await client.get("/js/app.js")
        js = resp_js.text
        combined = html.lower() + js.lower()
        elements = {
            "rate-cards": "환율 카드 섹션",
            "timing-section": "타이밍 추천 섹션",
            "ratechart": "차트 캔버스",
            "alert-section": "알림 섹션",
            "chart.js": "Chart.js CDN",
            "websocket": "WebSocket 코드",
        }
        for key, name in elements.items():
            result(f"  {name} 요소", key.lower() in combined)

        # ============================================================
        # TEST 10: 에지 케이스
        # ============================================================
        print("\n[10] 에지 케이스 처리")
        print("-" * 50)

        # 존재하지 않는 통화
        resp = await client.get("/api/rates/XYZ?days=30")
        result("없는 통화 조회", resp.status_code == 200, f"빈 결과 반환: {len(resp.json().get('rates', []))}건")

        # 없는 통화 타이밍
        resp = await client.get("/api/rates/timing/XYZ")
        data = resp.json()
        result("없는 통화 타이밍", data.get("recommendation") == "HOLD", "HOLD로 안전 처리")

        # 큰 기간 조회
        resp = await client.get("/api/rates/USD?days=365")
        result("365일 히스토리", resp.status_code == 200, f"{len(resp.json().get('rates', []))}건")

        # 소문자 통화 코드
        resp = await client.get("/api/rates/usd?days=7")
        result("소문자 통화 코드 처리", resp.status_code == 200)

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 70)
    print(f"  종합 결과: PASS {PASS} / FAIL {FAIL} / WARN {WARN}")
    print(f"  성공률: {PASS/(PASS+FAIL)*100:.1f}%")
    print("=" * 70)

    if FAIL > 0:
        print("\n  [!] 실패 항목이 있습니다. 위 로그를 확인하세요.")
        sys.exit(1)
    else:
        print("\n  모든 테스트 통과!")


if __name__ == "__main__":
    asyncio.run(main())
