from flask import Flask, render_template_string, jsonify, request
import requests
import csv
from io import StringIO
from datetime import datetime, timedelta
from collections import defaultdict
import time
import urllib.parse

app = Flask(__name__)

SHEET_ID = "1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY"

# ─────────────────────────────────────────────
#  In-memory cache  (works on local + gunicorn)
#  On Vercel serverless each invocation is fresh
#  so TTL is kept short but still helps warm hits
# ─────────────────────────────────────────────
CACHE = {}
CACHE_TTL = 300  # 5 minutes

def get_sheet_url(sheet_name):
    encoded = urllib.parse.quote(sheet_name)
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded}"

# ─────────────────────────────────────────────
#  PROVIDERS — columns taken DIRECTLY from Apps Script (1-based)
#  Apps Script: dCol, rCol, bCol, wCol
#  GE QC      : dCol=1  rCol=7  bCol=2  wCol=5
#  GE ZONES   : dCol=10 rCol=16 bCol=11 wCol=15
#  ECL QC     : dCol=1  rCol=7  bCol=2  wCol=5
#  ECL ZONES  : dCol=10 rCol=16 bCol=11 wCol=14
#  KERRY      : dCol=1  rCol=6  bCol=2  wCol=5
#  APX        : dCol=1  rCol=7  bCol=2  wCol=5
# ─────────────────────────────────────────────
PROVIDERS = [
    {"name": "GLOBAL EXPRESS (QC)",    "sheet": "GE QC Center & Zone",  "dateCol": 1,  "boxCol": 2,  "weightCol": 5,  "regionCol": 7,  "startRow": 2},
    {"name": "GLOBAL EXPRESS (ZONES)", "sheet": "GE QC Center & Zone",  "dateCol": 10, "boxCol": 11, "weightCol": 15, "regionCol": 16, "startRow": 2},
    {"name": "ECL LOGISTICS (QC)",     "sheet": "ECL QC Center & Zone", "dateCol": 1,  "boxCol": 2,  "weightCol": 5,  "regionCol": 7,  "startRow": 2},
    {"name": "ECL LOGISTICS (ZONES)",  "sheet": "ECL QC Center & Zone", "dateCol": 10, "boxCol": 11, "weightCol": 14, "regionCol": 16, "startRow": 2},
    {"name": "KERRY LOGISTICS",        "sheet": "Kerry",                 "dateCol": 1,  "boxCol": 2,  "weightCol": 5,  "regionCol": 6,  "startRow": 2},
    {"name": "APX EXPRESS",            "sheet": "APX",                   "dateCol": 1,  "boxCol": 2,  "weightCol": 5,  "regionCol": 7,  "startRow": 2},
]

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def fetch_sheet(sheet_name):
    key  = f"sheet_{sheet_name}"
    now  = time.time()
    if key in CACHE:
        ts, rows = CACHE[key]
        if now - ts < CACHE_TTL:
            return rows
    try:
        url  = get_sheet_url(sheet_name)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        rows = list(csv.reader(StringIO(resp.text)))
        CACHE[key] = (now, rows)
        return rows
    except Exception as e:
        print(f"fetch error [{sheet_name}]: {e}")
        if key in CACHE:
            return CACHE[key][1]
        return []

def parse_date(s):
    if not s or str(s).strip() == "":
        return None
    s = str(s).strip()
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y"]:
        try:
            return datetime.strptime(s, fmt)
        except:
            pass
    return None

def safe_float(v):
    try:
        c = str(v).replace(",", "").strip()
        if c in ("", "-", "n/a", "#n/a", "na"):
            return 0
        return float(c)
    except:
        return 0

BAD_REGIONS = {"", "N/A", "#N/A", "COUNTRY", "REGION", "NA", "-",
               "DESTINATION", "ZONE", "ORDER", "ORDER#", "ORDER NO", "COUNTRY/REGION"}

def valid_region(r):
    if not r: return False
    return str(r).strip().upper() not in BAD_REGIONS and len(str(r).strip()) > 1

def rating(boxes):
    if boxes >= 1500: return "★★★★★"
    if boxes >= 500:  return "★★★★☆"
    if boxes >= 100:  return "★★★☆☆"
    return "★★☆☆☆"

def trend(cur, prev):
    return {"text": "🚀 UP", "cls": "up"} if cur >= prev else {"text": "⚠️ DOWN", "cls": "down"}

