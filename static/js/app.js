// Swap Spot - Main Application
// 모든 환율은 KRW(원) 기준으로 표시

const CURRENCY_INFO = {
    USD: { name: '미국 달러', symbol: '$', unit: 1 },
    EUR: { name: '유로', symbol: '€', unit: 1 },
    JPY: { name: '일본 엔', symbol: '¥', unit: 100 },
    GBP: { name: '영국 파운드', symbol: '£', unit: 1 },
    CNY: { name: '중국 위안', symbol: '¥', unit: 1 },
    CNH: { name: '중국 위안(역외)', symbol: '¥', unit: 1 },
    CHF: { name: '스위스 프랑', symbol: 'Fr', unit: 1 },
    CAD: { name: '캐나다 달러', symbol: 'C$', unit: 1 },
    AUD: { name: '호주 달러', symbol: 'A$', unit: 1 },
    HKD: { name: '홍콩 달러', symbol: 'HK$', unit: 1 },
    SGD: { name: '싱가포르 달러', symbol: 'S$', unit: 1 },
    THB: { name: '태국 바트', symbol: '฿', unit: 1 },
    AED: { name: 'UAE 디르함', symbol: 'د.إ', unit: 1 },
    BHD: { name: '바레인 디나르', symbol: 'BD', unit: 1 },
    BND: { name: '브루나이 달러', symbol: 'B$', unit: 1 },
    DKK: { name: '덴마크 크로네', symbol: 'kr', unit: 1 },
    IDR: { name: '인도네시아 루피아', symbol: 'Rp', unit: 100 },
    KWD: { name: '쿠웨이트 디나르', symbol: 'KD', unit: 1 },
    MYR: { name: '말레이시아 링깃', symbol: 'RM', unit: 1 },
    NOK: { name: '노르웨이 크로네', symbol: 'kr', unit: 1 },
    NZD: { name: '뉴질랜드 달러', symbol: 'NZ$', unit: 1 },
    SAR: { name: '사우디 리얄', symbol: 'SR', unit: 1 },
    SEK: { name: '스웨덴 크로나', symbol: 'kr', unit: 1 },
};

const CONDITION_LABELS = {
    below: '이하',
    above: '이상',
    percent_change: '변동률(%)',
};

let rateChart = null;
let ws = null;
let currentRates = {};
let wsReconnectAttempts = 0;
let wsReconnectTimer = null;
let chartUpdateTimer = null;
let timingUpdateTimer = null;

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', () => {
    fetchLatestRates();
    fetchTimingData();
    initChart();
    loadAlerts();
    connectWebSocket();
    setupEventListeners();
    requestNotificationPermission();
    initTravelPlanner();
});

// ===== Event Listeners =====
function setupEventListeners() {
    document.getElementById('timing-currency').addEventListener('change', fetchTimingData);
    document.getElementById('chart-currency').addEventListener('change', () => debouncedChartUpdate());
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            debouncedChartUpdate();
        });
    });
    document.getElementById('add-alert-btn').addEventListener('click', addAlert);
    document.getElementById('travel-analyze-btn').addEventListener('click', fetchTravelTiming);
    document.getElementById('forecast-btn').addEventListener('click', fetchForecast);
}

// ===== Debounce helpers =====
function debouncedChartUpdate() {
    if (chartUpdateTimer) clearTimeout(chartUpdateTimer);
    chartUpdateTimer = setTimeout(() => updateChart(), 300);
}

function debouncedTimingUpdate() {
    if (timingUpdateTimer) clearTimeout(timingUpdateTimer);
    timingUpdateTimer = setTimeout(() => fetchTimingData(), 300);
}

// ===== Rates =====
async function fetchLatestRates() {
    try {
        const resp = await fetch('/api/rates/latest');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const rates = await resp.json();
        currentRates = {};
        rates.forEach(r => { currentRates[r.currency_code] = r; });
        renderRateCards(rates);
        updateStatus('connected', new Date());
    } catch (e) {
        console.error('Failed to fetch rates:', e);
        document.getElementById('rate-cards').innerHTML = '<tr><td colspan="7" class="loading">데이터 로딩 실패. 새로고침 해주세요.</td></tr>';
    }
}

