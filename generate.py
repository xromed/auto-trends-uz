#!/usr/bin/env python3
"""
Генерирует index.html с данными Google Trends по авторынку Узбекистана.
Запускается ежедневно через GitHub Actions.
"""

import json
import time
import sys
import hashlib
import random
from collections import defaultdict
from datetime import datetime

# ── Данные по умолчанию (если Google Trends недоступен) ──────────────
FALLBACK = {
    "brands": {
        "Chevrolet": 90, "Toyota": 62, "Hyundai": 50, "Haval": 47, "BYD": 41,
        "Kia": 38, "Chery": 34, "Geely": 28, "Lada": 24, "BMW": 20,
        "Mercedes": 18, "Honda": 16, "Daewoo": 14, "Nissan": 13, "Ravon": 10,
    },
    "models": {
        "Cobalt": 78, "Nexia": 72, "Malibu": 60, "Tracker": 52, "Captiva": 48,
        "Onix": 44, "Camry": 40, "Damas": 36, "Tucson": 32, "H6": 28,
        "Corolla": 26, "Sportage": 24, "Vesta": 20, "Tiggo": 18, "RAV4": 16,
        "Spark": 14, "Labo": 12, "Land Cruiser": 22, "Jolion": 18, "Atto 3": 15,
        "Elantra": 18, "Rio": 16, "Atlas": 12, "Granta": 10, "Almera": 9,
        "Santa Fe": 14, "Prado": 12, "Coolray": 10, "Cerato": 11, "CR-V": 8,
    },
}

# Привязка модели к бренду для подписей на графике
MODEL_BRANDS = {
    "Cobalt": "Chevrolet", "Nexia": "Chevrolet", "Malibu": "Chevrolet",
    "Tracker": "Chevrolet", "Captiva": "Chevrolet", "Onix": "Chevrolet",
    "Spark": "Chevrolet", "Labo": "Chevrolet", "Damas": "Chevrolet",
    "Camry": "Toyota", "Corolla": "Toyota", "RAV4": "Toyota",
    "Land Cruiser": "Toyota", "Prado": "Toyota", "Hilux": "Toyota",
    "Tucson": "Hyundai", "Santa Fe": "Hyundai", "Elantra": "Hyundai",
    "Creta": "Hyundai", "Accent": "Hyundai",
    "Sportage": "Kia", "Rio": "Kia", "Cerato": "Kia", "Seltos": "Kia",
    "H6": "Haval", "Jolion": "Haval", "F7": "Haval",
    "Tiggo": "Chery", "Arrizo": "Chery",
    "Atlas": "Geely", "Coolray": "Geely",
    "Vesta": "Lada", "Granta": "Lada", "Niva": "Lada",
    "Atto 3": "BYD", "Han": "BYD", "Seal": "BYD",
    "Spark": "Chevrolet", "Labo": "Chevrolet",
    "Land Cruiser": "Toyota", "Prado": "Toyota",
    "Elantra": "Hyundai", "Santa Fe": "Hyundai",
    "Rio": "Kia", "Cerato": "Kia",
    "Jolion": "Haval",
    "Atlas": "Geely", "Coolray": "Geely",
    "Almera": "Nissan",
    "CR-V": "Honda",
}

BRAND_GROUPS = [
    ["Chevrolet", "Toyota", "Hyundai", "Haval", "BYD"],
    ["Kia", "Chery", "Geely", "Lada", "BMW"],
    ["Mercedes", "Honda", "Daewoo", "Nissan", "Ravon"],
]
MODEL_GROUPS = [
    ["Cobalt", "Nexia", "Malibu", "Tracker", "Captiva"],
    ["Onix", "Camry", "Damas", "Tucson", "H6"],
    ["Corolla", "Sportage", "Vesta", "Tiggo", "RAV4"],
    ["Spark", "Labo", "Land Cruiser", "Jolion", "Atto 3"],
    ["Elantra", "Rio", "Atlas", "Granta", "Almera"],
    ["Santa Fe", "Prado", "Coolray", "Cerato", "CR-V"],
]