def get_week_bounds(week_start_str):
    if week_start_str:
        ws = datetime.strptime(week_start_str, "%Y-%m-%d")
    else:
        t  = datetime.now()
        ws = t - timedelta(days=t.weekday())
    ws = ws.replace(hour=0, minute=0, second=0, microsecond=0)
    we = ws + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return ws, we

# ─────────────────────────────────────────────
#  Core aggregation — shared by all 3 API routes
# ─────────────────────────────────────────────
def aggregate(provider, week_start, week_end, want_regions=True):
    rows   = fetch_sheet(provider["sheet"])
    si     = provider.get("startRow", 2) - 1
    dc     = provider["dateCol"]   - 1
    bc     = provider["boxCol"]    - 1
    wc     = provider["weightCol"] - 1
    rc     = provider["regionCol"] - 1
    max_c  = max(dc, bc, wc, rc)

    # Per-region per-day
    reg_days = defaultdict(lambda: [
        {"orders": 0, "boxes": 0.0, "weight": 0.0, "under20": 0, "over20": 0}
        for _ in range(7)
    ])
    # Day totals
    day_tot = [{"orders": 0, "boxes": 0.0, "weight": 0.0, "under20": 0, "over20": 0} for _ in range(7)]
    prev_boxes = 0.0
    prev_start = week_start - timedelta(days=7)
    prev_end   = week_start - timedelta(seconds=1)

    for row in rows[si:]:
        if len(row) <= max_c:
            continue
        dt = parse_date(row[dc])
        if not dt:
            continue
        region = str(row[rc]).strip()
        if not valid_region(region):
            continue
        region = region.upper()
        boxes  = safe_float(row[bc])
        weight = safe_float(row[wc])
        if boxes <= 0 and weight <= 0:
            continue
        u20 = 1 if weight < 20 else 0
        o20 = 1 if weight >= 20 else 0

        if week_start <= dt <= week_end:
            d = (dt - week_start).days
            if 0 <= d < 7:
                day_tot[d]["orders"]  += 1
                day_tot[d]["boxes"]   += boxes
                day_tot[d]["weight"]  += weight
                day_tot[d]["under20"] += u20
                day_tot[d]["over20"]  += o20
                if want_regions:
                    reg_days[region][d]["orders"]  += 1
                    reg_days[region][d]["boxes"]   += boxes
                    reg_days[region][d]["weight"]  += weight
                    reg_days[region][d]["under20"] += u20
                    reg_days[region][d]["over20"]  += o20

        if prev_start <= dt <= prev_end:
            prev_boxes += boxes

    grand = {
        "orders":  sum(d["orders"]  for d in day_tot),
        "boxes":   sum(d["boxes"]   for d in day_tot),
        "weight":  sum(d["weight"]  for d in day_tot),
        "under20": sum(d["under20"] for d in day_tot),
        "over20":  sum(d["over20"]  for d in day_tot),
    }
    return dict(reg_days), day_tot, grand, prev_boxes

# ─────────────────────────────────────────────
#  Routes — pages
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML, page="dashboard")

@app.route("/weekly-summary")
def weekly_summary():
    return render_template_string(HTML, page="weekly")

@app.route("/flight-load")
def flight_load():
    return render_template_string(HTML, page="flight")

@app.route("/api/clear-cache")
def clear_cache():
    global CACHE
    CACHE = {}
    return jsonify({"status": "cleared", "time": datetime.now().isoformat()})