function renderRateCards(rates) {
    const container = document.getElementById('rate-cards');
    if (!rates || !rates.length) {
        container.innerHTML = '<tr><td colspan="7" class="loading">데이터 없음. API 키를 확인해주세요.</td></tr>';
        return;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function cellHtml(r) {
        const code = escapeHtml(r.currency_code || '');
        const info = CURRENCY_INFO[r.currency_code] || { name: r.currency_name || r.currency_code, unit: 1 };
        const unitLabel = info.unit > 1 ? ` (${info.unit}단위)` : '';
        return `
            <td class="cell-clickable" onclick="selectCurrency('${code}')" data-currency="${code}"><span class="currency-code">${code}</span></td>
            <td class="cell-clickable" onclick="selectCurrency('${code}')"><span class="currency-name-cell">${escapeHtml(info.name)}${unitLabel}</span></td>
            <td class="col-right rate-value-cell cell-clickable" onclick="selectCurrency('${code}')">${krw(r.rate)}</td>`;
    }

    const rows = [];
    const half = Math.ceil(rates.length / 2);
    for (let i = 0; i < half; i++) {
        const left = rates[i];
        const right = rates[i + half];
        rows.push(`<tr class="rate-row" data-currency="${escapeHtml(left.currency_code)}${right ? ' ' + escapeHtml(right.currency_code) : ''}">
            ${cellHtml(left)}
            <td class="col-divider"></td>
            ${right ? cellHtml(right) : '<td></td><td></td><td></td>'}
        </tr>`);
    }
    container.innerHTML = rows.join('');
}

function selectCurrency(code) {
    document.getElementById('chart-currency').value = code;
    document.getElementById('timing-currency').value = code;
    debouncedChartUpdate();
    debouncedTimingUpdate();
}

// ===== Timing =====
async function fetchTimingData() {
    const currency = document.getElementById('timing-currency').value;
    const container = document.getElementById('timing-result');
    container.innerHTML = '<div class="timing-loading">분석 중...</div>';

    try {
        const resp = await fetch(`/api/rates/timing/${encodeURIComponent(currency)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderTiming(data, currency);
    } catch (e) {
        container.innerHTML = '<div class="timing-loading">분석 실패</div>';
    }
}

function renderTiming(data, currency) {
    const container = document.getElementById('timing-result');
    if (!data || !data.recommendation) {
        container.innerHTML = '<div class="timing-loading">데이터 부족</div>';
        return;
    }
    const rec = data.recommendation;
    const recLabel = { BUY: '매수 적기', HOLD: '관망', WAIT: '대기' }[rec] || rec;
    const recDesc = {
        BUY: '현재 환율이 최근 대비 낮은 수준입니다. 환전하기 좋은 시점일 수 있습니다.',
        HOLD: '환율이 평균 수준입니다. 급하지 않다면 추이를 지켜보세요.',
        WAIT: '현재 환율이 최근 대비 높은 수준입니다. 조금 더 기다려보는 것을 추천합니다.',
    }[rec] || '';
    const confPct = Math.round((data.confidence || 0) * 100);

    const signals = data.signals || {};
    const signalHtml = Object.entries(signals).map(([key, val]) => {
        const label = { moving_average: '이동평균', percentile: '백분위', bollinger: '볼린저' }[key] || key;
        const valLabel = { BUY: '매수', HOLD: '관망', WAIT: '대기' }[val] || val;
        return `<span class="signal-tag ${val}">${label}: ${valLabel}</span>`;
    }).join(' ');

    const info = CURRENCY_INFO[currency] || {};
    const unitNote = info.unit > 1 ? ` (${info.unit}단위당)` : '';

    container.innerHTML = `
        <div class="timing-badge ${rec}">
            <span>${recLabel}</span>
            <span class="confidence">신뢰도 ${confPct}%</span>
        </div>
        <div class="timing-details">
            <div class="timing-detail-item" style="grid-column: 1 / -1;">
                <div class="label">${currency}/KRW 환전 판단${unitNote}</div>
                <div class="value" style="font-size: 0.85rem; font-weight: 400; color: var(--text-secondary);">${recDesc}</div>
            </div>
            <div class="timing-detail-item">
                <div class="label">현재 환율 (원)</div>
                <div class="value">${krw(data.current_rate)}</div>
            </div>
            <div class="timing-detail-item">
                <div class="label">90일 내 위치</div>
                <div class="value">${data.percentile_90d != null ? data.percentile_90d + '%' : '-'} <span style="font-size:0.75rem;color:var(--text-secondary)">${data.percentile_90d != null ? '(상위 ' + (100 - data.percentile_90d).toFixed(1) + '%)' : ''}</span></div>
            </div>
            <div class="timing-detail-item">
                <div class="label">단기 이동평균 5일 (원)</div>
                <div class="value">${krw(data.ma_short)}</div>
            </div>
            <div class="timing-detail-item">
                <div class="label">장기 이동평균 20일 (원)</div>
                <div class="value">${krw(data.ma_long)}</div>
            </div>
            <div class="timing-detail-item" style="grid-column: 1 / -1;">
                <div class="label">시그널 분석</div>
                <div class="value">${signalHtml}</div>
            </div>
        </div>
    `;
}

// ===== Travel Planner =====
function initTravelPlanner() {
    const dateInput = document.getElementById('travel-date');
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    dateInput.min = tomorrow.toISOString().split('T')[0];
    dateInput.value = '';
}

async function fetchTravelTiming() {
    const currency = document.getElementById('travel-currency').value;
    const travelDate = document.getElementById('travel-date').value;
    const container = document.getElementById('travel-result');

    if (!travelDate) {
        container.innerHTML = '<div class="travel-empty">출발 날짜를 선택해주세요.</div>';
        return;
    }

    container.innerHTML = '<div class="travel-loading">분석 중...</div>';

    try {
        const resp = await fetch(`/api/rates/travel-timing/${encodeURIComponent(currency)}?travel_date=${encodeURIComponent(travelDate)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderTravelTiming(data);
    } catch (e) {
        container.innerHTML = '<div class="travel-loading">분석 실패</div>';
    }
}

function renderTravelTiming(data) {
    const container = document.getElementById('travel-result');

    if (!data || !data.recommendation) {
        container.innerHTML = '<div class="travel-loading">데이터 부족</div>';
        return;
    }

    const recLabels = { BUY: '지금 환전', HOLD: '조금 더 관망', WAIT: '하락 대기' };
    const recLabel = recLabels[data.recommendation] || data.recommendation;

    const urgencyColors = {
        immediate: 'var(--red)',
        urgent: '#ff8c42',
        caution: 'var(--yellow)',
        relaxed: 'var(--green)',
    };
    const urgencyBg = {
        immediate: 'rgba(255, 77, 106, 0.15)',
        urgent: 'rgba(255, 140, 66, 0.15)',
        caution: 'rgba(255, 183, 77, 0.15)',
        relaxed: 'rgba(0, 214, 143, 0.15)',
    };
    const color = urgencyColors[data.urgency] || 'var(--text-secondary)';
    const bg = urgencyBg[data.urgency] || 'transparent';

    const signalHtml = data.signals ? Object.entries(data.signals).map(([key, val]) => {
        const names = { moving_average: '이동평균', percentile: '백분위', bollinger: '볼린저' };
        return `<span class="signal-tag ${val}">${names[key] || key}: ${val}</span>`;
    }).join(' ') : '';

    container.innerHTML = `
        <div class="travel-result-card">
            <div class="travel-top">
                <div class="travel-badge" style="border-color:${color};background:${bg};color:${color}">
                    <div class="travel-dday">D-${data.days_remaining ?? '?'}</div>
                    <div class="travel-rec">${recLabel}</div>
                    <div class="travel-urgency">${data.urgency_label || ''}</div>
                </div>
                <div class="travel-info">
                    <div class="travel-message">${data.message || ''}</div>
                    <div class="travel-tip">${data.tip || ''}</div>
                </div>
            </div>
            <div class="travel-details">
                <div class="travel-detail-item">
                    <div class="label">현재 환율</div>
                    <div class="value">${krw(data.current_rate)}</div>
                </div>
                ${data.target_rate ? `<div class="travel-detail-item target-rate-item">
                    <div class="label">목표 환율</div>
                    <div class="value target-rate-value">${krw(data.target_rate)}</div>
                </div>` : ''}
                <div class="travel-detail-item">
                    <div class="label">90일 백분위</div>
                    <div class="value">${data.percentile_90d != null ? data.percentile_90d.toFixed(1) + '%' : '-'}</div>
                </div>
                <div class="travel-detail-item">
                    <div class="label">신뢰도</div>
                    <div class="value">${data.confidence != null ? (data.confidence * 100).toFixed(0) + '%' : '-'}</div>
                </div>
                <div class="travel-detail-item">
                    <div class="label">시그널</div>
                    <div class="value">${signalHtml}</div>
                </div>
            </div>
        </div>
    `;
}

// ===== Forecast (Monte Carlo) =====
async function fetchForecast() {
    const currency = document.getElementById('forecast-currency').value;
    const container = document.getElementById('forecast-result');
    container.innerHTML = '<div class="forecast-loading">시뮬레이션 실행 중...</div>';

    try {
        const resp = await fetch(`/api/rates/forecast/${encodeURIComponent(currency)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderForecast(data);
    } catch (e) {
        container.innerHTML = '<div class="forecast-loading">분석 실패</div>';
    }
}

function renderForecast(data) {
    const container = document.getElementById('forecast-result');

    if (!data || data.error) {
        container.innerHTML = `<div class="forecast-loading">${data?.error || '데이터 부족'}</div>`;
        return;
    }

    function getDateRange(weeks) {
        const start = new Date();
        const end = new Date();
        end.setDate(end.getDate() + weeks * 7);
        const fmt = d => `${d.getMonth() + 1}/${d.getDate()}`;
        return `${fmt(start)} ~ ${fmt(end)}`;
    }

    let html = `
        <div class="forecast-meta">
            <span>현재 환율: ${krw(data.current_rate)}</span>
        </div>
        <div class="forecast-horizons">
    `;

    for (const horizon of data.horizons) {
        html += `
            <div class="forecast-horizon-card">
                <div class="horizon-header">${getDateRange(horizon.weeks)}</div>
                <div class="horizon-distribution">
                    <span class="dist-range">${krw(horizon.distribution.p25)} ~ ${krw(horizon.distribution.p75)}</span>
                </div>
                <div class="horizon-targets">
        `;

        for (const target of horizon.targets) {
            const pctValue = Math.round(target.probability * 100);
            const barColor = pctValue >= 50 ? 'var(--green)'
                           : pctValue >= 25 ? 'var(--yellow)'
                           : 'var(--text-secondary)';

            html += `
                <div class="target-row">
                    <span class="target-rate">${target.label} 이하</span>
                    <div class="target-bar-wrap">
                        <div class="target-bar" style="width:${pctValue}%;background:${barColor}"></div>
                    </div>
                    <span class="target-prob" style="color:${barColor}">${pctValue}%</span>
                </div>
            `;
        }

        html += `</div></div>`;
    }

    html += `</div>`;
    container.innerHTML = html;
}

// ===== Chart =====
function initChart() {
    const ctx = document.getElementById('rateChart').getContext('2d');
    rateChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: '환전 시 수령액',
                    data: [],
                    borderColor: '#00d68f',
                    backgroundColor: 'rgba(0, 214, 143, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    borderWidth: 2.5,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#8b8fa3', maxTicksLimit: 10 },
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: {
                        color: '#8b8fa3',
                        callback: function(value) {
                            return value.toLocaleString('ko-KR') + '원';
                        },
                    },
                    title: {
                        display: true,
                        text: 'KRW (원)',
                        color: '#8b8fa3',
                        font: { size: 12 },
                    },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1a1d27',
                    borderColor: '#2a2e3f',
                    borderWidth: 1,
                    titleColor: '#e4e6eb',
                    bodyColor: '#e4e6eb',
                    callbacks: {
                        label: function(context) {
                            const val = context.parsed.y;
                            if (val == null) return null;
                            return `수령액: ${val.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}원`;
                        },
                    },
                },
                zoom: {
                    zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                    pan: { enabled: true, mode: 'x' },
                },
            },
        },
    });
    updateChart();
}

async function updateChart() {
    const currency = document.getElementById('chart-currency').value;
    const activeBtn = document.querySelector('.period-btn.active');
    const days = activeBtn ? parseInt(activeBtn.dataset.days) : 30;

    try {
        const resp = await fetch(`/api/rates/${encodeURIComponent(currency)}?days=${days}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (!data.rates || data.rates.length === 0) {
            rateChart.data.labels = [];
            rateChart.data.datasets[0].data = [];
            rateChart.data.datasets[0].label = `데이터 없음 (${currency}/KRW)`;
            rateChart.update();
            return;
        }

        const labels = data.rates.map(r => r.date);
        const ttBuy = data.rates.map(r => r.tt_buy_rate || r.rate);

        rateChart.data.labels = labels;
        rateChart.data.datasets[0].data = ttBuy;
        rateChart.data.datasets[0].label = `환전 시 수령액 (${currency}/KRW)`;
        rateChart.options.scales.y.title.text = `${currency}/KRW (원)`;
        rateChart.update();
    } catch (e) {
        console.error('Chart update failed:', e);
    }
}

// ===== WebSocket =====
function connectWebSocket() {
    if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/rates`);

    ws.onopen = () => {
        wsReconnectAttempts = 0;
        updateStatus('connected');
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'snapshot' || msg.type === 'update') {
                Object.entries(msg.data).forEach(([code, rate]) => {
                    currentRates[code] = rate;
                    flashCard(code);
                });
                const rateList = Object.values(currentRates);
                renderRateCards(rateList);
                updateStatus('connected', new Date());
            }
        } catch (e) {
            console.error('WS message parse error:', e);
        }
    };

    ws.onclose = () => {
        updateStatus('disconnected');
        scheduleReconnect();
    };

    ws.onerror = () => {
        updateStatus('disconnected');
    };
}

function scheduleReconnect() {
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
    const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 30000);
    wsReconnectAttempts++;
    console.log(`WS reconnect in ${delay}ms (attempt ${wsReconnectAttempts})`);
    wsReconnectTimer = setTimeout(connectWebSocket, delay);
}

// Keep-alive ping (single interval, set once)
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
    }
}, 30000);

function flashCard(currencyCode) {
    const cells = document.querySelectorAll(`.cell-clickable[data-currency="${currencyCode}"]`);
    cells.forEach(cell => {
        const row = cell.closest('tr');
        if (row) {
            row.classList.remove('flash');
            void row.offsetWidth;
            row.classList.add('flash');
        }
    });
}

function updateStatus(status, time) {
    const dot = document.querySelector('.dot');
    const statusText = document.getElementById('connection-status');
    const lastUpdated = document.getElementById('last-updated');

    if (!dot || !statusText) return;

    dot.className = 'dot ' + status;
    statusText.textContent = status === 'connected' ? '실시간 연결' : status === 'disconnected' ? '연결 끊김' : '연결 중...';

    if (time && lastUpdated) {
        lastUpdated.textContent = `(${time.toLocaleTimeString('ko-KR')})`;
    }
}

// ===== Alerts =====
async function loadAlerts() {
    try {
        const resp = await fetch('/api/alerts/');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const alerts = await resp.json();
        renderAlerts(alerts);
    } catch (e) {
        console.error('Failed to load alerts:', e);
    }
}

function renderAlerts(alerts) {
    const container = document.getElementById('alert-list');
    if (!alerts || !alerts.length) {
        container.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem; padding: 0.5rem;">설정된 알림 없음</div>';
        return;
    }
    container.innerHTML = alerts.map(a => {
        const condLabel = CONDITION_LABELS[a.condition] || a.condition;
        const valueLabel = a.condition === 'percent_change'
            ? `${a.threshold}%`
            : `${krw(a.threshold)}`;
        return `
            <div class="alert-item">
                <span class="alert-info">${a.currency_code}/KRW ${valueLabel} ${condLabel}</span>
                <button class="delete-btn" onclick="deleteAlert(${parseInt(a.id)})">X</button>
            </div>
        `;
    }).join('');
}

async function addAlert() {
    const currency = document.getElementById('alert-currency').value;
    const condition = document.getElementById('alert-condition').value;
    const threshold = parseFloat(document.getElementById('alert-threshold').value);

    if (isNaN(threshold) || threshold <= 0) {
        alert('유효한 임계값을 입력해주세요.');
        return;
    }

    try {
        const resp = await fetch('/api/alerts/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ currency_code: currency, condition, threshold }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || '알림 추가 실패');
            return;
        }
        document.getElementById('alert-threshold').value = '';
        loadAlerts();
    } catch (e) {
        console.error('Failed to add alert:', e);
    }
}

async function deleteAlert(id) {
    try {
        await fetch(`/api/alerts/${id}`, { method: 'DELETE' });
        loadAlerts();
    } catch (e) {
        console.error('Failed to delete alert:', e);
    }
}

// ===== Notifications =====
function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

function showNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, icon: '/assets/favicon.ico' });
    }
}

// ===== Utility =====
function formatNumber(num) {
    if (num == null) return '-';
    return parseFloat(num).toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function krw(num) {
    if (num == null) return '-';
    return parseFloat(num).toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '원';
}
