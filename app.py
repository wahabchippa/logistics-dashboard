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

PROVIDERS = [
    {"name": "GLOBAL EXPRESS (QC)", "short": "GE QC", "sheet": "GE QC Center & Zone", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, "startRow": 2, "color": "#3B82F6"},
    {"name": "GLOBAL EXPRESS (ZONE)", "short": "GE ZONE", "sheet": "GE QC Center & Zone", "dateCol": 10, "boxCol": 11, "weightCol": 15, "regionCol": 16, "startRow": 2, "color": "#8B5CF6"},
    {"name": "ECL LOGISTICS (QC)", "short": "ECL QC", "sheet": "ECL QC Center & Zone", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, "startRow": 3, "color": "#10B981"},
    {"name": "ECL LOGISTICS (ZONE)", "short": "ECL ZONE", "sheet": "ECL QC Center & Zone", "dateCol": 10, "boxCol": 11, "weightCol": 15, "regionCol": 16, "startRow": 3, "color": "#F59E0B"},
    {"name": "KERRY LOGISTICS", "short": "KERRY", "sheet": "Kerry", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, "startRow": 2, "color": "#EF4444"},
    {"name": "APX EXPRESS", "short": "APX", "sheet": "APX", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7, "startRow": 2, "color": "#EC4899"},
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
        return 5
    elif total_boxes >= 500:
        return 4
    elif total_boxes >= 100:
        return 3
    else:
        return 2

def get_trend(current, previous):
    if previous == 0 and current == 0:
        return {"text": "NEUTRAL", "class": "neutral", "icon": "●", "percent": 0}
    elif previous == 0:
        return {"text": "UP", "class": "up", "icon": "▲", "percent": 100}
    
    percent = ((current - previous) / previous) * 100
    if current >= previous:
        return {"text": "UP", "class": "up", "icon": "▲", "percent": round(percent, 1)}
    else:
        return {"text": "DOWN", "class": "down", "icon": "▼", "percent": round(abs(percent), 1)}

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
                "short": provider["short"],
                "color": provider["color"],
                "regions": dict(regions_data),
                "day_totals": day_totals,
                "grand_total": grand_total,
                "rating": get_rating(grand_total["boxes"]),
                "trend": get_trend(current_total["boxes"], prev_total["boxes"])
            })
        
        return jsonify({
            "week_start": week_start.strftime("%d %b %Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d %b %Y"),
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
            results.append({"name": provider["name"], "short": provider["short"], "color": provider["color"], "days": days_data, "total": total})
        
        max_weight = max(p["total"]["weight"] for p in results) if results else 0
        for p in results:
            p["is_winner"] = p["total"]["weight"] == max_weight and max_weight > 0
        
        return jsonify({
            "week_start": week_start.strftime("%d %b %Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d %b %Y"),
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
            
            tue_flight = {"orders": days_data[0]["orders"] + days_data[1]["orders"], "boxes": days_data[0]["boxes"] + days_data[1]["boxes"], "weight": days_data[0]["weight"] + days_data[1]["weight"]}
            thu_flight = {"orders": days_data[2]["orders"] + days_data[3]["orders"], "boxes": days_data[2]["boxes"] + days_data[3]["boxes"], "weight": days_data[2]["weight"] + days_data[3]["weight"]}
            sat_flight = {"orders": days_data[4]["orders"] + days_data[5]["orders"], "boxes": days_data[4]["boxes"] + days_data[5]["boxes"], "weight": days_data[4]["weight"] + days_data[5]["weight"]}
            total_flight = {"orders": tue_flight["orders"] + thu_flight["orders"] + sat_flight["orders"], "boxes": tue_flight["boxes"] + thu_flight["boxes"] + sat_flight["boxes"], "weight": tue_flight["weight"] + thu_flight["weight"] + sat_flight["weight"]}
            
            results.append({"name": provider["name"], "short": provider["short"], "color": provider["color"], "tue_flight": tue_flight, "thu_flight": thu_flight, "sat_flight": sat_flight, "total": total_flight})
        
        return jsonify({
            "week_start": week_start.strftime("%d %b %Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d %b %Y"),
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
    <title>G-OPS 3PL Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #050508;
            --bg-primary: #0c0d12;
            --bg-secondary: #12141c;
            --bg-card: #181a24;
            --bg-elevated: #1e212d;
            --border: rgba(255,255,255,0.06);
            --border-light: rgba(255,255,255,0.1);
            --gold: #d4a853;
            --gold-light: #e8c47a;
            --gold-dim: rgba(212,168,83,0.1);
            --green: #22c55e;
            --green-dim: rgba(34,197,94,0.1);
            --red: #ef4444;
            --red-dim: rgba(239,68,68,0.1);
            --blue: #3b82f6;
            --text-primary: #ffffff;
            --text-secondary: #a1a1aa;
            --text-muted: #52525b;
            --sidebar-width: 240px;
            --sidebar-collapsed: 68px;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* ═══════════════ SIDEBAR ═══════════════ */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--bg-primary);
            border-right: 1px solid var(--border);
            position: fixed;
            height: 100vh;
            display: flex;
            flex-direction: column;
            z-index: 100;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .sidebar.collapsed { width: var(--sidebar-collapsed); }
        
        .sidebar-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            position: relative;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .logo-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }
        
        .logo-text h1 {
            font-size: 15px;
            font-weight: 700;
            color: var(--text-primary);
            white-space: nowrap;
        }
        
        .logo-text p {
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 2px;
        }
        
        .sidebar.collapsed .logo-text { display: none; }
        
        .toggle-btn {
            position: absolute;
            right: -12px;
            top: 24px;
            width: 24px;
            height: 24px;
            background: var(--bg-elevated);
            border: 1px solid var(--border-light);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 10px;
            transition: all 0.2s;
            z-index: 10;
        }
        
        .toggle-btn:hover {
            background: var(--gold);
            color: var(--bg-dark);
            border-color: var(--gold);
        }
        
        .sidebar.collapsed .toggle-btn { transform: rotate(180deg); }
        
        .nav-menu { padding: 16px 10px; flex: 1; }
        
        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 14px;
            color: var(--text-secondary);
            text-decoration: none;
            border-radius: 8px;
            margin-bottom: 4px;
            transition: all 0.2s;
            font-size: 13px;
            font-weight: 500;
            position: relative;
        }
        
        .nav-item:hover {
            background: var(--bg-elevated);
            color: var(--text-primary);
        }
        
        .nav-item.active {
            background: var(--gold-dim);
            color: var(--gold);
        }
        
        .nav-item.active::before {
            content: '';
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 3px;
            height: 20px;
            background: var(--gold);
            border-radius: 0 3px 3px 0;
        }
        
        .nav-icon {
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 15px;
            flex-shrink: 0;
        }
        
        .nav-text { margin-left: 12px; white-space: nowrap; }
        
        .sidebar.collapsed .nav-text { display: none; }
        .sidebar.collapsed .nav-item { justify-content: center; padding: 12px; }
        
        /* Tooltip */
        .nav-item[data-tip]:hover::after {
            content: attr(data-tip);
            position: absolute;
            left: 100%;
            top: 50%;
            transform: translateY(-50%);
            background: var(--bg-elevated);
            color: var(--text-primary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            white-space: nowrap;
            margin-left: 12px;
            border: 1px solid var(--border-light);
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
        }
        
        .sidebar.collapsed .nav-item[data-tip]:hover::after { opacity: 1; }
        
        /* ═══════════════ MAIN CONTENT ═══════════════ */
        .main {
            margin-left: var(--sidebar-width);
            min-height: 100vh;
            transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        body.collapsed .main { margin-left: var(--sidebar-collapsed); }
        
        .topbar {
            background: var(--bg-primary);
            border-bottom: 1px solid var(--border);
            padding: 16px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 50;
        }
        
        .page-title h1 {
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .page-title p {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 2px;
        }
        
        .topbar-right {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .week-picker {
            display: flex;
            align-items: center;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 2px;
        }
        
        .week-picker label {
            padding: 0 12px;
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .week-picker input {
            background: var(--bg-elevated);
            border: none;
            color: var(--text-primary);
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            font-family: inherit;
        }
        
        .week-badge {
            background: var(--gold-dim);
            border: 1px solid rgba(212,168,83,0.2);
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            color: var(--gold);
        }
        
        .content { padding: 24px 28px; }
        
        /* ═══════════════ PROVIDER CARDS ═══════════════ */
        .provider-card {
            background: var(--bg-card);
            border-radius: 12px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
            overflow: hidden;
        }
        
        .provider-header {
            padding: 18px 22px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            flex-wrap: wrap;
            gap: 14px;
        }
        
        .provider-info {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        
        .provider-color {
            width: 4px;
            height: 36px;
            border-radius: 2px;
        }
        
        .provider-details h3 {
            font-size: 14px;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .provider-meta {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 4px;
        }
        
        .stars {
            display: flex;
            gap: 2px;
            font-size: 11px;
        }
        
        .star { color: var(--text-muted); }
        .star.on { color: var(--gold); }
        
        .trend-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
        }
        
        .trend-badge.up {
            background: var(--green-dim);
            color: var(--green);
        }
        
        .trend-badge.down {
            background: var(--red-dim);
            color: var(--red);
        }
        
        .trend-badge.neutral {
            background: var(--bg-elevated);
            color: var(--text-muted);
        }
        
        .provider-stats {
            display: flex;
            gap: 8px;
        }
        
        .stat-pill {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
        }
        
        .stat-pill.gold {
            background: linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 100%);
            color: var(--bg-dark);
            border: none;
        }
        
        .stat-pill span {
            color: var(--text-muted);
            font-weight: 500;
            margin-right: 4px;
        }
        
        .stat-pill.gold span { color: rgba(0,0,0,0.6); }
        
        /* ═══════════════ TABLE ═══════════════ */
        .table-scroll { overflow-x: auto; }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 1200px;
            font-size: 11px;
        }
        
        .data-table th {
            background: var(--bg-secondary);
            padding: 10px 6px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
            font-size: 9px;
            border-bottom: 1px solid var(--border);
        }
        
        .data-table th.day {
            font-size: 10px;
            color: var(--text-secondary);
        }
        
        .data-table th.flight {
            background: var(--gold-dim);
            color: var(--gold);
        }
        
        .data-table th.region-th {
            text-align: left;
            padding-left: 18px;
            min-width: 130px;
        }
        
        .data-table td {
            padding: 9px 6px;
            text-align: center;
            font-weight: 500;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
        }
        
        .data-table td.region-td {
            text-align: left;
            padding-left: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .data-table td.flight-td {
            background: rgba(212,168,83,0.02);
        }
        
        .data-table td.has-val {
            color: var(--text-primary);
        }
        
        .data-table tbody tr:hover {
            background: var(--bg-elevated);
        }
        
        .data-table .total-row {
            background: var(--bg-secondary);
        }
        
        .data-table .total-row td {
            color: var(--gold);
            font-weight: 700;
            border-top: 2px solid var(--gold);
            padding: 12px 6px;
        }
        
        /* ═══════════════ SUMMARY CARDS ═══════════════ */
        .summary-card {
            background: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border);
            overflow: hidden;
        }
        
        .summary-header {
            padding: 18px 22px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .summary-header h2 {
            font-size: 14px;
            font-weight: 700;
        }
        
        .summary-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        
        .summary-table th {
            background: var(--bg-secondary);
            padding: 12px 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
            font-size: 10px;
        }
        
        .summary-table th.flight {
            background: var(--gold-dim);
            color: var(--gold);
        }
        
        .summary-table td {
            padding: 14px 10px;
            text-align: center;
            font-weight: 500;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border);
        }
        
        .summary-table td:first-child {
            text-align: left;
            padding-left: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .summary-table .winner {
            background: var(--gold-dim);
        }
        
        .summary-table .winner td:first-child {
            color: var(--gold);
        }
        
        .summary-table .winner td:first-child::before {
            content: '🏆 ';
        }
        
        .total-cell {
            background: var(--bg-secondary) !important;
            color: var(--gold) !important;
            font-weight: 700 !important;
        }
        
        /* ═══════════════ LOADING & ERROR ═══════════════ */
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 80px;
            color: var(--text-muted);
        }
        
        .spinner {
            width: 36px;
            height: 36px;
            border: 3px solid var(--border);
            border-top-color: var(--gold);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 14px;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .error {
            background: var(--red-dim);
            border: 1px solid rgba(239,68,68,0.3);
            color: var(--red);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            margin: 24px;
        }
        
        /* ═══════════════ SCROLLBAR ═══════════════ */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-primary); }
        ::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
        
        /* ═══════════════ RESPONSIVE ═══════════════ */
        @media (max-width: 768px) {
            .sidebar { width: var(--sidebar-collapsed); }
            .sidebar .logo-text, .sidebar .nav-text { display: none; }
            .sidebar .nav-item { justify-content: center; }
            .main { margin-left: var(--sidebar-collapsed); }
            .toggle-btn { display: none; }
            .topbar { flex-direction: column; gap: 12px; align-items: flex-start; }
            .provider-header { flex-direction: column; align-items: flex-start; }
        }
    </style>
</head>
<body>
    <nav class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <div class="logo">
                <div class="logo-icon">📦</div>
                <div class="logo-text">
                    <h1>G-OPS 3PL</h1>
                    <p>Executive Portal</p>
                </div>
            </div>
            <div class="toggle-btn" onclick="toggleSidebar()">«</div>
        </div>
        <div class="nav-menu">
            <a href="/" class="nav-item {{ 'active' if page == 'dashboard' else '' }}" data-tip="Dashboard">
                <span class="nav-icon">📊</span>
                <span class="nav-text">Dashboard</span>
            </a>
            <a href="/weekly-summary" class="nav-item {{ 'active' if page == 'weekly' else '' }}" data-tip="Weekly Summary">
                <span class="nav-icon">📈</span>
                <span class="nav-text">Weekly Summary</span>
            </a>
            <a href="/flight-load" class="nav-item {{ 'active' if page == 'flight' else '' }}" data-tip="Flight Load">
                <span class="nav-icon">✈️</span>
                <span class="nav-text">Flight Load</span>
            </a>
        </div>
    </nav>

    <main class="main">
        <header class="topbar">
            <div class="page-title">
                <h1>{% if page == 'dashboard' %}Dashboard{% elif page == 'weekly' %}Weekly Summary{% else %}Flight Load{% endif %}</h1>
                <p>{% if page == 'dashboard' %}Real-time performance metrics{% elif page == 'weekly' %}Weekly comparison with winner{% else %}Consolidated flight shipments{% endif %}</p>
            </div>
            <div class="topbar-right">
                <div class="week-picker">
                    <label>📅 Week</label>
                    <input type="date" id="weekStart" onchange="loadPage()">
                </div>
                <div class="week-badge" id="weekInfo">Loading...</div>
            </div>
        </header>

        <div class="content" id="mainContent">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading data...</p>
            </div>
        </div>
    </main>

    <script>
        const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
        const FLIGHT_DAYS = [1, 3, 5];
        const COLS = ['O', 'B', 'W', '<20', '20+'];
        
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('collapsed');
            document.body.classList.toggle('collapsed');
            localStorage.setItem('sidebarCollapsed', document.body.classList.contains('collapsed'));
        }
        
        if (localStorage.getItem('sidebarCollapsed') === 'true') {
            document.getElementById('sidebar').classList.add('collapsed');
            document.body.classList.add('collapsed');
        }
        
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1));
        document.getElementById('weekStart').value = monday.toISOString().split('T')[0];
        
        const page = '{{ page }}';
        
        function loadPage() {
            if (page === 'dashboard') loadDashboard();
            else if (page === 'weekly') loadWeekly();
            else if (page === 'flight') loadFlight();
        }
        
        function stars(n) {
            let s = '';
            for (let i = 1; i <= 5; i++) s += '<span class="star ' + (i <= n ? 'on' : '') + '">★</span>';
            return s;
        }
        
        function fmt(v, t) {
            if (!v || v === 0) return '-';
            if (t === 'w') return v.toFixed(1);
            if (t === 'b') return Math.round(v).toLocaleString();
            return v;
        }
        
        async function loadDashboard() {
            const ws = document.getElementById('weekStart').value;
            const c = document.getElementById('mainContent');
            c.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading...</p></div>';
            
            try {
                const r = await fetch('/api/dashboard?week_start=' + ws);
                const d = await r.json();
                if (d.error) throw new Error(d.error);
                
                document.getElementById('weekInfo').textContent = d.week_start + ' → ' + d.week_end;
                
                let h = '';
                d.providers.forEach(p => {
                    const regions = Object.keys(p.regions).sort();
                    
                    h += '<div class="provider-card">';
                    h += '<div class="provider-header">';
                    h += '<div class="provider-info">';
                    h += '<div class="provider-color" style="background:' + p.color + '"></div>';
                    h += '<div class="provider-details">';
                    h += '<h3>' + p.name + '</h3>';
                    h += '<div class="provider-meta">';
                    h += '<div class="stars">' + stars(p.rating) + '</div>';
                    h += '<span class="trend-badge ' + p.trend.class + '">' + p.trend.icon + ' ' + p.trend.percent + '%</span>';
                    h += '</div></div></div>';
                    h += '<div class="provider-stats">';
                    h += '<div class="stat-pill"><span>Orders</span>' + p.grand_total.orders.toLocaleString() + '</div>';
                    h += '<div class="stat-pill"><span>Boxes</span>' + Math.round(p.grand_total.boxes).toLocaleString() + '</div>';
                    h += '<div class="stat-pill gold"><span>Weight</span>' + p.grand_total.weight.toFixed(1) + ' kg</div>';
                    h += '</div></div>';
                    
                    h += '<div class="table-scroll"><table class="data-table">';
                    h += '<thead><tr><th class="region-th" rowspan="2">Region</th>';
                    DAYS.forEach((day, i) => {
                        const f = FLIGHT_DAYS.includes(i);
                        h += '<th colspan="5" class="day ' + (f ? 'flight' : '') + '">' + day + (f ? ' ✈️' : '') + '</th>';
                    });
                    h += '</tr><tr>';
                    DAYS.forEach((_, i) => {
                        const f = FLIGHT_DAYS.includes(i);
                        COLS.forEach(col => h += '<th class="' + (f ? 'flight' : '') + '">' + col + '</th>');
                    });
                    h += '</tr></thead><tbody>';
                    
                    regions.forEach(region => {
                        const rd = p.regions[region];
                        h += '<tr><td class="region-td">' + region + '</td>';
                        rd.days.forEach((day, i) => {
                            const f = FLIGHT_DAYS.includes(i);
                            const fc = f ? ' flight-td' : '';
                            h += '<td class="' + fc + (day.orders ? ' has-val' : '') + '">' + fmt(day.orders) + '</td>';
                            h += '<td class="' + fc + (day.boxes ? ' has-val' : '') + '">' + fmt(day.boxes, 'b') + '</td>';
                            h += '<td class="' + fc + (day.weight ? ' has-val' : '') + '">' + fmt(day.weight, 'w') + '</td>';
                            h += '<td class="' + fc + (day.under20 ? ' has-val' : '') + '">' + fmt(day.under20) + '</td>';
                            h += '<td class="' + fc + (day.over20 ? ' has-val' : '') + '">' + fmt(day.over20) + '</td>';
                        });
                        h += '</tr>';
                    });
                    
                    h += '<tr class="total-row"><td class="region-td">TOTAL</td>';
                    p.day_totals.forEach((day, i) => {
                        const f = FLIGHT_DAYS.includes(i);
                        const fc = f ? ' flight-td' : '';
                        h += '<td class="' + fc + '">' + day.orders + '</td>';
                        h += '<td class="' + fc + '">' + Math.round(day.boxes).toLocaleString() + '</td>';
                        h += '<td class="' + fc + '">' + day.weight.toFixed(1) + '</td>';
                        h += '<td class="' + fc + '">' + day.under20 + '</td>';
                        h += '<td class="' + fc + '">' + day.over20 + '</td>';
                    });
                    h += '</tr></tbody></table></div></div>';
                });
                
                c.innerHTML = h;
            } catch (e) {
                c.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + e.message + '</p></div>';
            }
        }
        
        async function loadWeekly() {
            const ws = document.getElementById('weekStart').value;
            const c = document.getElementById('mainContent');
            c.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading...</p></div>';
            
            try {
                const r = await fetch('/api/weekly-summary?week_start=' + ws);
                const d = await r.json();
                if (d.error) throw new Error(d.error);
                
                document.getElementById('weekInfo').textContent = d.week_start + ' → ' + d.week_end;
                
                let h = '<div class="summary-card">';
                h += '<div class="summary-header"><span>📊</span><h2>Weekly Performance Summary</h2></div>';
                h += '<div class="table-scroll"><table class="summary-table">';
                h += '<thead><tr><th>Provider</th>';
                DAYS.forEach((day, i) => {
                    const f = FLIGHT_DAYS.includes(i);
                    h += '<th colspan="3" class="' + (f ? 'flight' : '') + '">' + day + (f ? ' ✈️' : '') + '</th>';
                });
                h += '<th colspan="3">TOTAL</th></tr>';
                h += '<tr><th></th>';
                for (let i = 0; i < 8; i++) h += '<th>O</th><th>B</th><th>KG</th>';
                h += '</tr></thead><tbody>';
                
                d.providers.forEach(p => {
                    h += '<tr class="' + (p.is_winner ? 'winner' : '') + '">';
                    h += '<td>' + p.name + '</td>';
                    p.days.forEach(day => {
                        h += '<td>' + fmt(day.orders) + '</td>';
                        h += '<td>' + fmt(day.boxes, 'b') + '</td>';
                        h += '<td>' + fmt(day.weight, 'w') + '</td>';
                    });
                    h += '<td class="total-cell">' + p.total.orders + '</td>';
                    h += '<td class="total-cell">' + Math.round(p.total.boxes).toLocaleString() + '</td>';
                    h += '<td class="total-cell">' + p.total.weight.toFixed(1) + '</td>';
                    h += '</tr>';
                });
                
                h += '</tbody></table></div></div>';
                c.innerHTML = h;
            } catch (e) {
                c.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + e.message + '</p></div>';
            }
        }
        
        async function loadFlight() {
            const ws = document.getElementById('weekStart').value;
            const c = document.getElementById('mainContent');
            c.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading...</p></div>';
            
            try {
                const r = await fetch('/api/flight-load?week_start=' + ws);
                const d = await r.json();
                if (d.error) throw new Error(d.error);
                
                document.getElementById('weekInfo').textContent = d.week_start + ' → ' + d.week_end;
                
                let h = '<div class="summary-card">';
                h += '<div class="summary-header"><span>✈️</span><h2>Consolidated Flight Load</h2></div>';
                h += '<div class="table-scroll"><table class="summary-table">';
                h += '<thead><tr><th>Provider</th>';
                h += '<th colspan="3" class="flight">TUE Flight</th>';
                h += '<th colspan="3" class="flight">THU Flight</th>';
                h += '<th colspan="3" class="flight">SAT Flight</th>';
                h += '<th colspan="3">TOTAL</th></tr>';
                h += '<tr><th></th>';
                for (let i = 0; i < 4; i++) h += '<th>O</th><th>B</th><th>KG</th>';
                h += '</tr></thead><tbody>';
                
                d.providers.forEach(p => {
                    h += '<tr><td>' + p.name + '</td>';
                    h += '<td>' + fmt(p.tue_flight.orders) + '</td>';
                    h += '<td>' + fmt(p.tue_flight.boxes, 'b') + '</td>';
                    h += '<td>' + fmt(p.tue_flight.weight, 'w') + '</td>';
                    h += '<td>' + fmt(p.thu_flight.orders) + '</td>';
                    h += '<td>' + fmt(p.thu_flight.boxes, 'b') + '</td>';
                    h += '<td>' + fmt(p.thu_flight.weight, 'w') + '</td>';
                    h += '<td>' + fmt(p.sat_flight.orders) + '</td>';
                    h += '<td>' + fmt(p.sat_flight.boxes, 'b') + '</td>';
                    h += '<td>' + fmt(p.sat_flight.weight, 'w') + '</td>';
                    h += '<td class="total-cell">' + p.total.orders + '</td>';
                    h += '<td class="total-cell">' + Math.round(p.total.boxes).toLocaleString() + '</td>';
                    h += '<td class="total-cell">' + p.total.weight.toFixed(1) + '</td>';
                    h += '</tr>';
                });
                
                h += '</tbody></table></div></div>';
                c.innerHTML = h;
            } catch (e) {
                c.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + e.message + '</p></div>';
            }
        }
        
        loadPage();
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True)