# ─────────────────────────────────────────────
#  API — Dashboard (region-wise)
# ─────────────────────────────────────────────
@app.route("/api/dashboard")
def api_dashboard():
    try:
        ws, we = get_week_bounds(request.args.get("week_start"))
        sheet_cache = {}
        results = []

        for prov in PROVIDERS:
            reg_days, day_tot, grand, prev_boxes = aggregate(prov, ws, we, want_regions=True)
            results.append({
                "name":       prov["name"],
                "regions":    {r: {"days": d} for r, d in sorted(reg_days.items())},
                "day_totals": day_tot,
                "grand_total":grand,
                "rating":     rating(grand["boxes"]),
                "trend":      trend(grand["boxes"], prev_boxes),
            })

        return jsonify({
            "week_start":     ws.strftime("%d-%b-%Y"),
            "week_end":       we.strftime("%d-%b-%Y"),
            "week_start_iso": ws.strftime("%Y-%m-%d"),
            "providers":      results,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

# ─────────────────────────────────────────────
#  API — Weekly summary (no regions)
# ─────────────────────────────────────────────
@app.route("/api/weekly-summary")
def api_weekly_summary():
    try:
        ws, we = get_week_bounds(request.args.get("week_start"))
        results = []

        for prov in PROVIDERS:
            _, day_tot, grand, _ = aggregate(prov, ws, we, want_regions=False)
            results.append({
                "name":  prov["name"],
                "days":  day_tot,
                "total": grand,
            })

        # Mark winner
        max_w = max((p["total"]["weight"] for p in results), default=0)
        for p in results:
            p["is_winner"] = p["total"]["weight"] == max_w and max_w > 0

        return jsonify({
            "week_start":     ws.strftime("%d-%b-%Y"),
            "week_end":       we.strftime("%d-%b-%Y"),
            "week_start_iso": ws.strftime("%Y-%m-%d"),
            "providers":      results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  API — Flight consolidation
# ─────────────────────────────────────────────
@app.route("/api/flight-load")
def api_flight_load():
    try:
        ws, we = get_week_bounds(request.args.get("week_start"))
        results = []

        for prov in PROVIDERS:
            _, day_tot, _, _ = aggregate(prov, ws, we, want_regions=False)

            def merge(a, b):
                return {
                    "orders": day_tot[a]["orders"]  + day_tot[b]["orders"],
                    "boxes":  day_tot[a]["boxes"]   + day_tot[b]["boxes"],
                    "weight": day_tot[a]["weight"]  + day_tot[b]["weight"],
                }

            tue = merge(0, 1)
            thu = merge(2, 3)
            sat = merge(4, 5)
            tot = {
                "orders": tue["orders"] + thu["orders"] + sat["orders"],
                "boxes":  tue["boxes"]  + thu["boxes"]  + sat["boxes"],
                "weight": tue["weight"] + thu["weight"] + sat["weight"],
            }
            results.append({"name": prov["name"], "tue_flight": tue, "thu_flight": thu, "sat_flight": sat, "total": tot})

        return jsonify({
            "week_start":     ws.strftime("%d-%b-%Y"),
            "week_end":       we.strftime("%d-%b-%Y"),
            "week_start_iso": ws.strftime("%Y-%m-%d"),
            "providers":      results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  HTML  (single-file template — no external deps)
# ─────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>3PL Executive Dashboard</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Segoe UI',sans-serif;background:#0B1120;color:#fff;min-height:100vh;display:flex}
  /* sidebar */
  .sb{width:220px;background:#0F172A;border-right:1px solid #1E293B;padding:0;position:fixed;height:100vh;overflow-y:auto;z-index:100}
  .sb-hdr{padding:18px 18px 14px;border-bottom:1px solid #1E293B}
  .sb-hdr h1{color:#FBBF24;font-size:15px;letter-spacing:1px}
  .sb-hdr p{color:#64748B;font-size:10px;margin-top:4px}
  .nav-a{display:flex;align-items:center;padding:11px 18px;color:#94A3B8;text-decoration:none;transition:.2s;border-left:3px solid transparent;font-size:13px}
  .nav-a:hover{background:#1E293B;color:#fff}
  .nav-a.active{background:#1E293B;color:#FBBF24;border-left-color:#FBBF24}
  .nav-a span{margin-left:9px}
  .sb-refresh{margin:16px;padding:9px;background:#1E293B;border:1px solid #334155;border-radius:6px;color:#94A3B8;font-size:11px;cursor:pointer;text-align:center;transition:.2s}
  .sb-refresh:hover{background:#334155;color:#FBBF24}
  /* main */
  .main{margin-left:220px;flex:1;min-height:100vh}
  .hdr{background:linear-gradient(135deg,#0B1120,#1E293B);padding:18px 28px;border-bottom:2px solid #FBBF24}
  .hdr h1{color:#FBBF24;font-size:20px;letter-spacing:2px}
  .hdr p{color:#94A3B8;font-size:11px;margin-top:4px}
  .wsel{background:#1E293B;padding:12px 28px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #334155;flex-wrap:wrap}
  .wsel label{color:#94A3B8;font-size:12px}
  .wsel input{background:#0F172A;border:1px solid #334155;color:#fff;padding:7px 11px;border-radius:5px;cursor:pointer;font-size:13px}
  .wsel input:focus{outline:1px solid #FBBF24}
  .week-info{color:#FBBF24;font-weight:700;font-size:12px;margin-left:auto}
  .ctr{padding:20px 28px}
  /* provider card */
  .card{background:#1E293B;border-radius:10px;margin-bottom:22px;overflow:hidden;border:1px solid #334155}
  .card-hdr{background:#0F172A;padding:13px 18px;border-bottom:2px solid #FBBF24;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
  .p-name{color:#FBBF24;font-weight:700;font-size:13px}
  .p-rating{color:#FBBF24;font-size:11px}
  .p-trend{font-size:11px;padding:2px 8px;border-radius:10px}
  .p-trend.up{background:#065F46;color:#34D399}
  .p-trend.down{background:#7F1D1D;color:#FCA5A5}
  .p-stats{display:flex;gap:6px;flex-wrap:wrap}
  .sbadge{background:#334155;padding:3px 9px;border-radius:11px;font-size:10px;color:#E2E8F0}
  .sbadge.hi{background:#FBBF24;color:#0B1120;font-weight:700}
  /* table */
  .tw{overflow-x:auto}
  .dt{width:100%;border-collapse:collapse;min-width:1100px;font-size:11px}
  .dt th{background:#0F172A;padding:7px 5px;color:#94A3B8;text-transform:uppercase;white-space:nowrap;font-size:9px;border:1px solid #1E293B}
  .dt th.fl{background:#1E293B;color:#FBBF24}
  .dt th.rh{text-align:left;padding-left:14px;min-width:120px}
  .dt td{padding:6px 5px;text-align:center;border-bottom:1px solid #1E293B;color:#CBD5E1}
  .dt td.rh{text-align:left;padding-left:14px;font-weight:500;color:#E2E8F0}
  .dt td.fl{background:rgba(251,191,36,.07)}
  .dt tr:hover td{background:rgba(255,255,255,.03)}
  .dt .tr-tot td{background:#0F172A;color:#FBBF24;font-weight:700;border-top:2px solid #FBBF24}
  /* summary / flight tables */
  .s-hdr{background:#0B1120;padding:13px 18px;border:2px solid #FBBF24;border-bottom:none;border-radius:10px 10px 0 0}
  .s-hdr h2{color:#FBBF24;font-size:13px}
  .st{width:100%;border-collapse:collapse;background:#1E293B;border:2px solid #FBBF24;border-top:none;border-radius:0 0 10px 10px;overflow:hidden;font-size:11px}
  .st th{background:#0F172A;padding:9px 7px;color:#94A3B8;font-size:9px;text-transform:uppercase;border:1px solid #1E293B}
  .st th.fl{background:#1E293B;color:#FBBF24}
  .st td{padding:9px 7px;text-align:center;border-bottom:1px solid #334155}
  .st .winner{background:rgba(251,191,36,.12)}
  .st .winner td:first-child{color:#FBBF24;font-weight:700}
  .st .gt{background:#0F172A!important;color:#FBBF24!important;font-weight:700!important}
  /* loading / error */
  .loader{text-align:center;padding:60px;color:#94A3B8}
  .spin{width:38px;height:38px;border:3px solid #334155;border-top:3px solid #FBBF24;border-radius:50%;animation:sp 1s linear infinite;margin:0 auto 14px}
  @keyframes sp{to{transform:rotate(360deg)}}
  .err{background:#7F1D1D;color:#FCA5A5;padding:18px;border-radius:8px;margin:18px;text-align:center}
  /* responsive */
  @media(max-width:800px){.sb{width:55px}.sb-hdr h1,.sb-hdr p,.nav-a span,.sb-refresh{display:none}.main{margin-left:55px}}
</style>
</head>
<body>
<nav class="sb">
  <div class="sb-hdr"><h1>✦ G-OPS 3PL</h1><p>Executive Portal</p></div>
  <a href="/" class="nav-a {{ 'active' if page=='dashboard' else '' }}">🏠<span>Dashboard</span></a>
  <a href="/weekly-summary" class="nav-a {{ 'active' if page=='weekly' else '' }}">📊<span>Weekly Summary</span></a>
  <a href="/flight-load" class="nav-a {{ 'active' if page=='flight' else '' }}">✈️<span>Flight Load</span></a>
  <div class="sb-refresh" onclick="clearCache()">🔄 Refresh Data</div>
</nav>

<div class="main">
  {% if page=='dashboard' %}
  <div class="hdr"><h1>✦ GLOBAL LOGISTICS EXECUTIVE PORTAL ✦</h1><p>3PL Weekly Performance — Region Wise Breakdown</p></div>
  {% elif page=='weekly' %}
  <div class="hdr"><h1>📊 WEEKLY PERFORMANCE SUMMARY</h1><p>🏆 Highest Weight Winner</p></div>
  {% elif page=='flight' %}
  <div class="hdr"><h1>✈️ CONSOLIDATED FLIGHT LOAD</h1><p>Pre-Flight + Flight Day Summary</p></div>
  {% endif %}

  <div class="wsel">
    <label>📅 SELECT WEEK START (MONDAY):</label>
    <input type="date" id="ws" onchange="onWeekChange()">
    <div class="week-info" id="wi">—</div>
  </div>
  <div class="ctr" id="ctr"><div class="loader"><div class="spin"></div><p>Loading data…</p></div></div>
</div>

<script>
const PAGE = "{{ page }}";
const DAYS = ["MON","TUE ✈️","WED","THU ✈️","FRI","SAT ✈️","SUN"];
const FD   = [1,3,5];
let debounce_timer = null;

// Set default Monday
(function(){
  const t = new Date(); const d = t.getDay();
  const diff = d === 0 ? -6 : 1 - d;
  t.setDate(t.getDate() + diff);
  document.getElementById("ws").value = t.toISOString().split("T")[0];
})();

function onWeekChange(){
  clearTimeout(debounce_timer);
  debounce_timer = setTimeout(load, 400);
}

function fmt(v, dec=0){
  if(!v || v===0) return "-";
  return dec>0 ? Number(v).toFixed(dec) : Number(v).toFixed(0);
}

async function load(){
  const ws = document.getElementById("ws").value;
  const ctr = document.getElementById("ctr");
  ctr.innerHTML = '<div class="loader"><div class="spin"></div><p>Loading data…</p></div>';
  try {
    let ep = "/api/dashboard";
    if(PAGE==="weekly") ep="/api/weekly-summary";
    if(PAGE==="flight") ep="/api/flight-load";
    const r = await fetch(ep + (ws ? "?week_start="+ws : ""));
    const d = await r.json();
    if(d.error) throw new Error(d.error);
    document.getElementById("wi").textContent = d.week_start + " → " + d.week_end;
    if(PAGE==="dashboard") renderDash(d);
    else if(PAGE==="weekly") renderWeekly(d);
    else renderFlight(d);
  } catch(e){
    ctr.innerHTML = '<div class="err"><b>⚠️ Error</b><br>'+e.message+'</div>';
  }
}

function renderDash(data){
  let h="";
  data.providers.forEach(p=>{
    const regs = Object.keys(p.regions).sort();
    h+=`<div class="card">
      <div class="card-hdr">
        <div style="display:flex;align-items:center;gap:12px">
          <span class="p-name">✦ ${p.name}</span>
          <span class="p-rating">${p.rating}</span>
          <span class="p-trend ${p.trend.cls}">${p.trend.text}</span>
        </div>
        <div class="p-stats">
          <span class="sbadge">Orders: ${p.grand_total.orders}</span>
          <span class="sbadge">Boxes: ${fmt(p.grand_total.boxes)}</span>
          <span class="sbadge hi">Weight: ${fmt(p.grand_total.weight,1)} kg</span>
        </div>
      </div>
      <div class="tw"><table class="dt"><thead>
        <tr><th class="rh" rowspan="2">ACTIVE REGIONS</th>`;
    DAYS.forEach((d,i)=>{ h+=`<th colspan="5" ${FD.includes(i)?'class="fl"':''}>${d}</th>`; });
    h+=`</tr><tr>`;
    DAYS.forEach((d,i)=>{
      ["O","B","W","<20","20+"].forEach(c=>{ h+=`<th ${FD.includes(i)?'class="fl"':''}>${c}</th>`; });
    });
    h+=`</tr></thead><tbody>`;
    regs.forEach(reg=>{
      const rd = p.regions[reg].days;
      h+=`<tr><td class="rh">${reg}</td>`;
      rd.forEach((d,i)=>{
        const fc = FD.includes(i)?'class="fl"':'';
        h+=`<td ${fc}>${fmt(d.orders)}</td><td ${fc}>${fmt(d.boxes)}</td><td ${fc}>${fmt(d.weight,1)}</td><td ${fc}>${fmt(d.under20)}</td><td ${fc}>${fmt(d.over20)}</td>`;
      });
      h+=`</tr>`;
    });
    h+=`<tr class="tr-tot"><td class="rh">▣ TOTAL SUMMARY</td>`;
    p.day_totals.forEach((d,i)=>{
      const fc = FD.includes(i)?'class="fl"':'';
      h+=`<td ${fc}>${fmt(d.orders)}</td><td ${fc}>${fmt(d.boxes)}</td><td ${fc}>${fmt(d.weight,1)}</td><td ${fc}>${fmt(d.under20)}</td><td ${fc}>${fmt(d.over20)}</td>`;
    });
    h+=`</tr></tbody></table></div></div>`;
  });
  document.getElementById("ctr").innerHTML=h;
}

function renderWeekly(data){
  let h=`<div class="s-hdr"><h2>📊 WEEKLY PERFORMANCE SUMMARY (🏆 HIGHEST WEIGHT WINNER)</h2></div>
    <div style="overflow-x:auto"><table class="st"><thead>
    <tr><th>PROVIDER</th>`;
  DAYS.forEach((d,i)=>{ h+=`<th colspan="3" ${FD.includes(i)?'class="fl"':''}>${d}</th>`; });
  h+=`<th colspan="3">GRAND TOTAL</th></tr><tr><th></th>`;
  for(let i=0;i<8;i++) h+=`<th>Ord</th><th>Box</th><th>KG</th>`;
  h+=`</tr></thead><tbody>`;
  data.providers.forEach(p=>{
    h+=`<tr ${p.is_winner?'class="winner"':''}>`;
    h+=`<td>${p.is_winner?"🏆 ":""}${p.name}</td>`;
    p.days.forEach(d=>{ h+=`<td>${fmt(d.orders)}</td><td>${fmt(d.boxes)}</td><td>${fmt(d.weight,1)}</td>`; });
    h+=`<td class="gt">${fmt(p.total.orders)}</td><td class="gt">${fmt(p.total.boxes)}</td><td class="gt">${fmt(p.total.weight,1)}</td>`;
    h+=`</tr>`;
  });
  h+=`</tbody></table></div>`;
  document.getElementById("ctr").innerHTML=h;
}

function renderFlight(data){
  let h=`<div class="s-hdr"><h2>✈️ CONSOLIDATED FLIGHT LOAD (PRE-FLIGHT + FLIGHT DAY)</h2></div>
    <div style="overflow-x:auto"><table class="st"><thead>
    <tr><th>PROVIDER</th>
    <th colspan="3" class="fl">✈️ TUE FLIGHT (Mon+Tue)</th>
    <th colspan="3" class="fl">✈️ THU FLIGHT (Wed+Thu)</th>
    <th colspan="3" class="fl">✈️ SAT FLIGHT (Fri+Sat)</th>
    <th colspan="3">TOTAL FLIGHT LOAD</th></tr>
    <tr><th></th>`;
  for(let i=0;i<4;i++) h+=`<th>Ord</th><th>Box</th><th>KG</th>`;
  h+=`</tr></thead><tbody>`;
  data.providers.forEach(p=>{
    const slots=[p.tue_flight,p.thu_flight,p.sat_flight,p.total];
    h+=`<tr><td>${p.name}</td>`;
    slots.forEach((s,i)=>{
      const gc = i===3?'class="gt"':'';
      h+=`<td ${gc}>${fmt(s.orders)}</td><td ${gc}>${fmt(s.boxes)}</td><td ${gc}>${fmt(s.weight,1)}</td>`;
    });
    h+=`</tr>`;
  });
  h+=`</tbody></table></div>`;
  document.getElementById("ctr").innerHTML=h;
}

async function clearCache(){
  try{
    await fetch("/api/clear-cache");
    load();
  }catch(e){}
}

load();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5000)
