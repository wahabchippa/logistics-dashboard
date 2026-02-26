from flask import Flask, render_template_string, jsonify, request
import requests
import csv
from io import StringIO
from datetime import datetime, timedelta
from collections import defaultdict
import time

app = Flask(__name__)

SHEET_ID = "1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY"

CACHE = {}
CACHE_DURATION = 300

def get_sheet_url(sheet_name):
    encoded_name = sheet_name.replace(" ", "%20").replace("&", "%26")
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  🔒 LOCKED COLUMNS - VERIFIED FROM ACTUAL SCREENSHOTS 27-FEB-2025        ║
# ║  DO NOT CHANGE! Python 0-based: A=0, B=1, C=2, ... J=9, K=10, etc.       ║
# ╠═══════════════════════════════════════════════════════════════════════════╣
# ║  GE QC:    B(1)=Date, C(2)=Cartons, F(5)=CW, H(7)=Region    | startRow=2 ║
# ║  GE Zone:  K(10)=Date, L(11)=Cartons, P(15)=CW, Q(16)=Region| startRow=2 ║
# ║  ECL QC:   B(1)=Date, C(2)=Cartons, F(5)=CW, H(7)=Region    | startRow=3 ║
# ║  ECL Zone: K(10)=Date, L(11)=Cartons, P(15)=CW, Q(16)=Region| startRow=3 ║
# ║  Kerry:    B(1)=Date, C(2)=Cartons, F(5)=CW, H(7)=Region    | startRow=2 ║
# ║  APX:      B(1)=Date, C(2)=Cartons, F(5)=CW, H(7)=Region    | startRow=2 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

PROVIDERS = [
    {
        "name": "GLOBAL EXPRESS (QC)", 
        "sheet": "GE QC Center & Zone", 
        "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, 
        "startRow": 2
    },
    {
        "name": "GLOBAL EXPRESS (ZONES)", 
        "sheet": "GE QC Center & Zone", 
        "dateCol": 10, "boxCol": 11, "weightCol": 15, "regionCol": 16,  # P=CW, Q=Region
        "startRow": 2
    },
    {
        "name": "ECL LOGISTICS (QC)", 
        "sheet": "ECL QC Center & Zone", 
        "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, 
        "startRow": 3
    },
    {
        "name": "ECL LOGISTICS (ZONES)", 
        "sheet": "ECL QC Center & Zone", 
        "dateCol": 10, "boxCol": 11, "weightCol": 15, "regionCol": 16,  # P=CW, Q=Region
        "startRow": 3
    },
    {
        "name": "KERRY LOGISTICS", 
        "sheet": "Kerry", 
        "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, 
        "startRow": 2
    },
    {
        "name": "APX EXPRESS", 
        "sheet": "APX", 
        "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, 
        "startRow": 2
    },
]

def fetch_sheet_data(sheet_name):
    global CACHE
    cache_key = f"sheet_{sheet_name}"
    now = time.time()
    
    if cache_key in CACHE:
        cached_time, cached_data = CACHE[cache_key]
        if now - cached_time < CACHE_DURATION:
            return cached_data
    
    try:
        url = get_sheet_url(sheet_name)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        reader = csv.reader(StringIO(response.text))
        data = list(reader)
        CACHE[cache_key] = (now, data)
        return data
    except Exception as e:
        print(f"Error fetching {sheet_name}: {e}")
        if cache_key in CACHE:
            return CACHE[cache_key][1]
        return []

def parse_date(date_str):
    if not date_str or str(date_str).strip() == "":
        return None
    date_str = str(date_str).strip()
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

def safe_float(val):
    try:
        clean = str(val).replace(',', '').replace(' ', '').strip()
        if clean == "" or clean == "-" or clean.upper() in ["N/A", "#N/A", "NA"]:
            return 0
        return float(clean)
    except:
        return 0