def make_fallback_trend(brand, base_value, length=12):
    """Детерминированный тренд по хэшу имени — одинаковый при каждом запуске."""
    seed = int(hashlib.md5(brand.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    values = []
    v = base_value * (0.7 + rng.random() * 0.3)
    for _ in range(length):
        v = max(5, min(100, v + (rng.random() - 0.47) * 12))
        values.append(round(v))
    values[-1] = base_value
    return values


def resample_monthly(df, columns):
    """Группируем недельные данные pytrends по месяцам, берём последние 12."""
    monthly = defaultdict(lambda: defaultdict(list))
    for date, row in df.iterrows():
        key = (date.year, date.month)
        for col in columns:
            if col in row.index:
                monthly[key][col].append(int(row[col]))
    sorted_keys = sorted(monthly.keys())[-12:]
    result = {col: [] for col in columns}
    for key in sorted_keys:
        for col in columns:
            vals = monthly[key].get(col, [0])
            result[col].append(round(sum(vals) / len(vals)) if vals else 0)
    return result


def fetch_trends():
    try:
        from pytrends.request import TrendReq
    except ImportError:
        print("pytrends не установлен, используем fallback данные")
        return {**FALLBACK, "trend_history": {}}

    pytrends = TrendReq(hl="ru-RU", tz=300, timeout=(10, 30), retries=3, backoff_factor=1)
    brands, models = {}, {}

    for group in BRAND_GROUPS:
        try:
            pytrends.build_payload(group, cat=47, timeframe="today 3-m", geo="UZ")
            time.sleep(3)
            df = pytrends.interest_over_time()
            if not df.empty:
                for kw in group:
                    if kw in df.columns:
                        brands[kw] = int(df[kw].mean())
        except Exception as e:
            print(f"  Ошибка {group}: {e}")
            for kw in group:
                brands[kw] = FALLBACK["brands"].get(kw, 0)
        time.sleep(2)

    for group in MODEL_GROUPS:
        try:
            pytrends.build_payload(group, cat=47, timeframe="today 3-m", geo="UZ")
            time.sleep(3)
            df = pytrends.interest_over_time()
            if not df.empty:
                for kw in group:
                    if kw in df.columns:
                        models[kw] = int(df[kw].mean())
        except Exception as e:
            print(f"  Ошибка {group}: {e}")
            for kw in group:
                models[kw] = FALLBACK["models"].get(kw, 0)
        time.sleep(2)

    if not brands:
        brands = FALLBACK["brands"]
    if not models:
        models = FALLBACK["models"]

    # Нормализуем к 100
    max_b = max(brands.values()) or 1
    max_m = max(models.values()) or 1
    brands = {k: round(v / max_b * 100) for k, v in brands.items()}
    models = {k: round(v / max_m * 100) for k, v in models.items()}

    # Получаем реальную историю топ-5 брендов за 12 месяцев
    top5 = [k for k, _ in sorted(brands.items(), key=lambda x: x[1], reverse=True)[:5]]
    trend_history = {}
    try:
        pytrends.build_payload(top5, cat=47, timeframe="today 12-m", geo="UZ")
        time.sleep(3)
        df12 = pytrends.interest_over_time()
        if not df12.empty:
            trend_history = resample_monthly(df12, top5)
            print(f"  История трендов получена: {len(list(trend_history.values())[0])} месяцев")
    except Exception as e:
        print(f"  Ошибка истории трендов: {e}")

    # Если история не получена — используем детерминированный fallback
    if not trend_history:
        trend_history = {b: make_fallback_trend(b, brands[b]) for b in top5}

    # Daily тренд за последний месяц
    daily_data = {"labels": [], "series": {b: [] for b in top5}}
    try:
        pytrends.build_payload(top5, cat=47, timeframe="today 1-m", geo="UZ")
        time.sleep(3)
        df_d = pytrends.interest_over_time()
        if not df_d.empty:
            daily_data["labels"] = [str(d.date()) for d in df_d.index]
            for b in top5:
                if b in df_d.columns:
                    daily_data["series"][b] = [int(v) for v in df_d[b]]
            print(f"  Daily тренд: {len(daily_data['labels'])} точек")
    except Exception as e:
        print(f"  Ошибка daily тренда: {e}")
        # Детерминированный fallback — 30 дней
        import datetime as dt
        today = datetime.utcnow().date()
        daily_data["labels"] = [str(today - dt.timedelta(days=29-i)) for i in range(30)]
        for b in top5:
            seed = int(hashlib.md5((b+"daily").encode()).hexdigest()[:8], 16)
            rng = random.Random(seed)
            v = brands[b] * (0.8 + rng.random() * 0.2)
            vals = []
            for _ in range(30):
                v = max(5, min(100, v + (rng.random() - 0.47) * 10))
                vals.append(round(v))
            daily_data["series"][b] = vals

    return {"brands": brands, "models": models, "trend_history": trend_history, "daily_data": daily_data}


def build_html(data):
    now = datetime.utcnow()
    date_str = now.strftime("%d.%m.%Y %H:%M") + " UTC"

    brands_json = json.dumps(data["brands"], ensure_ascii=False)
    daily_json = json.dumps(data.get("daily_data", {"labels": [], "series": {}}), ensure_ascii=False)
    # Реальная история трендов (или детерминированный fallback)
    trend_history = data.get("trend_history", {})
    if not trend_history:
        top5 = sorted(data["brands"].items(), key=lambda x: x[1], reverse=True)[:5]
        trend_history = {b: make_fallback_trend(b, v) for b, v in top5}
    trend_json = json.dumps(trend_history, ensure_ascii=False)
    # Для моделей добавляем бренд в ключ: "Cobalt (Chevrolet)"
    models_labeled = {
        f"{model} ({MODEL_BRANDS.get(model, '?')})": val
        for model, val in data["models"].items()
    }
    models_json = json.dumps(models_labeled, ensure_ascii=False)
    # Топ-12 для чарта + остальные → "Другие"
    models_sorted = sorted(models_labeled.items(), key=lambda x: x[1], reverse=True)
    TOP_N = 12
    top_models = dict(models_sorted[:TOP_N])
    other_sum = sum(v for _, v in models_sorted[TOP_N:])
    if other_sum > 0:
        top_models[f"Другие ({len(models_sorted) - TOP_N} моделей)"] = round(other_sum / max(len(models_sorted) - TOP_N, 1))
    models_chart_json = json.dumps(top_models, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Авторынок Узбекистана — Тренды поиска</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f1f5f9; color: #0f172a; min-height: 100vh; }}
    .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #1e40af 100%); color: white; padding: 20px 28px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; }}
    .header p {{ font-size: 12px; color: rgba(255,255,255,0.6); margin-top: 3px; }}
    .live-badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2); border-radius: 20px; padding: 5px 12px; font-size: 12px; }}
    .live-dot {{ width: 7px; height: 7px; background: #4ade80; border-radius: 50%; animation: blink 2s ease-in-out infinite; }}
    @keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:0.3}} }}
    .update-label {{ font-size: 11px; color: rgba(255,255,255,0.45); margin-top: 4px; text-align: right; }}
    .container {{ max-width: 1180px; margin: 0 auto; padding: 22px 18px 36px; }}
    .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }}
    @media (max-width: 700px) {{ .stat-grid {{ grid-template-columns: repeat(2,1fr); }} }}
    .stat-card {{ background: white; border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.07); }}
    .stat-label {{ font-size: 10px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.6px; }}
    .stat-value {{ font-size: 24px; font-weight: 800; color: #0f172a; margin: 4px 0 2px; line-height: 1; }}
    .stat-sub {{ font-size: 11px; color: #94a3b8; }}
    .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }}
    @media (max-width: 700px) {{ .charts-row {{ grid-template-columns: 1fr; }} }}
    .card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 4px 12px rgba(0,0,0,0.04); margin-bottom: 18px; }}
    .card-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }}
    .card-icon {{ width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 15px; }}
    .ci-blue {{ background: #dbeafe; }} .ci-green {{ background: #d1fae5; }} .ci-purple {{ background: #ede9fe; }} .ci-amber {{ background: #fef3c7; }}
    .card-title {{ font-size: 14px; font-weight: 600; color: #1e293b; }}
    .card-sub {{ font-size: 11px; color: #94a3b8; margin-top: 1px; }}
    .chart-box {{ position: relative; height: 300px; }}
    .chart-box-lg {{ position: relative; height: 340px; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .data-table thead th {{ text-align: left; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; padding: 8px 12px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }}
    .data-table tbody tr:hover {{ background: #f8fafc; }}
    .data-table td {{ padding: 9px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }}
    .rank-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 6px; font-size: 11px; font-weight: 700; }}
    .r1 {{ background:#fef9c3;color:#854d0e; }} .r2 {{ background:#f1f5f9;color:#475569; }} .r3 {{ background:#fef3c7;color:#92400e; }} .rn {{ background:#f8fafc;color:#94a3b8; }}
    .bar-bg {{ width: 120px; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 4px; }}
    .glink {{ display: inline-flex; align-items: center; gap: 4px; color: #3b82f6; font-size: 11px; text-decoration: none; background: #eff6ff; padding: 3px 8px; border-radius: 6px; }}
    .glink:hover {{ background: #dbeafe; }}
    .source-note {{ margin-top: 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 16px; font-size: 12px; color: #64748b; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }}
    .footer-bar {{ text-align: center; padding: 28px 16px; color: #94a3b8; font-size: 11px; line-height: 1.8; }}
    .footer-bar a {{ color: #3b82f6; text-decoration: none; }}
    .collapsible-head {{
      cursor: pointer; display: flex; align-items: center; gap: 10px;
      margin-bottom: 0; padding-bottom: 16px; user-select: none;
    }}
    .collapsible-head:hover {{ opacity: 0.85; }}
    .toggle-arrow {{
      margin-left: auto; font-size: 13px; color: #94a3b8;
      transition: transform 0.25s; display: inline-block;
    }}
    .collapsed .toggle-arrow {{ transform: rotate(-90deg); }}
    .collapsible-body {{ overflow: hidden; transition: max-height 0.3s ease, opacity 0.3s; }}
    .collapsible-body.hidden {{ display: none; }}
  </style>
</head>
<body>
<div class="header">
  <div>
    <h1>🚗 Авторынок Узбекистана</h1>
    <p>Тренды поисковых запросов по брендам и моделям · Google Trends · UZ</p>
  </div>
  <div style="text-align:right">
    <div class="live-badge"><span class="live-dot"></span> Обновляется ежедневно</div>
    <div class="update-label">Обновлено: {date_str}</div>
  </div>
</div>
<div class="container">
  <div class="stat-grid">
    <div class="stat-card"><div class="stat-label">Лидер поиска</div><div class="stat-value" id="s-brand">—</div><div class="stat-sub">самый искомый бренд</div></div>
    <div class="stat-card"><div class="stat-label">Топ модель</div><div class="stat-value" id="s-model">—</div><div class="stat-sub">самая искомая модель</div></div>
    <div class="stat-card"><div class="stat-label">Брендов</div><div class="stat-value" id="s-bcount">—</div><div class="stat-sub">в рейтинге</div></div>
    <div class="stat-card"><div class="stat-label">Моделей</div><div class="stat-value" id="s-mcount">—</div><div class="stat-sub">в рейтинге</div></div>
  </div>
  <div class="charts-row">
    <div class="card" style="margin-bottom:0">
      <div class="card-head"><div class="card-icon ci-blue">📊</div><div><div class="card-title">Топ брендов</div><div class="card-sub">Индекс поиска (0–100) · UZ · 3 мес.</div></div></div>
      <div class="chart-box"><canvas id="brandsChart"></canvas></div>
    </div>
    <div class="card" style="margin-bottom:0">
      <div class="card-head"><div class="card-icon ci-green">🏎️</div><div><div class="card-title">Топ моделей</div><div class="card-sub">Индекс поиска (0–100) · UZ · 3 мес.</div></div></div>
      <div class="chart-box"><canvas id="modelsChart"></canvas></div>
    </div>
  </div>
  <div style="height:18px"></div>
  <div class="card">
    <div class="card-head"><div class="card-icon ci-purple">📈</div><div><div class="card-title">Динамика — топ-5 брендов (12 мес.)</div><div class="card-sub">Симуляция на основе текущих индексов</div></div></div>
    <div class="chart-box-lg"><canvas id="trendChart"></canvas></div>
  </div>
  <div class="card" id="card-brands-table">
    <div class="collapsible-head" onclick="toggle('brands-table-body','card-brands-table')">
      <div class="card-icon ci-amber">📋</div>
      <div><div class="card-title">Полный рейтинг брендов</div><div class="card-sub">С прямыми ссылками в Google Trends</div></div>
      <span class="toggle-arrow">▼</span>
    </div>
    <div class="collapsible-body hidden" id="brands-table-body">
      <div style="overflow-x:auto">
        <table class="data-table">
          <thead><tr><th>#</th><th>Бренд</th><th>Индекс</th><th>Популярность</th><th>Trends</th></tr></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
      <div class="source-note">
        ℹ️ Данные: Google Trends (Авто, geo=UZ) · Обновляется ежедневно автоматически
        &nbsp;<a class="glink" href="https://trends.google.com/trends/explore?cat=47&geo=UZ&date=today%203-m" target="_blank">↗ Google Trends</a>
        &nbsp;<a class="glink" href="https://github.com/xromed/auto-trends-uz" target="_blank">↗ GitHub</a>
      </div>
    </div>
  </div>
  <div class="card" id="card-models-table">
    <div class="collapsible-head" onclick="toggle('models-table-body','card-models-table')">
      <div class="card-icon ci-green">🏎️</div>
      <div><div class="card-title">Полный рейтинг моделей</div><div class="card-sub">Все отслеживаемые модели с указанием бренда</div></div>
      <span class="toggle-arrow">▼</span>
    </div>
    <div class="collapsible-body hidden" id="models-table-body">
      <div style="overflow-x:auto">
        <table class="data-table">
          <thead><tr><th>#</th><th>Модель</th><th>Бренд</th><th>Индекс</th><th>Популярность</th><th>Trends</th></tr></thead>
          <tbody id="models-tbody"></tbody>
        </table>
      </div>
    </div>
  </div>
  <div class="card" id="card-daily">
    <div class="collapsible-head" onclick="toggle('daily-body','card-daily')">
      <div class="card-icon ci-purple">📅</div>
      <div><div class="card-title">Daily тренд — топ-5 брендов</div><div class="card-sub">Поиск по дням за последний месяц</div></div>
      <span class="toggle-arrow">▼</span>
    </div>
    <div class="collapsible-body hidden" id="daily-body">
      <div class="chart-box-lg"><canvas id="dailyChart"></canvas></div>
    </div>
  </div>
  <div class="footer-bar">
    Источник: <a href="https://trends.google.com" target="_blank">Google Trends</a> · Авто и транспорт · Узбекистан (UZ)<br>
    Обновлено: {date_str} · GitHub Actions автоматика
  </div>
</div>
<script>
const MONTHS=['Июл','Авг','Сен','Окт','Ноя','Дек','Янв','Фев','Мар','Апр','Май','Июн'];
const C=['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#ec4899','#84cc16','#f97316','#6366f1','#14b8a6','#f43f5e','#a855f7','#0ea5e9','#22c55e'];
const BRANDS={brands_json};
const MODELS={models_json};
const MODELS_CHART={models_chart_json};
const TREND_HISTORY={trend_json};
const DAILY={daily_json};
function sorted(obj,n=999){{return Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,n);}}
function set(id,v){{document.getElementById(id).textContent=v;}}
function toggle(bodyId, cardId){{
  const body=document.getElementById(bodyId);
  const card=document.getElementById(cardId);
  const isHidden=body.classList.contains('hidden');
  body.classList.toggle('hidden');
  card.classList.toggle('collapsed',!isHidden);
  // Если открываем daily chart — перерисовываем (нужен видимый контейнер)
  if(bodyId==='daily-body' && isHidden && !window._dailyRendered){{
    renderDaily(); window._dailyRendered=true;
  }}
}}
function renderDaily(){{
  if(!DAILY.labels||!DAILY.labels.length) return;
  const entries=Object.entries(DAILY.series);
  new Chart(document.getElementById('dailyChart'),{{
    type:'line',
    data:{{
      labels:DAILY.labels,
      datasets:entries.map(([name,vals],i)=>({{
        label:name,data:vals,borderColor:C[i],backgroundColor:C[i]+'15',
        tension:0.3,fill:false,pointRadius:2,pointHoverRadius:5,borderWidth:2
      }}))
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{position:'top',labels:{{font:{{size:12}},usePointStyle:true,padding:14}}}}}},
      scales:{{
        y:{{min:0,max:100,grid:{{color:'#f8fafc'}},ticks:{{font:{{size:11}}}}}},
        x:{{grid:{{display:false}},ticks:{{font:{{size:10}},maxTicksLimit:15}}}}
      }}
    }}
  }});
}}
function renderBar(id,data,cols){{
  const top=sorted(data,13);
  new Chart(document.getElementById(id),{{type:'bar',data:{{labels:top.map(x=>x[0]),datasets:[{{data:top.map(x=>x[1]),backgroundColor:top.map((_,i)=>cols[i%cols.length]+'bb'),borderColor:top.map((_,i)=>cols[i%cols.length]),borderWidth:1,borderRadius:5,borderSkipped:false}}]}},options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>` Индекс: ${{c.raw}}`}}}}}},scales:{{x:{{max:100,grid:{{color:'#f1f5f9'}},ticks:{{font:{{size:11}}}}}},y:{{grid:{{display:false}},ticks:{{font:{{size:12,weight:'600'}}}}}}}}}}  }});
}}
function renderTrend(){{
  const entries=Object.entries(TREND_HISTORY);
  new Chart(document.getElementById('trendChart'),{{type:'line',data:{{labels:MONTHS,datasets:entries.map(([name,vals],i)=>({{label:name,data:vals,borderColor:C[i],backgroundColor:C[i]+'18',tension:0.45,fill:false,pointRadius:3,borderWidth:2.5}}))}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{position:'top',labels:{{font:{{size:12}},usePointStyle:true,padding:14}}}}}},scales:{{y:{{min:0,max:100,grid:{{color:'#f8fafc'}},ticks:{{font:{{size:11}}}}}},x:{{grid:{{display:false}},ticks:{{font:{{size:11}}}}}}}}}}  }});
}}
function renderTable(){{
  const rows=sorted(BRANDS);
  document.getElementById('tbody').innerHTML=rows.map(([b,idx],i)=>{{
    const r=i+1,rc=r===1?'r1':r===2?'r2':r===3?'r3':'rn',col=C[i%C.length];
    const url=`https://trends.google.com/trends/explore?cat=47&geo=UZ&q=${{encodeURIComponent(b)}}&date=today%203-m`;
    return `<tr><td><span class="rank-badge ${{rc}}">${{r}}</span></td><td><strong>${{b}}</strong></td><td><strong>${{idx}}</strong></td><td><div class="bar-bg"><div class="bar-fill" style="width:${{idx}}%;background:${{col}}"></div></div></td><td><a class="glink" href="${{url}}" target="_blank">↗</a></td></tr>`;
  }}).join('');
}}
const bTop=sorted(BRANDS,1),mTop=sorted(MODELS,1);
set('s-brand',bTop[0][0]); set('s-model',mTop[0][0]);
set('s-bcount',Object.keys(BRANDS).length); set('s-mcount',Object.keys(MODELS).length);
renderBar('brandsChart',BRANDS,C);
renderBar('modelsChart',MODELS_CHART,['#10b981','#34d399','#6ee7b7','#a7f3d0','#6ee7b7']);
renderTrend(); renderTable();

// Таблица всех моделей
(function(){{
  const rows=sorted(MODELS);
  document.getElementById('models-tbody').innerHTML=rows.map(([full,idx],i)=>{{
    // full = "Cobalt (Chevrolet)"
    const m=full.match(/^(.+)\s\((.+)\)$/);
    const model=m?m[1]:full, brand=m?m[2]:'—';
    const r=i+1,rc=r===1?'r1':r===2?'r2':r===3?'r3':'rn',col='#10b981';
    const url=`https://trends.google.com/trends/explore?cat=47&geo=UZ&q=${{encodeURIComponent(model)}}&date=today%203-m`;
    return `<tr><td><span class="rank-badge ${{rc}}">${{r}}</span></td><td><strong>${{model}}</strong></td><td style="color:#64748b">${{brand}}</td><td><strong>${{idx}}</strong></td><td><div class="bar-bg"><div class="bar-fill" style="width:${{idx}}%;background:${{col}}"></div></div></td><td><a class="glink" href="${{url}}" target="_blank">↗</a></td></tr>`;
  }}).join('');
}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC] Запуск...")
    print("Получаем данные из Google Trends...")
    data = fetch_trends()
    top_brand = max(data["brands"], key=data["brands"].get)
    top_model = max(data["models"], key=data["models"].get)
    print(f"Топ бренд: {top_brand} ({data['brands'][top_brand]})")
    print(f"Топ модель: {top_model} ({data['models'][top_model]})")
    html = build_html(data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html сгенерирован ({len(html)} байт)")