def is_valid_region(region):
    if not region:
        return False
    region = str(region).strip().upper()
    invalid = ["", "N/A", "#N/A", "COUNTRY", "REGION", "NA", "-", "DESTINATION", "ZONE", "ORDER", "NOT APPLICABLE"]
    return region not in invalid and len(region) > 1

def get_rating(total_boxes):
    if total_boxes >= 1500:
        return "★★★★★"
    elif total_boxes >= 500:
        return "★★★★☆"
    elif total_boxes >= 100:
        return "★★★☆☆"
    else:
        return "★★☆☆☆"

def get_trend(current, previous):
    if current >= previous:
        return {"text": "🚀 UP", "class": "up"}
    else:
        return {"text": "⚠️ DOWN", "class": "down"}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, page="dashboard")

@app.route('/weekly-summary')
def weekly_summary():
    return render_template_string(HTML_TEMPLATE, page="weekly")

@app.route('/flight-load')
def flight_load():
    return render_template_string(HTML_TEMPLATE, page="flight")

@app.route('/api/clear-cache')
def clear_cache():
    global CACHE
    CACHE = {}
    return jsonify({"status": "Cache cleared", "time": datetime.now().isoformat()})

@app.route('/api/dashboard')
def api_dashboard():
    try:
        week_start_str = request.args.get('week_start')
        if week_start_str:
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d")
        else:
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
        
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(seconds=1)
        
        sheet_cache = {}
        results = []
        
        for provider in PROVIDERS:
            sheet_name = provider["sheet"]
            
            if sheet_name not in sheet_cache:
                sheet_cache[sheet_name] = fetch_sheet_data(sheet_name)
            
            data = sheet_cache[sheet_name]
            
            if not data:
                continue
            
            regions_data = defaultdict(lambda: {
                "days": [{"orders": 0, "boxes": 0, "weight": 0, "under20": 0, "over20": 0} for _ in range(7)],
                "total": {"orders": 0, "boxes": 0, "weight": 0, "under20": 0, "over20": 0}
            })
            
            current_total = {"orders": 0, "boxes": 0, "weight": 0}
            prev_total = {"boxes": 0}
            
            start_idx = provider.get("startRow", 2) - 1
            date_idx = provider["dateCol"]
            box_idx = provider["boxCol"]
            weight_idx = provider["weightCol"]
            region_idx = provider["regionCol"]
            
            for row in data[start_idx:]:
                try:
                    max_idx = max(date_idx, box_idx, weight_idx, region_idx)
                    if len(row) <= max_idx:
                        continue
                    
                    date_val = row[date_idx] if date_idx < len(row) else ""
                    row_date = parse_date(date_val)
                    
                    if not row_date:
                        continue
                    
                    region = str(row[region_idx]).strip() if region_idx < len(row) else ""
                    
                    if not is_valid_region(region):
                        continue
                    
                    region = region.upper()
                    
                    boxes = safe_float(row[box_idx]) if box_idx < len(row) else 0
                    weight = safe_float(row[weight_idx]) if weight_idx < len(row) else 0
                    
                    if boxes <= 0 and weight <= 0:
                        continue
                    
                    under20 = 1 if weight < 20 else 0
                    over20 = 1 if weight >= 20 else 0
                    
                    if week_start <= row_date <= week_end:
                        day_diff = (row_date - week_start).days
                        if 0 <= day_diff < 7:
                            regions_data[region]["days"][day_diff]["orders"] += 1
                            regions_data[region]["days"][day_diff]["boxes"] += boxes
                            regions_data[region]["days"][day_diff]["weight"] += weight
                            regions_data[region]["days"][day_diff]["under20"] += under20
                            regions_data[region]["days"][day_diff]["over20"] += over20
                            
                            regions_data[region]["total"]["orders"] += 1
                            regions_data[region]["total"]["boxes"] += boxes
                            regions_data[region]["total"]["weight"] += weight
                            
                            current_total["orders"] += 1
                            current_total["boxes"] += boxes
                            current_total["weight"] += weight
                    
                    if prev_week_start <= row_date <= prev_week_end:
                        prev_total["boxes"] += boxes
                        
                except:
                    continue
            
            day_totals = [{"orders": 0, "boxes": 0, "weight": 0, "under20": 0, "over20": 0} for _ in range(7)]
            for region, rdata in regions_data.items():
                for d in range(7):
                    day_totals[d]["orders"] += rdata["days"][d]["orders"]
                    day_totals[d]["boxes"] += rdata["days"][d]["boxes"]
                    day_totals[d]["weight"] += rdata["days"][d]["weight"]
                    day_totals[d]["under20"] += rdata["days"][d]["under20"]
                    day_totals[d]["over20"] += rdata["days"][d]["over20"]
            
            grand_total = {
                "orders": sum(d["orders"] for d in day_totals),
                "boxes": sum(d["boxes"] for d in day_totals),
                "weight": sum(d["weight"] for d in day_totals),
                "under20": sum(d["under20"] for d in day_totals),
                "over20": sum(d["over20"] for d in day_totals)
            }
            
            results.append({
                "name": provider["name"],
                "regions": dict(regions_data),
                "day_totals": day_totals,
                "grand_total": grand_total,
                "rating": get_rating(grand_total["boxes"]),
                "trend": get_trend(current_total["boxes"], prev_total["boxes"])
            })
        
        return jsonify({
            "week_start": week_start.strftime("%d-%b-%Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d-%b-%Y"),
            "week_start_iso": week_start.strftime("%Y-%m-%d"),
            "providers": results
        })
    
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/weekly-summary')
def api_weekly_summary():
    try:
        week_start_str = request.args.get('week_start')
        if week_start_str:
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d")
        else:
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
        
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        sheet_cache = {}
        results = []
        
        for provider in PROVIDERS:
            sheet_name = provider["sheet"]
            
            if sheet_name not in sheet_cache:
                sheet_cache[sheet_name] = fetch_sheet_data(sheet_name)
            
            data = sheet_cache[sheet_name]
            
            if not data:
                continue
            
            days_data = [{"orders": 0, "boxes": 0, "weight": 0} for _ in range(7)]
            
            start_idx = provider.get("startRow", 2) - 1
            date_idx = provider["dateCol"]
            box_idx = provider["boxCol"]
            weight_idx = provider["weightCol"]
            region_idx = provider["regionCol"]
            
            for row in data[start_idx:]:
                try:
                    max_idx = max(date_idx, box_idx, weight_idx, region_idx)
                    if len(row) <= max_idx:
                        continue
                    
                    date_val = row[date_idx] if date_idx < len(row) else ""
                    row_date = parse_date(date_val)
                    
                    if not row_date:
                        continue
                    
                    region = str(row[region_idx]).strip() if region_idx < len(row) else ""
                    
                    if not is_valid_region(region):
                        continue
                    
                    if week_start <= row_date <= week_end:
                        day_diff = (row_date - week_start).days
                        
                        if 0 <= day_diff < 7:
                            boxes = safe_float(row[box_idx]) if box_idx < len(row) else 0
                            weight = safe_float(row[weight_idx]) if weight_idx < len(row) else 0
                            
                            days_data[day_diff]["orders"] += 1
                            days_data[day_diff]["boxes"] += boxes
                            days_data[day_diff]["weight"] += weight
                except:
                    continue
            
            total = {
                "orders": sum(d["orders"] for d in days_data),
                "boxes": sum(d["boxes"] for d in days_data),
                "weight": sum(d["weight"] for d in days_data)
            }
            
            results.append({
                "name": provider["name"],
                "days": days_data,
                "total": total
            })
        
        max_weight = max(p["total"]["weight"] for p in results) if results else 0
        for p in results:
            p["is_winner"] = p["total"]["weight"] == max_weight and max_weight > 0
        
        return jsonify({
            "week_start": week_start.strftime("%d-%b-%Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d-%b-%Y"),
            "week_start_iso": week_start.strftime("%Y-%m-%d"),
            "providers": results
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/flight-load')
def api_flight_load():
    try:
        week_start_str = request.args.get('week_start')
        if week_start_str:
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d")
        else:
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
        
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        sheet_cache = {}
        results = []
        
        for provider in PROVIDERS:
            sheet_name = provider["sheet"]
            
            if sheet_name not in sheet_cache:
                sheet_cache[sheet_name] = fetch_sheet_data(sheet_name)
            
            data = sheet_cache[sheet_name]
            
            if not data:
                continue
            
            days_data = [{"orders": 0, "boxes": 0, "weight": 0} for _ in range(7)]
            
            start_idx = provider.get("startRow", 2) - 1
            date_idx = provider["dateCol"]
            box_idx = provider["boxCol"]
            weight_idx = provider["weightCol"]
            region_idx = provider["regionCol"]
            
            for row in data[start_idx:]:
                try:
                    max_idx = max(date_idx, box_idx, weight_idx, region_idx)
                    if len(row) <= max_idx:
                        continue
                    
                    date_val = row[date_idx] if date_idx < len(row) else ""
                    row_date = parse_date(date_val)
                    
                    if not row_date:
                        continue
                    
                    region = str(row[region_idx]).strip() if region_idx < len(row) else ""
                    
                    if not is_valid_region(region):
                        continue
                    
                    if week_start <= row_date <= week_end:
                        day_diff = (row_date - week_start).days
                        
                        if 0 <= day_diff < 7:
                            boxes = safe_float(row[box_idx]) if box_idx < len(row) else 0
                            weight = safe_float(row[weight_idx]) if weight_idx < len(row) else 0
                            
                            days_data[day_diff]["orders"] += 1
                            days_data[day_diff]["boxes"] += boxes
                            days_data[day_diff]["weight"] += weight
                except:
                    continue
            
            tue_flight = {
                "orders": days_data[0]["orders"] + days_data[1]["orders"],
                "boxes": days_data[0]["boxes"] + days_data[1]["boxes"],
                "weight": days_data[0]["weight"] + days_data[1]["weight"]
            }
            thu_flight = {
                "orders": days_data[2]["orders"] + days_data[3]["orders"],
                "boxes": days_data[2]["boxes"] + days_data[3]["boxes"],
                "weight": days_data[2]["weight"] + days_data[3]["weight"]
            }
            sat_flight = {
                "orders": days_data[4]["orders"] + days_data[5]["orders"],
                "boxes": days_data[4]["boxes"] + days_data[5]["boxes"],
                "weight": days_data[4]["weight"] + days_data[5]["weight"]
            }
            total_flight = {
                "orders": tue_flight["orders"] + thu_flight["orders"] + sat_flight["orders"],
                "boxes": tue_flight["boxes"] + thu_flight["boxes"] + sat_flight["boxes"],
                "weight": tue_flight["weight"] + thu_flight["weight"] + sat_flight["weight"]
            }
            
            results.append({
                "name": provider["name"],
                "tue_flight": tue_flight,
                "thu_flight": thu_flight,
                "sat_flight": sat_flight,
                "total": total_flight
            })
        
        return jsonify({
            "week_start": week_start.strftime("%d-%b-%Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d-%b-%Y"),
            "week_start_iso": week_start.strftime("%Y-%m-%d"),
            "providers": results
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3PL Executive Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0B1120; color: #fff; min-height: 100vh; display: flex; }
        .sidebar { width: 250px; background: #0F172A; border-right: 1px solid #1E293B; padding: 20px 0; position: fixed; height: 100vh; }
        .sidebar-header { padding: 0 20px 20px; border-bottom: 1px solid #1E293B; margin-bottom: 20px; }
        .sidebar-header h1 { color: #FBBF24; font-size: 16px; }
        .sidebar-header p { color: #64748B; font-size: 11px; margin-top: 5px; }
        .nav-item { display: flex; align-items: center; padding: 12px 20px; color: #94A3B8; text-decoration: none; border-left: 3px solid transparent; }
        .nav-item:hover { background: #1E293B; color: #fff; }
        .nav-item.active { background: #1E293B; color: #FBBF24; border-left-color: #FBBF24; }
        .nav-item span { margin-left: 10px; }
        .main-content { margin-left: 250px; flex: 1; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #0B1120, #1E293B); padding: 20px 30px; border-bottom: 2px solid #FBBF24; }
        .header h1 { color: #FBBF24; font-size: 22px; }
        .header p { color: #94A3B8; font-size: 12px; margin-top: 5px; }
        .week-selector { background: #1E293B; padding: 15px 30px; display: flex; align-items: center; gap: 15px; border-bottom: 1px solid #334155; }
        .week-selector label { color: #94A3B8; font-size: 13px; }
        .week-selector input { background: #0F172A; border: 1px solid #334155; color: #fff; padding: 8px 12px; border-radius: 5px; }
        .week-info { color: #FBBF24; font-weight: bold; margin-left: auto; }
        .container { padding: 20px 30px; }
        .provider-card { background: #1E293B; border-radius: 10px; margin-bottom: 25px; overflow: hidden; border: 1px solid #334155; }
        .provider-header { background: #0F172A; padding: 15px 20px; border-bottom: 2px solid #FBBF24; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .provider-title { display: flex; align-items: center; gap: 15px; }
        .provider-name { color: #FBBF24; font-weight: 700; font-size: 14px; }
        .rating { color: #FBBF24; font-size: 12px; }
        .trend { font-size: 12px; padding: 3px 8px; border-radius: 10px; }
        .trend.up { background: #065F46; color: #34D399; }
        .trend.down { background: #7F1D1D; color: #FCA5A5; }
        .provider-stats { display: flex; gap: 8px; flex-wrap: wrap; }
        .stat-badge { background: #334155; padding: 4px 10px; border-radius: 12px; font-size: 11px; }
        .stat-badge.highlight { background: #FBBF24; color: #0B1120; font-weight: 700; }
        .table-wrapper { overflow-x: auto; }
        .data-table { width: 100%; border-collapse: collapse; min-width: 1200px; }
        .data-table th { background: #0F172A; padding: 8px 6px; font-size: 9px; color: #94A3B8; text-transform: uppercase; }
        .data-table th.flight { background: #1E293B; color: #FBBF24; }
        .data-table th.region-col { text-align: left; padding-left: 15px; min-width: 120px; }
        .data-table td { padding: 6px; text-align: center; font-size: 11px; border-bottom: 1px solid #334155; }
        .data-table td.region-col { text-align: left; padding-left: 15px; font-weight: 500; color: #E2E8F0; }
        .data-table td.flight { background: rgba(251, 191, 36, 0.08); }
        .data-table tr:hover { background: rgba(255,255,255,0.03); }
        .data-table .total-row { background: #0F172A; }
        .data-table .total-row td { color: #FBBF24; font-weight: 700; border-top: 2px solid #FBBF24; }
        .summary-section { margin-top: 20px; }
        .summary-header { background: #0B1120; padding: 15px 20px; border: 2px solid #FBBF24; border-bottom: none; border-radius: 10px 10px 0 0; }
        .summary-header h2 { color: #FBBF24; font-size: 14px; }
        .summary-table { width: 100%; border-collapse: collapse; background: #1E293B; border: 2px solid #FBBF24; border-top: none; }
        .summary-table th { background: #0F172A; padding: 10px 8px; color: #94A3B8; font-size: 10px; }
        .summary-table th.flight { background: #1E293B; color: #FBBF24; }
        .summary-table td { padding: 10px 8px; text-align: center; font-size: 11px; border-bottom: 1px solid #334155; }
        .summary-table .winner { background: rgba(251, 191, 36, 0.15); }
        .summary-table .winner td:first-child { color: #FBBF24; font-weight: 700; }
        .grand-total { background: #0F172A !important; color: #FBBF24 !important; font-weight: 700 !important; }
        .loading { text-align: center; padding: 60px; color: #94A3B8; }
        .loading-spinner { width: 40px; height: 40px; border: 3px solid #334155; border-top: 3px solid #FBBF24; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .error { background: #7F1D1D; color: #FCA5A5; padding: 20px; border-radius: 8px; text-align: center; margin: 20px; }
        @media (max-width: 900px) { .sidebar { width: 60px; } .sidebar-header h1, .sidebar-header p, .nav-item span { display: none; } .main-content { margin-left: 60px; } }
    </style>
</head>
<body>
    <nav class="sidebar">
        <div class="sidebar-header"><h1>✦ G-OPS 3PL</h1><p>Executive Portal</p></div>
        <a href="/" class="nav-item {{ 'active' if page == 'dashboard' else '' }}">🏠 <span>Dashboard</span></a>
        <a href="/weekly-summary" class="nav-item {{ 'active' if page == 'weekly' else '' }}">📊 <span>Weekly Summary</span></a>
        <a href="/flight-load" class="nav-item {{ 'active' if page == 'flight' else '' }}">✈️ <span>Flight Load</span></a>
    </nav>
    <div class="main-content">
        {% if page == 'dashboard' %}
        <div class="header"><h1>✦ GLOBAL LOGISTICS EXECUTIVE PORTAL ✦</h1><p>3PL Weekly Performance Dashboard</p></div>
        <div class="week-selector"><label>📅 SELECT WEEK:</label><input type="date" id="weekStart" onchange="loadDashboard()"><div class="week-info" id="weekInfo">Loading...</div></div>
        <div class="container" id="mainContent"><div class="loading"><div class="loading-spinner"></div><p>Loading...</p></div></div>
        {% elif page == 'weekly' %}
        <div class="header"><h1>📊 WEEKLY PERFORMANCE SUMMARY</h1><p>🏆 Highest Weight Winner</p></div>
        <div class="week-selector"><label>📅 SELECT WEEK:</label><input type="date" id="weekStart" onchange="loadWeekly()"><div class="week-info" id="weekInfo">Loading...</div></div>
        <div class="container" id="mainContent"><div class="loading"><div class="loading-spinner"></div><p>Loading...</p></div></div>
        {% elif page == 'flight' %}
        <div class="header"><h1>✈️ CONSOLIDATED FLIGHT LOAD</h1><p>Pre-Flight + Flight Day Summary</p></div>
        <div class="week-selector"><label>📅 SELECT WEEK:</label><input type="date" id="weekStart" onchange="loadFlight()"><div class="week-info" id="weekInfo">Loading...</div></div>
        <div class="container" id="mainContent"><div class="loading"><div class="loading-spinner"></div><p>Loading...</p></div></div>
        {% endif %}
    </div>
    <script>
        const DAYS = ['MON', 'TUE ✈️', 'WED', 'THU ✈️', 'FRI', 'SAT ✈️', 'SUN'];
        const FLIGHT_DAYS = [1, 3, 5];
        const COLS = ['O', 'B', 'W', '<20', '20+'];
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + 1);
        if(document.getElementById('weekStart')) document.getElementById('weekStart').value = monday.toISOString().split('T')[0];
        
        async function loadDashboard() {
            const weekStart = document.getElementById('weekStart').value;
            const container = document.getElementById('mainContent');
            container.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>Loading...</p></div>';
            try {
                const response = await fetch('/api/dashboard?week_start=' + weekStart);
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                document.getElementById('weekInfo').textContent = data.week_start + ' → ' + data.week_end;
                renderDashboard(data);
            } catch (error) {
                container.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + error.message + '</p></div>';
            }
        }
        
        function renderDashboard(data) {
            let html = '';
            data.providers.forEach(provider => {
                const regions = Object.keys(provider.regions).sort();
                html += '<div class="provider-card"><div class="provider-header"><div class="provider-title">';
                html += '<span class="provider-name">✦ ' + provider.name + '</span>';
                html += '<span class="rating">RATING: ' + provider.rating + '</span>';
                html += '<span class="trend ' + provider.trend.class + '">' + provider.trend.text + '</span></div>';
                html += '<div class="provider-stats"><span class="stat-badge">Orders: ' + provider.grand_total.orders + '</span>';
                html += '<span class="stat-badge">Boxes: ' + provider.grand_total.boxes.toFixed(0) + '</span>';
                html += '<span class="stat-badge highlight">Weight: ' + provider.grand_total.weight.toFixed(1) + ' kg</span></div></div>';
                html += '<div class="table-wrapper"><table class="data-table"><thead><tr><th class="region-col" rowspan="2">REGIONS</th>';
                DAYS.forEach((day, i) => { html += '<th colspan="5" class="' + (FLIGHT_DAYS.includes(i) ? 'flight' : '') + '">' + day + '</th>'; });
                html += '</tr><tr>';
                DAYS.forEach((day, i) => { COLS.forEach(col => { html += '<th class="' + (FLIGHT_DAYS.includes(i) ? 'flight' : '') + '">' + col + '</th>'; }); });
                html += '</tr></thead><tbody>';
                regions.forEach(region => {
                    const rdata = provider.regions[region];
                    html += '<tr><td class="region-col">' + region + '</td>';
                    rdata.days.forEach((d, i) => {
                        const cls = FLIGHT_DAYS.includes(i) ? 'flight' : '';
                        html += '<td class="' + cls + '">' + (d.orders || '-') + '</td>';
                        html += '<td class="' + cls + '">' + (d.boxes ? d.boxes.toFixed(0) : '-') + '</td>';
                        html += '<td class="' + cls + '">' + (d.weight ? d.weight.toFixed(1) : '-') + '</td>';
                        html += '<td class="' + cls + '">' + (d.under20 || '-') + '</td>';
                        html += '<td class="' + cls + '">' + (d.over20 || '-') + '</td>';
                    });
                    html += '</tr>';
                });
                html += '<tr class="total-row"><td class="region-col">▣ TOTAL</td>';
                provider.day_totals.forEach((d, i) => {
                    const cls = FLIGHT_DAYS.includes(i) ? 'flight' : '';
                    html += '<td class="' + cls + '">' + d.orders + '</td><td class="' + cls + '">' + d.boxes.toFixed(0) + '</td><td class="' + cls + '">' + d.weight.toFixed(1) + '</td><td class="' + cls + '">' + d.under20 + '</td><td class="' + cls + '">' + d.over20 + '</td>';
                });
                html += '</tr></tbody></table></div></div>';
            });
            document.getElementById('mainContent').innerHTML = html;
        }
        
        async function loadWeekly() {
            const weekStart = document.getElementById('weekStart').value;
            const container = document.getElementById('mainContent');
            container.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>Loading...</p></div>';
            try {
                const response = await fetch('/api/weekly-summary?week_start=' + weekStart);
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                document.getElementById('weekInfo').textContent = data.week_start + ' → ' + data.week_end;
                let html = '<div class="summary-section"><div class="summary-header"><h2>📊 WEEKLY SUMMARY (🏆 HIGHEST WEIGHT)</h2></div>';
                html += '<div class="table-wrapper"><table class="summary-table"><thead><tr><th>PROVIDER</th>';
                DAYS.forEach((day, i) => { html += '<th colspan="3" class="' + (FLIGHT_DAYS.includes(i) ? 'flight' : '') + '">' + day + '</th>'; });
                html += '<th colspan="3">TOTAL</th></tr><tr><th></th>';
                for (let i = 0; i < 8; i++) html += '<th>Ord</th><th>Box</th><th>KG</th>';
                html += '</tr></thead><tbody>';
                data.providers.forEach(p => {
                    html += '<tr class="' + (p.is_winner ? 'winner' : '') + '"><td>' + (p.is_winner ? '🏆 ' : '') + p.name + '</td>';
                    p.days.forEach(d => { html += '<td>' + (d.orders || '-') + '</td><td>' + (d.boxes ? d.boxes.toFixed(0) : '-') + '</td><td>' + (d.weight ? d.weight.toFixed(1) : '-') + '</td>'; });
                    html += '<td class="grand-total">' + p.total.orders + '</td><td class="grand-total">' + p.total.boxes.toFixed(0) + '</td><td class="grand-total">' + p.total.weight.toFixed(1) + '</td></tr>';
                });
                html += '</tbody></table></div></div>';
                document.getElementById('mainContent').innerHTML = html;
            } catch (error) {
                container.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + error.message + '</p></div>';
            }
        }
        
        async function loadFlight() {
            const weekStart = document.getElementById('weekStart').value;
            const container = document.getElementById('mainContent');
            container.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>Loading...</p></div>';
            try {
                const response = await fetch('/api/flight-load?week_start=' + weekStart);
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                document.getElementById('weekInfo').textContent = data.week_start + ' → ' + data.week_end;
                let html = '<div class="summary-section"><div class="summary-header"><h2>✈️ FLIGHT LOAD</h2></div>';
                html += '<div class="table-wrapper"><table class="summary-table"><thead><tr><th>PROVIDER</th>';
                html += '<th colspan="3" class="flight">✈️ TUE (Mon+Tue)</th><th colspan="3" class="flight">✈️ THU (Wed+Thu)</th><th colspan="3" class="flight">✈️ SAT (Fri+Sat)</th><th colspan="3">TOTAL</th></tr>';
                html += '<tr><th></th>'; for (let i = 0; i < 4; i++) html += '<th>Ord</th><th>Box</th><th>KG</th>'; html += '</tr></thead><tbody>';
                data.providers.forEach(p => {
                    html += '<tr><td>' + p.name + '</td>';
                    html += '<td>' + (p.tue_flight.orders || '-') + '</td><td>' + (p.tue_flight.boxes ? p.tue_flight.boxes.toFixed(0) : '-') + '</td><td>' + (p.tue_flight.weight ? p.tue_flight.weight.toFixed(1) : '-') + '</td>';
                    html += '<td>' + (p.thu_flight.orders || '-') + '</td><td>' + (p.thu_flight.boxes ? p.thu_flight.boxes.toFixed(0) : '-') + '</td><td>' + (p.thu_flight.weight ? p.thu_flight.weight.toFixed(1) : '-') + '</td>';
                    html += '<td>' + (p.sat_flight.orders || '-') + '</td><td>' + (p.sat_flight.boxes ? p.sat_flight.boxes.toFixed(0) : '-') + '</td><td>' + (p.sat_flight.weight ? p.sat_flight.weight.toFixed(1) : '-') + '</td>';
                    html += '<td class="grand-total">' + p.total.orders + '</td><td class="grand-total">' + p.total.boxes.toFixed(0) + '</td><td class="grand-total">' + p.total.weight.toFixed(1) + '</td></tr>';
                });
                html += '</tbody></table></div></div>';
                document.getElementById('mainContent').innerHTML = html;
            } catch (error) {
                container.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + error.message + '</p></div>';
            }
        }
        
        const page = '{{ page }}';
        if (page === 'dashboard') loadDashboard();
        else if (page === 'weekly') loadWeekly();
        else if (page === 'flight') loadFlight();
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True)
