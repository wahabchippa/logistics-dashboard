from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from functools import wraps
import csv
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
import time
import os
import random

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
# ========== VIP TOKEN GENERATOR ==========
import json
VIP_TOKEN_CACHE = {"token": None, "expires": 0}
def get_auth_headers():
    global VIP_TOKEN_CACHE
    import time
    if time.time() >= VIP_TOKEN_CACHE["expires"]:
        try:
            req = urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
                'client_id': '320772774106-fpv7td9vqdcb9eg37utn6th5iihsl753.apps.googleusercontent.com',
                'client_secret': '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',
                'refresh_token': '1//04Om55oY1FH6rCgYIARAAGAQSNwF-L9Ir3d-HLOMyj3jMy8bh0s3C0dqHSVMMZtV33MT4e6EhnUD4bSMxOf-ouB-v-LL4KSMTGWI',
                'grant_type': 'refresh_token'
            }).encode('utf-8'))
            res = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
            VIP_TOKEN_CACHE = {"token": res['access_token'], "expires": time.time() + 3000}
        except Exception as e: print("Token Error:", e)
    return {'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache', 'Authorization': f'Bearer {VIP_TOKEN_CACHE.get("token", "")}'}


# ========== CACHE ==========
CACHE = {}
CACHE_DURATION = 900  # 15 منٹ
SHEET_ID = '1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY        '

# ========== PROVIDERS ==========
PROVIDERS = [
    {'name': 'GLOBAL EXPRESS (QC)', 'short': 'GE QC', 'sheet': 'GE QC Center & Zone', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'country_col': 6, 'order_col': 0, 'start_row': 2, 'color': '#3B82F6', 'group': 'GE'},
    {'name': 'GLOBAL EXPRESS (ZONE)', 'short': 'GE ZONE', 'sheet': 'GE QC Center & Zone', 'date_col': 10, 'box_col': 11, 'weight_col': 15, 'region_col': 16, 'country_col': 14, 'order_col': 9, 'start_row': 2, 'color': '#8B5CF6', 'group': 'GE'},
    {'name': 'EXPRESS COURIER LINK  (QC)', 'short': 'ECL QC', 'sheet': 'ECL QC Center & Zone', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'country_col': 6, 'order_col': 0, 'start_row': 3, 'color': '#10B981', 'group': 'ECL'},
    {'name': 'EXPRESS COURIER LINK (ZONE)', 'short': 'ECL ZONE', 'sheet': 'ECL QC Center & Zone', 'date_col': 10, 'box_col': 11, 'weight_col': 14, 'region_col': 16, 'country_col': 15, 'order_col': 9, 'start_row': 3, 'color': '#F59E0B', 'group': 'ECL'},
    {'name': 'KERRY', 'short': 'KERRY', 'sheet': 'Kerry', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'country_col': 6, 'order_col': 0, 'start_row': 2, 'color': '#EF4444', 'group': 'OTHER'},
    {'name': 'APX', 'short': 'APX', 'sheet': 'APX', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'country_col': 6, 'order_col': 0, 'start_row': 2, 'color': '#EC4899', 'group': 'OTHER'}
]

INVALID_REGIONS = {'', 'N/A', '#N/A', 'COUNTRY', 'REGION', 'DESTINATION', 'ZONE', 'ORDER', 'FLEEK ID', 'DATE', 'CARTONS'}

# ========== ORDER LOOKUP SOURCES ==========
_GE_SID   = "1Bt8od4x1xim2CO0vHcpYPR8eoA7L0XWqNsXqBsl9FBI"
_ECL_SID  = "1VGP6HYxb-vf3pTlKCT-WyjZlf3sy_j8BrZnjjSxUVJA"
_APX_SID  = "1WrrM_ewt0IcdG9ysKtXfIiSbSla52tsjq6FXP4rRlDo"
_KERRY_SID= "12p1mTHfQKrmbekNK2H9IROyBxPaaBg1C0T6EDSyioko"
ORDER_LOOKUP_EMAIL = 'wahab.chippa@joinfleek.com'
ORDER_LOOKUP_SOURCES = [
    {"name":"GE QC",    "sid":_GE_SID,    "tab":"Address and Tracking - QC Centre", "start":1, "o":0,"b":3, "cw":6, "v":12,"ti":13,"ic":14,"c":15,"cn":19,"tid":28,"mawb":31},
    {"name":"GE Zone",  "sid":_GE_SID,    "tab":"Address and Tracking - Zone",       "start":1, "o":0,"b":3, "cw":6, "v":12,"ti":13,"ic":14,"c":15,"cn":19,"tid":28,"mawb":31},
    {"name":"ECL QC",   "sid":_ECL_SID,   "tab":"Address and Tracking QC Center",    "start":1, "o":0,"b":3, "cw":6, "v":10,"ti":11,"ic":12,"c":13,"cn":17,"tid":25,"mawb":27},
    {"name":"ECL Zone", "sid":_ECL_SID,   "tab":"Address and Tracking Zone",         "start":2, "o":0,"b":4, "cw":8, "v":13,"ti":14,"ic":15,"c":16,"cn":20,"tid":28,"mawb":32},
    {"name":"APX",      "sid":_APX_SID,   "tab":"Address and Tracking",              "start":1, "o":0,"b":3, "cw":6, "v":11,"ti":12,"ic":13,"c":14,"cn":18,"tid":27,"mawb":32},
    {"name":"Kerry",    "sid":_KERRY_SID, "tab":"Address and Tracking",              "start":1, "o":0,"b":4, "cw":7, "v":14,"ti":15,"ic":16,"c":17,"cn":21,"tid":31,"mawb":37},
]
_olc = {}   # order lookup cache: key -> {"rows": [...], "time": float}

ACHIEVEMENTS = {
    'star_5': {'name': '5 Star Week', 'icon': '⭐', 'desc': '1500+ boxes in a week'},
    'star_4': {'name': '4 Star Week', 'icon': '🌟', 'desc': '500+ boxes in a week'},
    'champion': {'name': 'Weekly Champion', 'icon': '🏆', 'desc': 'Won the week'},
    'rocket': {'name': 'Rocket Growth', 'icon': '🚀', 'desc': '50%+ growth from last week'},
    'consistent': {'name': 'Consistent Performer', 'icon': '💪', 'desc': 'Active all 7 days'},
    'heavyweight': {'name': 'Heavyweight', 'icon': '🏋️', 'desc': '5000+ kg in a week'},
    'region_king': {'name': 'Region King', 'icon': '👑', 'desc': 'Most regions covered'},
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def get_week_range(date=None):
    if date is None:
        date = datetime.now()
    monday = date - timedelta(days=date.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday

def parse_date_range(request):
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    week_start_str = request.args.get('week_start')
    if start_str and end_str:
        start = datetime.strptime(start_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, microsecond=999999)
    elif week_start_str:
        start = datetime.strptime(week_start_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    else:
        start, end = get_week_range()
    return start, end

def parse_date(date_str):
    if not date_str or str(date_str).strip() in ['', '#N/A', 'N/A', 'DATE']:
        return None
    date_str = str(date_str).strip()
    formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%m/%d/%Y', '%Y/%m/%d', '%d.%m.%Y', '%d-%b-%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def fetch_sheet_data(sheet_name):
    cache_key = f"sheet_{sheet_name}"
    current_time = time.time()
    if cache_key in CACHE:
        cached_data, cache_time = CACHE[cache_key]
        if current_time - cache_time < CACHE_DURATION:
            return cached_data
    try:
        import json
        clean_id = SHEET_ID.strip()
        encoded_name = urllib.parse.quote(sheet_name)
        
        # 100% OFFICIAL GOOGLE SHEETS API LINK (No 401 Error)
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{clean_id}/values/{encoded_name}'
        
        req = urllib.request.Request(url, headers=get_auth_headers())
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            # API se data JSON format mein aata hai, usay nikalna
            rows = data.get('values', [])
            
            # Puranay CSV ki tarah saare cells ko text bana dena
            str_rows = [[str(cell) for cell in row] for row in rows]
            
            CACHE[cache_key] = (str_rows, current_time)
            return str_rows
    except Exception as e:
        print(f"Error fetching {sheet_name}: {e}")
        return []

def get_star_rating(boxes):
    if boxes >= 1500: return 5
    elif boxes >= 500: return 4
    elif boxes >= 100: return 3
    else: return 2

def process_provider_data(provider, week_start, week_end):
    rows = fetch_sheet_data(provider['sheet'])
    if not rows:
        return None
    data = {
        'name': provider['name'],
        'short': provider.get('short', provider['name']),
        'color': provider['color'],
        'group': provider.get('group', 'OTHER'),
        'total_orders': 0,
        'total_boxes': 0,
        'total_weight': 0.0,
        'total_under20': 0,
        'total_over20': 0,
        'regions': defaultdict(lambda: {
            'days': {day: {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0}
                    for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']}
        }),
        'daily_totals': {day: {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0}
                        for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']},
        'active_days': set()
    }
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for row_idx, row in enumerate(rows):
        if row_idx < provider['start_row'] - 1:
            continue
        try:
            if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col']):
                continue
            date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
            parsed_date = parse_date(date_val)
            if not parsed_date:
                continue
            if not (week_start <= parsed_date <= week_end):
                continue
            region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
            if region in INVALID_REGIONS or not region:
                continue
            try:
                boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
            except:
                boxes = 0
            try:
                weight = float(row[provider['weight_col']].replace(',', '')) if row[provider['weight_col']].strip() else 0.0
            except:
                weight = 0.0
            day_name = day_names[parsed_date.weekday()]
            data['total_orders'] += 1
            data['total_boxes'] += boxes
            data['total_weight'] += weight
            data['active_days'].add(day_name)
            if weight < 20:
                data['total_under20'] += 1
            else:
                data['total_over20'] += 1
            data['daily_totals'][day_name]['orders'] += 1
            data['daily_totals'][day_name]['boxes'] += boxes
            data['daily_totals'][day_name]['weight'] += weight
            if weight < 20:
                data['daily_totals'][day_name]['under20'] += 1
            else:
                data['daily_totals'][day_name]['over20'] += 1
            region_data = data['regions'][region]['days'][day_name]
            region_data['orders'] += 1
            region_data['boxes'] += boxes
            region_data['weight'] += weight
            if weight < 20:
                region_data['under20'] += 1
            else:
                region_data['over20'] += 1
        except Exception as e:
            continue
    data['stars'] = get_star_rating(data['total_boxes'])
    data['active_days'] = list(data['active_days'])
    data['regions'] = dict(data['regions'])
    for region in data['regions']:
        data['regions'][region] = dict(data['regions'][region])
    return data

def calculate_trend(current_boxes, previous_boxes):
    if previous_boxes == 0:
        if current_boxes > 0:
            return {'direction': 'up', 'percentage': 100}
        return {'direction': 'neutral', 'percentage': 0}
    change = ((current_boxes - previous_boxes) / previous_boxes) * 100
    if change >= 0:
        return {'direction': 'up', 'percentage': round(change, 1)}
    else:
        return {'direction': 'down', 'percentage': round(abs(change), 1)}

def get_provider_achievements(provider_data, is_winner=False, trend=None):
    achievements = []
    if provider_data['stars'] >= 5:
        achievements.append(ACHIEVEMENTS['star_5'])
    elif provider_data['stars'] >= 4:
        achievements.append(ACHIEVEMENTS['star_4'])
    if is_winner:
        achievements.append(ACHIEVEMENTS['champion'])
    if trend and trend['direction'] == 'up' and trend['percentage'] >= 50:
        achievements.append(ACHIEVEMENTS['rocket'])
    if len(provider_data.get('active_days', [])) >= 7:
        achievements.append(ACHIEVEMENTS['consistent'])
    if provider_data['total_weight'] >= 5000:
        achievements.append(ACHIEVEMENTS['heavyweight'])
    if len(provider_data.get('regions', {})) >= 5:
        achievements.append(ACHIEVEMENTS['region_king'])
    return achievements

FAVICON = '''<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%234f46e5'/%3E%3Ctext x='50' y='68' font-size='48' text-anchor='middle' fill='white' font-family='Arial' font-weight='bold'%3E3PL%3C/text%3E%3C/svg%3E">'''

# ========== BASE STYLES (UPDATED WITH ANIMATIONS) ==========
BASE_STYLES = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    :root {
        --bg-body: #f8fafc;
        --bg-sidebar: #ffffff;
        --bg-card: #ffffff;
        --text-main: #1e293b;
        --text-muted: #64748b;
        --border-color: #e2e8f0;
        --brand-color: #4f46e5;
        --brand-gradient: linear-gradient(145deg, #4f46e5, #8b5cf6);
        --hover-bg: #f1f5f9;
        --table-hdr: #f8fafc;
        --cell-empty: #f1f5f9;
        --flight-day-bg: #f1f5f9;
        --skeleton-base: #e2e8f0;
        --skeleton-highlight: #f1f5f9;
    }

    [data-theme="dark"] {
        --bg-body: #000000;
        --bg-sidebar: #111111;
        --bg-card: #111111;
        --text-main: #f1f5f9;
        --text-muted: #94a3b8;
        --border-color: #222222;
        --brand-color: #818cf8;
        --hover-bg: #222222;
        --table-hdr: #111111;
        --cell-empty: #222222;
        --flight-day-bg: #1e1e2e;
        --skeleton-base: #1e1e2e;
        --skeleton-highlight: #2a2a3a;
    }

    [data-theme="dark"] .provider-card:nth-child(odd) { background: #0f0f15; }
    [data-theme="dark"] .provider-card:nth-child(even) { background: #0a0a0f; }
    [data-theme="dark"] .stat-card:nth-child(odd) { background: #0f0f15; }
    [data-theme="dark"] .stat-card:nth-child(even) { background: #0a0a0f; }

    /* ===== DARK THEME OVERRIDES — fix all hardcoded light colors ===== */
    /* ===== DARK THEME — ALL FIXES ===== */
    body[data-theme="dark"] .trend-badge.up { background: rgba(16,185,129,0.15) !important; color: #34d399 !important; border-color: rgba(16,185,129,0.3) !important; }
    body[data-theme="dark"] .trend-badge.down { background: rgba(239,68,68,0.15) !important; color: #f87171 !important; border-color: rgba(239,68,68,0.3) !important; }
    body[data-theme="dark"] .kpi-trend.up { background: rgba(16,185,129,0.15) !important; color: #34d399 !important; border-color: rgba(16,185,129,0.3) !important; }
    body[data-theme="dark"] .kpi-trend.down { background: rgba(239,68,68,0.15) !important; color: #f87171 !important; border-color: rgba(239,68,68,0.3) !important; }
    body[data-theme="dark"] .winner-card { background: rgba(251,191,36,0.08) !important; border-color: rgba(251,191,36,0.4) !important; }
    body[data-theme="dark"] .rank-1 { background: rgba(251,191,36,0.25) !important; color: #fbbf24 !important; }
    body[data-theme="dark"] .rank-2 { background: rgba(148,163,184,0.2) !important; color: #cbd5e1 !important; }
    body[data-theme="dark"] .rank-3 { background: rgba(249,168,212,0.15) !important; color: #f9a8d4 !important; }

    /* All clickable number links — bright in dark mode */
    body[data-theme="dark"] a.orders-link,
    body[data-theme="dark"] a.boxes-link,
    body[data-theme="dark"] a.weight-link,
    body[data-theme="dark"] a.under20-link,
    body[data-theme="dark"] a.over20-link { color: #60a5fa !important; }
    body[data-theme="dark"] a.orders-link:hover,
    body[data-theme="dark"] a.boxes-link:hover,
    body[data-theme="dark"] a.weight-link:hover,
    body[data-theme="dark"] a.under20-link:hover,
    body[data-theme="dark"] a.over20-link:hover { color: #a78bfa !important; }

    /* Leaderboard table — all text bright */
    body[data-theme="dark"] .leaderboard-table td { color: #e2e8f0 !important; background: transparent; }
    body[data-theme="dark"] .leaderboard-table a { color: #60a5fa !important; }
    body[data-theme="dark"] .leaderboard-table .provider-name-text { color: #f1f5f9 !important; }

    /* Data table cells — bright text */
    body[data-theme="dark"] .data-table td { color: #e2e8f0 !important; }
    body[data-theme="dark"] .data-table td.region-col { color: #f1f5f9 !important; background: #111 !important; }
    body[data-theme="dark"] .data-table tr.total-row td { color: #818cf8 !important; background: rgba(129,140,248,0.1) !important; }

    /* Day-data cells — brighter colors */
    body[data-theme="dark"] .day-data span:nth-child(1), body[data-theme="dark"] .day-data a:nth-child(1) { color: #93c5fd !important; background: rgba(59,130,246,0.18) !important; }
    body[data-theme="dark"] .day-data span:nth-child(2), body[data-theme="dark"] .day-data a:nth-child(2) { color: #6ee7b7 !important; background: rgba(16,185,129,0.18) !important; }
    body[data-theme="dark"] .day-data span:nth-child(3), body[data-theme="dark"] .day-data a:nth-child(3) { color: #fcd34d !important; background: rgba(245,158,11,0.18) !important; }
    body[data-theme="dark"] .day-data span:nth-child(4), body[data-theme="dark"] .day-data a:nth-child(4) { color: #c4b5fd !important; background: rgba(139,92,246,0.18) !important; }
    body[data-theme="dark"] .day-data span:nth-child(5), body[data-theme="dark"] .day-data a:nth-child(5) { color: #f9a8d4 !important; background: rgba(236,72,153,0.18) !important; }

    /* Stat values, KPI values — white */
    body[data-theme="dark"] .stat-value,
    body[data-theme="dark"] .kpi-value,
    body[data-theme="dark"] .stat-item .stat-value { color: #f1f5f9 !important; }

    /* Comparison stats */
    body[data-theme="dark"] .comparison-stat-value { color: #f1f5f9 !important; }
    body[data-theme="dark"] .comparison-name { color: #f1f5f9 !important; }

    /* Provider name in card header */
    body[data-theme="dark"] .provider-name { color: #f1f5f9 !important; }

    /* Total row in leaderboard */
    body[data-theme="dark"] .leaderboard-table tr:last-child td { color: #818cf8 !important; font-weight: 700; }
    [data-theme="dark"] input[type="date"],
    [data-theme="dark"] input[type="text"],
    [data-theme="dark"] select { background: #1a1a1a; color: #f1f5f9; border-color: #333; color-scheme: dark; }
    [data-theme="dark"] input::placeholder { color: #555; }
    [data-theme="dark"] .data-table td { color: #e2e8f0; }
    [data-theme="dark"] .data-table td.region-col { background: #111; color: #e2e8f0; }
    [data-theme="dark"] .data-table tr.total-row td { background: rgba(129,140,248,0.12); color: #818cf8; }
    [data-theme="dark"] .leaderboard-table td { color: #e2e8f0; }
    [data-theme="dark"] .comparison-name { color: #f1f5f9; }
    [data-theme="dark"] .comparison-stat-value { color: #f1f5f9; }
    [data-theme="dark"] .page-title { color: #f1f5f9; }
    [data-theme="dark"] .provider-name { color: #f1f5f9; }
    [data-theme="dark"] .stat-value { color: #f1f5f9; }
    [data-theme="dark"] .kpi-value { color: #f1f5f9; }
    [data-theme="dark"] .chart-title { color: #f1f5f9; }
    [data-theme="dark"] .nav-item { color: #94a3b8; }
    [data-theme="dark"] .nav-item.active { color: #818cf8; background: rgba(129,140,248,0.12); border-left-color: #818cf8; }
    [data-theme="dark"] .nav-item:hover { background: #1a1a1a; color: #f1f5f9; }
    [data-theme="dark"] .nav-section-title { color: #555; }
    [data-theme="dark"] .search-input { background: #111; color: #f1f5f9; }
    [data-theme="dark"] #search-results { box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
    [data-theme="dark"] .day-data { background: #080808; border-color: #222; }
    [data-theme="dark"] .day-data span, [data-theme="dark"] .day-data a { border-right-color: #222; }
    [data-theme="dark"] .date-range-picker { background: #111; border-color: #222; }
    [data-theme="dark"] .qbtn { background: #1a1a1a; border-color: #333; color: #94a3b8; }
    [data-theme="dark"] .qbtn:hover { background: #222; color: #f1f5f9; }
    [data-theme="dark"] .range-input { background: #1a1a1a; border-color: #333; color: #f1f5f9; }
    [data-theme="dark"] .week-badge { background: rgba(129,140,248,0.12); color: #818cf8; }
    [data-theme="dark"] .provider-card { border-color: #1a1a1a; }
    [data-theme="dark"] .card-header { border-bottom-color: #1a1a1a; }
    [data-theme="dark"] .chart-card { background: #0f0f15; border-color: #1a1a1a; }
    [data-theme="dark"] .kpi-card { background: #0f0f15; border-color: #1a1a1a; }
    [data-theme="dark"] .comparison-card { background: #0f0f15; border-color: #1a1a1a; }
    [data-theme="dark"] .stat-card { border-color: #1a1a1a; }
    [data-theme="dark"] .stat-icon { background: #1a1a1a; border-color: #222; }
    [data-theme="dark"] .tab-btn { background: #1a1a1a; border-color: #333; color: #94a3b8; }
    [data-theme="dark"] .tab-btn:hover { background: #222; color: #f1f5f9; }
    [data-theme="dark"] .tab-btn.active { background: #818cf8; border-color: #818cf8; color: #fff; }
    [data-theme="dark"] .action-btn { background: #111; border-color: #333; color: #f1f5f9; }
    [data-theme="dark"] .action-btn:hover { border-color: #818cf8; color: #818cf8; }
    [data-theme="dark"] .download-btn { background: #1a1a1a; border-color: #333; color: #94a3b8; }
    [data-theme="dark"] .download-btn:hover { background: #818cf8; color: #fff; border-color: #818cf8; }
    [data-theme="dark"] .last-update { border-top-color: #1a1a1a; color: #555; }
    [data-theme="dark"] .search-item:hover { background: #1a1a1a; }
    [data-theme="dark"] .search-item-title { color: #f1f5f9; }
    [data-theme="dark"] .header-main { color: #f1f5f9; }
    [data-theme="dark"] .logo-icon { background: linear-gradient(145deg, #4f46e5, #7c3aed); }

    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Inter', sans-serif; background: var(--bg-body); color: var(--text-main); min-height: 100vh; font-size: 13px; line-height: 1.4; transition: background 0.3s, color 0.3s; }

    /* ========== ANIMATIONS ========== */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .provider-card, .stat-card, .comparison-card, .heatmap-item, .forecast-day, .provider-section {
        animation: fadeIn 0.4s ease-out;
    }
    .nav-item, .tab-btn, .qbtn, .action-btn, .apply-btn, .download-btn, .logout-btn {
        transition: all 0.2s;
    }
    .nav-item:hover, .tab-btn:hover, .qbtn:hover, .action-btn:hover, .apply-btn:hover, .download-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
    }
    .provider-card:hover, .stat-card:hover, .comparison-card:hover, .heatmap-item:hover, .forecast-day:hover, .provider-section:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 24px rgba(79,70,229,0.08);
        border-color: var(--brand-color);
    }

    /* Skeleton Loading */
    .skeleton {
        background: linear-gradient(90deg, var(--skeleton-base) 25%, var(--skeleton-highlight) 50%, var(--skeleton-base) 75%);
        background-size: 200% 100%;
        animation: skeleton-loading 1.5s infinite;
        border-radius: 4px;
        height: 20px;
        margin: 10px 0;
    }
    @keyframes skeleton-loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    /* Download Button */
    .download-btn {
        background: none;
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
        cursor: pointer;
        color: var(--text-muted);
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-left: 10px;
    }
    .download-btn:hover {
        background: var(--hover-bg);
        color: var(--brand-color);
        border-color: var(--brand-color);
    }

    /* Last Update */
    .last-update {
        font-size: 10px;
        color: var(--text-muted);
        padding: 8px 12px;
        border-top: 1px solid var(--border-color);
        margin-top: 8px;
        text-align: center;
    }

    /* Guest Mode Restrictions */
    body.guest-mode .day-data a,
    body.guest-mode .orders-link,
    body.guest-mode .boxes-link,
    body.guest-mode .weight-link,
    body.guest-mode .under20-link,
    body.guest-mode .over20-link,
    body.guest-mode .export-btn,
    body.guest-mode .search-box,
    body.guest-mode #forecast-link,
    body.guest-mode #logs-link,
    body.guest-mode .download-btn {
        display: none !important;
        pointer-events: none !important;
    }

    /* Sidebar */
    .sidebar {
        position: fixed;
        left: 0;
        top: 0;
        height: 100vh;
        width: 220px;
        background: var(--bg-sidebar);
        border-right: none;
        box-shadow: none;
        padding: 16px 12px;
        transition: all 0.2s ease;
        z-index: 100;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        scrollbar-width: none;
        -ms-overflow-style: none;
    }
    .sidebar::-webkit-scrollbar { display: none; }
    .sidebar.collapsed { width: 60px; }
    .sidebar-header {
        display: flex;
        align-items: center;
        gap: 10px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border-color);
        margin-bottom: 16px;
        width: 100%;
    }
    .logo-icon {
        width: 36px;
        height: 36px;
        background: var(--brand-gradient);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: #ffffff;
        font-size: 18px;
    }
    .header-titles {
        display: flex;
        flex-direction: column;
    }
    .header-main {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-main);
        line-height: 1.2;
    }
    .header-sub {
        font-size: 11px;
        color: var(--text-muted);
        margin-top: 2px;
    }
    .header-sub .admin-name {
        color: var(--text-main);
        font-weight: 500;
    }
    .header-sub .admin-role {
        color: #10b981;
        font-weight: 600;
    }
    body.dark .header-sub .admin-name { color: #f1f5f9; }
    body.dark .header-sub .admin-role { color: #10b981; }
    .sidebar.collapsed .header-main,
    .sidebar.collapsed .header-sub {
        opacity: 0;
        width: 0;
        display: none;
    }
    .sidebar.collapsed .sidebar-header { justify-content: center; }
    .sidebar.collapsed .logo-icon { display: none; }
    .sidebar.collapsed .sidebar-toggle { margin-left: 0; transform: rotate(180deg); }
    .nav-section { margin-bottom: 12px; }
    .nav-section-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); padding: 4px 8px; margin-bottom: 2px; font-weight: 600; }
    .sidebar.collapsed .nav-section-title { opacity: 0; }
    .nav-menu { display: flex; flex-direction: column; gap: 2px; flex-grow: 1; }
    .nav-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 8px;
        border-radius: 6px;
        color: var(--text-muted);
        text-decoration: none;
        transition: all 0.2s;
        font-size: 12px;
        font-weight: 500;
    }
    .nav-item:hover { background: var(--hover-bg); color: var(--text-main); }
    .nav-item.active { background: rgba(79,70,229,0.1); color: var(--brand-color); border-left: 3px solid var(--brand-color); }
    .nav-item svg { width: 16px; height: 16px; flex-shrink: 0; color: currentColor; }
    .sidebar.collapsed .nav-item span { opacity: 0; width: 0; }
    .sidebar-toggle { width: 28px; height: 28px; background: var(--brand-color); border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; border: none; color: #ffffff; font-size: 13px; flex-shrink: 0; margin-left: auto; transition: all 0.2s; }
    .sidebar-toggle:hover { opacity: 0.85; }
    .sidebar.collapsed .sidebar-toggle { transform: rotate(180deg); }
    .sidebar-footer { border-top: 1px solid var(--border-color); padding-top: 12px; margin-top: auto; }
    .admin-info { display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: var(--hover-bg); border-radius: 8px; margin-bottom: 8px; }
    .admin-avatar { width: 28px; height: 28px; background: var(--brand-color); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 14px; }
    .admin-role { font-size: 10px; color: var(--text-muted); }
    .logout-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border-radius: 6px;
        color: #ef4444;
        text-decoration: none;
        font-size: 12px;
        font-weight: 500;
        transition: 0.2s;
        width: fit-content;
    }
    .logout-btn:hover { background: rgba(239,68,68,0.1); }
    .logout-btn svg { width: 14px; height: 14px; }
    .sidebar.collapsed .logout-btn span { display: none; }
    .refresh-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border-radius: 6px;
        color: var(--brand-color);
        background: none;
        border: none;
        cursor: pointer;
        font-size: 12px;
        font-weight: 500;
        transition: 0.2s;
        width: fit-content;
    }
    .refresh-btn:hover { background: rgba(99,102,241,0.1); }
    .refresh-btn svg { width: 14px; height: 14px; flex-shrink: 0; }
    .sidebar.collapsed .refresh-btn span { display: none; }
    .refresh-btn.spinning svg { animation: spin 1s linear infinite; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

    /* Main Content */
    .main-content { margin-left: 220px; padding: 20px; transition: margin-left 0.2s; min-height: 100vh; }
    .main-content.expanded { margin-left: 60px; }

    /* Page Header */
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        flex-wrap: wrap;
        gap: 12px;
    }
    .page-title { font-size: 24px; font-weight: 700; color: var(--text-main); }
    .page-title span { color: var(--brand-color); }

    /* Top Actions */
    .top-actions {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        flex-wrap: wrap;
    }
    .search-box {
        position: relative;
        display: flex;
        align-items: center;
    }
    .search-input {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        color: var(--text-main);
        padding: 6px 12px 6px 32px;
        border-radius: 20px;
        font-size: 12px;
        outline: none;
        transition: 0.2s;
        width: 220px;
    }
    .search-input:focus { border-color: var(--brand-color); box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }
    .search-icon { position: absolute; left: 10px; color: var(--text-muted); font-size: 12px; }
    .shortcut-hint { position: absolute; right: 10px; font-size: 9px; background: var(--hover-bg); padding: 2px 4px; border-radius: 4px; color: var(--text-muted); border: 1px solid var(--border-color); }
    .action-group { display: flex; gap: 8px; }
    .action-btn {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        color: var(--text-main);
        padding: 6px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 4px;
        transition: 0.2s;
    }
    .action-btn:hover { border-color: var(--brand-color); color: var(--brand-color); }

    /* Search Results */
    #search-results {
        position: absolute;
        top: 100%;
        left: 0;
        width: 100%;
        max-width: 400px;
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-top: 8px;
        z-index: 1000;
        display: none;
        max-height: 400px;
        overflow-y: auto;
    }
    .search-item { padding: 12px 16px; border-bottom: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 4px; cursor: pointer; }
    .search-item:hover { background: var(--hover-bg); }
    .search-item-title { font-weight: 600; color: var(--text-main); display: flex; justify-content: space-between; }
    .search-item-meta { font-size: 11px; color: var(--text-muted); display: flex; gap: 10px; }

    /* Date Picker */
    .date-range-picker {
        background: var(--bg-card);
        border-radius: 16px;
        border: 1px solid var(--border-color);
        padding: 12px 16px;
    }
    .qbtns-row { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
    .qbtn { padding: 4px 12px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 30px; color: var(--text-muted); font-size: 10px; cursor: pointer; transition: 0.2s; }
    .qbtn:hover { background: var(--border-color); }
    .qbtn.active { background: var(--brand-color); border-color: var(--brand-color); color: #fff; }
    .date-inputs-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .range-input { padding: 4px 10px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 30px; color: var(--text-main); font-size: 11px; }
    .apply-btn { padding: 4px 14px; background: var(--brand-color); border: none; border-radius: 30px; color: #fff; font-size: 11px; cursor: pointer; }
    .week-badge { font-size: 11px; color: var(--brand-color); padding: 4px 12px; background: rgba(79,70,229,0.1); border-radius: 30px; }

    /* Provider Cards */
    .provider-card { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); margin-bottom: 20px; overflow: hidden; }
    .card-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--border-color); }
    .provider-info { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
    .provider-name { font-size: 18px; font-weight: 600; color: var(--text-main); }
    .star-rating { color: #fbbf24; font-size: 13px; letter-spacing: 2px; }
    .trend-badge { display: flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 30px; font-size: 11px; font-weight: 600; }
    .trend-badge.up { background: #e6f7e6; color: #10b981; border: 1px solid #a7f3d0; }
    .trend-badge.down { background: #fee2e2; color: #ef4444; border: 1px solid #fecaca; }
    .trend-badge.neutral { background: var(--hover-bg); color: var(--text-muted); border: 1px solid var(--border-color); }
    .card-stats { display: flex; gap: 16px; }
    .stat-item { text-align: center; padding: 4px 12px; background: var(--hover-bg); border-radius: 12px; border: 1px solid var(--border-color); }
    .stat-value { font-size: 18px; font-weight: 700; color: var(--text-main); }
    .stat-label { font-size: 9px; color: var(--text-muted); text-transform: uppercase; }

    /* Tables */
    .data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .data-table th { background: var(--table-hdr); padding: 8px 4px; text-align: center; font-weight: 600; color: var(--text-muted); font-size: 10px; text-transform: uppercase; border-bottom: 2px solid var(--brand-color); }
    .data-table th.region-col { text-align: left; padding-left: 12px; }
    .data-table td { padding: 6px 4px; text-align: center; border-bottom: 1px solid var(--border-color); color: var(--text-main); }
    .data-table td.region-col { text-align: left; padding-left: 12px; font-weight: 500; background: var(--hover-bg); }
    .data-table tr.total-row td { background: rgba(79,70,229,0.1); font-weight: 600; color: var(--brand-color); border-top: 2px solid var(--brand-color); }

    /* Day Data Grid */
    .day-data { display: flex; justify-content: center; gap: 2px; font-size: 10px; border: 1px solid var(--border-color); border-radius: 6px; overflow: hidden; background: var(--bg-body); margin: 2px 0; }
    .day-data span, .day-data a { flex: 1; min-width: 28px; padding: 3px 1px; text-align: center; font-weight: 500; border-right: 1px solid var(--border-color); color: inherit; text-decoration: none; }
    .day-data span:last-child, .day-data a:last-child { border-right: none; }
    .day-data span:nth-child(1), .day-data a:nth-child(1) { color: #3b82f6; background: rgba(59,130,246,0.1); }
    .day-data span:nth-child(2), .day-data a:nth-child(2) { color: #10b981; background: rgba(16,185,129,0.1); }
    .day-data span:nth-child(3), .day-data a:nth-child(3) { color: #f59e0b; background: rgba(245,158,11,0.1); }
    .day-data span:nth-child(4), .day-data a:nth-child(4) { color: #8b5cf6; background: rgba(139,92,246,0.1); }
    .day-data span:nth-child(5), .day-data a:nth-child(5) { color: #ec4899; background: rgba(236,72,153,0.1); }
    .day-data-empty { color: var(--text-muted); font-size: 10px; padding: 4px; background: var(--cell-empty); border-radius: 4px; }
    .orders-link:hover, .boxes-link:hover, .weight-link:hover { color: var(--brand-color); border-bottom: 1px dashed var(--brand-color); }

    /* Sub-header */
    .sub-header { display: flex; justify-content: center; gap: 4px; font-size: 8px; color: var(--text-muted); }
    .sub-header span { min-width: 28px; text-align: center; padding: 2px 0; }

    /* Stats Cards */
    .stats-row, .stats-row-5 { display: grid; gap: 12px; margin-bottom: 20px; }
    .stats-row { grid-template-columns: repeat(4, 1fr); }
    .stats-row-5 { grid-template-columns: repeat(5, 1fr); }
    .stat-card { background: var(--bg-card); border-radius: 16px; border: 1px solid var(--border-color); padding: 12px; display: flex; align-items: center; gap: 12px; }
    .stat-icon { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; background: var(--hover-bg); border: 1px solid var(--border-color); }
    .stat-content { flex: 1; }
    .stat-card .stat-value { font-size: 20px; font-weight: 700; color: var(--text-main); margin-bottom: 2px; }
    .stat-card .stat-label { font-size: 12px; color: var(--text-muted); }

    /* Charts */
    .charts-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 20px; }
    .chart-card { background: var(--bg-card); border-radius: 18px; border: 1px solid var(--border-color); padding: 16px; }
    .chart-card.full-width { grid-column: span 2; }
    .chart-title { font-size: 15px; font-weight: 600; color: var(--text-main); margin-bottom: 14px; display: flex; align-items: center; gap: 6px; }

    /* Leaderboard */
    .leaderboard-table { width: 100%; border-collapse: collapse; }
    .leaderboard-table th { background: var(--table-hdr); padding: 10px; text-align: left; font-weight: 600; color: var(--text-muted); font-size: 11px; border-bottom: 2px solid var(--brand-color); }
    .leaderboard-table td { padding: 10px; border-bottom: 1px solid var(--border-color); }
    .rank-badge { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; }
    .rank-1 { background: #fbbf24; color: #1e293b; }
    .rank-2 { background: #94a3b8; color: #ffffff; }
    .rank-3 { background: #f9a8d4; color: #1e293b; }
    .provider-cell { display: flex; align-items: center; gap: 10px; }
    .provider-color { width: 4px; height: 28px; border-radius: 2px; }

    /* KPI Cards */
    .kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }
    .kpi-card { background: var(--bg-card); border-radius: 18px; border: 1px solid var(--border-color); padding: 16px; text-align: center; }
    .kpi-icon { font-size: 28px; margin-bottom: 8px; }
    .kpi-value { font-size: 24px; font-weight: 700; color: var(--text-main); }
    .kpi-label { font-size: 12px; color: var(--text-muted); }
    .kpi-trend { font-size: 11px; margin-top: 8px; padding: 4px 10px; border-radius: 30px; display: inline-block; font-weight: 600; }
    .kpi-trend.up { background: #e6f7e6; color: #10b981; border: 1px solid #a7f3d0; }
    .kpi-trend.down { background: #fee2e2; color: #ef4444; border: 1px solid #fecaca; }

    /* Winner Card */
    .winner-card { background: #fef9e7; border: 2px solid #fbbf24; }

    /* Comparison Tabs */
    .tabs { display: flex; gap: 6px; margin-bottom: 20px; flex-wrap: wrap; }
    .tab-btn { padding: 5px 14px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 40px; color: var(--text-muted); font-size: 12px; font-weight: 600; cursor: pointer; }
    .tab-btn:hover { background: var(--border-color); }
    .tab-btn.active { background: var(--brand-color); border-color: var(--brand-color); color: #fff; }

    /* Comparison Cards */
    .comparison-grid { display: grid; grid-template-columns: 1fr auto 1fr; gap: 20px; align-items: start; }
    .comparison-card { background: var(--bg-card); border-radius: 18px; border: 1px solid var(--border-color); padding: 18px; }
    .comparison-vs { display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 700; color: var(--brand-color); padding: 16px; }
    .comparison-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); }
    .comparison-color { width: 5px; height: 32px; border-radius: 3px; }
    .comparison-name { font-size: 18px; font-weight: 600; color: var(--text-main); }
    .comparison-stat { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-color); }
    .comparison-stat-label { color: var(--text-muted); font-size: 12px; }
    .comparison-stat-value { color: var(--text-main); font-size: 14px; font-weight: 600; }
    .winner-indicator { color: #10b981; font-size: 11px; margin-left: 4px; }

    /* Heatmap */
    .heatmap-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-top: 16px; }
    .heatmap-item { background: var(--bg-card); border-radius: 16px; padding: 14px; text-align: center; border: 1px solid var(--border-color); }
    .heatmap-region { font-size: 14px; font-weight: 600; color: var(--text-main); }
    .heatmap-value { font-size: 20px; font-weight: 700; color: var(--brand-color); }

    /* Achievements */
    .achievements-row { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 8px; }
    .achievement-badge { display: flex; align-items: center; gap: 4px; padding: 3px 8px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 30px; font-size: 10px; color: var(--text-muted); }

    /* WhatsApp Report */
    .whatsapp-box { background: var(--bg-card); border: 2px solid #10b981; border-radius: 20px; padding: 20px; }
    .whatsapp-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); }
    .whatsapp-icon { font-size: 24px; }
    .whatsapp-title { font-size: 16px; font-weight: 700; color: #10b981; }
    .whatsapp-content { font-family: 'Courier New', monospace; background: var(--hover-bg); padding: 14px; border-radius: 12px; color: var(--text-main); border: 1px solid var(--border-color); }
    .copy-btn { background: #10b981; color: #ffffff; padding: 10px; border: none; border-radius: 40px; font-weight: 600; font-size: 12px; cursor: pointer; margin-top: 14px; width: 100%; }

    /* Login Page */
    .login-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--bg-body);
        padding: 20px;
    }
    .login-card {
        background: var(--bg-card);
        border-radius: 16px;
        border: 1px solid var(--border-color);
        padding: 40px 30px;
        width: 100%;
        max-width: 360px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    }
    .login-logo {
        width: 60px;
        height: 60px;
        background: var(--brand-gradient);
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 20px;
        color: white;
        font-size: 26px;
        font-weight: 700;
    }
    .login-title {
        font-size: 20px;
        font-weight: 600;
        color: var(--text-main);
        margin-bottom: 6px;
    }
    .login-subtitle {
        font-size: 13px;
        color: var(--text-muted);
        margin-bottom: 24px;
    }
    .login-form {
        display: flex;
        flex-direction: column;
        gap: 14px;
    }
    .form-group {
        text-align: left;
    }
    .form-label {
        display: block;
        font-size: 11px;
        font-weight: 600;
        color: var(--text-muted);
        margin-bottom: 4px;
    }
    .form-input {
        width: 100%;
        padding: 10px 12px;
        background: var(--bg-body);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        color: var(--text-main);
        font-size: 13px;
        transition: 0.2s;
    }
    .form-input:focus {
        outline: none;
        border-color: var(--brand-color);
        box-shadow: 0 0 0 3px rgba(79,70,229,0.1);
    }
    .login-btn {
        width: 100%;
        padding: 10px;
        background: var(--brand-color);
        border: none;
        border-radius: 10px;
        color: white;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: 0.2s;
    }
    .login-btn:hover {
        background: #6366f1;
    }
    .divider {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 12px 0;
        color: var(--text-muted);
        font-size: 11px;
    }
    .divider-line {
        flex: 1;
        height: 1px;
        background: var(--border-color);
    }
    .guest-btn {
        background: var(--bg-body);
        border: 1px solid var(--border-color);
        color: var(--text-main);
    }
    .guest-btn:hover {
        background: var(--hover-bg);
        border-color: var(--brand-color);
        color: var(--brand-color);
    }
    .error-message {
        background: #fee2e2;
        border: 1px solid #fecaca;
        border-radius: 8px;
        padding: 8px;
        color: #dc2626;
        font-size: 11px;
        margin-bottom: 12px;
    }

    /* Loading */
    .loading { display: flex; justify-content: center; align-items: center; height: 200px; color: var(--brand-color); }
    .spinner { width: 36px; height: 36px; border: 3px solid rgba(79,70,229,0.1); border-top-color: var(--brand-color); border-radius: 50%; animation: spin 1s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Forecast Page */
    .forecast-card { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); padding: 20px; margin-bottom: 20px; }
    .forecast-title { font-size: 18px; font-weight: 700; color: var(--text-main); margin-bottom: 14px; }
    .forecast-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-top: 14px; }
    .forecast-day { background: var(--hover-bg); border-radius: 12px; padding: 14px; text-align: center; }
    .forecast-day .day-name { font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
    .forecast-day .prediction { font-size: 16px; font-weight: 600; color: var(--brand-color); }
    .forecast-detail { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

    /* Logs Page */
    .logs-container { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); padding: 20px; }
    .log-entry { padding: 6px 10px; border-bottom: 1px solid var(--border-color); font-family: monospace; font-size: 11px; }
    .log-entry:last-child { border-bottom: none; }

    /* World Map Page */
    .map-container {
        height: 600px;
        width: 100%;
        background: var(--bg-card);
        border-radius: 20px;
        border: 1px solid var(--border-color);
        overflow: hidden;
        margin-top: 20px;
    }
    .map-legend {
        display: flex;
        gap: 20px;
        margin-top: 10px;
        justify-content: center;
        flex-wrap: wrap;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 12px;
    }
    .legend-color {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        opacity: 0.7;
    }

    /* Responsive */
    @media (max-width: 1200px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .stats-row-5 { grid-template-columns: repeat(3, 1fr); } .kpi-grid { grid-template-columns: repeat(2, 1fr); } .comparison-grid { grid-template-columns: 1fr; } .comparison-vs { display: none; } }
    @media (max-width: 768px) { .sidebar { width: 60px; } .main-content { margin-left: 60px; } .sidebar-toggle { width: 22px; height: 22px; right: -10px; } .stats-row, .stats-row-5, .kpi-grid { grid-template-columns: 1fr; } }

</style>
"""

# ========== SHARED JAVASCRIPT (UPDATED) ==========
SHARED_JS = """
<script>
// ===== DATE UTILITIES =====
function getISOWeek(date) { const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())); const dayNum = d.getUTCDay() || 7; d.setUTCDate(d.getUTCDate() + 4 - dayNum); const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1)); return Math.ceil((((d - yearStart) / 86400000) + 1) / 7); }
function formatWeight(w) { if (w === undefined || w === null || w === 0) return '-'; const r = Math.round(w * 10) / 10; return r % 1 === 0 ? Math.round(r).toString() : r.toFixed(1); }
function fmtLocal(date) { const y = date.getFullYear(); const m = String(date.getMonth() + 1).padStart(2, '0'); const d = String(date.getDate()).padStart(2, '0'); return `${y}-${m}-${d}`; }
function fmtDisp(date, includeYear) { if (includeYear === false) return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
function getMonday(date) { const d = new Date(date); const day = d.getDay(); const diff = d.getDate() - day + (day === 0 ? -6 : 1); return new Date(d.setDate(diff)); }

// ===== DATE RANGE PICKER =====
let dpStart = null; let dpEnd = null;
function dpInit(defaultPeriod) {
    defaultPeriod = defaultPeriod || 'week';
    const today = new Date(); today.setHours(0,0,0,0);
    if (defaultPeriod === 'today') { dpStart = new Date(today); dpEnd = new Date(today); } 
    else if (defaultPeriod === '7d') { dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 6); } 
    else if (defaultPeriod === '15d') { dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 14); } 
    else if (defaultPeriod === '30d') { dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 29); } 
    else if (defaultPeriod === 'week') { dpStart = getMonday(today); dpEnd = new Date(dpStart); dpEnd.setDate(dpEnd.getDate() + 6); } 
    else if (defaultPeriod === 'month') { dpStart = new Date(today.getFullYear(), today.getMonth(), 1); dpEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0); }
    document.getElementById('dpStart').value = fmtLocal(dpStart); document.getElementById('dpEnd').value = fmtLocal(dpEnd);
    document.querySelectorAll('.qbtn').forEach(b => { b.classList.toggle('active', b.dataset.period === defaultPeriod); });
    dpUpdateBadge();
}
function dpSetQuick(btn, period) {
    const today = new Date(); today.setHours(0,0,0,0);
    document.querySelectorAll('.qbtn').forEach(b => b.classList.remove('active')); btn.classList.add('active');
    switch(period) {
        case 'today': dpStart = new Date(today); dpEnd = new Date(today); break;
        case '7d': dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 6); break;
        case '15d': dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 14); break;
        case '30d': dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 29); break;
        case 'week': dpStart = getMonday(today); dpEnd = new Date(dpStart); dpEnd.setDate(dpEnd.getDate() + 6); break;
        case 'month': dpStart = new Date(today.getFullYear(), today.getMonth(), 1); dpEnd = new Date(today.getFullYear(), today.getMonth()+1, 0); break;
    }
    document.getElementById('dpStart').value = fmtLocal(dpStart); document.getElementById('dpEnd').value = fmtLocal(dpEnd);
    dpUpdateBadge(); loadData();
}
function dpApply() {
    const sv = document.getElementById('dpStart').value; const ev = document.getElementById('dpEnd').value;
    if (!sv || !ev) { alert('Please select both dates'); return; }
    dpStart = new Date(sv + 'T00:00:00'); dpEnd = new Date(ev + 'T00:00:00');
    if (dpStart > dpEnd) { alert('Start date must be before end date'); return; }
    document.querySelectorAll('.qbtn').forEach(b => b.classList.remove('active'));
    dpUpdateBadge(); loadData();
}
function dpUpdateBadge() {
    const badge = document.getElementById('dpBadge'); if (!badge || !dpStart || !dpEnd) return;
    const wk = getISOWeek(dpStart); const days = Math.round((dpEnd - dpStart) / 86400000) + 1;
    let txt = 'Week ' + wk + ' • ';
    if (days === 1) { txt += fmtDisp(dpStart, true); } 
    else if (days <= 31 && dpStart.getFullYear() === dpEnd.getFullYear()) { txt += fmtDisp(dpStart, false) + ' – ' + fmtDisp(dpEnd, true); if (days !== 7) txt += ' (' + days + 'd)'; } 
    else { txt += fmtDisp(dpStart, true) + ' – ' + fmtDisp(dpEnd, true); }
    badge.textContent = txt;
}
function dpParams() { return 'start_date=' + fmtLocal(dpStart) + '&end_date=' + fmtLocal(dpEnd); }
function getStarRating(stars) { return '★'.repeat(stars) + '☆'.repeat(5 - stars); }

// ===== LAST UPDATE TIME =====
function updateLastUpdateTime() {
    const now = new Date();
    const timeStr = now.toLocaleString();
    const element = document.getElementById('last-update-time');
    if (element) element.textContent = timeStr;
}

// ===== SKELETON SCREENS =====
function renderDashboardSkeleton() {
    let html = '';
    for (let i = 0; i < 6; i++) {
        html += `<div class="provider-card" style="padding: 20px;">
            <div class="skeleton" style="width: 60%; height: 30px;"></div>
            <div class="skeleton" style="width: 40%;"></div>
            <div class="skeleton" style="width: 100%; height: 200px;"></div>
        </div>`;
    }
    return html;
}

function renderDailyRegionSkeleton() {
    let html = '';
    for (let i = 0; i < 3; i++) {
        html += `<div class="provider-section" style="padding: 20px;">
            <div class="skeleton" style="width: 50%; height: 40px;"></div>
            <div class="skeleton" style="width: 100%; height: 150px;"></div>
        </div>`;
    }
    return html;
}

function renderComparisonSkeleton() {
    return `<div class="comparison-grid">
        <div class="comparison-card"><div class="skeleton" style="height: 200px;"></div></div>
        <div class="comparison-vs">VS</div>
        <div class="comparison-card"><div class="skeleton" style="height: 200px;"></div></div>
    </div>`;
}

// ===== EXPORT FUNCTIONS =====
function exportTableToCSV(table, filename) {
    let csv = [];
    let rows = table.querySelectorAll("tr");
    for (let i = 0; i < rows.length; i++) {
        let row = [], cols = rows[i].querySelectorAll("td, th");
        for (let j = 0; j < cols.length; j++) {
            let data = cols[j].innerText.replace(/(\\r\\n|\\n|\\r)/gm, "").replace(/"/g, '""');
            row.push('"' + data + '"');
        }
        csv.push(row.join(","));
    }
    let csvFile = new Blob([csv.join("\\n")], {type: "text/csv"});
    let dl = document.createElement("a");
    dl.download = filename; dl.href = window.URL.createObjectURL(csvFile);
    dl.style.display = "none"; document.body.appendChild(dl); dl.click();
}

function exportProviderTable(btn, providerName) {
    const card = btn.closest('.provider-card, .provider-section');
    const table = card.querySelector('table');
    const dateRange = document.getElementById('dpBadge').innerText;
    exportTableToCSV(table, `${providerName}_${dateRange}.csv`);
}

function exportComparisonTable() {
    const table = document.querySelector('.all-providers-table');
    if (table) {
        exportTableToCSV(table, `All_Providers_${fmtLocal(dpStart)}_to_${fmtLocal(dpEnd)}.csv`);
    } else {
        alert('No table to export');
    }
}

// ===== THEME TOGGLE =====
function toggleTheme() {
    const isDark = document.body.getAttribute('data-theme') === 'dark';
    document.body.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
    updateThemeButton();
    if(typeof applyChartTheme==='function') applyChartTheme();
    if(typeof loadData==='function') setTimeout(loadData, 50);
}
function updateThemeButton() {
    const btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;
    const isDark = document.body.getAttribute('data-theme') === 'dark';
    btn.innerHTML = isDark ? '☀️ Light' : '🌙 Dark';
}
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
    updateThemeButton();
});

// ===== SIDEBAR TOGGLE =====
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    sidebar.classList.toggle('collapsed');
    mainContent.classList.toggle('expanded');
    localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
}
document.addEventListener('DOMContentLoaded', function() {
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        document.getElementById('sidebar').classList.add('collapsed');
        document.getElementById('main-content').classList.add('expanded');
    }
});

// ===== GLOBAL SEARCH =====
function searchOrder(q) {
    const role = '{{ role }}';
    if (role !== 'admin') return;
    const resBox = document.getElementById('search-results');
    if(!q) { resBox.style.display = 'none'; return; }
    resBox.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted)">Searching...</div>';
    resBox.style.display = 'block';
    fetch('/api/search?q=' + encodeURIComponent(q))
        .then(res => res.json())
        .then(data => {
            if(data.length === 0) {
                resBox.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted)">No orders found</div>';
                return;
            }
            let html = '';
            data.forEach(item => {
                html += `<div class="search-item">
                    <div class="search-item-title"><span>#${item.order_id}</span> <span style="color:${item.color}">${item.provider}</span></div>
                    <div class="search-item-meta"><span>📅 ${item.date}</span><span>📍 ${item.region}</span><span>⚖️ ${item.weight}kg</span></div>
                </div>`;
            });
            resBox.innerHTML = html;
        })
        .catch(() => { resBox.innerHTML = '<div style="padding:15px;text-align:center;color:red">Error searching</div>'; });
}
document.addEventListener('click', e => {
    if(!e.target.closest('.search-box')) {
        const b = document.getElementById('search-results');
        if(b) b.style.display = 'none';
    }
});
document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === '/') {
        e.preventDefault();
        const input = document.getElementById('global-search');
        if (input) input.focus();
    }
});

// ===== NOTIFICATIONS =====
function checkNotifications() {
    const role = '{{ role }}';
    if (role !== 'admin') return;
    fetch('/api/notifications')
        .then(res => res.json())
        .then(data => {
            if (data.message && Notification.permission === 'granted') {
                new Notification('3PL Alert', { body: data.message });
            }
        });
}
if (Notification && Notification.permission === 'default') {
    Notification.requestPermission();
}
setInterval(checkNotifications, 30000);
</script>

"""

# Orders modal injected separately into each page via ORDERS_MODAL_HTML
ORDERS_MODAL_HTML = """
<div id="ordersModal" style="display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.55);backdrop-filter:blur(4px);align-items:center;justify-content:center;">
  <div id="ordersModalBox" style="background:var(--bg-card,#fff);border-radius:16px;width:92%;max-width:900px;max-height:85vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,0.35);overflow:hidden;animation:modalIn .2s ease;">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid var(--border-color,#e2e8f0);flex-shrink:0;">
      <div>
        <div id="ordersModalTitle" style="font-size:16px;font-weight:700;color:var(--text-primary,#1e293b);">Orders</div>
        <div id="ordersModalStats" style="display:flex;gap:16px;font-size:13px;color:var(--text-secondary,#64748b);margin-top:4px;"></div>
      </div>
      <button onclick="closeOrdersModal()" style="width:32px;height:32px;border-radius:50%;border:1px solid var(--border-color,#e2e8f0);background:none;cursor:pointer;font-size:20px;color:#64748b;line-height:1;">×</button>
    </div>
    <div id="ordersModalBody" style="overflow-y:auto;flex:1;padding:0;"></div>
    <div style="padding:12px 22px;border-top:1px solid var(--border-color,#e2e8f0);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
      <button onclick="exportOrdersCSV()" style="padding:7px 14px;border-radius:8px;border:1px solid var(--border-color,#e2e8f0);background:none;cursor:pointer;font-size:12px;color:#64748b;">📥 Export CSV</button>
      <span id="ordersModalCount" style="font-size:12px;color:#64748b;"></span>
    </div>
  </div>
</div>
<style>@keyframes modalIn{from{transform:scale(.95);opacity:0}to{transform:scale(1);opacity:1}}
#ordersModalTable{width:100%;border-collapse:collapse;font-size:13px;}
#ordersModalTable th{background:var(--bg-secondary,#f8fafc);color:#64748b;padding:10px 16px;text-align:left;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0;}
#ordersModalTable td{padding:9px 16px;border-bottom:1px solid var(--border-color,#e2e8f0);}
#ordersModalTable tr:hover td{background:var(--bg-hover,#f8fafc);}
body[data-theme="dark"] #ordersModalTable tr:hover td{background:#1e2a3a !important;color:#e2e8f0 !important;}
</style>
<script>
(function(){
var _od=[];
window._ordersData=_od;
window.openOrdersModal=function(url){
  var m=document.getElementById('ordersModal');
  if(!m)return;
  m.style.display='flex';
  document.body.style.overflow='hidden';
  document.getElementById('ordersModalBody').innerHTML='<div style="text-align:center;padding:60px;color:#64748b;">⏳ Loading orders...</div>';
  document.getElementById('ordersModalStats').innerHTML='';
  document.getElementById('ordersModalCount').textContent='';
  _od.length=0;
  var params=new URL(url,location.origin).searchParams;
  fetch('/api/orders?'+params.toString()).then(function(r){return r.json();}).then(function(data){
    _od.push.apply(_od,data.orders||[]);
    var title=(data.provider||'Orders')+(data.region?' — '+data.region:'')+(data.date_range?' · '+data.date_range:'');
    document.getElementById('ordersModalTitle').textContent=title;
    document.getElementById('ordersModalStats').innerHTML='<span>Orders: <b style="color:var(--brand-color,#4f46e5)">'+(data.total_orders||0)+'</b></span> <span>Boxes: <b style="color:var(--brand-color,#4f46e5)">'+(data.total_boxes||0)+'</b></span> <span>Weight: <b style="color:var(--brand-color,#4f46e5)">'+(data.total_weight||0)+' kg</b></span>';
    document.getElementById('ordersModalCount').textContent=_od.length+' rows';
    if(!_od.length){document.getElementById('ordersModalBody').innerHTML='<div style="text-align:center;padding:60px;color:#64748b">No orders found</div>';return;}
    var h='<table id="ordersModalTable"><thead><tr><th>#</th><th>Order ID</th><th>Date</th><th>Region</th><th>Country</th><th>Boxes</th><th>Weight (kg)</th></tr></thead><tbody>';
    for(var i=0;i<_od.length;i++){var o=_od[i];h+='<tr><td style="color:#94a3b8">'+(i+1)+'</td><td style="font-weight:600;font-family:monospace">'+o.order_id+'</td><td>'+o.date+'</td><td>'+(o.region||'-')+'</td><td>'+(o.country||'-')+'</td><td>'+o.boxes+'</td><td>'+o.weight+'</td></tr>';}
    h+='</tbody></table>';
    document.getElementById('ordersModalBody').innerHTML=h;
  }).catch(function(){document.getElementById('ordersModalBody').innerHTML='<div style="text-align:center;padding:60px;color:#ef4444">Failed to load orders</div>';});
};
window.closeOrdersModal=function(){
  var m=document.getElementById('ordersModal');
  if(m)m.style.display='none';
  document.body.style.overflow='';
};
window.exportOrdersCSV=function(){
  if(!_od.length)return;
  var rows=[['#','Order ID','Date','Region','Country','Boxes','Weight']];
  for(var i=0;i<_od.length;i++){var o=_od[i];rows.push([i+1,o.order_id,o.date,o.region||'',o.country||'',o.boxes,o.weight]);}
  var csv=rows.map(function(r){return r.map(function(c){return '"'+String(c).replace(/"/g,'""')+'"';}).join(',');}).join('\\n');
  var a=document.createElement('a');a.href='data:text/csv;charset=utf-8,\\uFEFF'+encodeURIComponent(csv);a.download='orders.csv';a.click();
};
// Backdrop click
document.getElementById('ordersModal').onclick=function(e){if(e.target===this)closeOrdersModal();};
// Escape key
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeOrdersModal();});
// Intercept all order links — use onclick on each link for reliability
function _attachOrderLinks(){
  document.querySelectorAll('a.orders-link,a.boxes-link,a.weight-link,a.under20-link,a.over20-link').forEach(function(a){
    if(a.dataset.omAttached)return;
    a.dataset.omAttached='1';
    a.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();openOrdersModal(a.href);});
  });
}
// Run on DOM changes (covers dynamically generated links)
if(window.MutationObserver){
  new MutationObserver(function(){_attachOrderLinks();}).observe(document.body,{childList:true,subtree:true});
}
// Also run immediately and after load
_attachOrderLinks();
window.addEventListener('load',_attachOrderLinks);
})();
</script>
"""

def DATE_PICKER_HTML(default_period='week'):
    return f"""
<div class="date-range-picker">
    <div class="qbtns-row">
        <button class="qbtn" data-period="today" onclick="dpSetQuick(this,'today')">Today</button>
        <button class="qbtn" data-period="7d" onclick="dpSetQuick(this,'7d')">7 Days</button>
        <button class="qbtn" data-period="15d" onclick="dpSetQuick(this,'15d')">15 Days</button>
        <button class="qbtn" data-period="30d" onclick="dpSetQuick(this,'30d')">30 Days</button>
        <button class="qbtn" data-period="week" onclick="dpSetQuick(this,'week')">This Week</button>
        <button class="qbtn" data-period="month" onclick="dpSetQuick(this,'month')">This Month</button>
    </div>
    <div class="date-inputs-row">
        <input type="date" id="dpStart" class="range-input" onchange="dpUpdateBadge()">
        <span class="range-sep">→</span>
        <input type="date" id="dpEnd" class="range-input" onchange="dpUpdateBadge()">
        <button class="apply-btn" onclick="dpApply()">Apply</button>
        <span class="week-badge" id="dpBadge">Loading...</span>
    </div>
</div>
"""

def ACTION_BAR_HTML(role):
    if role == 'admin':
        return """
    <div class="top-actions">
        <div class="search-box">
            <span class="search-icon">🔍</span>
            <input type="text" id="global-search" class="search-input" placeholder="Search Order ID..." onkeyup="if(this.value.length>2) searchOrder(this.value)">
            <span class="shortcut-hint">Ctrl+/</span>
            <div id="search-results"></div>
        </div>
        <div class="action-group">
            <button class="action-btn" id="theme-toggle-btn" onclick="toggleTheme()">🌙 Dark</button>
        </div>
    </div>
    """
    else:
        return """
    <div class="top-actions">
        <button class="action-btn" id="theme-toggle-btn" onclick="toggleTheme()">🌙 Dark</button>
    </div>
    """

SIDEBAR_HTML = """
<nav class="sidebar" id="sidebar">
    <div class="sidebar-header">
        <div class="logo-icon">3PL</div>
        <div class="header-titles">
            <div class="header-main">3PL Dashboard</div>
            <div class="header-sub">
                <span class="admin-name">{user_name}</span> <span class="admin-role">{user_role}</span>
            </div>
        </div>
        <div class="sidebar-toggle" onclick="toggleSidebar()">«</div>
    </div>
    <div class="nav-menu">
        <div class="nav-section">
            <div class="nav-section-title">MAIN</div>
            <a href="/" class="nav-item {active_dashboard}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
                <span>Dashboard</span>
            </a>
            <a href="/weekly-summary" class="nav-item {active_weekly}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                <span>Weekly Summary</span>
            </a>
            <a href="/daily-region" class="nav-item {active_daily_region}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                <span>Daily Region</span>
            </a>
            <a href="/flight-load" class="nav-item {active_flight}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
                <span>Flight Load</span>
            </a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">ANALYTICS</div>
            <a href="/analytics" class="nav-item {active_analytics}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" /></svg>
                <span>Analytics</span>
            </a>
            <a href="/kpi" class="nav-item {active_kpi}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
                <span>KPI Dashboard</span>
            </a>
            <a href="/comparison" class="nav-item {active_comparison}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                <span>Comparison</span>
            </a>
            <a href="/regions" class="nav-item {active_regions}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>Region Heatmap</span>
            </a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">REPORTS</div>
            <a href="/monthly" class="nav-item {active_monthly}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <span>Monthly Report</span>
            </a>
            <a href="/whatsapp" class="nav-item {active_whatsapp}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                <span>WhatsApp Report</span>
            </a>
            <a href="/achievements" class="nav-item {active_achievements}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
                <span>Achievements</span>
            </a>
        </div>
        {tid_link}
    </div>
    <div class="sidebar-footer">
        <div class="admin-info">
            <div class="admin-avatar">{user_initials}</div>
            <div style="display:flex;flex-direction:column;overflow:hidden;flex:1;min-width:0;">
                <span style="font-size:12px;font-weight:600;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user_name}</span>
                <span style="font-size:10px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user_email}</span>
            </div>
        </div>
        <button class="refresh-btn" id="sidebarRefreshBtn" onclick="sidebarForceRefresh()">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            <span>Refresh</span>
        </button>
        <a href="/logout" class="logout-btn">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            <span>Logout</span>
        </a>
        <div class="last-update">
            Last update: <span id="last-update-time">Never</span>
        </div>
    </div>
</nav>
"""

SIDEBAR_SCRIPT = """
<script>
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    sidebar.classList.toggle('collapsed');
    mainContent.classList.toggle('expanded');
    localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
}
document.addEventListener('DOMContentLoaded', function() {
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        document.getElementById('sidebar').classList.add('collapsed');
        document.getElementById('main-content').classList.add('expanded');
    }
});
function sidebarForceRefresh() {
    const btn = document.getElementById('sidebarRefreshBtn');
    if (!btn) return;
    btn.classList.add('spinning');
    btn.disabled = true;
    fetch('/api/clear-cache')
        .then(r => r.json())
        .then(() => {
            setTimeout(() => { location.reload(); }, 300);
        })
        .catch(() => {
            btn.classList.remove('spinning');
            btn.disabled = false;
            alert('Refresh failed. Try again.');
        });
}
</script>
"""

def sidebar(active, role='guest'):
    keys = ['dashboard','weekly','daily_region','flight','analytics','kpi','comparison','regions','monthly','whatsapp','achievements','worldmap','orderlookup']
    kwargs = {f'active_{k}': ('active' if k == active else '') for k in keys}
    # Get real user info from session
    email = (session.get('email') or '').strip().lower()
    name_part = email.split('@')[0] if email else ('Admin' if role == 'admin' else 'Guest')
    display_name = name_part.replace('.', ' ').replace('_', ' ').title()
    initials = ''.join([w[0].upper() for w in display_name.split()[:2]]) if display_name else ('A' if role=='admin' else 'G')
    kwargs['user_name'] = display_name
    kwargs['user_email'] = email or ''
    kwargs['user_initials'] = initials
    if role == 'admin':
        kwargs['user_role'] = 'Admin'
    else:
        kwargs['user_role'] = 'Guest'
    if email == ORDER_LOOKUP_EMAIL:
        kwargs['tid_link'] = """
        <div class="nav-section">
            <div class="nav-section-title">TOOLS</div>
            <a href="/order-lookup" class="nav-item {active_orderlookup}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                <span>Order Lookup</span>
            </a>
        </div>
        """.format(**kwargs)
    else:
        kwargs['tid_link'] = ''
        
    return SIDEBAR_HTML.format(**kwargs)

# ===== LOGIN =====
# ==============================================================================
# ✅ NEW EMAIL LOGIN SYSTEM
# Yahan naye users add karein — format: "email@domain.com": "password"
# ==============================================================================

USERS = {
    "husaain@joinfleek.com":      "hussain123",
    "wahab.chippa@joinfleek.com": "Rocket#2024",
    "albash@joinfleek.com":       "Albash123",
    "waris@joinfleek.com":        "waris123",
    "moiz@joinfleek.com":         "moiz1234",
    "usman@joinfleek.com":         "usman1234",
}

# Guest login ke liye ek simple password (optional, agar seedha guest button chahiye)
GUEST_PASSWORD = ""  # empty = no password needed, sirf "Guest" button click

# ==============================================================================
# LOGIN ROUTE — Is poori route ko replace karein
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        action = request.form.get('action')

        next_url = request.args.get('next') or url_for('dashboard')

        # ===== GUEST LOGIN =====
        if action == 'guest':
            session['logged_in'] = True
            session['role']      = 'guest'
            session.pop('email', None)
            return redirect(url_for('dashboard'))

        # ===== EMAIL + PASSWORD LOGIN =====
        email    = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()

        if email in USERS and USERS[email] == password:
            session['logged_in'] = True
            session['role']      = 'admin'
            session['email']     = email
            return redirect(next_url)
        else:
            error = 'Invalid email or password. Please try again.'

    return render_template_string(LOGIN_HTML, error=error, favicon=FAVICON)


# ==============================================================================
# LOGIN HTML TEMPLATE
# ==============================================================================

LOGIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login — 3PL Dashboard</title>
{{ favicon|safe }}
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', sans-serif;
    background: #0a0a14;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  /* ---- animated background ---- */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0;
    background:
      radial-gradient(ellipse 60% 50% at 20% 30%, rgba(79,70,229,0.15) 0%, transparent 70%),
      radial-gradient(ellipse 50% 40% at 80% 70%, rgba(16,185,129,0.1) 0%, transparent 70%);
    pointer-events: none;
  }

  .card {
    position: relative; z-index: 1;
    background: rgba(15,15,30,0.95);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 44px 40px;
    width: 100%; max-width: 400px;
    box-shadow: 0 25px 60px rgba(0,0,0,0.6);
    backdrop-filter: blur(20px);
  }

  .logo {
    width: 56px; height: 56px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 800; color: #fff;
    margin: 0 auto 22px;
    box-shadow: 0 8px 20px rgba(79,70,229,0.4);
  }

  h1 {
    text-align: center;
    font-size: 22px; font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 6px;
  }

  .subtitle {
    text-align: center;
    font-size: 13px; color: #64748b;
    margin-bottom: 30px;
  }

  .error {
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.35);
    border-radius: 10px;
    padding: 10px 14px;
    color: #fca5a5;
    font-size: 12px;
    margin-bottom: 18px;
    display: flex; align-items: center; gap: 8px;
  }

  .form { display: flex; flex-direction: column; gap: 14px; }

  .group { display: flex; flex-direction: column; gap: 6px; }

  label {
    font-size: 11px; font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.7px;
  }

  input[type="email"],
  input[type="password"] {
    width: 100%;
    padding: 11px 14px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    color: #f1f5f9;
    font-size: 14px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  input:focus {
    border-color: #4f46e5;
    box-shadow: 0 0 0 3px rgba(79,70,229,0.2);
  }

  .btn-main {
    width: 100%;
    padding: 12px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    border: none; border-radius: 10px;
    color: #fff;
    font-size: 14px; font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.15s;
    box-shadow: 0 4px 15px rgba(79,70,229,0.35);
  }
  .btn-main:hover { opacity: 0.9; transform: translateY(-1px); }

  .divider {
    display: flex; align-items: center; gap: 10px;
    margin: 6px 0;
  }
  .divider-line { flex: 1; height: 1px; background: rgba(255,255,255,0.08); }
  .divider-text { font-size: 11px; color: #475569; }

  .btn-guest {
    width: 100%;
    padding: 11px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    color: #94a3b8;
    font-size: 13px; font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.2s, border-color 0.2s, color 0.2s;
  }
  .btn-guest:hover {
    background: rgba(255,255,255,0.07);
    border-color: rgba(255,255,255,0.2);
    color: #e2e8f0;
  }

  .footer-note {
    text-align: center;
    font-size: 11px; color: #334155;
    margin-top: 22px;
  }

  .eye-btn {
    position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    background: none; border: none; cursor: pointer;
    color: #475569; font-size: 16px; padding: 4px;
    transition: color 0.2s;
  }
  .eye-btn:hover { color: #94a3b8; }
  .pwd-wrap { position: relative; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">3PL</div>
  <h1>Welcome Back</h1>
  <p class="subtitle">3PL Operations Dashboard</p>

  {% if error %}
  <div class="error">⚠️ {{ error }}</div>
  {% endif %}

  <form method="POST" class="form">

    <div class="group">
      <label for="email">Email Address</label>
      <input type="email" id="email" name="email"
             placeholder="you@joinfleek.com"
             autocomplete="email" required autofocus>
    </div>

    <div class="group">
      <label for="password">Password</label>
      <div class="pwd-wrap">
        <input type="password" id="password" name="password"
               placeholder="••••••••"
               autocomplete="current-password" required>
        <button type="button" class="eye-btn" onclick="togglePwd()" id="eyeBtn">👁</button>
      </div>
    </div>

    <button type="submit" name="action" value="login" class="btn-main">
      Sign In
    </button>

  </form>

  <div class="divider">
    <div class="divider-line"></div>
    <span class="divider-text">OR</span>
    <div class="divider-line"></div>
  </div>

  <form method="POST" style="margin:0;padding:0">
    <input type="hidden" name="action" value="guest">
    <button type="submit" class="btn-guest">
      👀 Continue as Guest (View Only)
    </button>
  </form>

  <p class="footer-note">Authorized Fleek Operations Personnel Only</p>
</div>

<script>
function togglePwd(){
  const inp = document.getElementById('password');
  const btn = document.getElementById('eyeBtn');
  if(inp.type === 'password'){ inp.type='text'; btn.textContent='🙈'; }
  else { inp.type='password'; btn.textContent='👁'; }
}
</script>
</body>
</html>
'''


# ==============================================================================
# LOGOUT ROUTE — yeh waise hi rahega, koi change nahi
# ==============================================================================

# @app.route('/logout')
# def logout():
#     session.clear()
#     return redirect(url_for('login'))

# NOTE: Upar wala logout route pehle se existing code mein hai — use rehne do.
# Sirf upper wala USERS dict + login() function + LOGIN_HTML replace karein.

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# NOTE: Upar wala logout route pehle se existing code mein hai — use rehne do.
# Sirf upper wala USERS dict + login() function + LOGIN_HTML replace karein.

# ===== DASHBOARD =====
@app.route('/')
@login_required
def dashboard():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3PL Dashboard</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('dashboard', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Provider <span>Dashboard</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="dashboard-content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
async function loadData() {
    document.getElementById('dashboard-content').innerHTML = renderDashboardSkeleton();
    try {
        const response = await fetch('/api/dashboard?' + dpParams());
        const data = await response.json();
        let html = '';
        for (const provider of data.providers) { html += renderProvider(provider); }
        document.getElementById('dashboard-content').innerHTML = html || '<div class="empty-state"><div class="empty-state-icon">📭</div><h3>No data for selected period</h3></div>';
        updateLastUpdateTime();
    } catch(e) { 
        document.getElementById('dashboard-content').innerHTML = '<p style="color:#ef4444;padding:20px">Error loading data: '+e.message+'</p>';
    }
}

function renderProvider(provider) {
    const role = '{{ role }}';
    const canClick = role === 'admin';
    const trendClass = provider.trend.direction === 'up' ? 'up' : (provider.trend.direction === 'down' ? 'down' : 'neutral');
    const trendIcon = provider.trend.direction === 'up' ? '▲' : (provider.trend.direction === 'down' ? '▼' : '–');
    let achHtml = '';
    if (provider.achievements && provider.achievements.length > 0) {
        achHtml = '<div class="achievements-row">' + provider.achievements.map(a => `<div class="achievement-badge"><span class="badge-icon">${a.icon}</span>${a.name}</div>`).join('') + '</div>';
    }
    const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    const flightDays = [1,3,5];
    const totals = {};
    days.forEach(d => totals[d] = {o:0,b:0,w:0,u:0,v:0});
    const sortedRegions = Object.keys(provider.regions).sort();
    let rowsHtml = '';
    for (const region of sortedRegions) {
        const rd = provider.regions[region].days;
        rowsHtml += '<tr><td class="region-col">' + region + '</td>';
        days.forEach((day, i) => {
            const d = rd[day];
            totals[day].o += d.orders; totals[day].b += d.boxes; totals[day].w += d.weight;
            totals[day].u += d.under20; totals[day].v += d.over20;
            const fc = flightDays.includes(i) ? ' style="background:var(--flight-day-bg)"' : '';
            if (d.orders > 0) {
                const dayIndex = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(day);
                const dayDate = new Date(dpStart);
                dayDate.setDate(dayDate.getDate() + dayIndex);
                const dateStr = fmtLocal(dayDate);

                if (canClick) {
                    rowsHtml += `<td class="day-cell"${fc}>
                        <div class="day-data">
                            <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="orders-link">${d.orders}</a>
                            <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="boxes-link">${d.boxes}</a>
                            <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="weight-link">${formatWeight(d.weight)}</a>
                            <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="under20-link">${d.under20}</a>
                            <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="over20-link">${d.over20}</a>
                        </div>
                    </td>`;
                } else {
                    rowsHtml += `<td class="day-cell"${fc}>
                        <div class="day-data">
                            <span class="orders">${d.orders}</span>
                            <span class="boxes">${d.boxes}</span>
                            <span class="weight">${formatWeight(d.weight)}</span>
                            <span class="under20">${d.under20}</span>
                            <span class="over20">${d.over20}</span>
                        </div>
                    </td>`;
                }
            } else {
                rowsHtml += `<td class="day-cell"${fc}><span class="day-data-empty">-</span></td>`;
            }
        });
        rowsHtml += '</tr>';
    }
    rowsHtml += '<tr class="total-row"><td class="region-col">TOTAL</td>';
    days.forEach((day,i) => {
        const t = totals[day];
        const fc = flightDays.includes(i) ? ' style="background:var(--flight-day-bg)"' : '';
        if (canClick) {
            rowsHtml += `<td class="day-cell"${fc}>
                <div class="day-data">
                    <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link">${t.o}</a>
                    <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link">${t.b}</a>
                    <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link">${formatWeight(t.w)}</a>
                    <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="under20-link">${t.u}</a>
                    <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="over20-link">${t.v}</a>
                </div>
            </td>`;
        } else {
            rowsHtml += `<td class="day-cell"${fc}>
                <div class="day-data">
                    <span class="orders">${t.o}</span>
                    <span class="boxes">${t.b}</span>
                    <span class="weight">${formatWeight(t.w)}</span>
                    <span class="under20">${t.u}</span>
                    <span class="over20">${t.v}</span>
                </div>
            </td>`;
        }
    });
    rowsHtml += '</tr>';
    const subHdr = days.map((_,i) => `<th${flightDays.includes(i)?' style="background:var(--flight-day-bg)"':''}><div class="sub-header"><span>O</span><span>B</span><span>W</span><span>&lt;20</span><span>20+</span></div></th>`).join('');
    const dayHdrs = days.map((d,i) => `<th class="day-col${flightDays.includes(i)?' flight-day':''}">${d}${flightDays.includes(i)?' ✈️':''}</th>`).join('');
    return `<div class="provider-card">
<div class="card-header" style="--pc:${provider.color}">
<style>.provider-card .card-header::before{background:${provider.color}}</style>
<div class="provider-info">
<span class="provider-name">${provider.name}</span>
<span class="star-rating">${getStarRating(provider.stars)}</span>
<span class="trend-badge ${trendClass}">${trendIcon} ${provider.trend.percentage}%</span>
${achHtml}
</div>
<div class="card-stats">
<div class="stat-item"><div class="stat-value">${provider.total_orders.toLocaleString()}</div><div class="stat-label">Orders</div></div>
<div class="stat-item"><div class="stat-value">${provider.total_boxes.toLocaleString()}</div><div class="stat-label">Boxes</div></div>
<div class="stat-item"><div class="stat-value">${formatWeight(provider.total_weight)} kg</div><div class="stat-label">Weight</div></div>
</div>
<button class="download-btn" onclick="exportProviderTable(this, '${provider.short}')">📥 CSV</button>
</div>
<div style="overflow-x:auto"><table class="data-table"><thead>
<tr><th class="region-col" rowspan="2">Region</th>${dayHdrs}</tr>
<tr class="sub-header-row">${subHdr}</tr>
</thead><tbody>${rowsHtml}</tbody></table></div></div>`;
}

dpInit('week');
loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== WEEKLY SUMMARY =====
@app.route('/weekly-summary')
@login_required
def weekly_summary():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Summary - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('weekly', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Weekly <span>Summary</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = renderDashboardSkeleton();
    try {
        const r = await fetch('/api/weekly-summary?' + dpParams());
        const data = await r.json();
        let html = '';
        const role = '{{ role }}';
        const canClick = role === 'admin';
        if (data.winner) {
            let achHtml = '';
            if (data.winner.achievements && data.winner.achievements.length > 0) {
                achHtml = '<div class="achievements-row" style="margin-top:12px">' + data.winner.achievements.map(a=>`<div class="achievement-badge"><span class="badge-icon">${a.icon}</span>${a.name}</div>`).join('') + '</div>';
            }
            html += `<div class="provider-card winner-card"><div class="card-header"><div class="provider-info">
<span style="font-size:32px;margin-right:12px">🏆</span><div>
<div class="provider-name" style="font-size:24px">Week Winner: ${data.winner.name}</div>
<div style="color:#4f46e5;margin-top:4px">${data.winner.total_boxes.toLocaleString()} boxes • ${formatWeight(data.winner.total_weight)} kg</div>
${achHtml}</div></div>
<button class="download-btn" onclick="exportProviderTable(this, 'Winner')">📥 CSV</button>
</div></div>`;
        }
        html += `<div class="provider-card"><div class="card-header"><div class="provider-info"><span class="provider-name">Provider Leaderboard</span></div>
<button class="download-btn" onclick="exportComparisonTable()">📥 CSV</button>
</div>
<table class="leaderboard-table"><thead><tr><th style="width:60px">Rank</th><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th><th style="text-align:right">Trend</th></tr></thead><tbody>`;
        data.providers.forEach((p,i) => {
            const rc = i < 3 ? 'rank-'+(i+1) : 'rank-other';
            const tc = p.trend.direction === 'up' ? 'up' : 'down';
            const ti = p.trend.direction === 'up' ? '▲' : '▼';
            if (canClick) {
                html += `<tr><td><div class="rank-badge ${rc}">${i+1}</div></td>
                    <td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td>
                    <td style="text-align:right;font-weight:600"><a href="/orders?provider=${encodeURIComponent(p.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link">${p.total_orders.toLocaleString()}</a></td>
                    <td style="text-align:right;font-weight:600"><a href="/orders?provider=${encodeURIComponent(p.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link">${p.total_boxes.toLocaleString()}</a></td>
                    <td style="text-align:right;font-weight:600"><a href="/orders?provider=${encodeURIComponent(p.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link">${formatWeight(p.total_weight)}</a></td>
                    <td style="text-align:right"><span class="trend-badge ${tc}">${ti} ${p.trend.percentage}%</span></td></tr>`;
            } else {
                html += `<tr><td><div class="rank-badge ${rc}">${i+1}</div></td>
                    <td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td>
                    <td style="text-align:right;font-weight:600">${p.total_orders.toLocaleString()}</td>
                    <td style="text-align:right;font-weight:600">${p.total_boxes.toLocaleString()}</td>
                    <td style="text-align:right;font-weight:600">${formatWeight(p.total_weight)}</td>
                    <td style="text-align:right"><span class="trend-badge ${tc}">${ti} ${p.trend.percentage}%</span></td></tr>`;
            }
        });
        html += '</tbody></table></div>';
        document.getElementById('content').innerHTML = html;
        updateLastUpdateTime();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== DAILY REGION =====
@app.route('/daily-region')
@login_required
def daily_region():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Region - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('daily_region', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Daily <span>Region Summary</span></h1>
    ''' + DATE_PICKER_HTML('today') + '''
</div>
<div class="stats-row-5" id="stat-cards"></div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<style>
    .provider-section {
        background: var(--bg-card);
        border-radius: 20px;
        border: 1px solid var(--border-color);
        margin-bottom: 20px;
        overflow: hidden;
        transition: all 0.2s;
    }
    .provider-section:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 24px rgba(79,70,229,0.08);
        border-color: var(--brand-color);
    }
    .provider-header-dr {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 20px;
        cursor: pointer;
        border-bottom: 1px solid var(--border-color);
        background: var(--bg-card);
    }
    .provider-header-left {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .provider-color-bar {
        width: 8px;
        height: 40px;
        border-radius: 4px;
    }
    .provider-header-info h3 {
        font-size: 18px;
        font-weight: 600;
        color: var(--text-main);
        margin: 0 0 4px 0;
    }
    .provider-header-info span {
        font-size: 12px;
        color: var(--text-muted);
    }
    .provider-header-stats {
        display: flex;
        align-items: center;
        gap: 24px;
    }
    .header-stat {
        text-align: center;
        padding: 4px 12px;
        background: var(--hover-bg);
        border-radius: 12px;
        border: 1px solid var(--border-color);
    }
    .header-stat-val {
        font-size: 18px;
        font-weight: 700;
        color: var(--text-main);
    }
    .header-stat-lbl {
        font-size: 9px;
        color: var(--text-muted);
        text-transform: uppercase;
    }
    .toggle-icon {
        font-size: 18px;
        color: var(--text-muted);
        transition: transform 0.2s;
    }
    .provider-body {
        padding: 0 20px 20px 20px;
        background: var(--bg-card);
    }
    .region-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }
    .region-table th {
        background: var(--table-hdr);
        padding: 10px 8px;
        text-align: center;
        font-weight: 600;
        color: var(--text-muted);
        font-size: 11px;
        text-transform: uppercase;
        border-bottom: 2px solid var(--brand-color);
    }
    .region-table th:first-child {
        text-align: left;
        padding-left: 16px;
    }
    .region-table td {
        padding: 10px 8px;
        text-align: center;
        border-bottom: 1px solid var(--border-color);
        color: var(--text-main);
    }
    .region-table td:first-child {
        text-align: left;
        padding-left: 16px;
        font-weight: 500;
        background: var(--hover-bg);
    }
    .region-table tr:last-child td {
        border-bottom: none;
    }
    .medal {
        margin-right: 8px;
        font-size: 14px;
    }
    .weight-light {
        color: #10b981;
        font-weight: 600;
    }
    .weight-heavy {
        color: #ef4444;
        font-weight: 600;
    }
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: var(--text-muted);
        background: var(--bg-card);
        border-radius: 20px;
        border: 1px solid var(--border-color);
    }
    .empty-state-icon {
        font-size: 48px;
        margin-bottom: 16px;
        opacity: 0.5;
    }
</style>
<script>
function toggleProvider(id) {
    const body = document.getElementById('bdy-'+id);
    const icon = document.querySelector('#hdr-'+id + ' .toggle-icon');
    if (body.style.display === 'none') {
        body.style.display = 'block';
        if (icon) icon.innerHTML = '▼';
    } else {
        body.style.display = 'none';
        if (icon) icon.innerHTML = '▶';
    }
}

async function loadData() {
    document.getElementById('content').innerHTML = renderDailyRegionSkeleton();
    try {
        const r = await fetch('/api/daily-region-summary?' + dpParams());
        const data = await r.json();

        const role = '{{ role }}';
        const canClick = role === 'admin';
        const statCards = document.getElementById('stat-cards');
        statCards.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(59,130,246,0.1)">📦</div>
                <div class="stat-content">
                    ${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link" style="color:inherit;">` : ''}
                        <div class="stat-value">${data.totals.orders.toLocaleString()}</div>
                    ${canClick ? '</a>' : ''}
                    <div class="stat-label">Total Orders</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(16,185,129,0.1)">📮</div>
                <div class="stat-content">
                    ${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link" style="color:inherit;">` : ''}
                        <div class="stat-value">${data.totals.boxes.toLocaleString()}</div>
                    ${canClick ? '</a>' : ''}
                    <div class="stat-label">Total Boxes</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(245,158,11,0.1)">⚖️</div>
                <div class="stat-content">
                    ${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link" style="color:inherit;">` : ''}
                        <div class="stat-value">${formatWeight(data.totals.weight)} kg</div>
                    ${canClick ? '</a>' : ''}
                    <div class="stat-label">Total Weight</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(34,197,94,0.1)">🪶</div>
                <div class="stat-content">
                    <div class="stat-value">${data.totals.under20.toLocaleString()}</div>
                    <div class="stat-label">&lt;20 kg</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(239,68,68,0.1)">🏋️</div>
                <div class="stat-content">
                    <div class="stat-value">${data.totals.over20.toLocaleString()}</div>
                    <div class="stat-label">20+ kg</div>
                </div>
            </div>
        `;

        if (data.totals.orders === 0) {
            document.getElementById('content').innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><h3>No Data Found</h3><p>No shipments for the selected period</p></div>';
            updateLastUpdateTime();
            return;
        }

        const medals = ['🥇', '🥈', '🥉'];
        let html = '';

        data.providers.forEach((provider, idx) => {
            html += `<div class="provider-section">
                <div class="provider-header-dr" id="hdr-${idx}" onclick="toggleProvider(${idx})">
                    <div class="provider-header-left">
                        <div class="provider-color-bar" style="background:${provider.color}"></div>
                        <div class="provider-header-info">
                            <h3>${provider.name}</h3>
                            <span>${provider.regions.length} region${provider.regions.length !== 1 ? 's' : ''}</span>
                        </div>
                    </div>
                    <div class="provider-header-stats">
                        <div class="header-stat">
                            <div class="header-stat-val">${provider.orders.toLocaleString()}</div>
                            <div class="header-stat-lbl">Orders</div>
                        </div>
                        <div class="header-stat">
                            <div class="header-stat-val">${provider.boxes.toLocaleString()}</div>
                            <div class="header-stat-lbl">Boxes</div>
                        </div>
                        <div class="header-stat">
                            <div class="header-stat-val">${formatWeight(provider.weight)}</div>
                            <div class="header-stat-lbl">Weight</div>
                        </div>
                        <button class="download-btn" onclick="exportProviderTable(this, '${provider.name}')">📥 CSV</button>
                        <span class="toggle-icon">▼</span>
                    </div>
                </div>
                <div class="provider-body" id="bdy-${idx}" style="display: ${idx === 0 ? 'block' : 'none'};">`;

            if (provider.regions.length > 0) {
                html += `<table class="region-table">
                    <thead>
                        <tr>
                            <th>Region</th>
                            <th>Orders</th>
                            <th>Boxes</th>
                            <th>Weight (kg)</th>
                            <th>&lt;20 kg</th>
                            <th>20+ kg</th>
                        </tr>
                    </thead>
                    <tbody>`;

                provider.regions.forEach((rg, i) => {
                    const medal = i < 3 ? `<span class="medal">${medals[i]}</span>` : '';

                    if (canClick) {
                        html += `<tr>
                            <td>${medal}${rg.name}</td>
                            <td><a href="/orders?provider=${encodeURIComponent(provider.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}&region=${encodeURIComponent(rg.name)}" class="orders-link">${rg.orders.toLocaleString()}</a></td>
                            <td><a href="/orders?provider=${encodeURIComponent(provider.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}&region=${encodeURIComponent(rg.name)}" class="boxes-link">${rg.boxes.toLocaleString()}</a></td>
                            <td><a href="/orders?provider=${encodeURIComponent(provider.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}&region=${encodeURIComponent(rg.name)}" class="weight-link">${formatWeight(rg.weight)}</a></td>
                            <td class="weight-light">${rg.under20.toLocaleString()}</td>
                            <td class="weight-heavy">${rg.over20.toLocaleString()}</td>
                        </tr>`;
                    } else {
                        html += `<tr>
                            <td>${medal}${rg.name}</td>
                            <td>${rg.orders.toLocaleString()}</td>
                            <td>${rg.boxes.toLocaleString()}</td>
                            <td>${formatWeight(rg.weight)}</td>
                            <td class="weight-light">${rg.under20.toLocaleString()}</td>
                            <td class="weight-heavy">${rg.over20.toLocaleString()}</td>
                        </tr>`;
                    }
                });

                html += `</tbody></table>`;
            } else {
                html += `<div style="padding: 30px; text-align: center; color: var(--text-muted);">No regions data for this provider</div>`;
            }

            html += `</div></div>`;
        });

        document.getElementById('content').innerHTML = html;
        updateLastUpdateTime();

    } catch(e) {
        console.error(e);
        document.getElementById('content').innerHTML = '<div class="empty-state"><div class="empty-state-icon">❌</div><h3>Error Loading Data</h3><p>' + e.message + '</p></div>';
    }
}

dpInit('today');
loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== FLIGHT LOAD =====
@app.route('/flight-load')
@login_required
def flight_load():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flight Load - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('flight', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Flight <span>Load</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = renderDashboardSkeleton();
    try {
        const r = await fetch('/api/flight-load?' + dpParams());
        const data = await r.json();
        let html = '';
        const role = '{{ role }}';
        const canClick = role === 'admin';
        for (const flight of data.flights) {
            html += `<div class="provider-card"><div class="card-header"><div class="provider-info"><span style="font-size:24px;margin-right:12px">✈️</span><span class="provider-name">${flight.name}</span></div>
<div class="card-stats">
<div class="stat-item"><div class="stat-value">${flight.total_orders.toLocaleString()}</div><div class="stat-label">Orders</div></div>
<div class="stat-item"><div class="stat-value">${flight.total_boxes.toLocaleString()}</div><div class="stat-label">Boxes</div></div>
<div class="stat-item"><div class="stat-value">${formatWeight(flight.total_weight)} kg</div><div class="stat-label">Weight</div></div>
</div>
<button class="download-btn" onclick="exportTableToCSV(this.closest('.provider-card').querySelector('table'), '${flight.name.replace(/ /g,'_')}_${fmtLocal(dpStart)}.csv')">📥 CSV</button>
</div>
<table class="leaderboard-table"><thead><tr><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th></tr></thead><tbody>`;
            for (const p of flight.providers) {
                if (canClick) {
                    html += `<tr><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td>
                        <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link">${p.orders.toLocaleString()}</a></td>
                        <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link">${p.boxes.toLocaleString()}</a></td>
                        <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link">${formatWeight(p.weight)}</a></td></tr>`;
                } else {
                    html += `<tr><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td>
                        <td style="text-align:right">${p.orders.toLocaleString()}</td>
                        <td style="text-align:right">${p.boxes.toLocaleString()}</td>
                        <td style="text-align:right">${formatWeight(p.weight)}</td></tr>`;
                }
            }
            html += '</tbody></table></div>';
        }
        document.getElementById('content').innerHTML = html;
        updateLastUpdateTime();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== ANALYTICS =====
@app.route('/analytics')
@login_required
def analytics():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Analytics - 3PL</title>{{ favicon|safe }}<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('analytics', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Analytics & <span>Insights</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div class="stats-row-5" id="stat-cards"></div>
<div class="charts-grid">
<div class="chart-card full-width"><div class="chart-title">📈 Orders & Boxes Trend</div><div class="chart-container"><canvas id="trendChart"></canvas></div></div>
<div class="chart-card"><div class="chart-title">🏆 Provider Performance</div><div class="chart-container"><canvas id="providerChart"></canvas></div></div>
<div class="chart-card"><div class="chart-title">🌍 Top Regions</div><div class="chart-container"><canvas id="regionChart"></canvas></div></div>
<div class="chart-card"><div class="chart-title">📊 Weight Categories by Region</div><div class="chart-container"><canvas id="weightRegionChart"></canvas></div></div>
<div class="chart-card"><div class="chart-title">📊 Weight Categories by 3PL</div><div class="chart-container"><canvas id="weightProviderChart"></canvas></div></div>
</div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
let charts = {};
function applyChartTheme(){
    const dark = document.body.getAttribute('data-theme')==='dark';
    Chart.defaults.color = dark ? '#94a3b8' : '#475569';
    Chart.defaults.borderColor = dark ? '#222222' : '#e2e8f0';
}
applyChartTheme();

function destroyCharts() { Object.values(charts).forEach(c => c && c.destroy()); charts = {}; }

async function loadData() {
    destroyCharts();
    document.getElementById('stat-cards').innerHTML = renderDashboardSkeleton();
    try {
        const r = await fetch('/api/analytics-data?' + dpParams());
        const data = await r.json();

        const role = '{{ role }}';
        const canClick = role === 'admin';
        const statCards = document.getElementById('stat-cards');
        statCards.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(59,130,246,0.1)">📋</div>
                <div class="stat-content">
                    ${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link" style="color:inherit;">` : ''}
                        <div class="stat-value">${data.totals.orders.toLocaleString()}</div>
                    ${canClick ? '</a>' : ''}
                    <div class="stat-label">Total Orders</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(16,185,129,0.1)">📦</div>
                <div class="stat-content">
                    ${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link" style="color:inherit;">` : ''}
                        <div class="stat-value">${data.totals.boxes.toLocaleString()}</div>
                    ${canClick ? '</a>' : ''}
                    <div class="stat-label">Total Boxes</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(212,168,83,0.1)">⚖️</div>
                <div class="stat-content">
                    ${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link" style="color:inherit;">` : ''}
                        <div class="stat-value">${formatWeight(data.totals.weight)} kg</div>
                    ${canClick ? '</a>' : ''}
                    <div class="stat-label">Total Weight</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(34,197,94,0.1)">🪶</div>
                <div class="stat-content">
                    <div class="stat-value">${data.totals.under20.toLocaleString()}</div>
                    <div class="stat-label">Light (<20 kg)</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background:rgba(239,68,68,0.1)">🏋️</div>
                <div class="stat-content">
                    <div class="stat-value">${data.totals.over20.toLocaleString()}</div>
                    <div class="stat-label">Heavy (20+ kg)</div>
                </div>
            </div>
        `;

        charts.trend = new Chart(document.getElementById('trendChart'), { type:'line', data:{ labels:data.trend.labels, datasets:[{label:'Orders',data:data.trend.orders,borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,0.1)',fill:true,tension:0.4,pointRadius:4},{label:'Boxes',data:data.trend.boxes,borderColor:'#10b981',backgroundColor:'rgba(16,185,129,0.1)',fill:true,tension:0.4,pointRadius:4}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top'}},scales:{y:{beginAtZero:true,grid:{color:'#e2e8f0'}},x:{grid:{display:false}}}}});
        charts.provider = new Chart(document.getElementById('providerChart'), { type:'doughnut', data:{labels:data.providers.map(p=>p.name),datasets:[{data:data.providers.map(p=>p.boxes),backgroundColor:data.providers.map(p=>p.color+'CC'),borderColor:'#ffffff',borderWidth:3}]}, options:{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{legend:{position:'right',labels:{padding:12,usePointStyle:true}}}}});
        const topR = data.regions.slice(0,8);
        charts.region = new Chart(document.getElementById('regionChart'), { type:'bar', data:{labels:topR.map(r=>r.name),datasets:[{label:'Boxes',data:topR.map(r=>r.boxes),backgroundColor:'#4f46e599',borderColor:'#4f46e5',borderWidth:2,borderRadius:6}]}, options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,grid:{color:'#e2e8f0'}},y:{grid:{display:false}}}}});
        const wR = data.regions.slice(0,6);
        charts.weightRegion = new Chart(document.getElementById('weightRegionChart'), { type:'bar', data:{labels:wR.map(r=>r.name),datasets:[{label:'<20 kg',data:wR.map(r=>r.under20),backgroundColor:'#10b981',borderColor:'#10b981',borderWidth:1,borderRadius:4},{label:'20+ kg',data:wR.map(r=>r.over20),backgroundColor:'#ef4444',borderColor:'#ef4444',borderWidth:1,borderRadius:4}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top'}},scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,beginAtZero:true,grid:{color:'#e2e8f0'}}}}});
        charts.weightProvider = new Chart(document.getElementById('weightProviderChart'), { type:'bar', data:{labels:data.providers.map(p=>p.name),datasets:[{label:'<20 kg',data:data.providers.map(p=>p.under20),backgroundColor:'#10b981',borderColor:'#10b981',borderWidth:1,borderRadius:4},{label:'20+ kg',data:data.providers.map(p=>p.over20),backgroundColor:'#ef4444',borderColor:'#ef4444',borderWidth:1,borderRadius:4}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top'}},scales:{x:{grid:{display:false}},y:{beginAtZero:true,grid:{color:'#e2e8f0'}}}}});
        updateLastUpdateTime();
    } catch(e) { console.error(e); }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== KPI =====
@app.route('/kpi')
@login_required
def kpi_dashboard():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KPI Dashboard - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('kpi', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">KPI <span>Dashboard</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="kpi-grid">' + 
        '<div class="kpi-card"><div class="skeleton" style="height:80px"></div></div>'.repeat(9) + '</div>';
    try {
        const r = await fetch('/api/kpi?' + dpParams());
        const data = await r.json();
        const kpis = [
            {icon:'📦',label:'Total Boxes',value:data.total_boxes.toLocaleString(),trend:data.boxes_trend},
            {icon:'📋',label:'Total Orders',value:data.total_orders.toLocaleString(),trend:data.orders_trend},
            {icon:'⚖️',label:'Total Weight',value:formatWeight(data.total_weight)+' kg',trend:data.weight_trend},
            {icon:'📊',label:'Avg Boxes/Day',value:Math.round(data.avg_boxes_per_day).toString(),trend:null},
            {icon:'📈',label:'Avg Weight/Order',value:data.avg_weight_per_order.toFixed(1)+' kg',trend:null},
            {icon:'🌍',label:'Active Regions',value:data.active_regions,trend:null},
            {icon:'🏆',label:'Top Provider',value:data.top_provider,trend:null},
            {icon:'🗺️',label:'Top Region',value:data.top_region,trend:null},
            {icon:'📅',label:'Best Day',value:data.best_day,trend:null}
        ];
        let html = '<div class="kpi-grid">';
        kpis.forEach(k => {
            let tHtml = '';
            if (k.trend) {
                const tc = k.trend.direction === 'up' ? 'up' : 'down';
                const ti = k.trend.direction === 'up' ? '▲' : '▼';
                tHtml = `<div class="kpi-trend ${tc}">${ti} ${k.trend.percentage}% vs prev period</div>`;
            }
            html += `<div class="kpi-card"><div class="kpi-icon">${k.icon}</div><div class="kpi-value">${k.value}</div><div class="kpi-label">${k.label}</div>${tHtml}</div>`;
        });
        html += '</div>';
        document.getElementById('content').innerHTML = html;
        updateLastUpdateTime();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== COMPARISON =====
@app.route('/comparison')
@login_required
def comparison():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparison - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('comparison', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Provider <span>Comparison</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div class="tabs">
    <button class="tab-btn active" onclick="showTab(this, 'ge-ecl')">GE vs ECL</button>
    <button class="tab-btn" onclick="showTab(this, 'qc-zone')">QC vs ZONE</button>
    <button class="tab-btn" onclick="showTab(this, 'all')">All Providers</button>
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<style>
    .comparison-grid {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: 24px;
        align-items: start;
        margin-bottom: 30px;
    }
    .comparison-card {
        background: var(--bg-card);
        border-radius: 24px;
        border: 1px solid var(--border-color);
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.02);
        transition: all 0.2s;
    }
    .comparison-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 24px rgba(79,70,229,0.08);
        border-color: var(--brand-color);
    }
    .comparison-vs {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        font-weight: 700;
        color: var(--brand-color);
        background: var(--bg-card);
        width: 70px;
        height: 70px;
        border-radius: 50%;
        border: 2px solid var(--border-color);
        margin: 0 auto;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .comparison-header {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 2px solid var(--border-color);
    }
    .comparison-color {
        width: 8px;
        height: 40px;
        border-radius: 4px;
    }
    .comparison-name {
        font-size: 20px;
        font-weight: 700;
        color: var(--text-main);
    }
    .comparison-stats {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .comparison-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px dashed var(--border-color);
    }
    .comparison-stat:last-child {
        border-bottom: none;
    }
    .comparison-stat-label {
        color: var(--text-muted);
        font-size: 14px;
        font-weight: 500;
    }
    .comparison-stat-value {
        color: var(--text-main);
        font-size: 18px;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .winner-indicator {
        color: #fbbf24;
        font-size: 20px;
        filter: drop-shadow(0 2px 4px rgba(251,191,36,0.3));
    }
    .all-providers-table {
        width: 100%;
        border-collapse: collapse;
        background: var(--bg-card);
        border-radius: 24px;
        overflow: hidden;
        border: 1px solid var(--border-color);
    }
    .all-providers-table th {
        background: var(--table-hdr);
        padding: 16px 12px;
        text-align: left;
        font-weight: 600;
        color: var(--text-muted);
        font-size: 12px;
        text-transform: uppercase;
        border-bottom: 2px solid var(--brand-color);
    }
    .all-providers-table td {
        padding: 14px 12px;
        border-bottom: 1px solid var(--border-color);
        color: var(--text-main);
        font-size: 14px;
    }
    .all-providers-table tr:last-child td {
        border-bottom: none;
    }
    .all-providers-table tr:hover td {
        background: var(--hover-bg);
    }
    .provider-cell {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .provider-color-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
    }
    .avg-badge {
        background: var(--hover-bg);
        padding: 4px 10px;
        border-radius: 30px;
        font-size: 12px;
        color: var(--text-muted);
        border: 1px solid var(--border-color);
        margin-left: 8px;
    }
    .tab-btn {
        padding: 8px 24px;
        font-size: 14px;
        font-weight: 600;
    }
</style>
<script>
let curTab = 'ge-ecl';
let curData = null;

function showTab(btn, tab) {
    curTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderComparison();
}

function renderCard(p1, p2, title1, title2) {
    const stats = [
        { key: 'total_orders', label: 'Orders' },
        { key: 'total_boxes', label: 'Boxes' },
        { key: 'total_weight', label: 'Weight (kg)' }
    ];
    
    let stats1 = '', stats2 = '';
    
    stats.forEach(s => {
        const v1 = p1[s.key];
        const v2 = p2[s.key];
        const isWinner1 = v1 > v2;
        const isWinner2 = v2 > v1;
        const display1 = s.key === 'total_weight' ? formatWeight(v1) : v1.toLocaleString();
        const display2 = s.key === 'total_weight' ? formatWeight(v2) : v2.toLocaleString();
        
        stats1 += `<div class="comparison-stat">
            <span class="comparison-stat-label">${s.label}</span>
            <span class="comparison-stat-value">
                ${display1}
                ${isWinner1 ? '<span class="winner-indicator">👑</span>' : ''}
            </span>
        </div>`;
        
        stats2 += `<div class="comparison-stat">
            <span class="comparison-stat-label">${s.label}</span>
            <span class="comparison-stat-value">
                ${display2}
                ${isWinner2 ? '<span class="winner-indicator">👑</span>' : ''}
            </span>
        </div>`;
    });
    
    const avg1 = p1.total_orders > 0 ? (p1.total_weight / p1.total_orders).toFixed(1) : '0';
    const avg2 = p2.total_orders > 0 ? (p2.total_weight / p2.total_orders).toFixed(1) : '0';
    const avgWinner1 = parseFloat(avg1) > parseFloat(avg2);
    const avgWinner2 = parseFloat(avg2) > parseFloat(avg1);
    
    stats1 += `<div class="comparison-stat">
        <span class="comparison-stat-label">Avg W/Order</span>
        <span class="comparison-stat-value">
            ${avg1} kg
            ${avgWinner1 ? '<span class="winner-indicator">👑</span>' : ''}
        </span>
    </div>`;
    
    stats2 += `<div class="comparison-stat">
        <span class="comparison-stat-label">Avg W/Order</span>
        <span class="comparison-stat-value">
            ${avg2} kg
            ${avgWinner2 ? '<span class="winner-indicator">👑</span>' : ''}
        </span>
    </div>`;
    
    return `<div class="comparison-grid">
        <div class="comparison-card">
            <div class="comparison-header">
                <div class="comparison-color" style="background:${p1.color}"></div>
                <div class="comparison-name">${title1 || p1.short || p1.name}</div>
            </div>
            <div class="comparison-stats">
                ${stats1}
            </div>
        </div>
        <div class="comparison-vs">VS</div>
        <div class="comparison-card">
            <div class="comparison-header">
                <div class="comparison-color" style="background:${p2.color}"></div>
                <div class="comparison-name">${title2 || p2.short || p2.name}</div>
            </div>
            <div class="comparison-stats">
                ${stats2}
            </div>
            <button class="download-btn" onclick="exportTableToCSV(this.closest('.comparison-card').querySelector('.comparison-stats'), '${title1}_vs_${title2}_${fmtLocal(dpStart)}.csv')" style="margin-top:15px">📥 CSV</button>
        </div>
    </div>`;
}

function renderAllProviders(providers) {
    const role = '{{ role }}';
    const canClick = role === 'admin';
    
    let html = `<table class="all-providers-table">
        <thead>
            <tr>
                <th>Provider</th>
                <th style="text-align:right">Orders</th>
                <th style="text-align:right">Boxes</th>
                <th style="text-align:right">Weight (kg)</th>
                <th style="text-align:right">Avg/Order</th>
                <th style="text-align:right">Light/Heavy</th>
            </tr>
        </thead>
        <tbody>`;
    
    providers.sort((a, b) => b.total_boxes - a.total_boxes).forEach(p => {
        const avg = p.total_orders > 0 ? (p.total_weight / p.total_orders).toFixed(1) : '0';
        
        if (canClick) {
            html += `<tr>
                <td>
                    <div class="provider-cell">
                        <div class="provider-color-dot" style="background:${p.color}"></div>
                        <span>${p.short || p.name}</span>
                    </div>
                </td>
                <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link">${p.total_orders.toLocaleString()}</a></td>
                <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link">${p.total_boxes.toLocaleString()}</a></td>
                <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.short)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link">${formatWeight(p.total_weight)}</a></td>
                <td style="text-align:right">${avg} kg</td>
                <td style="text-align:right"><span class="avg-badge">${p.total_under20} / ${p.total_over20}</span></td>
            </tr>`;
        } else {
            html += `<tr>
                <td>
                    <div class="provider-cell">
                        <div class="provider-color-dot" style="background:${p.color}"></div>
                        <span>${p.short || p.name}</span>
                    </div>
                </td>
                <td style="text-align:right">${p.total_orders.toLocaleString()}</td>
                <td style="text-align:right">${p.total_boxes.toLocaleString()}</td>
                <td style="text-align:right">${formatWeight(p.total_weight)}</td>
                <td style="text-align:right">${avg} kg</td>
                <td style="text-align:right"><span class="avg-badge">${p.total_under20} / ${p.total_over20}</span></td>
            </tr>`;
        }
    });
    
    html += `</tbody></table>`;
    return html;
}

function renderComparison() {
    if (!curData || !curData.providers) return;
    
    const ps = curData.providers;
    let html = '';
    
    if (curTab === 'ge-ecl') {
        const ge = ps.filter(p => p.group === 'GE');
        const ecl = ps.filter(p => p.group === 'ECL');
        
        const geTotal = {
            name: 'GE Total',
            short: 'GE Total',
            color: '#3B82F6',
            total_orders: ge.reduce((s, p) => s + p.total_orders, 0),
            total_boxes: ge.reduce((s, p) => s + p.total_boxes, 0),
            total_weight: ge.reduce((s, p) => s + p.total_weight, 0),
            total_under20: ge.reduce((s, p) => s + p.total_under20, 0),
            total_over20: ge.reduce((s, p) => s + p.total_over20, 0)
        };
        
        const eclTotal = {
            name: 'ECL Total',
            short: 'ECL Total',
            color: '#10B981',
            total_orders: ecl.reduce((s, p) => s + p.total_orders, 0),
            total_boxes: ecl.reduce((s, p) => s + p.total_boxes, 0),
            total_weight: ecl.reduce((s, p) => s + p.total_weight, 0),
            total_under20: ecl.reduce((s, p) => s + p.total_under20, 0),
            total_over20: ecl.reduce((s, p) => s + p.total_over20, 0)
        };
        
        html = '<h3 style="color:var(--brand-color); margin-bottom:24px; font-size:18px;">Global Express vs ECL Logistics</h3>';
        html += renderCard(geTotal, eclTotal, 'GE Total', 'ECL Total');
        
    } else if (curTab === 'qc-zone') {
        const qc = ps.filter(p => p.name.includes('QC'));
        const zone = ps.filter(p => p.name.includes('ZONE'));
        
        const qcTotal = {
            name: 'QC Total',
            short: 'QC Total',
            color: '#8B5CF6',
            total_orders: qc.reduce((s, p) => s + p.total_orders, 0),
            total_boxes: qc.reduce((s, p) => s + p.total_boxes, 0),
            total_weight: qc.reduce((s, p) => s + p.total_weight, 0),
            total_under20: qc.reduce((s, p) => s + p.total_under20, 0),
            total_over20: qc.reduce((s, p) => s + p.total_over20, 0)
        };
        
        const zoneTotal = {
            name: 'Zone Total',
            short: 'Zone Total',
            color: '#F59E0B',
            total_orders: zone.reduce((s, p) => s + p.total_orders, 0),
            total_boxes: zone.reduce((s, p) => s + p.total_boxes, 0),
            total_weight: zone.reduce((s, p) => s + p.total_weight, 0),
            total_under20: zone.reduce((s, p) => s + p.total_under20, 0),
            total_over20: zone.reduce((s, p) => s + p.total_over20, 0)
        };
        
        html = '<h3 style="color:var(--brand-color); margin-bottom:24px; font-size:18px;">QC Center vs Zone</h3>';
        html += renderCard(qcTotal, zoneTotal, 'QC Total', 'Zone Total');
        
    } else {
        html = '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;"><h3 style="color:var(--brand-color); font-size:18px;">All Providers Comparison</h3><button class="download-btn" onclick="exportComparisonTable()">📥 CSV</button></div>';
        html += renderAllProviders(ps);
    }
    
    document.getElementById('content').innerHTML = html;
    updateLastUpdateTime();
}

async function loadData() {
    document.getElementById('content').innerHTML = renderComparisonSkeleton();
    try {
        const r = await fetch('/api/dashboard?' + dpParams());
        curData = await r.json();
        renderComparison();
    } catch(e) {
        document.getElementById('content').innerHTML = '<div style="color:#ef4444; text-align:center; padding:40px;">Error loading data: ' + e.message + '</div>';
    }
}

dpInit('week');
loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== REGIONS =====
@app.route('/regions')
@login_required
def regions():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Region Heatmap - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('regions', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Region <span>Heatmap</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
function heatColor(v,mx) {
    const r=v/mx;
    if(r>=0.8) return '#4f46e5'; if(r>=0.6) return '#6366f1';
    if(r>=0.4) return '#818cf8'; if(r>=0.2) return '#a5b4fc'; return '#c7d2fe';
}
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="heatmap-container">' + 
        '<div class="heatmap-item"><div class="skeleton" style="height:60px"></div></div>'.repeat(8) + '</div>';
    try {
        const r = await fetch('/api/regions?' + dpParams());
        const data = await r.json();
        const mx = Math.max(...data.regions.map(r=>r.orders)) || 1;
        let html = '<div class="heatmap-container">';
        data.regions.forEach(rg => {
            const c = heatColor(rg.orders,mx);
            html+=`<div class="heatmap-item" style="border-color:${c}"><div class="heatmap-region">${rg.name}</div><div class="heatmap-value" style="color:${c}">${rg.orders}</div><div class="heatmap-label">orders</div><div class="heatmap-label" style="margin-top:4px">${rg.boxes} boxes • ${formatWeight(rg.weight)} kg</div></div>`;
        });
        html += '</div>';
        document.getElementById('content').innerHTML = html;
        updateLastUpdateTime();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== MONTHLY =====
@app.route('/monthly')
@login_required
def monthly_report():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monthly Report - 3PL</title>{{ favicon|safe }}<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('monthly', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Monthly <span>Report</span></h1>
    ''' + DATE_PICKER_HTML('month') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
let chart = null;
async function loadData() {
    document.getElementById('content').innerHTML = renderDashboardSkeleton();
    try {
        const r = await fetch('/api/monthly?' + dpParams());
        const data = await r.json();
        const role = '{{ role }}';
        const canClick = role === 'admin';
        let html = `<div class="stats-row">
<div class="stat-card"><div class="stat-icon" style="background:rgba(59,130,246,0.1)">📋</div><div class="stat-content">${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link" style="color:inherit;">` : ''}<div class="stat-value">${data.total_orders.toLocaleString()}</div>${canClick ? '</a>' : ''}<div class="stat-label">Total Orders</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(16,185,129,0.1)">📦</div><div class="stat-content">${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link" style="color:inherit;">` : ''}<div class="stat-value">${data.total_boxes.toLocaleString()}</div>${canClick ? '</a>' : ''}<div class="stat-label">Total Boxes</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(212,168,83,0.1)">⚖️</div><div class="stat-content">${canClick ? `<a href="/orders?provider=all&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link" style="color:inherit;">` : ''}<div class="stat-value">${formatWeight(data.total_weight)} kg</div>${canClick ? '</a>' : ''}<div class="stat-label">Total Weight</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(139,92,246,0.1)">📊</div><div class="stat-content"><div class="stat-value">${Math.round(data.avg_per_day)}</div><div class="stat-label">Avg Orders/Day</div></div></div>
</div>
<div class="charts-grid"><div class="chart-card full-width"><div class="chart-title">Weekly Breakdown</div><div class="chart-container"><canvas id="weeklyChart"></canvas></div></div></div>
<div class="provider-card"><div class="card-header"><div class="provider-info"><span class="provider-name">Provider Monthly Summary</span></div><button class="download-btn" onclick="exportComparisonTable()">📥 CSV</button></div>
<table class="leaderboard-table"><thead><tr><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th></tr></thead><tbody>`;
        data.providers.forEach(p => {
            if (canClick) {
                html+=`<tr><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div>${p.name}</div></td>
                    <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="orders-link">${p.orders.toLocaleString()}</a></td>
                    <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="boxes-link">${p.boxes.toLocaleString()}</a></td>
                    <td style="text-align:right"><a href="/orders?provider=${encodeURIComponent(p.name)}&start=${fmtLocal(dpStart)}&end=${fmtLocal(dpEnd)}" class="weight-link">${formatWeight(p.weight)}</a></td></tr>`;
            } else {
                html+=`<tr><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div>${p.name}</div></td>
                    <td style="text-align:right">${p.orders.toLocaleString()}</td>
                    <td style="text-align:right">${p.boxes.toLocaleString()}</td>
                    <td style="text-align:right">${formatWeight(p.weight)}</td></tr>`;
            }
        });
        html += '</tbody></table></div>';
        document.getElementById('content').innerHTML = html;
        if (chart) chart.destroy();
        chart = new Chart(document.getElementById('weeklyChart'), { type:'bar', data:{labels:data.weeks.map(w=>w.label),datasets:[{label:'Boxes',data:data.weeks.map(w=>w.boxes),backgroundColor:'#4f46e599',borderColor:'#4f46e5',borderWidth:2,borderRadius:8}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,grid:{color:'#e2e8f0'}},x:{grid:{display:false}}}}});
        updateLastUpdateTime();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('month'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== WHATSAPP =====
@app.route('/whatsapp')
@login_required
def whatsapp_report():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WhatsApp Report - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('whatsapp', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">WhatsApp <span>Report</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
function copyText(text) {
    navigator.clipboard.writeText(text).then(() => {
        const b = document.querySelector('.copy-btn');
        b.innerHTML = '✓ Copied!'; setTimeout(()=>{b.innerHTML='📋 Copy to Clipboard';},2000);
    });
}
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="whatsapp-box"><div class="skeleton" style="height:200px"></div></div>';
    try {
        const r = await fetch('/api/whatsapp?' + dpParams());
        const data = await r.json();
        document.getElementById('content').innerHTML = `<div class="whatsapp-box"><div class="whatsapp-header"><span class="whatsapp-icon">📱</span><span class="whatsapp-title">Report - Ready to Share</span><button class="download-btn" onclick="copyText(document.getElementById('report-text').textContent)" style="margin-left:auto">📋 Copy</button></div><div class="whatsapp-content" id="report-text">${data.report}</div><button class="copy-btn" onclick="copyText(document.getElementById('report-text').textContent)">📋 Copy to Clipboard</button></div>`;
        updateLastUpdateTime();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== ACHIEVEMENTS =====
@app.route('/achievements')
@login_required
def achievements_page():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Achievements - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body class="''' + mode_class + '''">
''' + sidebar('achievements', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Provider <span>Achievements</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = renderDashboardSkeleton();
    try {
        const r = await fetch('/api/dashboard?' + dpParams());
        const data = await r.json();
        let html = '';
        data.providers.forEach(p => {
            const ach = p.achievements || [];
            html+=`<div class="provider-card" style="margin-bottom:16px"><div class="card-header"><div class="provider-info"><div style="background:${p.color};width:8px;height:40px;border-radius:4px"></div><span class="provider-name">${p.name}</span><span style="color:#64748b;font-size:14px">${p.total_boxes.toLocaleString()} boxes</span></div><button class="download-btn" onclick="exportProviderTable(this, '${p.name}')">📥 CSV</button></div>
<div style="padding:20px">${ach.length>0?'<div style="display:flex;flex-wrap:wrap;gap:12px">'+ach.map(a=>`<div style="background:var(--hover-bg);border:1px solid var(--border-color);border-radius:12px;padding:16px;text-align:center;min-width:120px"><div style="font-size:32px;margin-bottom:8px">${a.icon}</div><div style="font-size:14px;font-weight:600;color:var(--brand-color)">${a.name}</div><div style="font-size:11px;color:var(--text-muted);margin-top:4px">${a.desc}</div></div>`).join('')+'</div>':'<div style="color:var(--text-muted);text-align:center;padding:20px">No achievements this period 💪</div>'}</div></div>`;
        });
        document.getElementById('content').innerHTML = html;
        updateLastUpdateTime();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

# ===== FORECAST =====
@app.route('/forecast')
@login_required
def forecast():
    role = session.get('role', 'guest')
    if role != 'admin':
        return "Access Denied", 403
    return render_template_string('''
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Forecast - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body>
''' + sidebar('forecast', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Forecast <span>Predictions</span></h1>
</div>
<div id="forecast-content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
async function loadForecast() {
    document.getElementById('forecast-content').innerHTML = '<div class="forecast-grid">' + 
        '<div class="forecast-day"><div class="skeleton" style="height:80px"></div></div>'.repeat(6) + '</div>';
    try {
        const r = await fetch('/api/forecast');
        const data = await r.json();
        let html = '<div class="forecast-card"><div class="forecast-title">Next Week Predictions (Mon–Sat)</div><div class="forecast-grid">';
        const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        days.forEach((day, idx) => {
            html += `<div class="forecast-day">
                <div class="day-name">${day}</div>
                <div class="prediction">📦 ${data[idx].boxes} boxes</div>
                <div class="forecast-detail">📋 ${data[idx].orders} orders</div>
                <div class="forecast-detail">⚖️ ${data[idx].weight} kg</div>
            </div>`;
        });
        html += '</div></div>';
        document.getElementById('forecast-content').innerHTML = html;
        updateLastUpdateTime();
    } catch(e) {
        document.getElementById('forecast-content').innerHTML = '<p style="color:#ef4444">Error loading forecast</p>';
    }
}
loadForecast();
</script></body></html>''', favicon=FAVICON)

# ===== LOGS =====
@app.route('/logs')
@login_required
def logs():
    role = session.get('role', 'guest')
    if role != 'admin':
        return "Access Denied", 403
    logs_data = [
        "2026-02-28 10:23: admin logged in",
        "2026-02-28 10:25: admin viewed Dashboard",
        "2026-02-28 10:30: admin exported CSV",
        "2026-02-28 10:32: admin searched for order 'ORD123'",
        "2026-02-28 11:05: admin viewed Forecast",
        "2026-02-28 11:10: admin logged out",
    ]
    logs_html = ''.join(f'<div class="log-entry">{log}</div>' for log in logs_data)
    return render_template_string('''
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Activity Logs - 3PL</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body>
''' + sidebar('logs', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">Activity <span>Logs</span></h1>
</div>
<div class="logs-container">
    ''' + logs_html + '''
</div>
<div class="last-update" style="margin-top:20px">
    Last update: <span id="last-update-time">Never</span>
</div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>updateLastUpdateTime();</script>
</body></html>''', favicon=FAVICON)

# ===== WORLD MAP =====
@app.route('/world-map')
@login_required
def world_map():
    role = session.get('role', 'guest')
    mode_class = 'guest-mode' if role == 'guest' else 'admin-mode'
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>World Map - 3PL</title>
    {{ favicon|safe }}
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    ''' + BASE_STYLES + '''
    <style>
        #world-map {
            height: 600px;
            width: 100%;
            border-radius: 20px;
            border: 1px solid var(--border-color);
            z-index: 1;
        }
        .map-controls {
            margin-bottom: 20px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        .map-legend {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 10px;
            padding: 10px;
            background: var(--bg-card);
            border-radius: 10px;
            border: 1px solid var(--border-color);
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
        }
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            opacity: 0.7;
        }
        .region-popup {
            font-size: 12px;
        }
        .region-popup b {
            color: var(--brand-color);
        }
    </style>
</head>
<body class="''' + mode_class + '''">
''' + sidebar('worldmap', role) + '''
<main class="main-content" id="main-content">
''' + ACTION_BAR_HTML(role) + '''
<div class="page-header">
    <h1 class="page-title">World <span>Map</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>

<div class="map-controls">
    <div style="color: var(--text-muted);">World Map order tracker</div>
</div>

<div id="world-map"></div>

<div class="map-legend" id="map-legend"></div>

</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + ORDERS_MODAL_HTML + '''
<script>
let map;
let markers = [];

function initMap(regions) {
    if (map) {
        map.remove();
        markers = [];
    }
    
    // دنیا کا نقشہ
    map = L.map('world-map').setView([20, 0], 2);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // ریجن کے کوآرڈینیٹس
    const regionCoords = {
        'UNITED KINGDOM': [55.3781, -3.4360],
        'UNITED STATES': [37.0902, -95.7129],
        'AUSTRALIA': [-25.2744, 133.7751],
        'NEW ZEALAND': [-40.9006, 174.8860],
        'EU': [50.0, 10.0],
        'CANADA': [56.1304, -106.3468],
        'GERMANY': [51.1657, 10.4515],
        'FRANCE': [46.2276, 2.2137],
        'ITALY': [41.8719, 12.5674],
        'SPAIN': [40.4637, -3.7492],
        'NETHERLANDS': [52.1326, 5.2913],
        'BELGIUM': [50.5039, 4.4699],
        'SWITZERLAND': [46.8182, 8.2275],
        'SWEDEN': [60.1282, 18.6435],
        'NORWAY': [60.4720, 8.4689],
        'DENMARK': [56.2639, 9.5018],
        'FINLAND': [61.9241, 25.7482],
        'POLAND': [51.9194, 19.1451],
        'CZECH REPUBLIC': [49.8175, 15.4730],
        'AUSTRIA': [47.5162, 14.5501],
        'HUNGARY': [47.1625, 19.5033],
        'SLOVAKIA': [48.6690, 19.6990],
        'SLOVENIA': [46.1512, 14.9955],
        'CROATIA': [45.1000, 15.2000],
        'ROMANIA': [45.9432, 24.9668],
        'BULGARIA': [42.7339, 25.4858],
        'GREECE': [39.0742, 21.8243],
        'PORTUGAL': [39.3999, -8.2245],
        'IRELAND': [53.1424, -7.6921],
        'ICELAND': [64.9631, -19.0208],
        'RUSSIA': [61.5240, 105.3188],
        'CHINA': [35.8617, 104.1954],
        'JAPAN': [36.2048, 138.2529],
        'SOUTH KOREA': [35.9078, 127.7669],
        'INDIA': [20.5937, 78.9629],
        'BRAZIL': [-14.2350, -51.9253],
        'ARGENTINA': [-38.4161, -63.6167],
        'MEXICO': [23.6345, -102.5528],
        'SOUTH AFRICA': [-30.5595, 22.9375],
        'EGYPT': [26.8206, 30.8025],
        'SAUDI ARABIA': [23.8859, 45.0792],
        'UAE': [23.4241, 53.8478],
        'TURKEY': [38.9637, 35.2433],
        'ISRAEL': [31.0461, 34.8516],
        'PAKISTAN': [30.3753, 69.3451],
        'BANGLADESH': [23.6850, 90.3563],
        'INDONESIA': [-0.7893, 113.9213],
        'MALAYSIA': [4.2105, 101.9758],
        'SINGAPORE': [1.3521, 103.8198],
        'THAILAND': [15.8700, 100.9925],
        'VIETNAM': [14.0583, 108.2772],
        'PHILIPPINES': [12.8797, 121.7740],
    };
    
    // زیادہ سے زیادہ آرڈرز کا پتہ لگائیں
    const maxOrders = Math.max(...regions.map(r => r.orders), 1);
    
    regions.forEach(region => {
        const name = region.name;
        const orders = region.orders;
        const boxes = region.boxes;
        const weight = region.weight;
        
        // کوآرڈینیٹس ڈھونڈیں
        let coord = regionCoords[name];
        if (!coord) {
            // اگر کوآرڈینیٹس نہ ہوں تو نقشے میں نہ دکھائیں
            return;
        }
        
        // دائرے کا سائز آرڈرز کے مطابق
        const radius = Math.max(5, Math.min(30, 5 + (orders / maxOrders) * 25));
        
        // رنگ (پیلا سے گہرا نیلا)
        const intensity = orders / maxOrders;
        const color = intensity > 0.7 ? '#ef4444' : (intensity > 0.4 ? '#f59e0b' : '#3b82f6');
        
        // دائرہ بنائیں
        const circle = L.circleMarker(coord, {
            radius: radius,
            fillColor: color,
            color: '#ffffff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.7
        }).addTo(map);
        
        // پاپ اپ
        circle.bindPopup(`
            <div class="region-popup">
                <b>${name}</b><br>
                📦 Orders: ${orders.toLocaleString()}<br>
                📮 Boxes: ${boxes.toLocaleString()}<br>
                ⚖️ Weight: ${formatWeight(weight)} kg
            </div>
        `);
        
        markers.push(circle);
    });
    
    // لیجنڈ بنائیں
    const legend = document.getElementById('map-legend');
    legend.innerHTML = `
        <div class="map-legend" id="map-legend">
    <div class="legend-item"><span class="legend-color" style="background:#3b82f6"></span> Low orders</div>
    <div class="legend-item"><span class="legend-color" style="background:#f59e0b"></span> Medium orders</div>
    <div class="legend-item"><span class="legend-color" style="background:#ef4444"></span> High orders</div>
    <div class="legend-item"><span>Circle size = Number of orders</span></div>
</div>
    `;
}

function exportMapData() {
    // نقشے کا ڈیٹا CSV میں ایکسپورٹ کریں
    const markersData = markers.map(m => {
        const popup = m.getPopup();
        const content = popup ? popup.getContent() : '';
        // پاپ اپ سے ڈیٹا نکالیں (آسان طریقہ)
        return content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    }).join('\\n');
    
    const blob = new Blob([markersData], {type: 'text/plain'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `world_map_${fmtLocal(dpStart)}.txt`;
    a.click();
}

async function loadData() {
    document.getElementById('world-map').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/regions?' + dpParams());
        const data = await r.json();
        initMap(data.regions);
        updateLastUpdateTime();
    } catch(e) {
        document.getElementById('world-map').innerHTML = '<p style="color:#ef4444; text-align:center; padding:40px;">Error loading map data</p>';
    }
}

dpInit('week');
loadData();
</script>
</body>
</html>
''', role=role, favicon=FAVICON)

# ===== API ENDPOINTS =====
@app.route('/api/dashboard')
def api_dashboard():
    start_date, end_date = parse_date_range(request)
    prev_start = start_date - (end_date - start_date) - timedelta(seconds=1)
    prev_end = start_date - timedelta(seconds=1)
    providers_data = []
    max_boxes = 0
    winner_idx = 0
    for idx, provider in enumerate(PROVIDERS):
        current_data = process_provider_data(provider, start_date, end_date)
        previous_data = process_provider_data(provider, prev_start, prev_end)
        if current_data:
            prev_boxes = previous_data['total_boxes'] if previous_data else 0
            current_data['trend'] = calculate_trend(current_data['total_boxes'], prev_boxes)
            if current_data['total_boxes'] > max_boxes:
                max_boxes = current_data['total_boxes']
                winner_idx = len(providers_data)
            providers_data.append(current_data)
    for idx, p in enumerate(providers_data):
        is_winner = idx == winner_idx and p['total_boxes'] > 0
        p['achievements'] = get_provider_achievements(p, is_winner, p['trend'])
    return jsonify({'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(), 'providers': providers_data})

@app.route('/api/weekly-summary')
def api_weekly_summary():
    start_date, end_date = parse_date_range(request)
    prev_start = start_date - (end_date - start_date) - timedelta(seconds=1)
    prev_end = start_date - timedelta(seconds=1)
    providers_data = []
    for provider in PROVIDERS:
        current_data = process_provider_data(provider, start_date, end_date)
        previous_data = process_provider_data(provider, prev_start, prev_end)
        if current_data:
            prev_boxes = previous_data['total_boxes'] if previous_data else 0
            current_data['trend'] = calculate_trend(current_data['total_boxes'], prev_boxes)
            providers_data.append(current_data)
    providers_data.sort(key=lambda x: x['total_boxes'], reverse=True)
    winner = None
    if providers_data and providers_data[0]['total_boxes'] > 0:
        winner = providers_data[0]
        winner['achievements'] = get_provider_achievements(winner, True, winner['trend'])
    return jsonify({'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(), 'winner': winner, 'providers': providers_data})

@app.route('/api/flight-load')
def api_flight_load():
    start_date, end_date = parse_date_range(request)
    providers_data = []
    for provider in PROVIDERS:
        data = process_provider_data(provider, start_date, end_date)
        if data:
            providers_data.append(data)
    flights = [
        {'name': 'Tuesday Flight (Mon + Tue)', 'days': ['Mon', 'Tue']},
        {'name': 'Thursday Flight (Wed + Thu)', 'days': ['Wed', 'Thu']},
        {'name': 'Saturday Flight (Fri + Sat)', 'days': ['Fri', 'Sat']}
    ]
    flight_data = []
    for flight in flights:
        fi = {'name': flight['name'], 'total_orders': 0, 'total_boxes': 0, 'total_weight': 0, 'providers': []}
        for provider in providers_data:
            pf = {'name': provider['name'], 'color': provider['color'], 'orders': 0, 'boxes': 0, 'weight': 0}
            for region_data in provider['regions'].values():
                for day in flight['days']:
                    dd = region_data['days'].get(day, {})
                    pf['orders'] += dd.get('orders', 0)
                    pf['boxes'] += dd.get('boxes', 0)
                    pf['weight'] += dd.get('weight', 0)
            fi['total_orders'] += pf['orders']
            fi['total_boxes'] += pf['boxes']
            fi['total_weight'] += pf['weight']
            fi['providers'].append(pf)
        fi['providers'].sort(key=lambda x: x['boxes'], reverse=True)
        flight_data.append(fi)
    return jsonify({'flights': flight_data})

@app.route('/api/daily-region-summary')
def api_daily_region_summary():
    start_date, end_date = parse_date_range(request)
    result = {
        'totals': {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0},
        'providers': []
    }
    for provider in PROVIDERS:
        pd = {'name': provider['short'], 'color': provider['color'], 'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0, 'regions': {}}
        rows = fetch_sheet_data(provider['sheet'])
        if not rows:
            result['providers'].append(pd)
            continue
        for row_idx, row in enumerate(rows):
            if row_idx < provider['start_row'] - 1:
                continue
            try:
                if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col']):
                    continue
                date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
                parsed_date = parse_date(date_val)
                if not parsed_date or not (start_date <= parsed_date <= end_date):
                    continue
                region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
                if region in INVALID_REGIONS or not region:
                    continue
                try:
                    boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
                except:
                    boxes = 0
                try:
                    weight = float(row[provider['weight_col']].replace(',', '')) if row[provider['weight_col']].strip() else 0.0
                except:
                    weight = 0.0
                pd['orders'] += 1; pd['boxes'] += boxes; pd['weight'] += weight
                if weight < 20: pd['under20'] += 1
                else: pd['over20'] += 1
                if region not in pd['regions']:
                    pd['regions'][region] = {'name': region, 'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0}
                pd['regions'][region]['orders'] += 1
                pd['regions'][region]['boxes'] += boxes
                pd['regions'][region]['weight'] += weight
                if weight < 20: pd['regions'][region]['under20'] += 1
                else: pd['regions'][region]['over20'] += 1
            except:
                continue
        pd['regions'] = sorted(pd['regions'].values(), key=lambda x: x['boxes'], reverse=True)
        result['totals']['orders'] += pd['orders']
        result['totals']['boxes'] += pd['boxes']
        result['totals']['weight'] += pd['weight']
        result['totals']['under20'] += pd['under20']
        result['totals']['over20'] += pd['over20']
        result['providers'].append(pd)
    result['providers'].sort(key=lambda x: x['boxes'], reverse=True)
    return jsonify(result)

@app.route('/api/analytics-data')
def api_analytics_data():
    start_date, end_date = parse_date_range(request)
    result = {'totals': {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0},
              'trend': {'labels': [], 'orders': [], 'boxes': []}, 'providers': [], 'regions': []}
    provider_data = {}
    region_data = {}
    trend_data = defaultdict(lambda: {'orders': 0, 'boxes': 0})
    days_diff = (end_date - start_date).days + 1
    for provider in PROVIDERS:
        pkey = provider['short']
        provider_data[pkey] = {'name': provider['short'], 'color': provider['color'], 'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0}
        rows = fetch_sheet_data(provider['sheet'])
        if not rows:
            continue
        for row_idx, row in enumerate(rows):
            if row_idx < provider['start_row'] - 1:
                continue
            try:
                if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col']):
                    continue
                date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
                parsed_date = parse_date(date_val)
                if not parsed_date or not (start_date <= parsed_date <= end_date):
                    continue
                region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
                if region in INVALID_REGIONS or not region:
                    continue
                try:
                    boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
                except:
                    boxes = 0
                try:
                    weight = float(row[provider['weight_col']].replace(',', '')) if row[provider['weight_col']].strip() else 0.0
                except:
                    weight = 0.0
                result['totals']['orders'] += 1; result['totals']['boxes'] += boxes; result['totals']['weight'] += weight
                if weight < 20: result['totals']['under20'] += 1
                else: result['totals']['over20'] += 1
                provider_data[pkey]['orders'] += 1; provider_data[pkey]['boxes'] += boxes; provider_data[pkey]['weight'] += weight
                if weight < 20: provider_data[pkey]['under20'] += 1
                else: provider_data[pkey]['over20'] += 1
                if region not in region_data:
                    region_data[region] = {'name': region, 'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0}
                region_data[region]['orders'] += 1; region_data[region]['boxes'] += boxes; region_data[region]['weight'] += weight
                if weight < 20: region_data[region]['under20'] += 1
                else: region_data[region]['over20'] += 1
                if days_diff <= 1:
                    date_key = parsed_date.strftime('%H:00')
                elif days_diff <= 31:
                    date_key = parsed_date.strftime('%b %d')
                else:
                    date_key = parsed_date.strftime('%b %Y')
                trend_data[date_key]['orders'] += 1; trend_data[date_key]['boxes'] += boxes
            except:
                continue
    if days_diff <= 1:
        labels = [f'{h:02d}:00' for h in range(24)]
    elif days_diff <= 31:
        labels = [(start_date + timedelta(days=i)).strftime('%b %d') for i in range(days_diff)]
    else:
        seen = []
        d = start_date
        while d <= end_date:
            lbl = d.strftime('%b %Y')
            if lbl not in seen: seen.append(lbl)
            d = d + timedelta(days=32)
            d = d.replace(day=1)
        labels = seen
    result['trend']['labels'] = labels
    for lbl in labels:
        result['trend']['orders'].append(trend_data[lbl]['orders'])
        result['trend']['boxes'].append(trend_data[lbl]['boxes'])
    result['providers'] = sorted(provider_data.values(), key=lambda x: x['boxes'], reverse=True)
    result['regions'] = sorted(region_data.values(), key=lambda x: x['boxes'], reverse=True)
    return jsonify(result)

@app.route('/api/kpi')
def api_kpi():
    start_date, end_date = parse_date_range(request)
    prev_start = start_date - (end_date - start_date) - timedelta(seconds=1)
    prev_end = start_date - timedelta(seconds=1)
    total_orders = 0; total_boxes = 0; total_weight = 0
    prev_orders = 0; prev_boxes = 0; prev_weight = 0
    all_regions = set(); daily_totals = defaultdict(int)
    provider_totals = {}; region_totals = defaultdict(int)
    for provider in PROVIDERS:
        current_data = process_provider_data(provider, start_date, end_date)
        previous_data = process_provider_data(provider, prev_start, prev_end)
        if current_data:
            total_orders += current_data['total_orders']; total_boxes += current_data['total_boxes']; total_weight += current_data['total_weight']
            all_regions.update(current_data['regions'].keys())
            provider_totals[current_data['short']] = current_data['total_boxes']
            for day, data in current_data['daily_totals'].items():
                daily_totals[day] += data['orders']
            for region_name, region_info in current_data['regions'].items():
                for day_data in region_info['days'].values():
                    region_totals[region_name] += day_data['boxes']
        if previous_data:
            prev_orders += previous_data['total_orders']; prev_boxes += previous_data['total_boxes']; prev_weight += previous_data['total_weight']
    days_in_range = (end_date - start_date).days + 1
    best_day = max(daily_totals, key=daily_totals.get) if daily_totals else 'N/A'
    top_provider = max(provider_totals, key=provider_totals.get) if provider_totals else 'N/A'
    top_region = max(region_totals, key=region_totals.get) if region_totals else 'N/A'
    return jsonify({
        'total_orders': total_orders, 'total_boxes': total_boxes, 'total_weight': total_weight,
        'avg_boxes_per_day': total_boxes / days_in_range if days_in_range > 0 else 0,
        'avg_weight_per_order': total_weight / total_orders if total_orders > 0 else 0,
        'active_regions': len(all_regions), 'top_provider': top_provider,
        'top_region': top_region, 'best_day': best_day,
        'boxes_trend': calculate_trend(total_boxes, prev_boxes),
        'orders_trend': calculate_trend(total_orders, prev_orders),
        'weight_trend': calculate_trend(total_weight, prev_weight)
    })

@app.route('/api/regions')
def api_regions():
    start_date, end_date = parse_date_range(request)
    region_data = defaultdict(lambda: {'orders': 0, 'boxes': 0, 'weight': 0})
    for provider in PROVIDERS:
        data = process_provider_data(provider, start_date, end_date)
        if data:
            for region_name, region_info in data['regions'].items():
                for day_data in region_info['days'].values():
                    region_data[region_name]['orders'] += day_data['orders']
                    region_data[region_name]['boxes'] += day_data['boxes']
                    region_data[region_name]['weight'] += day_data['weight']
    regions = [{'name': k, **v} for k, v in region_data.items()]
    regions.sort(key=lambda x: x['orders'], reverse=True)
    return jsonify({'regions': regions})

@app.route('/api/monthly')
def api_monthly():
    start_date, end_date = parse_date_range(request)
    total_orders = 0; total_boxes = 0; total_weight = 0
    provider_totals = defaultdict(lambda: {'orders': 0, 'boxes': 0, 'weight': 0, 'color': '#64748b'})
    weeks_data = []
    current = start_date
    week_num = 1
    while current <= end_date:
        week_start = current - timedelta(days=current.weekday())
        week_end_dt = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        week_boxes = 0
        for provider in PROVIDERS:
            data = process_provider_data(provider, max(week_start, start_date), min(week_end_dt, end_date))
            if data:
                total_orders += data['total_orders']; total_boxes += data['total_boxes']; total_weight += data['total_weight']
                week_boxes += data['total_boxes']
                provider_totals[data['name']]['orders'] += data['total_orders']
                provider_totals[data['name']]['boxes'] += data['total_boxes']
                provider_totals[data['name']]['weight'] += data['total_weight']
                provider_totals[data['name']]['color'] = data['color']
        weeks_data.append({'label': f'Week {week_num}', 'boxes': week_boxes})
        current = week_start + timedelta(days=7); week_num += 1
    providers = [{'name': k, **v} for k, v in provider_totals.items()]
    providers.sort(key=lambda x: x['boxes'], reverse=True)
    days_in_range = (end_date - start_date).days + 1
    return jsonify({'total_orders': total_orders, 'total_boxes': total_boxes, 'total_weight': total_weight, 'avg_per_day': total_orders / days_in_range if days_in_range > 0 else 0, 'weeks': weeks_data, 'providers': providers})

@app.route('/api/whatsapp')
def api_whatsapp():
    start_date, end_date = parse_date_range(request)
    providers_data = []
    total_orders = 0; total_boxes = 0; total_weight = 0
    for provider in PROVIDERS:
        data = process_provider_data(provider, start_date, end_date)
        if data:
            providers_data.append(data)
            total_orders += data['total_orders']; total_boxes += data['total_boxes']; total_weight += data['total_weight']
    providers_data.sort(key=lambda x: x['total_boxes'], reverse=True)
    date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    report = f"📊 *3PL Report*\n📅 {date_range}\n\n━━━━━━━━━━━━━━━━━━━━\n\n🏆 *PROVIDER RANKING*\n\n"
    medals = ['🥇','🥈','🥉','4️⃣','5️⃣','6️⃣']
    for i, p in enumerate(providers_data):
        report += f"{medals[i]} *{p['short']}*\n   📦 {p['total_boxes']:,} boxes | ⚖️ {p['total_weight']:,.1f} kg\n\n"
    report += f"━━━━━━━━━━━━━━━━━━━━\n\n📈 *TOTALS*\n\n📋 Orders: *{total_orders:,}*\n📦 Boxes: *{total_boxes:,}*\n⚖️ Weight: *{total_weight:,.1f} kg*\n\n━━━━━━━━━━━━━━━━━━━━\n_Generated by 3PL Dashboard_"
    return jsonify({'report': report})

@app.route('/api/daily-summary')
def api_daily_summary():
    start_date, end_date = parse_date_range(request)
    result = {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0, 'regions': {}}
    for provider in PROVIDERS:
        rows = fetch_sheet_data(provider['sheet'])
        if not rows:
            continue
        for row_idx, row in enumerate(rows):
            if row_idx < provider['start_row'] - 1:
                continue
            try:
                if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col']):
                    continue
                date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
                parsed_date = parse_date(date_val)
                if not parsed_date or not (start_date <= parsed_date <= end_date):
                    continue
                region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
                if region in INVALID_REGIONS or not region:
                    continue
                try:
                    boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
                except:
                    boxes = 0
                try:
                    weight = float(row[provider['weight_col']].replace(',', '')) if row[provider['weight_col']].strip() else 0.0
                except:
                    weight = 0.0
                result['orders'] += 1; result['boxes'] += boxes; result['weight'] += weight
                if weight < 20: result['under20'] += 1
                else: result['over20'] += 1
                if region not in result['regions']:
                    result['regions'][region] = {'name': region, 'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0}
                result['regions'][region]['orders'] += 1; result['regions'][region]['boxes'] += boxes; result['regions'][region]['weight'] += weight
                if weight < 20: result['regions'][region]['under20'] += 1
                else: result['regions'][region]['over20'] += 1
            except:
                continue
    result['regions'] = sorted(result['regions'].values(), key=lambda x: x['boxes'], reverse=True)
    return jsonify(result)

@app.route('/api/clear-cache')
def clear_cache():
    global CACHE, _bc, _sc, _jc, _rc, _snc
    CACHE = {}
    _bc["data"] = None; _bc["time"] = 0
    _sc["data"] = None; _sc["time"] = 0
    _jc["data"] = None; _jc["time"] = 0
    _rc["data"] = None; _rc["time"] = 0
    _snc.clear()
    return jsonify({'status': 'success', 'message': 'Cache cleared'})

@app.route('/api/forecast')
def api_forecast():
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    predictions = []
    for _ in range(6):
        predictions.append({
            'orders': random.randint(50, 200),
            'boxes': random.randint(80, 300),
            'weight': round(random.uniform(500, 2500), 1)
        })
    return jsonify([{'day': d, **predictions[i]} for i, d in enumerate(days)])

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    results = []
    for provider in PROVIDERS:
        rows = fetch_sheet_data(provider['sheet'])
        if not rows:
            continue
        for row_idx, row in enumerate(rows):
            if row_idx < provider['start_row'] - 1:
                continue
            try:
                order_col = provider.get('order_col', 0)
                if order_col >= len(row):
                    continue
                if query in row[order_col].strip().lower():
                    date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
                    parsed = parse_date(date_val)
                    date_str = parsed.strftime('%Y-%m-%d') if parsed else 'N/A'
                    region = row[provider['region_col']].strip() if provider['region_col'] < len(row) else 'N/A'
                    weight = float(row[provider['weight_col']].replace(',', '')) if provider['weight_col'] < len(row) else 0
                    results.append({
                        'provider': provider['name'],
                        'order_id': row[order_col],
                        'date': date_str,
                        'region': region,
                        'weight': weight,
                        'color': provider['color']
                    })
                    if len(results) >= 20:
                        break
            except:
                continue
    return jsonify(results)

notifications = []

@app.route('/api/notifications')
def api_notifications():
    global notifications
    if notifications:
        msg = notifications.pop(0)
        return jsonify({'message': msg})
    return jsonify({'message': None})

def add_notification(msg):
    notifications.append(msg)

@app.route('/api/orders')
@login_required
def api_orders():
    if session.get('role') == 'guest':
        return jsonify({"error": "Access denied"}), 403
    provider_short = request.args.get('provider')
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    region = request.args.get('region', '').strip()
    day = request.args.get('day')
    if not provider_short or not start_str or not end_str:
        return jsonify({"error": "Missing parameters"}), 400
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except:
        return jsonify({"error": "Invalid date"}), 400
    def collect(provider, rows):
        out = []
        for row_idx, row in enumerate(rows):
            if row_idx < provider['start_row'] - 1: continue
            try:
                if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col'], provider.get('order_col', 0)): continue
                date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
                parsed_date = parse_date(date_val)
                if not parsed_date or not (start_date <= parsed_date <= end_date): continue
                row_region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
                if region and row_region != region: continue
                if day:
                    dd = datetime.strptime(day, '%Y-%m-%d')
                    if parsed_date.date() != dd.date(): continue
                order_id = row[provider.get('order_col', 0)].strip() if provider.get('order_col', 0) < len(row) else 'N/A'
                country_col = provider.get('country_col')
                country = row[country_col].strip() if country_col is not None and country_col < len(row) else ''
                try: boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
                except: boxes = 0
                try: weight = round(float(row[provider['weight_col']].replace(',', '')), 1) if row[provider['weight_col']].strip() else 0.0
                except: weight = 0.0
                out.append({'order_id': order_id, 'date': parsed_date.strftime('%Y-%m-%d'), 'region': row_region, 'country': country, 'boxes': boxes, 'weight': weight})
            except: continue
        return out
    all_orders = []
    provider_display = provider_short
    if provider_short == 'all':
        provider_display = 'All Providers'
        for p in PROVIDERS:
            rows = fetch_sheet_data(p['sheet'])
            if rows: all_orders.extend(collect(p, rows))
    else:
        p = next((x for x in PROVIDERS if x['short'] == provider_short), None)
        if not p: return jsonify({"error": "Provider not found"}), 404
        rows = fetch_sheet_data(p['sheet'])
        if rows: all_orders = collect(p, rows)
        provider_display = provider_short
    all_orders.sort(key=lambda x: x['date'])
    total_boxes = sum(o['boxes'] for o in all_orders)
    total_weight = round(sum(o['weight'] for o in all_orders), 1)
    date_range = f"{start_str} → {end_str}" if start_str != end_str else start_str
    return jsonify({
        "provider": provider_display, "region": region, "date_range": date_range,
        "total_orders": len(all_orders), "total_boxes": total_boxes, "total_weight": total_weight,
        "orders": all_orders
    })

@app.route('/api/order-lookup')
@login_required
def api_order_lookup():
    if (session.get('email') or '').strip().lower() != ORDER_LOOKUP_EMAIL:
        return jsonify({"error": "Access denied"}), 403
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"results": [], "error": "Enter an order number"})
    q_upper = q.upper()
    now = time.time()
    def fetch_source(src):
        key = f"{src['sid']}_{src['tab']}"
        cached = _olc.get(key)
        if cached and (now - cached["time"]) < 600:
            rows = cached["rows"]
        else:
            # Tab name is hardcoded — skip resolve_sheet_name entirely
            # Limit to columns A:AN (index 0-39) to reduce payload size
            api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{src['sid']}/values/{urllib.parse.quote(src['tab'] + '!A:AN')}"
            try:
                req = urllib.request.Request(api_url, headers=get_auth_headers())
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = json.loads(r.read().decode("utf-8"))
                rows = [[str(c) for c in row] for row in raw.get("values", [])]
                _olc[key] = {"rows": rows, "time": now}
            except Exception as e:
                print(f"[ORDER_LOOKUP] {src['name']}: {e}")
                return src['name'], []
        matches = []
        for row in rows[src['start']:]:
            p = row + [''] * 60
            order_val = p[src['o']].strip()
            if not order_val: continue
            if q_upper not in order_val.upper(): continue
            matches.append({
                "provider": src['name'],
                "order": order_val,
                "boxes": p[src['b']].strip(),
                "cw": p[src['cw']].strip(),
                "vendor": p[src['v']].strip(),
                "title": p[src['ti']].strip(),
                "item_count": p[src['ic']].strip(),
                "customer": p[src['c']].strip(),
                "country": p[src['cn']].strip(),
                "tid": p[src['tid']].strip(),
                "mawb": p[src['mawb']].strip(),
            })
        return src['name'], matches
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_source, src): src['name'] for src in ORDER_LOOKUP_SOURCES}
        for f in concurrent.futures.as_completed(futs, timeout=30):
            try:
                name, matches = f.result()
                all_results.extend(matches)
            except: pass
    all_results.sort(key=lambda x: x['order'])
    return jsonify({"results": all_results, "total": len(all_results), "query": q})

@app.route('/api/order-lookup/warmup')
@login_required
def api_order_lookup_warmup():
    """Pre-fetches all 6 provider sheets into cache so first search is instant."""
    if (session.get('email') or '').strip().lower() != ORDER_LOOKUP_EMAIL:
        return jsonify({"error": "Access denied"}), 403
    now = time.time()
    fetched = []
    errors = []
    def warm_source(src):
        key = f"{src['sid']}_{src['tab']}"
        cached = _olc.get(key)
        if cached and (now - cached["time"]) < 600:
            return src['name'], True, "cached"
        api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{src['sid']}/values/{urllib.parse.quote(src['tab'] + '!A:AN')}"
        try:
            req = urllib.request.Request(api_url, headers=get_auth_headers())
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = json.loads(r.read().decode("utf-8"))
            rows = [[str(c) for c in row] for row in raw.get("values", [])]
            _olc[key] = {"rows": rows, "time": now}
            return src['name'], True, len(rows)
        except Exception as e:
            print(f"[WARMUP] {src['name']}: {e}")
            return src['name'], False, str(e)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(warm_source, src) for src in ORDER_LOOKUP_SOURCES]
        for f in concurrent.futures.as_completed(futs, timeout=35):
            try:
                name, ok, info = f.result()
                if ok:
                    fetched.append(name)
                else:
                    errors.append(name)
            except Exception as e:
                errors.append(str(e))
    return jsonify({"status": "ok", "ready": fetched, "errors": errors})

@app.route('/order-lookup', strict_slashes=False)
@login_required
def order_lookup_page():
    if (session.get('email') or '').strip().lower() != ORDER_LOOKUP_EMAIL:
        return "Access Denied", 403
    return ORDER_LOOKUP_HTML

@app.route('/orders')
@login_required
def order_details():
    if session.get('role') == 'guest':
        return "Access Denied. Guests cannot view detailed Order IDs. Please login as Admin.", 403

    provider_short = request.args.get('provider')
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    region = request.args.get('region', '').strip()
    day = request.args.get('day')
    
    if not provider_short or not start_str or not end_str:
        return "Missing parameters", 400
    
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except:
        return "Invalid date", 400
    
    if provider_short == 'all':
        all_orders = []
        for provider in PROVIDERS:
            rows = fetch_sheet_data(provider['sheet'])
            if not rows:
                continue
            for row_idx, row in enumerate(rows):
                if row_idx < provider['start_row'] - 1:
                    continue
                try:
                    if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col'], provider.get('order_col', 0)):
                        continue
                    date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
                    parsed_date = parse_date(date_val)
                    if not parsed_date or not (start_date <= parsed_date <= end_date):
                        continue
                    row_region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
                    if region and row_region != region:
                        continue
                    if day:
                        day_date = datetime.strptime(day, '%Y-%m-%d')
                        if parsed_date.date() != day_date.date():
                            continue
                    order_id = row[provider.get('order_col', 0)].strip() if provider.get('order_col', 0) < len(row) else 'N/A'
                    try:
                        boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
                    except:
                        boxes = 0
                    try:
                        weight = float(row[provider['weight_col']].replace(',', '')) if row[provider['weight_col']].strip() else 0.0
                    except:
                        weight = 0.0
                    all_orders.append({
                        'order_id': order_id,
                        'date': parsed_date.strftime('%Y-%m-%d'),
                        'region': row_region,
                        'boxes': boxes,
                        'weight': weight
                    })
                except:
                    continue
        all_orders.sort(key=lambda x: x['date'])
        orders = all_orders
        provider_short_display = 'All Providers'
    else:
        provider = next((p for p in PROVIDERS if p['short'] == provider_short), None)
        if not provider:
            return "Provider not found", 404
        
        rows = fetch_sheet_data(provider['sheet'])
        if not rows:
            return "No data", 404
        
        orders = []
        for row_idx, row in enumerate(rows):
            if row_idx < provider['start_row'] - 1:
                continue
            try:
                if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col'], provider.get('order_col', 0)):
                    continue
                
                date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
                parsed_date = parse_date(date_val)
                if not parsed_date:
                    continue
                if not (start_date <= parsed_date <= end_date):
                    continue
                
                row_region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
                if region and row_region != region:
                    continue
                
                if day:
                    day_date = datetime.strptime(day, '%Y-%m-%d')
                    if parsed_date.date() != day_date.date():
                        continue
                
                order_id = row[provider.get('order_col', 0)].strip() if provider.get('order_col', 0) < len(row) else 'N/A'
                
                try:
                    boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
                except:
                    boxes = 0
                try:
                    weight = float(row[provider['weight_col']].replace(',', '')) if row[provider['weight_col']].strip() else 0.0
                except:
                    weight = 0.0
                
                orders.append({
                    'order_id': order_id,
                    'date': parsed_date.strftime('%Y-%m-%d'),
                    'region': row_region,
                    'boxes': boxes,
                    'weight': weight
                })
            except Exception as e:
                continue
        orders.sort(key=lambda x: x['date'])
        provider_short_display = provider_short
    
    mode_class = 'guest-mode' if session.get('role') == 'guest' else 'admin-mode'
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Order Details - {{ provider_short }}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {{ favicon|safe }}
    <style>
        body { background: #f8fafc; color: #1e293b; font-family: 'Inter', sans-serif; padding: 20px; }
        h1 { color: #4f46e5; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #f1f5f9; color: #475569; padding: 10px; text-align: left; }
        td { padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }
        tr:hover { background: #f1f5f9; }
        .back-btn { display: inline-block; margin-bottom: 20px; padding: 8px 16px; background: #4f46e5; color: #ffffff; text-decoration: none; border-radius: 6px; }
        .stats { display: flex; gap: 20px; margin-bottom: 20px; }
        .stat-box { background: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #4f46e5; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
        .download-btn { background: none; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px 8px; font-size: 12px; cursor: pointer; color: #64748b; display: inline-flex; align-items: center; gap: 4px; margin-left: 10px; }
        .download-btn:hover { background: #f1f5f9; color: #4f46e5; border-color: #4f46e5; }
        .last-update { font-size: 10px; color: #64748b; text-align: center; margin-top: 20px; }
    </style>
</head>
<body class="''' + mode_class + '''">
    <a href="javascript:history.back()" class="back-btn">← Back</a>
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <h1>Orders - {{ provider_short }}</h1>
        <button class="download-btn" onclick="exportTableToCSV(document.querySelector('table'), '{{ provider_short }}_orders.csv')">📥 CSV</button>
    </div>
    <div class="stats">
        <div class="stat-box">Total Orders: {{ orders|length }}</div>
        <div class="stat-box">Total Boxes: {{ orders|sum(attribute='boxes') }}</div>
        <div class="stat-box">Total Weight: {{ "%.1f"|format(orders|sum(attribute='weight')) }} kg</div>
    </div>
    {% if region %}<p><strong>Region:</strong> {{ region }}</p>{% endif %}
    {% if day %}<p><strong>Date:</strong> {{ day }}</p>{% endif %}
    <table>
        <thead>
            <tr>
                <th>Order ID</th>
                <th>Date</th>
                <th>Region</th>
                <th>Boxes</th>
                <th>Weight (kg)</th>
            </tr>
        </thead>
        <tbody>
            {% for order in orders %}
            <tr>
                <td>{{ order.order_id }}</td>
                <td>{{ order.date }}</td>
                <td>{{ order.region }}</td>
                <td>{{ order.boxes }}</td>
                <td>{{ "%.1f"|format(order.weight) }}</td>
            </tr>
            {% else %}
            <tr><td colspan="5" style="text-align:center;">No orders found</td></tr>
            {% endfor %}
        </tbody>
    </table>
    <div class="last-update">Last update: <span id="last-update-time">Never</span></div>
    <script>
        function exportTableToCSV(table, filename) {
            let csv = [];
            let rows = table.querySelectorAll("tr");
            for (let i = 0; i < rows.length; i++) {
                let row = [], cols = rows[i].querySelectorAll("td, th");
                for (let j = 0; j < cols.length; j++) {
                    let data = cols[j].innerText.replace(/(\\r\\n|\\n|\\r)/gm, "").replace(/"/g, '""');
                    row.push('"' + data + '"');
                }
                csv.push(row.join(","));
            }
            let csvFile = new Blob([csv.join("\\n")], {type: "text/csv"});
            let dl = document.createElement("a");
            dl.download = filename; dl.href = window.URL.createObjectURL(csvFile);
            dl.style.display = "none"; document.body.appendChild(dl); dl.click();
        }
        document.getElementById('last-update-time').textContent = new Date().toLocaleString();
    </script>
</body>
</html>
    ''', orders=orders, provider_short=provider_short_display, region=region, day=day, favicon=FAVICON)

# ==============================================================================
# ==============================================================================
# BUNDLING INTELLIGENCE HUB — COMPLETE FINAL VERSION
# ==============================================================================
import urllib.request, csv, re, ssl, time, math, concurrent.futures
from datetime import datetime, timedelta
from flask import jsonify, request, session, render_template_string

_bc={"data":None,"time":0}; _jc={"data":None,"time":0}; _sc={"data":None,"time":0}; _rc={"data":None,"time":0}
_snc={}  # sheet name cache: (sheet_id, gid) -> tab name (permanent, tab names don't change)
CD=600
RATES_CD=3600

FULL_ACCESS = {
    "husaain@joinfleek.com",
    "wahab.chippa@joinfleek.com",
    "albash@joinfleek.com",
    "waris@joinfleek.com",
    "moiz@joinfleek.com",
}

def user_mode():
    email=(session.get("email") or session.get("user_email") or session.get("username") or "").lower().strip()
    role=(session.get("role") or "").lower().strip()
    if role=="admin" or email in FULL_ACCESS: return "full"
    if email or role or session.get("user"): return "guest"
    return None

JS=("https://docs.google.com/spreadsheets/d/e/2PACX-1vQRsiVaciOMON0xaXXEi1guBYrqfVNpD-j4My_9YokGd5kftqjAXvri5c_gLB_VRXeoDLzEtz9h5y8x/pub?gid=1409345116&single=true&output=csv")
SS=("https://docs.google.com/spreadsheets/d/e/2PACX-1vRiyUpVH_MmkslyY7VvaltDXF5Gmj8GrE6i3YNmyOGEIsRh0QcEzmcYWT7HUSNLnB165H6yeZvPzgpH/pub?gid=1570463436&single=true&output=csv")

def estimate_item_weight(title, item_count):
    """Estimate weight per order using category keywords + piece count."""
    t=(title or "").lower(); ic=max(item_count,1)
    # Category weight per piece (kg)
    if any(w in t for w in ['jacket','coat','blazer','puffer','parka','overcoat','bomber']): pw=0.55
    elif any(w in t for w in ['shoe','shoes','boot','boots','sneaker','sneakers','heel','heels','trainer','loafer','sandal','footwear']): pw=0.70
    elif any(w in t for w in ['jeans','denim','trouser','trousers','pant','pants','chino','cargo','legging']): pw=0.48
    elif any(w in t for w in ['dress','gown','jumpsuit','playsuit','romper','overall']): pw=0.38
    elif any(w in t for w in ['sweater','hoodie','sweatshirt','pullover','knitwear','knit','fleece']): pw=0.42
    elif any(w in t for w in ['shirt','blouse','tshirt','t-shirt','polo','tunic','top','crop','vest','tank']): pw=0.28
    elif any(w in t for w in ['skirt','shorts','short']): pw=0.22
    elif any(w in t for w in ['bag','handbag','purse','backpack','tote','clutch','satchel']): pw=0.45
    elif any(w in t for w in ['sock','socks','stocking','tight','tights','hosiery']): pw=0.08
    elif any(w in t for w in ['underwear','brief','briefs','bra','bralette','lingerie','thong','knicker','panty']): pw=0.10
    elif any(w in t for w in ['watch','jewel','jewellery','jewelry','necklace','ring','earring','bracelet','pendant','brooch']): pw=0.14
    elif any(w in t for w in ['hat','cap','beanie','beret','scarf','gloves','mitten']): pw=0.12
    elif any(w in t for w in ['belt','tie','bow tie','cufflink']): pw=0.15
    elif any(w in t for w in ['phone','laptop','tablet','electronic','console','camera','speaker','tech']): pw=0.60
    elif any(w in t for w in ['tracksuit','suit','set','co-ord']): pw=0.65
    else: pw=0.30  # generic clothing default
    return pw * ic

def sd(d):
    for fmt in ("%Y-%m-%d","%d/%m/%Y","%m/%d/%Y","%d-%b-%y","%d-%b-%Y","%Y/%m/%d"):
        try: return datetime.strptime(str(d).split()[0],fmt).strftime("%Y-%m-%d")
        except: pass
    return "1970-01-01"

def ctids(raw):
    raw=str(raw).strip()
    # Reject blank, placeholders, formula artifacts
    if not raw: return []
    if raw.startswith("="): return []  # Google Sheets formula leaked
    if raw.lower() in ["pending","none","n/a","-","tbd","update soon","#n/a","#ref!","#value!","#error!"]: return []
    # Only extract real tracking ID patterns:
    # 1550xxxxxxxxxx / 1500xxxxxxxxxx (15-16 digits)
    # JDxxxxxxxxxx, YTxxxxxxxxxx, 1Zxxxxxxxxxxxxxxxx (UPS)
    PATTERNS=[
        r"\b(1[56]\d{12,14})\b",          # 1550... / 1560...
        r"\b(0?15[05]\d{10,13})\b",       # 01550... 
        r"\b(1Z[A-Z0-9]{15,18})\b",        # UPS
        r"\b(JD\d{10,18})\b",             # DHL
        r"\b(YT\d{10,18})\b",             # Yodel
        r"\b(TT\d{10,18})\b",             # TT
    ]
    out=[]
    for pat in PATTERNS:
        for m in re.finditer(pat,raw,re.IGNORECASE):
            t=m.group(1).strip()
            if t not in out: out.append(t)
    return out

def pdt(val):
    if not val or str(val).strip() in ["","nan","N/A","-","None","null"]: return None
    v=str(val).strip()
    for fmt in ["%B %d, %Y, %H:%M","%B %d, %Y %H:%M:%S","%B %d, %Y %H:%M","%B %d, %Y",
                "%Y-%m-%d %H:%M:%S","%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S.%f",
                "%d/%m/%Y %H:%M:%S","%d/%m/%Y %H:%M","%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%d-%b-%Y","%d %b %Y"]:
        try: return datetime.strptime(v.split("+")[0].strip(),fmt)
        except: pass
    return None

def dayb(a,b):
    if a and b:
        d=(b-a).total_seconds()
        if d<0: return None
        return f"{int(d/3600)}h" if d<86400 else f"{d/86400:.1f}d"
    return None

def fdt(dt): return dt.strftime("%d %b %Y, %H:%M") if dt else None

def grg(country):
    if not country: return "EU"
    c=country.strip().lower()
    m={"united kingdom":"United Kingdom","uk":"United Kingdom","gb":"United Kingdom",
       "united states":"United States","usa":"United States","us":"United States",
       "australia":"Australia","switzerland":"Switzerland","new zealand":"New Zealand",
       "canada":"Canada","china":"China","ghana":"Ghana","japan":"Japan","india":"India",
       "philippines":"Philippines","saudi arabia":"Saudi Arabia","saudia arabia":"Saudi Arabia",
       "singapore":"Singapore","south africa":"South Africa","south korea":"South Korea",
       "thailand":"Thailand","malaysia":"Malaysia","indonesia":"Indonesia","hong kong":"Hong Kong",
       "uae":"UAE","united arab emirates":"UAE","nigeria":"Nigeria","kenya":"Kenya"}
    return m.get(c,"EU")

def ctx():
    c=ssl.create_default_context(); c.check_hostname=False; c.verify_mode=ssl.CERT_NONE; return c

def parse_weight_bracket(s):
    """Parse '7-8 kg' -> (7,8), '30+ kg' -> (30,9999), '0-1 kg' -> (0,1)"""
    s=str(s).strip().lower().replace("kg","").strip()
    if "+" in s:
        try: return (float(re.sub(r"[^0-9.]","",s.replace("+",""))),9999.0)
        except: return None
    if "-" in s:
        parts=s.split("-")
        try: return (float(re.sub(r"[^0-9.]","",parts[0])),float(re.sub(r"[^0-9.]","",parts[1])))
        except: return None
    return None

def lookup_rate(rm_brackets, country, billed_kg, default=4.50):
    """
    rm_brackets: { country_lower: [(min,max,rate), ...] }
    billed_kg: ceil(actual_weight) — the charged kg
    Returns the matching per-kg rate.
    """
    ctry=str(country).strip().lower()
    # Try exact country match, then aliases
    ALIASES={
        "united kingdom":["uk","gb","england","britain","u.k","u.k."],
        "united states":["usa","us","america","u.s","u.s.a"],
        "united arab emirates":["uae","dubai","u.a.e"],
        "saudi arabia":["saudia arabia","ksa","saudi"],
        "south korea":["korea"],
        "new zealand":["nz"],
        "netherlands":["holland"],
    }
    candidates=[]
    if ctry in rm_brackets:
        candidates=rm_brackets[ctry]
    else:
        for canon,alts in ALIASES.items():
            if ctry in alts or ctry==canon:
                key=canon if canon in rm_brackets else next((a for a in alts if a in rm_brackets),None)
                if key: candidates=rm_brackets[key]; break
        if not candidates:
            # partial match
            for k,v in rm_brackets.items():
                if k in ctry or ctry in k:
                    candidates=v; break
    if not candidates:
        return default
    # Find bracket where billed_kg falls: min < billed <= max
    for (mn,mx,rate) in sorted(candidates,key=lambda x:x[0]):
        if mn < billed_kg <= mx:
            return rate
    # Fallback: nearest bracket (for edge cases like billed=0)
    if billed_kg<=candidates[0][1]: return candidates[0][2]
    return candidates[-1][2]  # heaviest bracket

def fetch_rates(cx):
    try:
        url="https://docs.google.com/spreadsheets/d/e/2PACX-1vRiyUpVH_MmkslyY7VvaltDXF5Gmj8GrE6i3YNmyOGEIsRh0QcEzmcYWT7HUSNLnB165H6yeZvPzgpH/pub?gid=1463817545&single=true&output=csv"
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=20,context=cx) as r:
            data=list(csv.reader(r.read().decode("utf-8",errors="ignore").splitlines()))
        # Col H=7: country, Col J=9: weight bracket, Col M=12: per kg rate
        COUNTRY_COL=7; BRACKET_COL=9; RATE_COL=12
        rm_brackets={}   # country_lower -> [(min,max,rate), ...]
        rm_flat={}       # country_lower -> default rate (heaviest bracket as fallback)
        for row in data[1:]:
            p=row+[""]*20
            ctry=str(p[COUNTRY_COL]).strip().lower()
            bracket_raw=str(p[BRACKET_COL]).strip()
            rate_raw=str(p[RATE_COL]).strip()
            if not ctry or ctry in ["country","shipping_address_country","","nan","#n/a"]: continue
            if not rate_raw: continue
            try:
                rate_val=float(re.sub(r"[^0-9.]","",rate_raw))
                if not (0.01<rate_val<500): continue
            except: continue
            bracket=parse_weight_bracket(bracket_raw)
            if ctry not in rm_brackets: rm_brackets[ctry]=[]
            if bracket:
                rm_brackets[ctry].append((bracket[0],bracket[1],rate_val))
            # Also keep a simple flat rate (average of all brackets)
            if ctry not in rm_flat: rm_flat[ctry]=[]
            rm_flat[ctry].append(rate_val)
        # Compute flat average per country as fallback
        rm_avg={k:round(sum(v)/len(v),4) for k,v in rm_flat.items() if v}
        countries=len(rm_brackets)
        sample={k:[f"{mn}-{mx}kg=£{r}" for mn,mx,r in v[:2]] for k,v in list(rm_brackets.items())[:3]}
        print(f"[RATES] Loaded {countries} countries with weight-bracket rates. Sample: {sample}")
        return "RATES",(rm_brackets,rm_avg)
    except Exception as e:
        print(f"[RATES] ERROR: {e}")
        return "RATES",({},{})

def fetch_status():
    global _sc
    now = time.time()
    if _sc["data"] and (now - _sc["time"]) < CD: return _sc["data"]
    try:
        # Status is in the Journey sheet — col E (idx 4) = order ID, col F (idx 5) = status
        sheet_id = "1493mgOui4QYrJ9hXGKaFHm2Bj21cqW51BkeX6gzWccg"
        gid = "1409345116"
        sheet_name = resolve_sheet_name(sheet_id, gid)
        if not sheet_name:
            print(f"[STATUS] gid {gid} not found"); return {}
        val_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{urllib.parse.quote(sheet_name)}"
        req = urllib.request.Request(val_url, headers=get_auth_headers())
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = json.loads(r.read().decode("utf-8"))
        rows_raw = raw.get("values", [])
        data = [[str(c) for c in row] for row in rows_raw]
        sm = {}
        for row in data[1:]:
            p = row + [""] * 20
            fid = str(p[4]).strip()   # Column E = order ID
            status = str(p[5]).strip() # Column F = status
            if fid and fid.lower() not in ["", "nan", "fleek_id", "fleek id", "order_id"] and status:
                sm[fid.upper()] = status
        print(f"[STATUS] loaded {len(sm)} statuses from journey sheet")
        _sc["data"] = sm; _sc["time"] = now; return sm
    except Exception as e:
        print(f"[STATUS] fetch error: {e}"); return {}

def fetch_journey():
    global _jc
    now = time.time()
    if _jc["data"] and (now - _jc["time"]) < CD: return _jc["data"]
    try:
        sheet_id = "1493mgOui4QYrJ9hXGKaFHm2Bj21cqW51BkeX6gzWccg"
        gid = "1409345116"
        sheet_name = resolve_sheet_name(sheet_id, gid)
        if not sheet_name:
            print(f"[JOURNEY] gid {gid} not found in spreadsheet"); return {}
        val_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{urllib.parse.quote(sheet_name)}"
        req = urllib.request.Request(val_url, headers=get_auth_headers())
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = json.loads(r.read().decode("utf-8"))
        rows_raw = raw.get("values", [])
        data = [[str(c) for c in row] for row in rows_raw]
        jm = {}
        for row in data[1:]:
            p = row + [""] * 100
            fid = str(p[4]).strip()
            if not fid or fid.lower() in ["", "nan", "fleek_id", "fleek id"]: continue
            jm[fid.upper()] = {
                "created_at": str(p[0]).strip(), "accepted_at": str(p[8]).strip(),
                "pickup_ready_at": str(p[9]).strip(), "cancelled_at": str(p[12]).strip(),
                "qc_pending_at": str(p[13]).strip(), "qc_approved_at": str(p[14]).strip(),
                "handedover_at": str(p[30]).strip(), "freight_at": str(p[31]).strip(),
                "courier_at": str(p[34]).strip(), "delivered_at": str(p[36]).strip()
            }
        _jc["data"] = jm; _jc["time"] = now
        return jm
    except Exception as e:
        print(f"[JOURNEY] fetch error: {e}")
        return {}

def fetch_sheet(name, url, col, start, cx):
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=get_auth_headers())
            with urllib.request.urlopen(req, timeout=30, context=cx) as r:
                data = list(csv.reader(r.read().decode("utf-8", errors="ignore").splitlines()))
            rows = []; lo = ld = lv = lc = lcn = lt = ""
            for row in data[start:]:
                if not row: continue
                p = row + [""] * 60
                ro = str(p[col["o"]]).strip(); rw = str(p[col["w"]]).strip(); rti = str(p[col["title"]]).strip()
                rw_clean = rw.replace("0", "").replace(".", "").strip()
                if not ro and not rw_clean and not rti: continue
                if ro: lo = ro
                co = ro if ro else lo
                if not co or not re.search(r"\d", co): continue
                try: rw_float = float(rw or 0)
                except: rw_float = 0
                if not ro and not rti and rw_float == 0: continue
                if co.lower() in ["n/a", "nan", "order", "orderid", "order id"]: continue
                
                dv = str(p[col["d"]]).strip()
                vv = str(p[col["v"]]).strip()
                cv = str(p[col["c"]]).strip()
                cnv = str(p[col["cn"]]).strip()
                tv = str(p[col["t"]]).strip()
                
                if dv: ld = dv
                if vv: lv = vv
                if cv: lc = cv
                if cnv: lcn = cnv
                if tv: lt = tv
                
                bxv = str(p[col["b"]]).strip()
                if not bxv and col.get("b2") is not None:
                    bxv2 = str(p[col["b2"]]).strip()
                    if bxv2 and re.match(r"^[0-9]+$", bxv2): bxv = bxv2
                    
                rows.append({
                    "order": co, "date": dv or ld, "date_std": sd(dv or ld),
                    "boxes": bxv, "weight": rw,
                    "vendor": vv or lv, "title": rti or "N/A", "item_count": str(p[col["ic"]]).strip() or "1",
                    "customer": cv or lc, "country": cnv or lcn, "tid": tv or lt
                })
            print(f"[OK] {name}: {len(rows)} rows")
            return name, rows
        except Exception as e:
            print(f"[WARN] {name} attempt {attempt+1}: {e}")
            if attempt == 0: time.sleep(0.5)
    return name, []

def fetch_all():
    global _bc
    now = time.time()
    if _bc["data"] and (now - _bc["time"]) < CD: return _bc["data"]
    
    # AAPKI EXACT COLUMN MAPPING — using Sheets API v4 (no redirect/401)
    ECL_ID = "1VGP6HYxb-vf3pTlKCT-WyjZlf3sy_j8BrZnjjSxUVJA"
    GE_ID  = "1Bt8od4x1xim2CO0vHcpYPR8eoA7L0XWqNsXqBsl9FBI"
    # format: (sheet_id, gid, col_map, start_row)
    SOURCES = {
        "ECL QC Center": (ECL_ID, 0,
            {"o":0, "d":1, "b":3, "w":6, "v":10, "title":11, "ic":12, "c":13, "cn":17, "t":25}, 1),
        "ECL Zone": (ECL_ID, 928309568,
            {"o":0, "d":1, "b":4, "w":8, "v":13, "title":14, "ic":15, "c":16, "cn":20, "t":28}, 2),
        "GE Zone": (GE_ID, 10726393,
            {"o":0, "d":1, "b":3, "w":6, "v":12, "title":13, "ic":14, "c":15, "cn":19, "t":28}, 2),
    }

    cx = ctx()
    res = {}
    rates_cached = _rc["data"] and (now - _rc["time"]) < RATES_CD

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(fetch_sheet, n, sid, gid, c, s, cx): n for n, (sid, gid, c, s) in SOURCES.items()}
        futs[ex.submit(fetch_status)] = "STATUS_INLINE"
        if not rates_cached:
            futs[ex.submit(fetch_rates, cx)] = "RATES"
        try:
            for f in concurrent.futures.as_completed(futs, timeout=30):
                n = futs[f]
                try:
                    k, d = f.result()
                    if k == "STATUS_INLINE": pass
                    else: res[k] = d
                except: 
                    if n not in ("RATES", "STATUS_INLINE"): res[n] = []
        except concurrent.futures.TimeoutError:
            for f in futs:
                if not f.done(): f.cancel()
                n = futs[f]
                if n not in ("RATES", "STATUS_INLINE"): res[n] = []
                
    if "RATES" not in res:
        if _rc["data"]: res["RATES"] = _rc["data"]
        else: res["RATES"] = ({}, {})
    if "RATES" in res and not isinstance(res["RATES"], tuple):
        res["RATES"] = ({}, {})
        
    _bc["data"] = res; _bc["time"] = now; return res

# --- API ---
@app.route("/api/nexus/debug_rates")
def api_debug_rates():
    mode=user_mode()
    if not mode: return jsonify({"error":"Access denied"}),403
    sheets=fetch_all()
    rates_data=sheets.get("RATES",({},{}))
    rm_brackets,rm_avg=rates_data if isinstance(rates_data,tuple) else ({},{})
    out={k:[{"min":mn,"max":mx,"rate":r} for mn,mx,r in v] for k,v in rm_brackets.items()}
    return jsonify({"countries":len(rm_brackets),"brackets":out,"averages":rm_avg})

@app.route("/api/nexus/debug_status")
def api_debug_status():
    mode=user_mode()
    if not mode: return jsonify({"error":"Access denied"}),403
    result={}
    # 1. Test SS URL directly
    try:
        req=urllib.request.Request(SS,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=20,context=ctx()) as r:
            raw=r.read().decode("utf-8",errors="ignore")
        rows=list(csv.reader(raw.splitlines()))
        result["ss_url"]={"status":"ok","total_rows":len(rows),
            "header":rows[0] if rows else [],
            "row1":rows[1] if len(rows)>1 else [],
            "row2":rows[2] if len(rows)>2 else [],
            "row3":rows[3] if len(rows)>3 else []}
    except Exception as e:
        result["ss_url"]={"status":"error","error":str(e)}
    # 2. Show current sm cache sample
    sm=_sc.get("data") or {}
    sm_sample=dict(list(sm.items())[:5])
    result["status_cache"]={"count":len(sm),"sample":sm_sample}
    # 3. Show bundle order IDs sample
    sheets=_bc.get("data") or {}
    bundle_ids=[]
    for src in ["ECL QC Center","ECL Zone","GE Zone"]:
        for r in (sheets.get(src) or [])[:3]:
            bundle_ids.append(r.get("order",""))
    result["bundle_order_ids_sample"]=bundle_ids
    # 4. Check overlap
    if sm and bundle_ids:
        matches=[oid for oid in bundle_ids if oid.upper() in sm]
        result["id_match_test"]={"checked":len(bundle_ids),"matched":len(matches),"matches":matches}
    return jsonify(result)

@app.route("/api/nexus/clear_cache")
def api_clear_cache():
    global _bc, _sc, _jc, _snc
    _bc["data"]=None; _bc["time"]=0
    _sc["data"]=None; _sc["time"]=0
    _jc["data"]=None; _jc["time"]=0
    _snc.clear()
    return jsonify({"cleared": True})

@app.route("/api/nexus/debug_data")
def api_debug_data():
    mode=user_mode()
    if not mode: return jsonify({"error":"Access denied"}),403
    result={}
    cx=ctx()
    # 1. Test OAuth token
    try:
        req=urllib.request.Request('https://oauth2.googleapis.com/token',data=urllib.parse.urlencode({
            'client_id':'320772774106-fpv7td9vqdcb9eg37utn6th5iihsl753.apps.googleusercontent.com',
            'client_secret':'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',
            'refresh_token':'1//04Om55oY1FH6rCgYIARAAGAQSNwF-L9Ir3d-HLOMyj3jMy8bh0s3C0dqHSVMMZtV33MT4e6EhnUD4bSMxOf-ouB-v-LL4KSMTGWI',
            'grant_type':'refresh_token'
        }).encode('utf-8'))
        tres=json.loads(urllib.request.urlopen(req,timeout=10).read().decode('utf-8'))
        token=tres.get('access_token','')
        result["oauth_token"]={"status":"ok","token_preview":token[:20]+"..." if token else "EMPTY"}
    except Exception as e:
        result["oauth_token"]={"status":"error","error":str(e)}
        token=""
    # 2. Test sheet URLs with Sheets API v4 (no redirect, no 401)
    ECL_ID="1VGP6HYxb-vf3pTlKCT-WyjZlf3sy_j8BrZnjjSxUVJA"
    GE_ID="1Bt8od4x1xim2CO0vHcpYPR8eoA7L0XWqNsXqBsl9FBI"
    _sid=SHEET_ID.strip()
    headers={'User-Agent':'Mozilla/5.0','Authorization':f'Bearer {token}'}
    # Test metadata + values for each sheet
    TEST_SHEETS=[
        ("ECL QC Center", ECL_ID, 0),
        ("ECL Zone", ECL_ID, 928309568),
        ("GE Zone", GE_ID, 10726393),
    ]
    for name, sid, gid in TEST_SHEETS:
        try:
            # Step 1: resolve gid → sheet name
            meta_url=f"https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=sheets.properties"
            req=urllib.request.Request(meta_url,headers=headers)
            with urllib.request.urlopen(req,timeout=15) as r:
                meta=json.loads(r.read().decode("utf-8"))
            sheet_name=None
            for s in meta.get("sheets",[]):
                if str(s.get("properties",{}).get("sheetId",""))==str(gid):
                    sheet_name=s["properties"]["title"]; break
            if not sheet_name:
                result[name]={"status":"error","error":f"gid {gid} not found in spreadsheet"}
                continue
            # Step 2: fetch values
            val_url=f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{urllib.parse.quote(sheet_name)}"
            req=urllib.request.Request(val_url,headers=headers)
            with urllib.request.urlopen(req,timeout=15) as r:
                raw=json.loads(r.read().decode("utf-8"))
            rows=raw.get("values",[])
            result[name]={"status":"ok","sheet_name":sheet_name,"total_rows":len(rows),"first_row":rows[0] if rows else [],"second_row":rows[1] if len(rows)>1 else []}
        except Exception as e:
            result[name]={"status":"error","error":str(e)}
    # Also test status sheet
    try:
        st_url=f"https://sheets.googleapis.com/v4/spreadsheets/{_sid}?fields=sheets.properties"
        req=urllib.request.Request(st_url,headers=headers)
        with urllib.request.urlopen(req,timeout=15) as r:
            meta=json.loads(r.read().decode("utf-8"))
        sheet_name=None
        for s in meta.get("sheets",[]):
            if str(s.get("properties",{}).get("sheetId",""))=="1570463436":
                sheet_name=s["properties"]["title"]; break
        if sheet_name:
            val_url=f"https://sheets.googleapis.com/v4/spreadsheets/{_sid}/values/{urllib.parse.quote(sheet_name)}"
            req=urllib.request.Request(val_url,headers=headers)
            with urllib.request.urlopen(req,timeout=15) as r:
                raw=json.loads(r.read().decode("utf-8"))
            rows=raw.get("values",[])
            result["Status"]={"status":"ok","sheet_name":sheet_name,"total_rows":len(rows),
                "header_row":rows[0] if rows else [],
                "sample_rows":rows[1:4] if len(rows)>1 else []}
        else:
            result["Status"]={"status":"error","error":"gid 1570463436 not found"}
    except Exception as e:
        result["Status"]={"status":"error","error":str(e)}
    return jsonify(result)

@app.route("/api/nexus/app_data")
def api_app_data():
    try:
        return _api_app_data_inner()
    except Exception as e:
        import traceback; print("[API ERROR]", traceback.format_exc())
        return jsonify({"success":False,"error":str(e),"kpi":{},"source_stats":{},"bundles":[]}),500

def _api_app_data_inner():
    sheets=fetch_all(); sm=fetch_status()
    rates_data=sheets.get("RATES",({},{}))
    if isinstance(rates_data,tuple): rm_brackets,rm_avg=rates_data
    else: rm_brackets,rm_avg={},{}
    DR=4.50
    bundles=[]; tb=to2=0; tsav=0.0
    ss={"ECL QC Center":{"orders":0,"boxes":0},"PK Zone":{"orders":0,"boxes":0}}
    NA_VALS={"n/a","#n/a","not applicable","na","none","null","-","nan",""}
    for src in ["ECL QC Center","ECL Zone","GE Zone"]:
        rows=sheets.get(src,[]); cb=None
        pk="PK Zone" if src in ["ECL Zone","GE Zone"] else src
        for r in rows:
            oid=r["order"].upper(); bx=r["boxes"]
            # Skip N/A orders
            if oid.lower().replace(" ","") in NA_VALS or "#n/a" in oid.lower(): continue
            ttl=r["title"]; ctry=r["country"]
            # Skip N/A titles or countries that break data
            if not oid or not re.search(r"\d",oid): continue
            od={"order_id":oid,"weight":r["weight"],"title":ttl,
                "item_count":r["item_count"],"country":ctry,"status":sm.get(oid,"—")}
            if bx!="":
                if cb and len(cb["orders"])>1:
                    bundles.append(cb); tb+=1; to2+=len(cb["orders"])
                    ss[pk]["orders"]+=len(cb["orders"]); ss[pk]["boxes"]+=1
                tids=ctids(r["tid"])
                cb={"orders":[od],"date":r["date"],"date_std":r["date_std"],
                    "customer":r["customer"],"vendor":r["vendor"],"country":ctry,
                    "source":src,"region":grg(ctry),"boxes_val":bx,
                    "tid":", ".join(tids) if tids else ""}
            else:
                if cb:
                    cb["orders"].append(od)
                    if r["tid"] not in ["N/A",""] and cb["tid"]=="Pending Tracking":
                        t2=ctids(r["tid"])
                        if t2: cb["tid"]=", ".join(t2)
        if cb and len(cb["orders"])>1:
            bundles.append(cb); tb+=1; to2+=len(cb["orders"])
            ss[pk]["orders"]+=len(cb["orders"]); ss[pk]["boxes"]+=1
    for b in bundles:
        tq=0; bw=0.0; isc=0.0
        raw_ctry=str(b.get("country","")).strip()
        # rate set per-order and per-bundle using weight brackets below
        for o in b["orders"]:
            try: ic_raw=int(float(re.sub(r"[^0-9.]","",str(o["item_count"])) or 1)); tq+=ic_raw
            except: ic_raw=1
            try: wt=float(re.sub(r"[^0-9.]","",str(o["weight"])) or 0)
            except: wt=0.0
            bw+=wt
            # For individual cost: use actual weight if available, else estimate from category+pieces
            if wt>0:
                indiv_wt=wt
            else:
                indiv_wt=estimate_item_weight(o["title"], ic_raw)
            indiv_billed=max(math.ceil(indiv_wt),1)
            o_rate=lookup_rate(rm_brackets, raw_ctry, indiv_billed, DR)
            isc+=indiv_billed*o_rate
        b["total_items"]=tq; b["weight_kg"]=round(bw,2)
        bundle_billed=max(math.ceil(bw),1)
        pr=lookup_rate(rm_brackets, raw_ctry, bundle_billed, DR)
        bc=bundle_billed*pr
        sv=isc-bc; b["savings_gbp"]=round(sv if sv>0 else 0,2)
        b["rate_gbp"]=round(pr,2); b["indiv_cost"]=round(isc,2); b["bundle_cost"]=round(bc,2)
        tsav+=b["savings_gbp"]
    bundles.sort(key=lambda x:x["date_std"],reverse=True)
    return jsonify({"success":True,
        "kpi":{"total_bundles":tb,"total_orders_bundled":to2,
               "saved_shipments":to2-tb if tb>0 else 0,"total_savings_gbp":round(tsav,2)},
        "source_stats":ss,"bundles":bundles,"rates_map":rm_avg,
        "total_rows":{s:len(sheets.get(s,[])) for s in ["ECL QC Center","ECL Zone","GE Zone"]}})

@app.route("/api/nexus/order_journey/<oid>")
def api_order_journey(oid):
    jm=fetch_journey(); row=jm.get(str(oid).strip().upper())
    if not row: return jsonify({"success":False,"message":"Order not found."})
    dc=pdt(row["created_at"]); da=pdt(row["accepted_at"]); dp=pdt(row["pickup_ready_at"])
    dca=pdt(row["cancelled_at"]); dqp=pdt(row["qc_pending_at"]); dqa=pdt(row["qc_approved_at"])
    dh=pdt(row["handedover_at"]); dfr=pdt(row["freight_at"]); dco=pdt(row["courier_at"]); dd=pdt(row["delivered_at"])
    steps=[("Created → Accepted",dc,da),("Accepted → Pickup",da,dp),("Pickup → QC Pending",dp,dqp),
           ("QC Pending → QC Approved",dqp,dqa),("QC → Handover",dqa,dh),("Handover → Freight",dh,dfr),
           ("Freight → Courier",dfr,dco),("Courier → Delivered",dco,dd)]
    last=next((dt for dt in [dd,dco,dfr,dh,dqa,dqp,dp,da,dc] if dt),None)
    return jsonify({"success":True,"order_id":oid,"is_cancelled":bool(dca),
        "timeline":{"created_at":fdt(dc),"accepted_at":fdt(da),"pickup_ready_at":fdt(dp),
            "cancelled_at":fdt(dca),"qc_pending_at":fdt(dqp),"qc_approved_at":fdt(dqa),
            "handedover_at":fdt(dh),"freight_at":fdt(dfr),"courier_at":fdt(dco),"delivered_at":fdt(dd)},
        "step_metrics":[{"label":l,"duration":dayb(s,e)} for l,s,e in steps],
        "key_metrics":{"qc_to_handover":dayb(dqa,dh),"handover_to_freight":dayb(dh,dfr),
            "total_journey":dayb(dc,dd or last)}})

@app.route("/bundling")
@app.route("/bundling/status")
@app.route("/bundling/summary")
def bundling_spa():
    mode=user_mode()
    if not mode:
        return "<div style='text-align:center;padding:100px;background:#05050f;color:#fff;height:100vh'><h2>⛔ Access Denied</h2></div>",403
    gflag="true" if mode=="guest" else "false"
    email=(session.get("email") or session.get("user_email") or session.get("username") or "").lower().strip()
    import json as _json
    # Don't block page render on sheet fetching — rates loaded async via app_data API
    rm_js="const RATES_MAP={};"
    html=BUNDLING_HTML.replace("window.onload=init;","const GUEST="+gflag+";\nconst USER_EMAIL='"+email+"';\n"+rm_js+"\nwindow.onload=init;")
    return render_template_string(html)

def resolve_sheet_name(sheet_id, gid):
    """Resolve a gid (tab id) to its sheet title using Sheets API v4 metadata. Cached permanently."""
    global _snc
    key = (sheet_id, str(gid))
    if key in _snc:
        return _snc[key]
    try:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}?fields=sheets.properties"
        req = urllib.request.Request(url, headers=get_auth_headers())
        with urllib.request.urlopen(req, timeout=15) as r:
            meta = json.loads(r.read().decode("utf-8"))
        # Cache ALL tabs from this spreadsheet in one go
        for s in meta.get("sheets", []):
            p = s.get("properties", {})
            _snc[(sheet_id, str(p.get("sheetId", "")))] = p.get("title", "")
        return _snc.get(key)
    except Exception as e:
        print(f"[WARN] resolve_sheet_name({sheet_id},{gid}): {e}")
    return None

def fetch_sheet(name, sheet_id, gid, col, start, cx):
    sheet_name = resolve_sheet_name(sheet_id, gid)
    if not sheet_name:
        print(f"[ERROR] {name}: could not resolve gid {gid} to sheet name")
        return name, []
    api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{urllib.parse.quote(sheet_name)}"
    for attempt in range(2):
        try:
            req = urllib.request.Request(api_url, headers=get_auth_headers())
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = json.loads(r.read().decode("utf-8"))
            rows_raw = raw.get("values", [])
            data = [[str(c) for c in row] for row in rows_raw]
            rows=[]; lo=ld=lv=lc=lcn=lt=""
            for row in data[start:]:
                if not row: continue
                p=row+[""]*60
                ro=str(p[col["o"]]).strip(); rw=str(p[col["w"]]).strip(); rti=str(p[col["title"]]).strip()
                rw_clean=rw.replace("0","").replace(".","").strip()
                if not ro and not rw_clean and not rti: continue
                if ro: lo=ro
                co=ro if ro else lo
                if not co or not re.search(r"\d",co): continue
                try:
                    rw_float=float(rw or 0)
                except: rw_float=0
                if not ro and not rti and rw_float==0: continue
                if co.lower() in ["n/a","nan","order","orderid","order id"]: continue
                dv=str(p[col["d"]]).strip(); vv=str(p[col["v"]]).strip()
                cv=str(p[col["c"]]).strip(); cnv=str(p[col["cn"]]).strip(); tv=str(p[col["t"]]).strip()
                if dv: ld=dv
                if vv: lv=vv
                if cv: lc=cv
                if cnv: lcn=cnv
                if tv: lt=tv
                bxv=str(p[col["b"]]).strip()
                if not bxv and col.get("b2") is not None:
                    bxv2=str(p[col["b2"]]).strip()
                    if bxv2 and re.match(r"^[0-9]+$",bxv2): bxv=bxv2
                rows.append({"order":co,"date":dv or ld,"date_std":sd(dv or ld),
                    "boxes":bxv,"weight":rw,
                    "vendor":vv or lv,"title":rti or "N/A","item_count":str(p[col["ic"]]).strip() or "0",
                    "customer":cv or lc,"country":cnv or lcn,"tid":tv or lt})
            print(f"[OK] {name}: {len(rows)} rows"); return name,rows
        except Exception as e:
            print(f"[WARN] {name} attempt {attempt+1}: {e}")
            if attempt==0: time.sleep(0.5)  # shorter retry delay
    return name,[]

ORDER_LOOKUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Order Lookup — 3PL</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%234f46e5'/%3E%3Ctext x='50' y='68' font-size='48' text-anchor='middle' fill='white' font-family='Arial' font-weight='bold'%3E3PL%3C/text%3E%3C/svg%3E">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:'Inter',sans-serif;background:#060610;color:#e2e8f0;}
body{display:flex;flex-direction:column;height:100vh;overflow:hidden;}

/* ── Topbar ── */
.topbar{flex-shrink:0;background:#0b0b1c;border-bottom:1px solid #13132a;padding:0 28px;height:50px;display:flex;align-items:center;justify-content:space-between;}
.tb-left{display:flex;align-items:center;gap:10px;}
.tb-logo{width:28px;height:28px;background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:7px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:7.5px;color:#fff;letter-spacing:-.3px;}
.tb-title{font-size:13px;font-weight:700;color:#e2e8f0;}
.tb-sep{width:1px;height:14px;background:#1a1a35;margin:0 2px;}
.tb-sub{font-size:11px;color:#2d3d58;}
.tb-right{display:flex;align-items:center;gap:12px;}
.tb-status{font-size:11px;color:#2d3d58;}
.tb-back{padding:5px 14px;border-radius:6px;border:1px solid #1a1a35;background:none;color:#3d4f70;font-size:11px;font-weight:500;text-decoration:none;transition:.15s;white-space:nowrap;}
.tb-back:hover{border-color:#4f46e5;color:#818cf8;background:rgba(79,70,229,.07);}

/* ── Search bar ── */
.searchbar{flex-shrink:0;padding:12px 28px;background:#0b0b1c;border-bottom:1px solid #13132a;display:flex;align-items:center;gap:12px;}
.sbox{display:flex;align-items:center;gap:8px;flex:0 0 520px;background:#0e0e22;border:1.5px solid #1b1b38;border-radius:10px;padding:0 8px 0 14px;transition:border-color .2s,box-shadow .2s;}
.sbox:focus-within{border-color:#4f46e5;box-shadow:0 0 0 3px rgba(79,70,229,.1);}
.sico{color:#253048;flex-shrink:0;}
.si{flex:1;background:none;border:none;outline:none;font-size:14px;color:#e2e8f0;font-family:inherit;padding:9px 0;}
.si::placeholder{color:#1e2c42;}
.sbtn{flex-shrink:0;padding:9px 24px;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;letter-spacing:.2px;transition:.2s;}
.sbtn:hover{box-shadow:0 4px 16px rgba(79,70,229,.4);transform:translateY(-1px);}
.sbtn:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none;}
.divider{width:1px;height:20px;background:#13132a;flex-shrink:0;}
.pills{display:flex;align-items:center;gap:5px;flex-wrap:wrap;}
.pill{padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700;border:1px solid;white-space:nowrap;}

/* ── Scrollable results ── */
.results-wrap{flex:1;overflow-y:auto;padding:18px 28px 32px;}
.results-wrap::-webkit-scrollbar{width:4px;}
.results-wrap::-webkit-scrollbar-thumb{background:#1a1a35;border-radius:2px;}

/* ── State screens ── */
.state-screen{display:flex;flex-direction:column;align-items:center;justify-content:center;height:60vh;text-align:center;gap:10px;}
.state-ico{font-size:44px;opacity:.5;}
.state-txt{font-size:13px;color:#253048;}
.spin{width:32px;height:32px;border:2.5px solid rgba(79,70,229,.1);border-top-color:#4f46e5;border-radius:50%;animation:rot 1s linear infinite;}
@keyframes rot{to{transform:rotate(360deg)}}

/* ── Result count ── */
.rcount{font-size:12px;color:#2d3d58;margin-bottom:14px;}
.rcount b{color:#6366f1;}

/* ── Cards — single column, full width ── */
.rcard{background:#0c0c1e;border:1px solid #14142e;border-radius:12px;margin-bottom:12px;overflow:hidden;animation:fadeup .18s ease;transition:border-color .15s;}
.rcard:hover{border-color:#21213e;}
@keyframes fadeup{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* Card: header row */
.rcard-hd{display:flex;align-items:center;padding:12px 20px;border-bottom:1px solid #14142e;gap:12px;}
.ro{font-size:17px;font-weight:800;font-family:'Courier New',monospace;color:#f1f5f9;letter-spacing:.4px;flex-shrink:0;}
.rbadge{padding:2px 11px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:.3px;flex-shrink:0;}
.hd-spacer{flex:1;}
.rcust{font-size:12px;color:#475569;font-weight:500;}

/* Card: info grid — 6 cells in one row */
.rcard-info{display:grid;grid-template-columns:repeat(6,1fr);border-bottom:1px solid #14142e;}
.ri{padding:10px 16px;border-right:1px solid #14142e;}
.ri:last-child{border-right:none;}
.rl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:#1f2e44;margin-bottom:4px;}
.rv{font-size:12px;font-weight:600;color:#94a3b8;line-height:1.3;}
.rv.hi{color:#c8d4e8;}
.rv.ac{color:#818cf8;}
.rv.gr{color:#10b981;font-family:'Courier New',monospace;font-size:11px;letter-spacing:.3px;}

/* Card: title + tracking footer */
.rcard-ft{display:flex;align-items:stretch;border-top:0;}
.ft-title{flex:1;padding:9px 16px;border-right:1px solid #14142e;}
.ft-tids{flex:1.6;padding:9px 16px;}
.ft-label{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:#1f2e44;margin-bottom:5px;}
.ft-val{font-size:12px;color:#6b7e9a;line-height:1.5;}
.tid-list{display:flex;flex-wrap:wrap;gap:4px;}
.tid-chip{display:inline-flex;align-items:center;gap:5px;background:rgba(99,102,241,.07);border:1px solid rgba(99,102,241,.18);border-radius:5px;padding:3px 9px;}
.tid-n{font-size:9px;font-weight:700;color:#6366f1;min-width:12px;}
.tid-v{font-family:'Courier New',monospace;font-size:11px;color:#818cf8;font-weight:700;}
</style>
</head>
<body>

<div class="topbar">
  <div class="tb-left">
    <div class="tb-logo">3PL</div>
    <span class="tb-title">Order Lookup</span>
    <div class="tb-sep"></div>
    <span class="tb-sub">Search across all 6 providers</span>
  </div>
  <div class="tb-right">
    <span id="wstatus" class="tb-status"></span>
    <a href="/" class="tb-back">&#8592; Dashboard</a>
  </div>
</div>

<div class="searchbar">
  <div class="sbox">
    <svg class="sico" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
    <input class="si" id="si" placeholder="Enter order number — e.g. 143595_78" onkeydown="if(event.key==='Enter')doSearch()">
  </div>
  <button class="sbtn" id="sbtn" onclick="doSearch()">Search</button>
  <div class="divider"></div>
  <div class="pills">
    <span class="pill" style="color:#3B82F6;border-color:#3B82F622;background:#3B82F608">GE QC</span>
    <span class="pill" style="color:#8B5CF6;border-color:#8B5CF622;background:#8B5CF608">GE Zone</span>
    <span class="pill" style="color:#10B981;border-color:#10B98122;background:#10B98108">ECL QC</span>
    <span class="pill" style="color:#F59E0B;border-color:#F59E0B22;background:#F59E0B08">ECL Zone</span>
    <span class="pill" style="color:#EC4899;border-color:#EC489922;background:#EC489908">APX</span>
    <span class="pill" style="color:#EF4444;border-color:#EF444422;background:#EF444408">Kerry</span>
  </div>
</div>

<div class="results-wrap">
  <div id="results">
    <div class="state-screen"><div class="state-ico">📦</div><div class="state-txt">Enter an order number above to search</div></div>
  </div>
</div>

<script>
var C={"GE QC":"#3B82F6","GE Zone":"#8B5CF6","ECL QC":"#10B981","ECL Zone":"#F59E0B","APX":"#EC4899","Kerry":"#EF4444"};
function doSearch(){
  var q=document.getElementById('si').value.trim();
  if(!q)return;
  var btn=document.getElementById('sbtn');
  btn.disabled=true; btn.textContent='Searching...';
  document.getElementById('results').innerHTML='<div class="state-screen"><div class="spin"></div><div class="state-txt" style="margin-top:10px">Searching all providers...</div></div>';
  fetch('/api/order-lookup?q='+encodeURIComponent(q))
  .then(function(r){return r.json();})
  .then(function(data){
    btn.disabled=false; btn.textContent='Search';
    var res=data.results||[];
    if(!res.length){
      document.getElementById('results').innerHTML='<div class="state-screen"><div class="state-ico">🔎</div><div class="state-txt">No orders found for <b style="color:#6366f1">'+escH(q)+'</b></div></div>';
      return;
    }
    var html='<div class="rcount">Found <b>'+res.length+'</b> result'+(res.length>1?'s':'')+' for <b>'+escH(q)+'</b></div>';
    res.forEach(function(r){
      var c=C[r.provider]||'#4f46e5';
      var mawb=r.mawb&&r.mawb.trim()?r.mawb:'—';
      var tids=r.tid&&r.tid.trim()?r.tid.split(',').map(function(t){return t.trim();}).filter(Boolean):[];
      html+='<div class="rcard">';
      // Header
      html+='<div class="rcard-hd">'
        +'<span class="ro">'+escH(r.order)+'</span>'
        +'<span class="rbadge" style="background:'+c+'15;color:'+c+'">'+escH(r.provider)+'</span>'
        +'<span class="hd-spacer"></span>'
        +'<span class="rcust">'+escH(r.customer||'')+'</span>'
        +'</div>';
      // 6-col info grid
      html+='<div class="rcard-info">'
        +'<div class="ri"><div class="rl">Country</div><div class="rv hi">'+escH(r.country||'—')+'</div></div>'
        +'<div class="ri"><div class="rl">Boxes</div><div class="rv hi">'+escH(r.boxes||'—')+'</div></div>'
        +'<div class="ri"><div class="rl">Chargeable Wt</div><div class="rv">'+escH(r.cw?r.cw+' kg':'—')+'</div></div>'
        +'<div class="ri"><div class="rl">Item Count</div><div class="rv">'+escH(r.item_count||'—')+'</div></div>'
        +'<div class="ri"><div class="rl">Vendor</div><div class="rv ac">'+escH(r.vendor||'—')+'</div></div>'
        +'<div class="ri"><div class="rl">MAWB</div><div class="rv gr">'+escH(mawb)+'</div></div>'
        +'</div>';
      // Footer: title + tids
      html+='<div class="rcard-ft">'
        +'<div class="ft-title"><div class="ft-label">Title</div><div class="ft-val">'+escH(r.title||'—')+'</div></div>'
        +'<div class="ft-tids"><div class="ft-label">Tracking IDs'+(tids.length?' <span style="color:#4f46e5">('+tids.length+')</span>':'')+'</div>';
      if(tids.length){
        html+='<div class="tid-list">';
        tids.forEach(function(t,i){html+='<div class="tid-chip"><span class="tid-n">'+(i+1)+'</span><span class="tid-v">'+escH(t)+'</span></div>';});
        html+='</div>';
      } else { html+='<div class="ft-val">—</div>'; }
      html+='</div></div>';
      html+='</div>';
    });
    document.getElementById('results').innerHTML=html;
  })
  .catch(function(){
    btn.disabled=false; btn.textContent='Search';
    document.getElementById('results').innerHTML='<div class="state-screen"><div class="state-ico">❌</div><div class="state-txt">Search failed. Please try again.</div></div>';
  });
}
function escH(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
document.getElementById('si').focus();

// Warmup: pre-load all sheets in background so first search is instant
(function warmup(){
  var ws=document.getElementById('wstatus');
  ws.style.color='#475569';
  ws.textContent='⟳ Preparing data for fast search...';
  fetch('/api/order-lookup/warmup')
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.errors&&d.errors.length){
      ws.style.color='#f59e0b';
      ws.textContent='⚠ Partial load ('+d.ready.length+'/6). May be slower.';
    } else {
      ws.style.color='#10b981';
      ws.textContent='✓ Ready — all '+d.ready.length+' providers loaded';
      setTimeout(function(){ws.style.opacity='0';},3000);
    }
  })
  .catch(function(){
    ws.style.color='#ef4444';
    ws.textContent='⚠ Could not pre-load data. Search may take longer.';
  });
})();
</script>
</body></html>
"""

BUNDLING_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bundling Intelligence Hub</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%234f46e5'/%3E%3Ctext x='50' y='68' font-size='48' text-anchor='middle' fill='white' font-family='Arial' font-weight='bold'%3E3PL%3C/text%3E%3C/svg%3E">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0}

/* =========================================
   DARK THEME — PURE BLACK PREMIUM
   ========================================= */
[data-theme="dark"]{
  --bg:#000000;
  --s1:#0c0c0c;
  --s2:#111111;
  --s3:#161616;
  --bd:#1e1e1e;
  --bd2:#282828;
  --t1:#f0f0f0;
  --t2:#b8b8b8;
  --t3:#555555;
  --t4:#2e2e2e;
  --card:#0c0c0c;
  --sidebar:#070707;
  --sb-border:#1a1a1a;
  --sb-text:#888888;
  --sb-active-bg:rgba(138,43,226,0.16);
  --sb-active-border:#7c3aed;
  --sb-active-text:#c4b5fd;
  --input:#050505;
  --hover:rgba(255,255,255,0.03);
  --shadow:0 2px 12px rgba(0,0,0,0.9);
  --shadow2:0 8px 40px rgba(0,0,0,0.95);
  --acc:#8b5cf6;
  --acc2:#7c3aed;
  --green:#22c55e;
  --green2:#16a34a;
  --blue:#60a5fa;
  --blue2:#3b82f6;
  --purple:#a78bfa;
  --orange:#fb923c;
  --yellow:#fbbf24;
  --red:#f87171;
  --cyan:#22d3ee;
  --glow-acc:0 0 20px rgba(139,92,246,0.3);
  --glow-green:0 0 16px rgba(34,197,94,0.25);
}

/* =========================================
   LIGHT THEME
   ========================================= */
[data-theme="light"]{
  --bg:#f1f5f9;
  --s1:#ffffff;
  --s2:#f8fafc;
  --s3:#f1f5f9;
  --bd:#e2e8f0;
  --bd2:#cbd5e1;
  --t1:#0f172a;
  --t2:#1e293b;
  --t3:#475569;
  --t4:#94a3b8;
  --card:#ffffff;
  --sidebar:#ffffff;
  --sb-border:#e2e8f0;
  --sb-text:#64748b;
  --sb-active-bg:rgba(109,40,217,0.08);
  --sb-active-border:#7c3aed;
  --sb-active-text:#6d28d9;
  --input:#f8fafc;
  --hover:rgba(0,0,0,0.025);
  --shadow:0 1px 4px rgba(0,0,0,0.07),0 4px 16px rgba(0,0,0,0.05);
  --shadow2:0 4px 24px rgba(0,0,0,0.1);
  --acc:#7c3aed;
  --acc2:#6d28d9;
  --green:#16a34a;
  --green2:#15803d;
  --blue:#2563eb;
  --blue2:#1d4ed8;
  --purple:#7c3aed;
  --orange:#ea580c;
  --yellow:#d97706;
  --red:#dc2626;
  --cyan:#0891b2;
  --glow-acc:none;
  --glow-green:none;
}

html,body{height:100%;}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--t1);min-height:100vh;transition:background .3s,color .3s;overflow:hidden;}

/* =========================================
   APP LAYOUT — SIDEBAR
   ========================================= */
.app-wrap{display:flex;height:100vh;overflow:hidden;}

/* SIDEBAR */
.sidebar{
  width:240px;flex-shrink:0;
  background:var(--sidebar);
  border-right:none;
  display:flex;flex-direction:column;
  overflow:hidden;
  position:relative;z-index:100;
  transition:width .25s ease;
}
[data-theme="dark"] .sidebar{
  background:linear-gradient(180deg,#0a0a0a 0%,#060606 100%);
  box-shadow:4px 0 20px rgba(0,0,0,0.5);
}
[data-theme="light"] .sidebar{
  background:#ffffff;
  box-shadow:2px 0 12px rgba(0,0,0,0.06);
  border-right:1px solid #e2e8f0;
}
[data-theme="light"] .sb-head{border-bottom-color:#e2e8f0;}
[data-theme="light"] .sb-tab{color:#64748b;}
[data-theme="light"] .sb-tab:hover{color:#0f172a;background:rgba(0,0,0,0.04);}
[data-theme="light"] .sb-tab.active{color:#6d28d9;background:rgba(109,40,217,0.08);border-left-color:#7c3aed;}
[data-theme="light"] .sb-tab.active .sb-tab-icon{filter:none;}
[data-theme="light"] .sb-ico{box-shadow:0 4px 16px rgba(109,40,217,0.3);}
[data-theme="light"] .sb-section-label{color:#94a3b8;}
[data-theme="light"] .sb-title{color:#0f172a;}
[data-theme="light"] .sb-sub{color:#64748b;}
[data-theme="light"] .sb-back{color:#64748b;}
[data-theme="light"] .sb-back:hover{color:#0f172a;background:rgba(0,0,0,0.04);}
[data-theme="light"] .theme-pill{background:#f8fafc;border-color:#e2e8f0;color:#475569;}
[data-theme="light"] .theme-pill:hover{border-color:#7c3aed;color:#6d28d9;}
[data-theme="light"] .sb-foot{border-top-color:#e2e8f0;}
[data-theme="light"] .sb-user-card{background:rgba(109,40,217,0.06);border-color:rgba(109,40,217,0.15);}
[data-theme="light"] .sb-last-update{color:#94a3b8;}
.sb-head{padding:20px 18px 16px;border-bottom:1px solid var(--sb-border);}
.sb-logo-wrap{display:flex;align-items:center;gap:12px;}
.sb-ico{
  width:36px;height:36px;flex-shrink:0;
  background:linear-gradient(135deg,#5b21b6,#7c3aed);
  border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  font-size:18px;
  box-shadow:0 3px 12px rgba(139,92,246,0.5);
}
.sb-info{overflow:hidden;}
.sb-title{font-size:13px;font-weight:800;color:#ffffff;letter-spacing:-.3px;white-space:nowrap;}
.sb-sub{font-size:10px;color:var(--sb-text);margin-top:2px;white-space:nowrap;}

/* NAV */
.sb-nav{flex:1;overflow-y:auto;padding:12px 10px;display:flex;flex-direction:column;gap:2px;}
.sb-nav::-webkit-scrollbar{width:0;}
.sb-section-label{
  font-size:9px;font-weight:800;text-transform:uppercase;
  letter-spacing:1.5px;color:var(--t3);
  padding:8px 8px 6px;margin-top:4px;
}
.sb-tab{
  display:flex;align-items:center;gap:10px;
  padding:9px 12px;border-radius:9px;
  font-size:12px;font-weight:600;
  color:var(--sb-text);
  cursor:pointer;transition:.15s;
  border:1px solid transparent;
  background:transparent;font-family:inherit;
  text-align:left;white-space:nowrap;
  letter-spacing:-.1px;
}
.sb-tab:hover{color:var(--t1);background:rgba(255,255,255,0.07);}
[data-theme="dark"] .sb-tab:hover{color:#e2e2e2;}
.sb-tab.active{
  color:var(--sb-active-text);
  background:var(--sb-active-bg);
  border-color:rgba(139,92,246,0.25);
}
[data-theme="dark"] .sb-tab.active{
  box-shadow:inset 3px 0 0 var(--sb-active-border), 0 0 12px rgba(139,92,246,0.1);
  border-left-color:var(--sb-active-border);
}
.sb-tab-icon{
  font-size:14px;flex-shrink:0;
  width:28px;height:28px;
  display:flex;align-items:center;justify-content:center;
  border-radius:7px;
  background:rgba(255,255,255,0.04);
  transition:.15s;
}
.sb-tab:hover .sb-tab-icon{background:rgba(255,255,255,0.08);}
.sb-tab.active .sb-tab-icon{background:rgba(139,92,246,0.2);}
[data-theme="light"] .sb-tab-icon{background:rgba(0,0,0,0.04);}
[data-theme="light"] .sb-tab:hover .sb-tab-icon{background:rgba(0,0,0,0.07);}
[data-theme="light"] .sb-tab.active .sb-tab-icon{background:rgba(109,40,217,0.1);}
.sb-tab-label{flex:1;}
.sb-tab-dot{
  width:6px;height:6px;border-radius:50%;
  background:var(--acc);opacity:0;
  transition:.15s;flex-shrink:0;
}
.sb-tab.active .sb-tab-dot{opacity:1;box-shadow:0 0 6px var(--acc);}

/* SIDEBAR FOOTER */
.sb-foot{
  padding:14px 10px;
  border-top:1px solid var(--sb-border);
  display:flex;flex-direction:column;gap:8px;
}
.theme-pill{
  display:flex;align-items:center;gap:8px;
  padding:9px 12px;
  background:rgba(255,255,255,0.04);
  border:1px solid var(--sb-border);
  border-radius:10px;
  cursor:pointer;font-size:11.5px;font-weight:700;
  color:var(--sb-text);transition:.2s;font-family:inherit;
  width:100%;
}
.theme-pill:hover{border-color:var(--acc);color:var(--sb-active-text);background:var(--sb-active-bg);}
.theme-pill .icon{font-size:14px;}
.sb-back{
  display:flex;align-items:center;gap:8px;
  padding:8px 12px;border-radius:10px;
  font-size:11.5px;font-weight:600;color:var(--sb-text);
  text-decoration:none;transition:.15s;
  border:1px solid rgba(255,255,255,0.08);
  background:rgba(255,255,255,0.03);
  font-weight:700;
}
.sb-back:hover{color:#fff;background:rgba(255,255,255,0.1);border-color:rgba(255,255,255,0.15);}
[data-theme="light"] .sb-back{border-color:rgba(0,0,0,0.08);background:rgba(0,0,0,0.02);color:#475569;font-weight:700;}
[data-theme="light"] .sb-back:hover{color:#0f172a;background:rgba(0,0,0,0.06);border-color:rgba(0,0,0,0.12);}

/* SIDEBAR TOGGLE */
.sb-toggle-fixed{
  background:var(--s2);border:1px solid var(--bd);
  cursor:pointer;color:var(--t2);
  padding:7px 9px;border-radius:9px;
  transition:.15s;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
}
.sb-toggle-fixed:hover{color:var(--t1);border-color:var(--acc);background:var(--s3);}
.sidebar.collapsed{width:60px;}
.sidebar.collapsed .sb-info,
.sidebar.collapsed .sb-tab-label,
.sidebar.collapsed .sb-tab-dot,
.sidebar.collapsed .sb-section-label,
.sidebar.collapsed .sb-user-info,
.sidebar.collapsed .sb-last-update,
.sidebar.collapsed .theme-pill .icon+span,
.sidebar.collapsed .sb-back svg+span,
.sidebar.collapsed .sb-foot-divider{display:none;}
.sidebar.collapsed .sb-tab{justify-content:center;padding:10px;gap:0;}
.sidebar.collapsed .sb-tab-icon{width:32px;height:32px;font-size:15px;}
.sidebar.collapsed .sb-foot{padding:10px 6px;}
.sidebar.collapsed .theme-pill{justify-content:center;padding:9px;}
.sidebar.collapsed .sb-back{justify-content:center;padding:8px;}
.sidebar.collapsed .sb-nav{padding:8px 6px;}
.sidebar.collapsed .sb-user-card{justify-content:center;padding:8px;}

.sb-foot-divider{height:1px;background:var(--sb-border);margin:4px 0;}

/* MAIN CONTENT AREA */
.main-wrap{
  flex:1;display:flex;flex-direction:column;
  overflow:hidden;
  background:var(--bg);
}

/* TOP BAR */
.topbar{
  display:flex;justify-content:space-between;align-items:center;
  padding:0 24px;height:56px;flex-shrink:0;
  background:var(--s1);
  border-bottom:1px solid var(--bd);
  box-shadow:var(--shadow);
}
[data-theme="dark"] .topbar{background:#0a0a0a;border-bottom-color:#1a1a1a;}
.tb-page-title{font-size:16px;font-weight:800;color:var(--t1);letter-spacing:-.4px;}
.tb-actions{display:flex;align-items:center;gap:8px;}
.tbtn{
  padding:7px 14px;border-radius:8px;font-size:12px;font-weight:700;
  cursor:pointer;font-family:inherit;
  display:inline-flex;align-items:center;gap:6px;
  text-decoration:none;transition:.15s;white-space:nowrap;
  border:1px solid var(--bd);
}
.tbtn:hover{transform:translateY(-1px);}
.tbtn-back{background:var(--s2);color:var(--t2);}
[data-theme="dark"] .tbtn-back{background:#111;color:#888;border-color:#222;}
.tbtn-refresh{
  background:linear-gradient(135deg,#16a34a,#22c55e);
  color:#000;border-color:transparent;
  box-shadow:0 3px 12px rgba(34,197,94,.3);font-weight:800;
}
.tbtn-theme-inline{
  background:var(--s2);color:var(--t2);
  border-color:var(--bd);font-size:14px;padding:7px 10px;
}
.tbtn-theme-inline:hover{border-color:var(--acc);}

/* MAIN SCROLL AREA */
.main{
  flex:1;overflow-y:auto;
  padding:22px 24px;
}
.main::-webkit-scrollbar{width:6px;}
.main::-webkit-scrollbar-track{background:transparent;}
.main::-webkit-scrollbar-thumb{background:var(--bd2);border-radius:3px;}
.main::-webkit-scrollbar-thumb:hover{background:var(--t3);}
.pane{display:none;animation:fadeIn .2s ease;}
.pane.active{display:block;}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}

/* =========================================
   FILTER BAR
   ========================================= */
.fbar{
  background:var(--s1);
  border:1px solid var(--bd);
  border-radius:14px;
  padding:18px 20px;margin-bottom:20px;
  box-shadow:var(--shadow);
}
[data-theme="dark"] .fbar{background:var(--s2);border-color:var(--bd);}
.frow{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-bottom:12px;}
.frow:last-child{margin-bottom:0;}
.fg{display:flex;flex-direction:column;gap:5px;}
.fl{font-size:10px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:1.2px;}
.fi{
  background:var(--input);
  border:1.5px solid var(--bd);
  color:var(--t1);padding:9px 13px;
  border-radius:9px;font-family:inherit;
  outline:none;font-size:13px;transition:.2s;min-width:0;
}
.fi:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(139,92,246,0.12);}
.fi option{background:var(--s2);color:var(--t1);}
input[type="date"].fi{color-scheme:dark;}
[data-theme="light"] input[type="date"].fi{color-scheme:light;}
input[type="date"]::-webkit-calendar-picker-indicator{
  cursor:pointer;opacity:1;
  filter:invert(1) brightness(10) saturate(0);
  background-color:transparent;
}
[data-theme="light"] input[type="date"]::-webkit-calendar-picker-indicator{
  filter:none;opacity:0.7;
}
/* Make date input text visible in dark mode */
[data-theme="dark"] input[type="date"].fi{
  color:#e0e0e0;
}
[data-theme="dark"] input[type="date"].fi::-webkit-datetime-edit-fields-wrapper{
  color:#e0e0e0;
}
[data-theme="dark"] input[type="date"].fi::-webkit-datetime-edit-text{color:#888;}
[data-theme="dark"] input[type="date"].fi::-webkit-datetime-edit-month-field,
[data-theme="dark"] input[type="date"].fi::-webkit-datetime-edit-day-field,
[data-theme="dark"] input[type="date"].fi::-webkit-datetime-edit-year-field{color:#e0e0e0;}
.fg-grow{flex:1;min-width:200px;}
.qbtns{display:flex;gap:6px;flex-wrap:wrap;}
.qb{
  padding:7px 14px;background:var(--s3);
  border:1.5px solid var(--bd);border-radius:20px;
  color:var(--t3);font-size:12px;font-family:inherit;
  font-weight:600;cursor:pointer;transition:.15s;
}
.qb:hover{color:var(--t1);border-color:var(--acc);background:rgba(139,92,246,.06);}
.qb.on{background:rgba(139,92,246,.1);border-color:var(--acc);color:var(--acc);}
.abtn{
  padding:9px 22px;
  background:linear-gradient(135deg,var(--acc2),var(--acc));
  border:none;border-radius:9px;color:#fff;
  font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;
  box-shadow:0 4px 14px rgba(139,92,246,0.35);transition:.15s;
}
.abtn:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(139,92,246,.45);}
.cbtn{
  padding:9px 16px;background:transparent;
  border:1.5px solid var(--bd);border-radius:9px;
  color:var(--t3);font-size:13px;cursor:pointer;font-family:inherit;transition:.15s;
}
.cbtn:hover{border-color:var(--red);color:var(--red);}

/* =========================================
   KPI CARDS
   ========================================= */
.kg{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px;}
.kc{
  background:var(--card);border:1px solid var(--bd);
  border-radius:16px;padding:22px 20px;
  position:relative;overflow:hidden;
  box-shadow:var(--shadow);transition:.25s;cursor:default;
}
[data-theme="dark"] .kc{background:var(--s2);}
.kc:hover{transform:translateY(-3px);box-shadow:var(--shadow2);}
.kc::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--green),var(--cyan));
  border-radius:16px 16px 0 0;
}
.kc-accent-yellow::before{background:linear-gradient(90deg,var(--yellow),var(--orange));}
.kc-accent-blue::before{background:linear-gradient(90deg,var(--blue),var(--cyan));}
.kc-accent-green::before{background:linear-gradient(90deg,var(--green),#4ade80);}
.kc-accent-purple::before{background:linear-gradient(90deg,var(--acc),var(--purple));}
.kv{font-size:30px;font-weight:900;letter-spacing:-1.5px;margin-bottom:5px;color:var(--t1);}
.kl{font-size:10px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:1px;}

/* Source Stats */
.sg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px;}
.sc{
  background:var(--s2);border:1px solid var(--bd);
  border-radius:16px;padding:20px 22px;
  box-shadow:var(--shadow);transition:.25s;
  position:relative;overflow:hidden;
}
.sc:hover{transform:translateY(-2px);}
.sct{font-size:11px;font-weight:800;color:var(--green);margin-bottom:16px;
  text-transform:uppercase;letter-spacing:1.2px;display:flex;align-items:center;gap:8px;}
.sct::before{content:'';width:7px;height:7px;border-radius:50%;background:var(--green);
  box-shadow:var(--glow-green);}
.scst{display:flex;justify-content:space-around;text-align:center;}
.scv{font-size:28px;font-weight:900;color:var(--t1);letter-spacing:-1px;}
.scl{font-size:10px;color:var(--t3);font-weight:700;text-transform:uppercase;margin-top:4px;}

/* =========================================
   TABLE
   ========================================= */
.tw{overflow-x:auto;border-radius:14px;}
table.mt{
  width:100%;border-collapse:collapse;
  background:var(--card);border-radius:14px;
  border:1px solid var(--bd);overflow:hidden;box-shadow:var(--shadow);
}
[data-theme="dark"] table.mt{background:var(--s2);}
table.mt th{
  background:var(--s3);padding:13px 16px;font-size:10px;
  color:var(--t3);text-transform:uppercase;font-weight:800;
  border-bottom:1px solid var(--bd);text-align:left;letter-spacing:1px;
}
table.mt td{
  padding:14px 16px;border-bottom:1px solid var(--bd);
  vertical-align:top;font-size:13px;color:var(--t1);
}
table.mt tr:last-child td{border-bottom:none;}
table.mt tr:hover td{background:var(--hover);}
.bbox{
  background:var(--s3);border:1px solid var(--bd);
  border-radius:10px;padding:10px 12px;
}
[data-theme="dark"] .bbox{background:rgba(255,255,255,.02);border-color:var(--bd);}
.bi{
  display:grid;grid-template-columns:170px 1fr 50px;
  gap:10px;padding:8px 0;
  border-bottom:1px dashed var(--bd);align-items:start;
}
.bi:last-child{border-bottom:none;padding-bottom:0;}
.olink{
  color:var(--green);font-weight:800;cursor:pointer;
  font-family:monospace;font-size:12px;
  background:rgba(34,197,94,.07);
  padding:4px 8px;border-radius:7px;
  border:1px solid rgba(34,197,94,.2);
  display:inline-flex;align-items:center;gap:4px;transition:.15s;
}
.olink:hover{background:rgba(34,197,94,.15);transform:translateY(-1px);}
.spill{
  display:inline-block;padding:4px 10px;
  border-radius:6px;font-size:11px;font-weight:700;
  margin-top:3px;white-space:nowrap;
  border:1px solid transparent;
}

/* =========================================
   STATUS FILTER PILLS
   ========================================= */
.pbx{
  background:var(--s2);border:1px solid var(--bd);
  border-radius:14px;padding:16px 20px;margin-bottom:18px;
}
.sp{
  padding:5px 13px;border-radius:7px;
  font-size:11.5px;font-weight:700;
  cursor:pointer;border:1.5px solid transparent;
  transition:.15s;display:inline-block;font-family:inherit;
}
.sp:hover{transform:translateY(-1px);}
.sp.on{box-shadow:0 0 0 2px rgba(255,255,255,.3);}

/* =========================================
   PROVIDER CARD
   ========================================= */
.pcard{
  background:var(--card);border:1px solid var(--bd);
  border-radius:18px;overflow:hidden;
  margin-bottom:22px;box-shadow:var(--shadow);transition:.2s;
}
[data-theme="dark"] .pcard{background:var(--s2);}
.pcard:hover{border-color:var(--bd2);}
.phdr{
  display:flex;justify-content:space-between;align-items:center;
  padding:18px 22px;border-bottom:1px solid var(--bd);
  flex-wrap:wrap;gap:14px;background:var(--s3);
}
[data-theme="dark"] .phdr{background:rgba(255,255,255,.025);}
.phdr-left{display:flex;flex-direction:column;gap:6px;}
.pname{font-size:17px;font-weight:800;color:var(--t1);letter-spacing:-.4px;}
.pname-sub{font-size:11px;color:var(--t3);}
.pname-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
.stars{color:var(--yellow);font-size:13px;letter-spacing:1.5px;}
.pbadge{padding:4px 12px;border-radius:6px;font-size:11px;font-weight:800;}
.pbadge.up{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.25);}
.pbadge.dn{background:rgba(248,113,113,.1);color:var(--red);border:1px solid rgba(248,113,113,.25);}
.pkbadge{
  background:linear-gradient(135deg,#f59e0b,#fbbf24);
  color:#000;padding:4px 12px;border-radius:6px;
  font-size:11px;font-weight:800;
}
.pstats{display:flex;gap:12px;align-items:center;flex-wrap:wrap;}
.pstat{
  text-align:center;cursor:pointer;
  padding:10px 16px;border-radius:12px;
  border:1.5px solid var(--bd);transition:.15s;min-width:72px;
  background:var(--s2);
}
[data-theme="dark"] .pstat{background:rgba(255,255,255,.03);}
.pstat:hover{background:rgba(139,92,246,.08);border-color:var(--acc);transform:translateY(-1px);}
.pstat-v{font-size:22px;font-weight:900;letter-spacing:-.5px;}
.pstat-l{font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:3px;letter-spacing:.8px;}
.csvbtn{
  padding:7px 14px;background:transparent;
  border:1.5px solid var(--bd);color:var(--t3);
  border-radius:9px;font-size:11px;cursor:pointer;font-family:inherit;
  transition:.15s;font-weight:700;
}
.csvbtn:hover{border-color:var(--yellow);color:var(--yellow);}

/* =========================================
   MATRIX TABLE
   ========================================= */
.tw2{overflow-x:auto;padding:4px 4px 8px;}
table.mx{width:100%;border-collapse:collapse;min-width:860px;}
table.mx th.dh{
  background:var(--s3);text-align:center;
  padding:11px 4px;font-size:11px;font-weight:800;
  color:var(--t2);border-bottom:2px solid var(--acc);
  border-left:1px solid var(--bd);
}
table.mx th.sh{
  background:var(--s3);text-align:center;
  padding:7px 3px;font-size:9px;font-weight:800;
  color:var(--t3);text-transform:uppercase;
  border-bottom:2px solid var(--bd);
  border-left:1px solid var(--bd);letter-spacing:.5px;
}
table.mx th.rh{
  background:var(--s3);text-align:left;
  padding:11px 16px;font-size:10px;font-weight:800;
  color:var(--t3);text-transform:uppercase;
  border-bottom:2px solid var(--acc);letter-spacing:1px;
}
table.mx td{
  padding:10px 6px;text-align:center;
  border-bottom:1px solid var(--bd);
  border-left:1px solid var(--bd);
  font-size:12px;font-weight:600;color:var(--t2);
}
table.mx td.rc{
  text-align:left;padding:10px 16px;
  font-weight:700;color:var(--t1);font-size:13px;
  border-left:none;background:var(--s3);
}
table.mx td.vo{color:var(--blue);}
table.mx td.vb{color:var(--green);}
table.mx td.vw{color:var(--yellow);}
table.mx td.vl{color:var(--purple);}
table.mx td.vg{color:var(--red);}
table.mx td.dash{color:var(--t4);font-size:10px;}
table.mx tr:hover td{background:var(--hover);}
table.mx tr.ttr td{background:rgba(139,92,246,.06);font-weight:900;font-size:13px;}
table.mx tr.ttr td.rc{color:var(--yellow);background:rgba(251,191,36,.05);}
table.mx tr.ttr td.vo{color:#93c5fd;}
table.mx tr.ttr td.vb{color:#86efac;}
table.mx tr.ttr td.vw{color:var(--yellow);}
table.mx td.clk{cursor:pointer;}
table.mx td.clk:hover{opacity:.75;text-decoration:underline;}
table.mx th.ds,table.mx td.ds{border-left:2px solid var(--bd2);}

/* =========================================
   REGIONAL
   ========================================= */
.reg-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:20px;}
.mini-card{
  background:var(--s2);border:1px solid var(--bd);
  border-radius:16px;padding:20px;box-shadow:var(--shadow);
}
.mini-title{font-size:13px;font-weight:800;color:var(--t1);margin-bottom:16px;display:flex;align-items:center;gap:8px;}
.mini-title .dot{width:8px;height:8px;border-radius:50%;}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.bar-label{font-size:11px;color:var(--t2);width:120px;flex-shrink:0;font-weight:600;}
.bar-track{flex:1;height:12px;background:var(--s3);border-radius:6px;overflow:hidden;}
.bar-fill{height:100%;border-radius:6px;transition:.6s;}
.bar-val{font-size:11px;font-weight:700;width:40px;text-align:right;color:var(--t2);}

/* WEEK LABEL */
.wklabel{
  font-size:11px;color:var(--acc);
  background:rgba(139,92,246,.08);
  border:1px solid rgba(139,92,246,.2);
  border-radius:20px;padding:6px 14px;
  display:inline-block;margin-bottom:18px;font-weight:700;
}

/* =========================================
   LOADER
   ========================================= */
.lw{text-align:center;padding:80px 20px;}
.ld{
  width:40px;height:40px;
  border:3px solid var(--bd);
  border-top-color:var(--acc);
  border-radius:50%;
  animation:sp .7s linear infinite;
  margin:0 auto 14px;
  box-shadow:0 0 12px rgba(139,92,246,.2);
}
@keyframes sp{to{transform:rotate(360deg)}}
.lp{color:var(--t3);font-size:13px;font-weight:500;}
.lp2{color:var(--t4);font-size:11px;margin-top:6px;}

/* =========================================
   MODALS
   ========================================= */
.mov{
  display:none;position:fixed;inset:0;
  background:rgba(0,0,0,.8);z-index:9999;
  backdrop-filter:blur(14px);
  justify-content:center;align-items:center;padding:20px;
}
.mov.open{display:flex;}
.mdl{
  background:var(--s1);border:1px solid var(--bd);
  border-radius:20px;padding:28px;
  width:100%;max-width:680px;
  max-height:88vh;overflow-y:auto;position:relative;
  box-shadow:0 24px 80px rgba(0,0,0,.7);
}
[data-theme="dark"] .mdl{background:#111;border-color:#1e1e1e;}
.mdl.wide{max-width:920px;}
.mcl{
  position:absolute;top:14px;right:14px;
  background:var(--s3);border:1px solid var(--bd);
  color:var(--t1);width:32px;height:32px;
  border-radius:50%;cursor:pointer;font-size:14px;
  display:flex;align-items:center;justify-content:center;transition:.15s;
}
.mcl:hover{background:var(--red);border-color:var(--red);color:#fff;}

/* Journey Timeline */
.tl{position:relative;padding-left:28px;margin-top:14px;}
.tl::before{
  content:'';position:absolute;left:9px;top:4px;bottom:4px;
  width:2px;background:linear-gradient(180deg,var(--green),rgba(139,92,246,.2));border-radius:2px;
}
.tli{position:relative;margin-bottom:14px;}
.tld{
  position:absolute;left:-21px;top:3px;
  width:11px;height:11px;border-radius:50%;
  border:2px solid var(--bd2);background:var(--s2);
}
.tld.done{background:var(--green);border-color:var(--green);box-shadow:0 0 6px rgba(34,197,94,.4);}
.tld.can{background:var(--red);border-color:var(--red);}
.tld.pend{border-color:var(--bd2);}
.tll{font-size:10px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.8px;}
.tlv{font-size:13px;color:var(--t1);font-weight:600;margin-top:2px;}
.tlv.pv{color:var(--t4);font-style:italic;}
.tlv.cv{color:var(--red);}
.mg{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;}
.mc{background:var(--s3);border:1px solid var(--bd);border-radius:12px;padding:14px;text-align:center;}
.mv{font-size:20px;font-weight:900;color:var(--green);}
.mv.w{color:var(--yellow);}.mv.d{color:var(--red);}.mv.n{color:var(--t3);font-size:14px;}
.ml{font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:4px;}
.stp-g{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:16px;}
.stp{background:var(--s3);border:1px solid var(--bd);border-radius:10px;padding:10px;text-align:center;}
.stpv{font-size:13px;font-weight:700;color:var(--t1);}
.stpl{font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-bottom:2px;}
.cbanner{
  background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.25);
  border-radius:10px;padding:10px 14px;margin-bottom:14px;
  color:var(--red);font-weight:700;font-size:12px;
}
.shd{
  font-size:10px;font-weight:800;text-transform:uppercase;
  letter-spacing:1.2px;color:var(--acc);
  margin:16px 0 10px;padding-bottom:7px;border-bottom:1px solid var(--bd);
}
.mld{width:24px;height:24px;border:3px solid var(--bd);border-top-color:var(--green);border-radius:50%;animation:sp .7s linear infinite;margin:28px auto;}
.rc{font-size:12px;color:var(--t3);margin-bottom:10px;}
.rc b{color:var(--t1);}

/* Section header */
.section-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;}
.section-title{font-size:20px;font-weight:800;color:var(--t1);letter-spacing:-.5px;}
.section-sub{font-size:12px;color:var(--t3);margin-top:2px;}

/* Empty state */
.empty-state{text-align:center;padding:80px 20px;color:var(--t3);background:var(--s2);border:1px solid var(--bd);border-radius:16px;}
.empty-icon{font-size:48px;margin-bottom:16px;opacity:.4;}

/* =========================================
   USER CARD IN SIDEBAR
   ========================================= */
.sb-user-card{
  display:flex;align-items:center;gap:10px;
  padding:10px 12px;border-radius:10px;
  background:rgba(139,92,246,.08);
  border:1px solid rgba(139,92,246,.2);
  margin-bottom:8px;
}
.sb-user-avatar{
  width:34px;height:34px;border-radius:50%;
  background:linear-gradient(135deg,#7c3aed,#8b5cf6);
  display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:900;color:#fff;flex-shrink:0;
  box-shadow:0 2px 8px rgba(139,92,246,.4);
}
.sb-user-info{overflow:hidden;flex:1;}
.sb-user-email{font-size:10px;font-weight:700;color:#a78bfa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sb-user-role{font-size:9px;color:var(--sb-text);margin-top:1px;text-transform:uppercase;letter-spacing:.8px;}
.sb-last-update{font-size:9px;color:var(--sb-text);margin-bottom:8px;padding:0 4px;letter-spacing:.3px;}

/* =========================================
   KPI CARDS - UPGRADED
   ========================================= */
.kc-inner{display:flex;align-items:flex-start;justify-content:space-between;}
.kc-icon{
  width:44px;height:44px;border-radius:12px;
  display:flex;align-items:center;justify-content:center;
  font-size:22px;flex-shrink:0;
}
.kc-data{flex:1;}
.kc-trend{
  font-size:10px;font-weight:700;margin-top:6px;
  display:flex;align-items:center;gap:4px;
}
.kc-trend.up{color:var(--green);}
.kc-trend.dn{color:var(--red);}
.kc-trend.neu{color:var(--t3);}

/* =========================================
   ORDER SEARCH
   ========================================= */
.os-result-card{
  background:var(--s2);border:1px solid var(--bd);
  border-radius:16px;padding:24px;margin-bottom:18px;
  box-shadow:var(--shadow);
}
.os-header{display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-bottom:20px;}
.os-order-id{font-size:22px;font-weight:900;font-family:monospace;color:var(--acc);letter-spacing:-.5px;}
.os-status-badge{padding:6px 14px;border-radius:8px;font-size:12px;font-weight:800;border:1.5px solid transparent;}
.os-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:20px;}
.os-info-box{background:var(--s3);border:1px solid var(--bd);border-radius:12px;padding:14px;}
.os-info-label{font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700;letter-spacing:1px;margin-bottom:6px;}
.os-info-val{font-size:14px;font-weight:800;color:var(--t1);}
.os-bundle-section{margin-top:18px;}
.os-bundle-title{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--acc);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--bd);}
.os-sibling{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 14px;border-radius:10px;
  background:var(--s3);border:1px solid var(--bd);
  margin-bottom:8px;transition:.15s;
}
.os-sibling.is-self{border-color:var(--acc);background:rgba(139,92,246,.08);}
.os-sibling:hover{border-color:var(--bd2);}
.os-sibling-id{font-family:monospace;font-weight:800;color:var(--green);font-size:12px;}
.os-sibling-detail{font-size:11px;color:var(--t3);}
.os-comparison-box{
  background:linear-gradient(135deg,rgba(34,197,94,.06),rgba(139,92,246,.06));
  border:1px solid rgba(34,197,94,.2);
  border-radius:12px;padding:16px;margin-top:16px;
}
.os-comp-title{font-size:11px;font-weight:800;color:var(--green);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;}
.os-comp-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px dashed rgba(255,255,255,.05);}
.os-comp-row:last-child{border-bottom:none;}
.os-comp-label{font-size:12px;color:var(--t3);}
.os-comp-val{font-size:13px;font-weight:800;}
.sla-badge{
  display:inline-flex;align-items:center;gap:5px;
  padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;
}
.sla-ok{background:rgba(34,197,94,.1);color:var(--green);border:1px solid rgba(34,197,94,.25);}
.sla-warn{background:rgba(251,191,36,.1);color:var(--yellow);border:1px solid rgba(251,191,36,.25);}
.sla-breach{background:rgba(248,113,113,.12);color:var(--red);border:1px solid rgba(248,113,113,.3);animation:pulse-red 2s ease infinite;}
@keyframes pulse-red{0%,100%{box-shadow:0 0 0 0 rgba(248,113,113,0);}50%{box-shadow:0 0 0 4px rgba(248,113,113,.2);}}

/* =========================================
   CUSTOMER PROFILES
   ========================================= */
.cust-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}
.cust-card{
  background:var(--s2);border:1px solid var(--bd);
  border-radius:16px;padding:20px;
  box-shadow:var(--shadow);transition:.2s;cursor:pointer;
  position:relative;overflow:hidden;
}
.cust-card:hover{transform:translateY(-3px);box-shadow:var(--shadow2);border-color:var(--acc);}
.cust-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--acc),var(--purple));}
.cust-avatar{
  width:46px;height:46px;border-radius:14px;
  display:flex;align-items:center;justify-content:center;
  font-size:18px;font-weight:900;color:#fff;
  margin-bottom:12px;
  background:linear-gradient(135deg,var(--acc2),var(--purple));
  box-shadow:0 4px 12px rgba(139,92,246,.3);
}
.cust-name{font-size:14px;font-weight:800;color:var(--t1);margin-bottom:3px;letter-spacing:-.2px;}
.cust-vendor{font-size:11px;color:var(--t3);margin-bottom:14px;}
.cust-stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.cust-stat{background:var(--s3);border:1px solid var(--bd);border-radius:9px;padding:10px;text-align:center;}
.cust-stat-v{font-size:18px;font-weight:900;color:var(--t1);letter-spacing:-.5px;}
.cust-stat-l{font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:2px;}
.cust-saved{
  margin-top:10px;padding:10px;
  background:rgba(34,197,94,.07);border:1px solid rgba(34,197,94,.2);
  border-radius:9px;text-align:center;
}
.cust-saved-v{font-size:20px;font-weight:900;color:var(--green);}
.cust-saved-l{font-size:9px;color:var(--green);text-transform:uppercase;font-weight:700;opacity:.8;}
.cust-countries{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px;}
.cust-country-tag{font-size:10px;padding:3px 8px;background:var(--s3);border:1px solid var(--bd);border-radius:20px;color:var(--t3);font-weight:600;}

/* =========================================
   ROUTE INTELLIGENCE
   ========================================= */
.route-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px;}
.route-card{background:var(--s2);border:1px solid var(--bd);border-radius:16px;padding:22px;box-shadow:var(--shadow);}
.route-country{font-size:16px;font-weight:800;color:var(--t1);margin-bottom:4px;display:flex;align-items:center;gap:10px;}
.route-insight{font-size:11px;color:var(--acc);font-weight:700;margin-bottom:16px;padding:6px 10px;background:rgba(139,92,246,.08);border-radius:8px;display:inline-block;}
.route-day-bars{margin-top:12px;}
.route-day-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
.route-day-label{font-size:11px;font-weight:700;width:32px;color:var(--t2);}
.route-day-track{flex:1;height:20px;background:var(--s3);border-radius:6px;overflow:hidden;position:relative;}
.route-day-fill{height:100%;border-radius:6px;transition:.7s;display:flex;align-items:center;padding-left:8px;}
.route-day-fill span{font-size:10px;font-weight:800;color:#000;opacity:.9;}
.route-day-val{font-size:11px;font-weight:700;width:30px;text-align:right;color:var(--t2);}
.route-best-tag{font-size:10px;padding:2px 8px;border-radius:20px;background:rgba(34,197,94,.15);color:var(--green);font-weight:800;border:1px solid rgba(34,197,94,.3);}

@media(max-width:900px){.cust-grid{grid-template-columns:1fr 1fr;}.route-grid{grid-template-columns:1fr;}}
@media(max-width:600px){.cust-grid{grid-template-columns:1fr;}.os-grid{grid-template-columns:1fr;}}

/* =========================================
   ANALYTICS
   ========================================= */
.an-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px;}
.an-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px;}
.an-card{
  background:var(--s2);border:1px solid var(--bd);
  border-radius:16px;padding:22px;box-shadow:var(--shadow);
  position:relative;overflow:hidden;transition:.2s;
}
.an-card:hover{transform:translateY(-2px);box-shadow:var(--shadow2);}
.an-card-title{
  font-size:11px;font-weight:800;text-transform:uppercase;
  letter-spacing:1px;color:var(--t3);margin-bottom:16px;
  display:flex;align-items:center;gap:8px;
}
.an-card-title .dot{width:7px;height:7px;border-radius:50%;}
.donut-wrap{display:flex;align-items:center;gap:24px;}
.donut-svg{flex-shrink:0;}
.donut-legend{flex:1;}
.legend-item{display:flex;align-items:center;gap:10px;padding:7px 10px;border-radius:8px;margin-bottom:4px;transition:.15s;}
.legend-item.clk-item{cursor:pointer;}
.legend-item.clk-item:hover{background:var(--hover);}
.legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;}
.legend-label{font-size:12px;font-weight:600;color:var(--t1);flex:1;}
.legend-val{font-size:13px;font-weight:900;color:var(--t1);}
.legend-pct{font-size:10px;color:var(--t3);margin-left:4px;}
.an-bar-row{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.an-bar-label{font-size:11px;color:var(--t2);width:130px;flex-shrink:0;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.an-bar-track{flex:1;height:14px;background:var(--s3);border-radius:7px;overflow:hidden;cursor:pointer;transition:.15s;}
.an-bar-track:hover{opacity:.8;}
.an-bar-fill{height:100%;border-radius:7px;transition:.7s;}
.an-bar-val{font-size:11px;font-weight:800;width:48px;text-align:right;}
.an-hero{text-align:center;padding:10px 0;}
.an-hero-val{font-size:36px;font-weight:900;letter-spacing:-2px;}
.an-hero-label{font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700;letter-spacing:1px;margin-top:4px;}
.guest-blur{filter:blur(6px);pointer-events:none;user-select:none;}

/* Responsive */
@media(max-width:1024px){
  .sidebar{width:200px;}
  .sb-tab-label{font-size:11.5px;}
}
@media(max-width:768px){
  .sidebar{position:fixed;left:-240px;z-index:999;height:100%;transition:left .25s;}
  .sidebar.open{left:0;}
  .main-wrap{width:100%;}
  .kg{grid-template-columns:1fr 1fr;}
  .sg{grid-template-columns:1fr;}
  .reg-grid{grid-template-columns:1fr;}
  .an-grid{grid-template-columns:1fr 1fr;}
  .an-grid-2{grid-template-columns:1fr;}
}
@media(max-width:520px){
  .kg{grid-template-columns:1fr;}
  .an-grid{grid-template-columns:1fr;}
}

</style>
</head>
<body>
<div class="app-wrap">

<!-- SIDEBAR -->
<aside class="sidebar" id="sidebar">
  <div class="sb-head">
    <div class="sb-logo-wrap">
      <div class="sb-ico">3PL</div>
      <div class="sb-info">
        <div class="sb-title">3PL Dashboard</div>
        <div class="sb-sub">Bundling Intelligence Hub</div>
      </div>
    </div>
  </div>
  <nav class="sb-nav">
    <div class="sb-section-label">Workspace</div>
    <button class="sb-tab active" data-pane="bundle" onclick="sw('bundle',this)">
      <span class="sb-tab-icon">📦</span>
      <span class="sb-tab-label">Bundle Intelligence</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="status" onclick="sw('status',this)">
      <span class="sb-tab-icon">📡</span>
      <span class="sb-tab-label">Status Intelligence</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="search" onclick="sw('search',this)">
      <span class="sb-tab-icon">🔍</span>
      <span class="sb-tab-label">Order Search</span>
      <span class="sb-tab-dot"></span>
    </button>
    <div class="sb-section-label" style="margin-top:8px">Intelligence</div>
    <button class="sb-tab" data-pane="customers" onclick="sw('customers',this)">
      <span class="sb-tab-icon">👥</span>
      <span class="sb-tab-label">Customers</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="route" onclick="sw('route',this)">
      <span class="sb-tab-icon">🛣️</span>
      <span class="sb-tab-label">Route Intelligence</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="analytics" onclick="sw('analytics',this)">
      <span class="sb-tab-icon">📈</span>
      <span class="sb-tab-label">Analytics</span>
      <span class="sb-tab-dot"></span>
    </button>
    <div class="sb-section-label" style="margin-top:8px">Reports</div>
    <button class="sb-tab" data-pane="summary" onclick="sw('summary',this)">
      <span class="sb-tab-icon">📊</span>
      <span class="sb-tab-label">Weekly Summary</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="week4" onclick="sw('week4',this)">
      <span class="sb-tab-icon">📅</span>
      <span class="sb-tab-label">4-Week Summary</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="regional" onclick="sw('regional',this)">
      <span class="sb-tab-icon">🌍</span>
      <span class="sb-tab-label">Regional View</span>
      <span class="sb-tab-dot"></span>
    </button>
    <div class="sb-section-label" style="margin-top:8px" id="sbToolsLabel">Tools</div>
    <button class="sb-tab" data-pane="receipt" onclick="sw('receipt',this)" id="sbReceipt">
      <span class="sb-tab-icon">🧾</span>
      <span class="sb-tab-label">Bundle Receipts</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="predict" onclick="sw('predict',this)" id="sbPredict">
      <span class="sb-tab-icon">🔮</span>
      <span class="sb-tab-label">Prediction</span>
      <span class="sb-tab-dot"></span>
    </button>
    <button class="sb-tab" data-pane="certificate" onclick="sw('certificate',this)" id="sbCertificate">
      <span class="sb-tab-icon">🏅</span>
      <span class="sb-tab-label">Savings Certificate</span>
      <span class="sb-tab-dot"></span>
    </button>
  </nav>
  <div class="sb-foot">
    <div class="sb-foot-divider"></div>
    <div class="sb-user-card" id="sbUserCard">
      <div class="sb-user-avatar" id="sbAvatar">?</div>
      <div class="sb-user-info">
        <div class="sb-user-email" id="sbEmail">Loading...</div>
        <div class="sb-user-role">Administrator</div>
      </div>
    </div>
    <div class="sb-last-update" id="sbLastUpdate">🕐 Last update: —</div>
  </div>
</aside>

<!-- MAIN CONTENT -->
<div class="main-wrap">
  <div class="topbar">
    <div style="display:flex;align-items:center;gap:12px">
      <button class="sb-toggle-fixed" onclick="toggleSidebar()" title="Toggle sidebar" id="sbToggle">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <rect x="2" y="4.5" width="14" height="1.8" rx=".9" fill="currentColor"/>
          <rect x="2" y="8.1" width="9" height="1.8" rx=".9" fill="currentColor"/>
          <rect x="2" y="11.7" width="14" height="1.8" rx=".9" fill="currentColor"/>
        </svg>
      </button>
      <div class="tb-page-title" id="tbTitle">📦 Bundle Intelligence</div>
    </div>
    <div class="tb-actions">
      <button class="tbtn tbtn-refresh" onclick="hardRefresh()">🔄 Refresh</button>
      <a href="/" class="tbtn tbtn-home" title="Main Dashboard" style="text-decoration:none;display:flex;align-items:center;gap:5px">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9 11L5 7l4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Main Dashboard
      </a>
      <button class="tbtn tbtn-theme-inline" id="themeInlineBtn" onclick="toggleTheme()" title="Toggle theme">☀️</button>
    </div>
  </div>

<!-- MAIN -->
<div class="main">
  <!-- GLOBAL LOADER -->
  <div id="gLoad" class="lw">
    <div class="ld"></div>
    <p class="lp">Loading data from all sources...</p>
    <p class="lp2" id="lStat">Connecting...</p>
  </div>

  <!-- ===== BUNDLE TAB ===== -->
  <div class="pane active" id="pane-bundle">
    <div class="fbar">
      <div class="frow">
        <div class="fg fg-grow">
          <div class="fl">🔍 Search Order ID or Customer</div>
          <input type="text" id="bq" class="fi" placeholder="e.g. 12345 or John Doe" oninput="rBundle()">
        </div>
        <div class="fg">
          <div class="fl">📅 From</div>
          <input type="date" id="bf" class="fi" onchange="rBundle()">
        </div>
        <div class="fg">
          <div class="fl">📅 To</div>
          <input type="date" id="bt" class="fi" onchange="rBundle()">
        </div>
        <div class="fg">
          <div class="fl">Source</div>
          <select id="bs" class="fi" onchange="rBundle()">
            <option value="all">All Sources</option>
            <option value="ECL QC Center">ECL QC Center</option>
            <option value="ECL Zone">ECL Zone</option>
            <option value="GE Zone">GE Zone</option>
          </select>
        </div>
      </div>
    </div>

    <div class="sg">
      <div class="sc">
        <div class="sct">ECL QC Center</div>
        <div class="scst">
          <div><div class="scv" id="bqo">0</div><div class="scl">Orders</div></div>
          <div style="width:1px;background:var(--bd);"></div>
          <div><div class="scv" id="bqb">0</div><div class="scl">Bundles</div></div>
        </div>
      </div>
      <div class="sc" style="border-left:3px solid var(--blue)">
        <div class="sct" style="color:var(--blue)">PK Zone (ECL &amp; GE)</div>
        <div class="scst">
          <div><div class="scv" id="bpo">0</div><div class="scl">Orders</div></div>
          <div style="width:1px;background:var(--bd);"></div>
          <div><div class="scv" id="bpb">0</div><div class="scl">Bundles</div></div>
        </div>
      </div>
    </div>

    <div class="kg">
      <div class="kc">
        <div class="kc-inner">
          <div class="kc-data">
            <div class="kv" id="bk1">0</div>
            <div class="kl">📦 Bundles Packed</div>
          </div>
          <div class="kc-icon" style="background:rgba(96,165,250,.1)">📦</div>
        </div>
      </div>
      <div class="kc">
        <div class="kc-inner">
          <div class="kc-data">
            <div class="kv" id="bk2">0</div>
            <div class="kl">🛒 Orders Merged</div>
          </div>
          <div class="kc-icon" style="background:rgba(167,139,250,.1)">🛒</div>
        </div>
      </div>
      <div class="kc kc-accent-yellow">
        <div class="kc-inner">
          <div class="kc-data">
            <div class="kv" id="bk3" style="color:var(--yellow)">0</div>
            <div class="kl" style="color:var(--yellow)">🚚 Shipments Saved</div>
          </div>
          <div class="kc-icon" style="background:rgba(251,191,36,.1)">🚚</div>
        </div>
      </div>
      <div class="kc kc-accent-green">
        <div class="kc-inner">
          <div class="kc-data">
            <div class="kv" id="bk4" style="color:var(--green)">£0</div>
            <div class="kl" style="color:var(--green)">💰 Total Saved (Est.)</div>
          </div>
          <div class="kc-icon" style="background:rgba(34,197,94,.1)">💰</div>
        </div>
      </div>
    </div>

    <div class="tw">
      <table class="mt">
        <thead>
          <tr>
            <th>Date &amp; Source</th>
            <th>Client</th>
            <th>📦 Box Analytics</th>
            <th>Orders (click → Journey)</th>
          </tr>
        </thead>
        <tbody id="btb"></tbody>
      </table>
    </div>
  </div>

  <!-- ===== STATUS TAB ===== -->
  <div class="pane" id="pane-status">
    <div class="fbar">
      <div class="frow">
        <div class="fg" style="flex:1">
          <div class="fl">⚡ Quick Select</div>
          <div class="qbtns">
            <button class="qb" onclick="qs(this,'today')">Today</button>
            <button class="qb" onclick="qs(this,'7d')">Last 7 Days</button>
            <button class="qb" onclick="qs(this,'15d')">Last 15 Days</button>
            <button class="qb" onclick="qs(this,'30d')">Last 30 Days</button>
            <button class="qb" onclick="qs(this,'week')">This Week</button>
            <button class="qb" onclick="qs(this,'month')">This Month</button>
          </div>
        </div>
      </div>
      <div class="frow">
        <div class="fg"><div class="fl">📅 From</div><input type="date" id="sf" class="fi"></div>
        <div class="fg"><div class="fl">📅 To</div><input type="date" id="st" class="fi"></div>
        <div class="fg fg-grow">
          <div class="fl">🔍 Search</div>
          <input type="text" id="sq" class="fi" placeholder="Order ID or customer...">
        </div>
        <div class="fg">
          <div class="fl">Source</div>
          <select id="ss" class="fi">
            <option value="all">All Sources</option>
            <option value="ECL QC Center">ECL QC Center</option>
            <option value="ECL Zone">ECL Zone</option>
            <option value="GE Zone">GE Zone</option>
          </select>
        </div>
        <div class="fg" style="flex-direction:row;gap:8px;align-items:flex-end">
          <button class="cbtn" onclick="clrSt()">Clear</button>
          <button class="abtn" onclick="rStatus()">Apply</button>
        </div>
      </div>
    </div>

    <div id="spw" style="display:none" class="pbx">
      <div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1px;color:var(--acc);margin-bottom:10px">
        📊 Filter by Status — click to select
      </div>
      <div id="spills" style="display:flex;flex-wrap:wrap;gap:7px"></div>
    </div>

    <div class="kg">
      <div class="kc"><div class="kv" id="stot">0</div><div class="kl">Total Orders</div></div>
      <div class="kc kc-accent-green"><div class="kv" id="sdel" style="color:var(--green)">0</div><div class="kl" style="color:var(--green)">Delivered</div></div>
      <div class="kc kc-accent-yellow"><div class="kv" id="str2" style="color:var(--yellow)">0</div><div class="kl" style="color:var(--yellow)">In Transit</div></div>
      <div class="kc" style="--kc-accent:var(--red)"><div class="kv" id="scan" style="color:var(--red)">0</div><div class="kl" style="color:var(--red)">Cancelled</div></div>
    </div>
    <div class="rc" id="src2"></div>
    <div class="tw">
      <table class="mt">
        <thead>
          <tr>
            <th>#</th><th>Order ID</th><th>Date</th><th>Status</th>
            <th>Source</th><th>Customer</th><th>Country</th><th>Weight</th>
          </tr>
        </thead>
        <tbody id="stb"></tbody>
      </table>
    </div>
  </div>

  <!-- ===== WEEKLY SUMMARY TAB ===== -->
  <div class="pane" id="pane-summary">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px">
        <div class="fg">
          <div class="fl">Week Starting (Monday)</div>
          <input type="date" id="ws" class="fi">
        </div>
        <div class="fg">
          <div class="fl">&nbsp;</div>
          <div class="qbtns">
            <button class="qb on" onclick="setWk(0,this)">This Week</button>
            <button class="qb" onclick="setWk(-1,this)">Last Week</button>
            <button class="qb" onclick="setWk(-2,this)">2 Weeks Ago</button>
          </div>
        </div>
        <div class="fg">
          <div class="fl">&nbsp;</div>
          <button class="abtn" onclick="rSummary()">Load Week</button>
        </div>
      </div>
    </div>
    <div id="sumCards"></div>
  </div>

  <!-- ===== 4-WEEK TAB ===== -->
  <div class="pane" id="pane-week4">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px">
        <div class="fg">
          <div class="fl">Latest Monday</div>
          <input type="date" id="w4e" class="fi">
        </div>
        <div class="fg">
          <div class="fl">&nbsp;</div>
          <button class="qb on" onclick="setW4Now(this)">Current 4 Weeks</button>
        </div>
        <div class="fg">
          <div class="fl">&nbsp;</div>
          <button class="abtn" onclick="rW4()">Load</button>
        </div>
      </div>
    </div>
    <div id="w4cards"></div>
  </div>

  <!-- ===== REGIONAL VIEW TAB ===== -->
  <div class="pane" id="pane-regional">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px">
        <div class="fg">
          <div class="fl">Week Starting (Monday)</div>
          <input type="date" id="rws" class="fi">
        </div>
        <div class="fg">
          <div class="fl">&nbsp;</div>
          <div class="qbtns">
            <button class="qb on" onclick="setRWk(0,this)">This Week</button>
            <button class="qb" onclick="setRWk(-1,this)">Last Week</button>
            <button class="qb" onclick="setRWk(-2,this)">2 Weeks Ago</button>
          </div>
        </div>
        <div class="fg">
          <div class="fl">&nbsp;</div>
          <button class="abtn" onclick="rRegional()">Load</button>
        </div>
      </div>
    </div>
    <div id="regCards"></div>
  </div>

  <!-- ===== ANALYTICS TAB ===== -->
  <div class="pane" id="pane-analytics">
    <div id="analyticsBody"></div>
  </div>

  <!-- ===== ORDER SEARCH TAB ===== -->
  <div class="pane" id="pane-search">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px">
        <div class="fg" style="flex:1">
          <div class="fl">🔍 Search by Order ID</div>
          <input type="text" id="osq" class="fi" placeholder="e.g. 132514_06 — press Enter or click Search" onkeydown="if(event.key==='Enter')rOrderSearch()">
        </div>
        <div class="fg"><div class="fl">&nbsp;</div><button class="abtn" onclick="rOrderSearch()">🔍 Search</button></div>
      </div>
    </div>
    <div id="osResult"></div>
  </div>

  <!-- ===== CUSTOMERS TAB ===== -->
  <div class="pane" id="pane-customers">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px">
        <div class="fg" style="flex:1">
          <div class="fl">🔍 Filter Customer</div>
          <input type="text" id="custQ" class="fi" placeholder="Customer name..." oninput="rCustomers()">
        </div>
        <div class="fg">
          <div class="fl">Sort By</div>
          <select id="custSort" class="fi" onchange="rCustomers()">
            <option value="orders">Most Orders</option>
            <option value="saved">Most Saved (£)</option>
            <option value="weight">Total Weight</option>
          </select>
        </div>
      </div>
    </div>
    <div id="custCards"></div>
  </div>

  <!-- ===== ROUTE INTELLIGENCE TAB ===== -->
  <div class="pane" id="pane-route">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px">
        <div class="fg">
          <div class="fl">📅 From Date</div>
          <input type="date" id="rtFrom" class="fi" onchange="rRoute()">
        </div>
        <div class="fg">
          <div class="fl">📅 To Date</div>
          <input type="date" id="rtTo" class="fi" onchange="rRoute()">
        </div>
        <div class="fg">
          <div class="fl">🌍 Country Filter</div>
          <input type="text" id="rtCountry" class="fi" placeholder="e.g. United Kingdom" oninput="rRoute()">
        </div>
        <div class="fg"><div class="fl">&nbsp;</div>
          <div style="display:flex;gap:8px">
            <button class="qb on" onclick="setRouteRange(0,this)">All Time</button>
            <button class="qb" onclick="setRouteRange(30,this)">30 Days</button>
            <button class="qb" onclick="setRouteRange(7,this)">7 Days</button>
            <button class="cbtn" onclick="clearRouteFilter(this)">Clear</button>
          </div>
        </div>
      </div>
    </div>
    <div id="routeBody"></div>
  </div>


  <!-- ===== BUNDLE RECEIPT TAB ===== -->
  <div class="pane" id="pane-receipt">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px">
        <div class="fg fg-grow">
          <div class="fl">🔍 Search Bundle by Order ID or Customer</div>
          <input type="text" id="rcptQ" class="fi" placeholder="e.g. 133325_02 or luciana rivera" oninput="rReceipt()">
        </div>
        <div class="fg">
          <div class="fl">📅 From</div>
          <input type="date" id="rcptFrom" class="fi" onchange="rReceipt()">
        </div>
        <div class="fg">
          <div class="fl">📅 To</div>
          <input type="date" id="rcptTo" class="fi" onchange="rReceipt()">
        </div>
        <div class="fg"><div class="fl">&nbsp;</div>
          <button class="cbtn" onclick="g('rcptQ').value='';g('rcptFrom').value='';g('rcptTo').value='';rReceipt()">Clear</button>
        </div>
      </div>
    </div>
    <div id="rcptList"></div>
  </div>

  <!-- ===== PREDICTION TAB ===== -->
  <div class="pane" id="pane-predict">
    <div id="predictBody"></div>
  </div>

  <!-- ===== SAVINGS CERTIFICATE TAB ===== -->
  <div class="pane" id="pane-certificate">
    <div class="fbar">
      <div class="frow" style="align-items:flex-end;gap:14px;flex-wrap:wrap">
        <div class="fg">
          <div class="fl">📅 Quarter</div>
          <select id="certQuarter" class="fi" onchange="rCertificate()">
            <option value="Q1">Q1 (Jan–Mar)</option>
            <option value="Q2">Q2 (Apr–Jun)</option>
            <option value="Q3">Q3 (Jul–Sep)</option>
            <option value="Q4">Q4 (Oct–Dec)</option>
          </select>
        </div>
        <div class="fg">
          <div class="fl">📅 Year</div>
          <select id="certYear" class="fi" onchange="rCertificate()">
            <option value="2026">2026</option>
            <option value="2025">2025</option>
            <option value="2024">2024</option>
          </select>
        </div>
        <div class="fg"><div class="fl">&nbsp;</div>
          <button class="abtn" onclick="printCertificate()">🖨️ Print / Save PDF</button>
        </div>
      </div>
    </div>
    <div id="certBody"></div>
  </div>

</div>

</div><!-- /main -->
</div><!-- /main-wrap -->
</div><!-- /app-wrap -->

<!-- JOURNEY MODAL -->
<div class="mov" id="jMov" onclick="if(event.target===this)cMod('jMov')">
  <div class="mdl">
    <button class="mcl" onclick="cMod('jMov')">✕</button>
    <div id="jBody"><div class="mld"></div></div>
  </div>
</div>

<!-- ORDERS MODAL -->
<div class="mov" id="oMov" onclick="if(event.target===this)cMod('oMov')">
  <div class="mdl wide">
    <button class="mcl" onclick="cMod('oMov')">✕</button>
    <div style="font-size:15px;font-weight:800;color:var(--yellow);margin-bottom:16px" id="oTit">Orders</div>
    <div id="oBody"></div>
  </div>
</div>

<script>
// ============================================================
// THEME TOGGLE
// ============================================================
function toggleSidebar(){
  const sb=document.getElementById('sidebar');
  if(!sb) return;
  const isCollapsed=sb.classList.toggle('collapsed');
  try{localStorage.setItem('sb_collapsed',isCollapsed?'1':'0');}catch(e){}
}
// Restore sidebar collapse state on load
(function(){
  try{
    if(localStorage.getItem('sb_collapsed')==='1'){
      const sb=document.getElementById('sidebar');
      if(sb) sb.classList.add('collapsed');
    }
  }catch(e){}
})();

function toggleTheme(){
  const html=document.documentElement;
  const isDark=html.getAttribute('data-theme')==='dark';
  html.setAttribute('data-theme',isDark?'light':'dark');
  const pill=document.getElementById('themePill');
  const lbl=document.getElementById('themeLabel');
  const inlineBtn=document.getElementById('themeInlineBtn');
  if(isDark){
    if(pill){pill.querySelector('.icon').textContent='🌙'; lbl.textContent='Dark Mode';}
    if(inlineBtn) inlineBtn.textContent='🌙';
  } else {
    if(pill){pill.querySelector('.icon').textContent='☀️'; lbl.textContent='Light Mode';}
    if(inlineBtn) inlineBtn.textContent='☀️';
  }
  try{localStorage.setItem('bih_theme',isDark?'light':'dark');}catch(e){}
  if(_rendered.status) setTimeout(rStatus,0);
}
// Load saved theme
(function(){
  try{
    const saved=localStorage.getItem('bih_theme');
    const inlineBtn=document.getElementById('themeInlineBtn');
    if(saved==='light'){
      document.documentElement.setAttribute('data-theme','light');
      document.addEventListener('DOMContentLoaded',function(){
        const pill=document.getElementById('themePill');
        if(pill){pill.querySelector('.icon').textContent='🌙';document.getElementById('themeLabel').textContent='Dark Mode';}
        if(inlineBtn) inlineBtn.textContent='🌙';
      });
    } else {
      if(inlineBtn) inlineBtn.textContent='☀️';
    }
  }catch(e){}
})();

// ============================================================
// GLOBAL STATE
// ============================================================
let D=null, SEL=null;
const DAYS=["MON","TUE","WED","THU","FRI","SAT","SUN"];
const FLT=[1,3,5]; // Tue Thu Sat = flight days
const SRCS=["ECL QC Center","ECL Zone","GE Zone"];

// ============================================================
// INIT
// ============================================================
async function init(){
  const ls=g("lStat");
  try{
    ls.textContent="Fetching from 3 sources simultaneously...";
    const r=await fetch("/api/nexus/app_data");
    if(!r.ok) throw new Error("HTTP "+r.status);
    D=await r.json();
    const mon=gMon(new Date());
    g("ws").value=fi(mon); g("w4e").value=fi(mon); g("rws").value=fi(mon);
    g("gLoad").style.display="none";
    g("pane-bundle").classList.add("active");
    _rendered.bundle=true;
    cacheRates();
    initUserCard();
    updateLastUpdate();
    // Hide tabs based on access
    if(GUEST){
      const hideIds=["sbPredict","sbCertificate","sbToolsLabel"];
      hideIds.forEach(id=>{const el=g(id);if(el)el.style.display="none";});
    }
    // Auto-set current quarter
    const _now=new Date();
    const _qm=_now.getMonth();
    const _q=_qm<3?"Q1":_qm<6?"Q2":_qm<9?"Q3":"Q4";
    const _qs=g("certQuarter"); if(_qs) _qs.value=_q;
    const _ys=g("certYear"); if(_ys) _ys.value=_now.getFullYear();
    rBundle();
  }catch(e){
    g("gLoad").innerHTML=`<div style="color:var(--red);font-size:14px">Error: ${e.message}<br><br><button class="abtn" onclick="init()">Retry</button></div>`;
  }
}
function hardRefresh(){
  D=null;
  Object.keys(_rendered).forEach(k=>_rendered[k]=false);
  g("gLoad").style.display="block";
  document.querySelectorAll(".pane").forEach(p=>p.classList.remove("active"));
  document.querySelectorAll(".sb-tab").forEach(t=>t.classList.remove("active"));
  document.querySelector(".sb-tab[data-pane='bundle']").classList.add("active");
  if(g("tbTitle")) g("tbTitle").textContent="📦 Bundle Intelligence";
  _bPage=0; _bFiltered=[]; _stPage=0; _stFiltered=[];
  init();
}

// ============================================================
// TAB SWITCH
// ============================================================
const _rendered={bundle:false,status:false,summary:false,week4:false,regional:false,analytics:false,search:false,customers:false,route:false,receipt:false,predict:false,certificate:false};
const PAGE_TITLES={bundle:"📦 Bundle Intelligence",status:"📡 Status Intelligence",summary:"📊 Weekly Summary",week4:"📅 4-Week Summary",regional:"🌍 Regional View",analytics:"📈 Analytics",search:"🔍 Order Search",customers:"👥 Customer Intelligence",route:"🛣️ Route Intelligence",receipt:"🧾 Bundle Receipts",predict:"🔮 Prediction",certificate:"🏅 Savings Certificate"};
function sw(name,tab){
  document.querySelectorAll(".sb-tab").forEach(t=>t.classList.remove("active"));
  tab.classList.add("active");
  document.querySelectorAll(".pane").forEach(p=>p.classList.remove("active"));
  g("pane-"+name).classList.add("active");
  const tt=g("tbTitle"); if(tt) tt.textContent=PAGE_TITLES[name]||name;
  if(!D) return;
  if(!_rendered[name]){
    _rendered[name]=true;
    setTimeout(()=>{
      if(name==="status") rStatus();
      else if(name==="summary") rSummary();
      else if(name==="week4") rW4();
      else if(name==="regional") rRegional();
      else if(name==="analytics") rAnalytics();
      else if(name==="customers") rCustomers();
      else if(name==="route") rRoute();
      else if(name==="receipt") rReceipt();
      else if(name==="predict") rPredict();
      else if(name==="certificate") rCertificate();
    },30);
  }
}

// ============================================================
// UTILS
// ============================================================
function g(id){return document.getElementById(id);}
function fi(d){return d instanceof Date?d.toISOString().split("T")[0]:d;}
function gMon(d){d=new Date(d);const dy=d.getDay(),diff=d.getDate()-dy+(dy===0?-6:1);return new Date(d.setDate(diff));}
function addD(d,n){const r=new Date(d);r.setDate(r.getDate()+n);return r;}

function sStyle(st){
  const dark=document.documentElement.getAttribute("data-theme")==="dark";
  if(!st||st==="—") return dark?{bg:"rgba(255,255,255,.04)",c:"#444"}:{bg:"#f1f5f9",c:"#64748b",bd:"#e2e8f0"};
  const s=st.toLowerCase();
  if(dark){
    if(s.includes("deliver")) return {bg:"rgba(34,197,94,.12)",c:"#4ade80",bd:"rgba(34,197,94,.3)"};
    if(s.includes("freight")) return {bg:"rgba(96,165,250,.12)",c:"#93c5fd",bd:"rgba(96,165,250,.3)"};
    if(s.includes("courier")) return {bg:"rgba(167,139,250,.12)",c:"#c4b5fd",bd:"rgba(167,139,250,.3)"};
    if(s.includes("cancel"))  return {bg:"rgba(248,113,113,.12)",c:"#fca5a5",bd:"rgba(248,113,113,.3)"};
    if(s.includes("qc"))      return {bg:"rgba(251,191,36,.12)",c:"#fde68a",bd:"rgba(251,191,36,.3)"};
    if(s.includes("hand"))    return {bg:"rgba(96,165,250,.12)",c:"#93c5fd",bd:"rgba(96,165,250,.3)"};
    if(s.includes("pending")) return {bg:"rgba(251,191,36,.1)",c:"#fcd34d",bd:"rgba(251,191,36,.2)"};
    if(s.includes("hold"))    return {bg:"rgba(248,113,113,.1)",c:"#f87171",bd:"rgba(248,113,113,.2)"};
    return {bg:"rgba(255,255,255,.05)",c:"#94a3b8",bd:"rgba(255,255,255,.1)"};
  } else {
    if(s.includes("deliver")) return {bg:"#dcfce7",c:"#15803d",bd:"#86efac"};
    if(s.includes("freight")) return {bg:"#dbeafe",c:"#1d4ed8",bd:"#93c5fd"};
    if(s.includes("courier")) return {bg:"#ede9fe",c:"#6d28d9",bd:"#c4b5fd"};
    if(s.includes("cancel"))  return {bg:"#fee2e2",c:"#b91c1c",bd:"#fca5a5"};
    if(s.includes("qc"))      return {bg:"#fef9c3",c:"#92400e",bd:"#fde68a"};
    if(s.includes("hand"))    return {bg:"#e0f2fe",c:"#0369a1",bd:"#7dd3fc"};
    if(s.includes("pending")) return {bg:"#fef3c7",c:"#b45309",bd:"#fcd34d"};
    if(s.includes("hold"))    return {bg:"#fee2e2",c:"#991b1b",bd:"#fca5a5"};
    return {bg:"#f1f5f9",c:"#475569",bd:"#cbd5e1"};
  }
}
function spill(st){
  if(!st||st==="—") return "";
  const s=sStyle(st);
  return `<span class="spill" style="background:${s.bg};color:${s.c};border-color:${s.bd||s.c+'44'}">📡 ${st}</span>`;
}
function starsFor(n){return "★".repeat(n)+"☆".repeat(5-n);}

// ============================================================
// BUNDLE TAB
// ============================================================
const BUNDLE_PAGE=50; let _bPage=0, _bFiltered=[];
function rBundle(){
  if(!D) return;
  const q=g("bq").value.toLowerCase().trim(),fr=g("bf").value,to=g("bt").value,src=g("bs").value;
  const ss=D.source_stats||{},kpi=D.kpi||{};
  g("bqo").textContent=ss["ECL QC Center"]?.orders||0;
  g("bqb").textContent=ss["ECL QC Center"]?.boxes||0;
  g("bpo").textContent=ss["PK Zone"]?.orders||0;
  g("bpb").textContent=ss["PK Zone"]?.boxes||0;
  g("bk1").textContent=kpi.total_bundles||0;
  g("bk2").textContent=kpi.total_orders_bundled||0;
  g("bk3").textContent=kpi.saved_shipments||0;
  g("bk4").textContent="£"+(kpi.total_savings_gbp||0).toLocaleString(undefined,{minimumFractionDigits:2});
  _bFiltered=(D.bundles||[]).filter(b=>{
    if(src!=="all"&&b.source!==src) return false;
    if(fr&&b.date_std<fr) return false;
    if(to&&b.date_std>to) return false;
    if(q) return b.orders.some(o=>o.order_id.toLowerCase().includes(q))||
                  (b.customer&&b.customer.toLowerCase().includes(q));
    return true;
  });
  _bPage=0;
  g("btb").innerHTML="";
  renderBundlePage();
}
function renderBundlePage(){
  const start=_bPage*BUNDLE_PAGE;
  const slice=_bFiltered.slice(start,start+BUNDLE_PAGE);
  const tbody=g("btb");
  // Remove old load-more row
  const old=document.getElementById("bLoadMore");
  if(old) old.remove();
  if(!_bFiltered.length){
    tbody.innerHTML=`<tr><td colspan="4" style="text-align:center;padding:50px;color:var(--t3)">No bundles found.</td></tr>`;
    return;
  }
  let h="";
  slice.forEach(b=>{
    const items=b.orders.map(o=>`
      <div class="bi">
        <div><span class="olink" onclick="openJ('${o.order_id}')">${o.order_id} ▾</span>
        ${spill(o.status)}<div style="font-size:10px;color:var(--t3);margin-top:2px">Wt: ${o.weight} kg</div></div>
        <div style="font-size:11px;color:var(--t3)">${(o.title||"").substring(0,42)}</div>
        <div style="font-weight:800;text-align:right">${o.item_count}</div>
      </div>`).join("");
    const aw=b.weight_kg||0,bw=Math.max(Math.ceil(aw),1);
    h+=`<tr>
      <td><b style="font-size:14px">${b.date||""}</b><br><span style="color:var(--t3);font-size:11px">${b.source}</span></td>
      <td><b>${b.customer||""}</b><br><span style="color:var(--t3);font-size:11px">${b.vendor||""}</span><br><span style="color:var(--t3);font-size:11px">${b.country||""}</span></td>
      <td>
        <div class="bbox">
          <span style="color:var(--t3);font-size:11px">TID:</span> <b style="font-family:monospace;font-size:11px">${b.tid||"—"}</b><br>
          <span style="color:var(--t3);font-size:11px">BOX:</span> <b style="color:var(--green)">${b.boxes_val}</b>
        </div>
        <div style="margin-top:8px;background:rgba(0,230,118,.07);border:1px solid rgba(0,230,118,.2);padding:10px;border-radius:8px">
          <div style="font-size:11px;display:flex;justify-content:space-between;color:var(--t3);margin-bottom:3px"><span>Total Wt:</span><b>${aw} kg</b></div>
          <div style="font-size:11px;display:flex;justify-content:space-between;color:var(--t3);margin-bottom:3px"><span>Billed Wt:</span><b>${bw} kg</b></div>
          <div style="font-size:13px;color:var(--green);display:flex;justify-content:space-between;font-weight:800"><span>💰 Saved:</span><span>£${(b.savings_gbp||0).toFixed(2)}</span></div>
        </div>
      </td>
      <td><div class="bbox">${items}</div></td>
    </tr>`;
  });
  const tmp=document.createElement("tbody");
  tmp.innerHTML=h;
  while(tmp.firstChild) tbody.appendChild(tmp.firstChild);
  // Load more button
  const shown=start+slice.length;
  if(shown<_bFiltered.length){
    const tr=document.createElement("tr");
    tr.id="bLoadMore";
    tr.innerHTML=`<td colspan="4" style="text-align:center;padding:20px">
      <button class="abtn" onclick="_bPage++;renderBundlePage()">
        Load More (${shown} of ${_bFiltered.length})
      </button>
    </td>`;
    tbody.appendChild(tr);
  }
}

// ============================================================
// STATUS TAB
// ============================================================
function qs(btn,p){
  document.querySelectorAll("#pane-status .qb").forEach(b=>b.classList.remove("on"));
  btn.classList.add("on");
  const today=new Date();today.setHours(0,0,0,0);
  let fr,to=new Date(today);
  if(p==="today") fr=new Date(today);
  else if(p==="7d"){fr=new Date(today);fr.setDate(fr.getDate()-6);}
  else if(p==="15d"){fr=new Date(today);fr.setDate(fr.getDate()-14);}
  else if(p==="30d"){fr=new Date(today);fr.setDate(fr.getDate()-29);}
  else if(p==="week"){fr=gMon(new Date(today));to=new Date(fr);to.setDate(to.getDate()+6);}
  else if(p==="month"){fr=new Date(today.getFullYear(),today.getMonth(),1);to=new Date(today.getFullYear(),today.getMonth()+1,0);}
  g("sf").value=fi(fr);g("st").value=fi(to);
}
function clrSt(){g("sf").value="";g("st").value="";g("sq").value="";g("ss").value="all";SEL=null;rStatus();}

function rStatus(){
  if(!D) return;
  const q=g("sq").value.toLowerCase().trim(),fr=g("sf").value,to=g("st").value,src=g("ss").value;
  const orders=[];
  (D.bundles||[]).forEach(b=>b.orders.forEach(o=>orders.push({
    order_id:o.order_id,date:b.date,date_std:b.date_std,source:b.source,
    customer:b.customer,country:b.country,weight:o.weight,status:o.status
  })));
  const fl=orders.filter(o=>{
    if(src!=="all"&&o.source!==src) return false;
    if(fr&&o.date_std<fr) return false;
    if(to&&o.date_std>to) return false;
    if(SEL&&o.status!==SEL) return false;
    if(q) return o.order_id.toLowerCase().includes(q)||(o.customer&&o.customer.toLowerCase().includes(q));
    return true;
  });
  const cnt={};fl.forEach(o=>{cnt[o.status]=(cnt[o.status]||0)+1;});
  const sorted=Object.entries(cnt).sort((a,b)=>b[1]-a[1]);
  let ph="";sorted.forEach(([st,n])=>{
    const s=sStyle(st);const esc=st.replace(/'/g,"\\'");
    ph+=`<span class="sp ${SEL===st?"on":""}" onclick="selSt(this,'${esc}')" style="background:${s.bg};color:${s.c};border-color:${s.c}44">${st} <b>${n}</b></span>`;
  });
  g("spills").innerHTML=ph;g("spw").style.display=sorted.length?"block":"none";
  const del=fl.filter(o=>o.status.toLowerCase().includes("deliver")).length;
  const tr=fl.filter(o=>o.status.toLowerCase().includes("freight")||o.status.toLowerCase().includes("courier")).length;
  const can=fl.filter(o=>o.status.toLowerCase().includes("cancel")).length;
  g("stot").textContent=fl.length.toLocaleString();g("sdel").textContent=del.toLocaleString();
  g("str2").textContent=tr.toLocaleString();g("scan").textContent=can.toLocaleString();
  g("src2").innerHTML=`Showing <b>${fl.length.toLocaleString()}</b> of <b>${orders.length.toLocaleString()}</b> orders`;
  _stFiltered=fl; _stPage=0;
  g("stb").innerHTML="";
  renderStatusPage();
}
const STATUS_PAGE=100; let _stPage=0, _stFiltered=[];
function renderStatusPage(){
  const start=_stPage*STATUS_PAGE;
  const slice=_stFiltered.slice(start,start+STATUS_PAGE);
  const tbody=g("stb");
  const old=document.getElementById("stLoadMore"); if(old) old.remove();
  let h="";
  if(!_stFiltered.length){h=`<tr><td colspan="8" style="text-align:center;padding:50px;color:var(--t3)">No orders found</td></tr>`;}
  else slice.forEach((o,i)=>{
    const s=sStyle(o.status);
    h+=`<tr><td style="color:var(--t3)">${start+i+1}</td>
      <td style="font-family:monospace;font-weight:800;color:var(--blue)">${o.order_id}</td>
      <td style="color:var(--t3)">${o.date||"—"}</td>
      <td><span class="spill" style="background:${s.bg};color:${s.c};border-color:${s.bd||s.c+'44'}">${o.status}</span></td>
      <td><span class="spill" style="background:var(--s3);color:var(--t3);border-color:var(--bd)">${o.source}</span></td>
      <td>${o.customer||"—"}</td>
      <td style="color:var(--t3)">${o.country||"—"}</td>
      <td style="color:var(--t3)">${o.weight||"—"} kg</td></tr>`;
  });
  const tmp=document.createElement("tbody"); tmp.innerHTML=h;
  while(tmp.firstChild) tbody.appendChild(tmp.firstChild);
  const shown=start+slice.length;
  if(shown<_stFiltered.length){
    const tr=document.createElement("tr"); tr.id="stLoadMore";
    tr.innerHTML=`<td colspan="8" style="text-align:center;padding:18px">
      <button class="abtn" onclick="_stPage++;renderStatusPage()">
        Load More (${shown} of ${_stFiltered.length})
      </button></td>`;
    tbody.appendChild(tr);
  }
}
function selSt(pill,st){SEL=SEL===st?null:st;rStatus();}

// ============================================================
// SUMMARY
// ============================================================
function wkBundles(mon){
  const s=new Date(mon);s.setHours(0,0,0,0);
  const e=addD(s,6);e.setHours(23,59,59,999);
  return (D.bundles||[]).filter(b=>{const d=new Date(b.date_std);return d>=s&&d<=e;});
}

function buildCard(src,bundles,wkLabel){
  const sb=bundles.filter(b=>b.source===src);
  const totO=sb.reduce((a,b)=>a+b.orders.length,0);
  const totB=sb.length;
  const totW=sb.reduce((a,b)=>a+(b.weight_kg||0),0);
  const rm={};
  sb.forEach(b=>{
    const rg=b.region||"EU"; const d=new Date(b.date_std);
    const di=d.getDay()===0?6:d.getDay()-1;
    if(!rm[rg])rm[rg]={};
    if(!rm[rg][di])rm[rg][di]={o:0,bx:0,w:0,lt:0,ge:0,list:[]};
    rm[rg][di].o+=b.orders.length;rm[rg][di].bx+=1;
    rm[rg][di].w+=b.weight_kg||0;
    rm[rg][di].lt+=(b.weight_kg||0)<20?1:0;
    rm[rg][di].ge+=(b.weight_kg||0)>=20?1:0;
    b.orders.forEach(o=>rm[rg][di].list.push({...o,date:b.date_std}));
  });
  const regs=Object.keys(rm).sort();
  const dt=Array.from({length:7},()=>({o:0,bx:0,w:0,lt:0,ge:0}));
  regs.forEach(rg=>[0,1,2,3,4,5,6].forEach(di=>{
    if(rm[rg][di]){dt[di].o+=rm[rg][di].o;dt[di].bx+=rm[rg][di].bx;dt[di].w+=rm[rg][di].w;dt[di].lt+=rm[rg][di].lt;dt[di].ge+=rm[rg][di].ge;}
  }));
  const uid=(src+"_"+wkLabel).replace(/[\s\/\-]/g,"_");
  window["RM_"+uid]=rm; window["RM_"+uid+"_dt"]=dt;
  window["RM_"+uid+"_all"]=sb;

  let rows="";
  regs.forEach(rg=>{
    rows+=`<tr><td class="rc">${rg}</td>`;
    [0,1,2,3,4,5,6].forEach(di=>{
      const v=rm[rg][di];const sep=di>0?"ds":"";
      if(!v){rows+=`<td class="dash ${sep}">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td>`;}
      else{rows+=`<td class="vo ${sep} clk" onclick="showOrd('${uid}','${rg}',${di})">${v.o}</td><td class="vb">${v.bx}</td><td class="vw">${v.w.toFixed(1)}</td><td class="vl">${v.lt}</td><td class="vg">${v.ge}</td>`;}
    });
    rows+="</tr>";
  });
  rows+=`<tr class="ttr"><td class="rc">TOTAL</td>`;
  dt.forEach((t,di)=>{
    const sep=di>0?"ds":"";
    if(!t.o){rows+=`<td class="dash ${sep}">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td>`;}
    else{const cc=GUEST?"":"clk",ce=GUEST?"":` onclick="showOrdDay('${uid}',${di})"`;rows+=`<td class="vo ${sep} ${cc}"${ce}>${t.o}</td><td class="vb ${cc}"${ce}>${t.bx}</td><td class="vw ${cc}"${ce}>${t.w.toFixed(1)}</td><td class="vl">${t.lt}</td><td class="vg">${t.ge}</td>`;}
  });
  rows+="</tr>";

  const stars=starsFor(4);
  const totWDisp=totW<1000?totW.toFixed(1)+" kg":(totW/1000).toFixed(2)+" T";
  return `<div class="pcard">
    <div class="phdr">
      <div class="phdr-left">
        <div class="pname-row">
          <div class="pname">${src}</div>
          <div class="stars">${stars}</div>
        </div>
        <div class="pname-sub">${wkLabel}</div>
      </div>
      <div class="pstats">
        <div class="pstat" ${GUEST?"":'onclick="showAllOrd(\''+uid+'\',\'O\')"'}>
          <div class="pstat-v" style="color:var(--blue)">${totO.toLocaleString()}</div>
          <div class="pstat-l">ORDERS</div>
        </div>
        <div class="pstat" ${GUEST?"":'onclick="showAllOrd(\''+uid+'\',\'B\')"'}>
          <div class="pstat-v" style="color:var(--green)">${totB.toLocaleString()}</div>
          <div class="pstat-l">BOXES</div>
        </div>
        <div class="pstat" ${GUEST?"":'onclick="showAllOrd(\''+uid+'\',\'W\')"'}>
          <div class="pstat-v" style="color:var(--yellow)">${totWDisp}</div>
          <div class="pstat-l">WEIGHT</div>
        </div>
        <button class="csvbtn" onclick="doCSV('${uid}','${src}','${wkLabel}')">📋 CSV</button>
      </div>
    </div>
    <div class="tw2"><table class="mx">
      <thead>
        <tr>
          <th class="rh" rowspan="2">REGION</th>
          ${DAYS.map((d,i)=>`<th class="dh ${i>0?"ds":""}" colspan="5">${d}${FLT.includes(i)?" ✈️":""}</th>`).join("")}
        </tr>
        <tr>${DAYS.map((_,i)=>`<td class="sh ${i>0?"ds":""}">O</td><td class="sh">B</td><td class="sh">W</td><td class="sh">&lt;20</td><td class="sh">20+</td>`).join("")}</tr>
      </thead>
      <tbody>${rows}</tbody>
    </table></div>
  </div>`;
}

function setWk(offset,btn){
  document.querySelectorAll("#pane-summary .qb").forEach(b=>b.classList.remove("on"));
  if(btn)btn.classList.add("on");
  const mon=gMon(new Date());mon.setDate(mon.getDate()+offset*7);g("ws").value=fi(mon);
}
function rSummary(){
  if(!D) return;
  const ws=g("ws").value; if(!ws) return;
  const mon=new Date(ws);mon.setHours(0,0,0,0);
  const wl=`${fi(mon)} – ${fi(addD(mon,6))}`;
  const bundles=wkBundles(mon);
  const cont=g("sumCards");
  cont.innerHTML="";
  if(!bundles.length){cont.innerHTML=`<div class="empty-state"><div class="empty-icon">📭</div><div>No data.</div></div>`;return;}
  let i=0;
  function next(){
    if(i>=SRCS.length) return;
    const tmp=document.createElement("div");
    tmp.innerHTML=buildCard(SRCS[i],bundles,wl);
    cont.appendChild(tmp.firstChild);
    i++; setTimeout(next,0);
  }
  next();
}

function setW4Now(btn){
  document.querySelectorAll("#pane-week4 .qb").forEach(b=>b.classList.remove("on"));
  if(btn)btn.classList.add("on");
  g("w4e").value=fi(gMon(new Date()));
}
function rW4(){
  if(!D) return;
  const ws=g("w4e").value; if(!ws) return;
  const lat=new Date(ws);lat.setHours(0,0,0,0);
  const cont=g("w4cards");
  cont.innerHTML=`<div class="lw"><div class="ld"></div><p class="lp">Building 4-week comparison...</p></div>`;
  setTimeout(()=>_buildW4(lat,cont),40);
}

function _buildW4(lat,cont){
  // Build 4 weeks of data
  const weeks=[];
  for(let wi=0;wi<4;wi++){
    const mon=new Date(lat);mon.setDate(mon.getDate()-wi*7);
    const sun=addD(mon,6);
    const bundles=wkBundles(mon);
    const qc=bundles.filter(b=>b.source==="ECL QC Center");
    const pk=bundles.filter(b=>b.source==="ECL Zone"||b.source==="GE Zone");
    const wStats=(arr)=>({
      orders:arr.reduce((a,b)=>a+b.orders.length,0),
      bundles:arr.length,
      weight:arr.reduce((a,b)=>a+(b.weight_kg||0),0),
      savings:arr.reduce((a,b)=>a+(b.savings_gbp||0),0),
      items:arr.reduce((a,b)=>a+(b.total_items||0),0),
      list:arr,
    });
    weeks.unshift({
      label:`W${4-wi}`,
      range:`${fi(mon)} – ${fi(sun)}`,
      mon:new Date(mon),
      qc:wStats(qc),
      pk:wStats(pk),
      all:wStats(bundles),
    });
  }

  // Trend arrows
  const arr=(a,b)=>a>b?"▲":a<b?"▼":"—";
  const arrc=(a,b)=>a>b?"var(--green)":a<b?"var(--red)":"var(--t3)";

  // Build horizontal comparison table
  let html=`
  <!-- SUMMARY COMPARISON BANNER -->
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px;">
  ${weeks.map((w,i)=>{
    const prev=weeks[i-1];
    const tot=w.all;
    return `<div style="background:var(--s2);border:1px solid var(--bd);border-radius:16px;padding:18px;position:relative;overflow:hidden;box-shadow:var(--shadow)">
      <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--acc),var(--blue))"></div>
      <div style="font-size:11px;font-weight:800;color:var(--acc);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px">${w.label}</div>
      <div style="font-size:10px;color:var(--t3);margin-bottom:14px">${w.range}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div style="text-align:center">
          <div style="font-size:24px;font-weight:900;color:var(--blue)">${tot.orders.toLocaleString()}</div>
          <div style="font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700">Orders</div>
          ${prev?`<div style="font-size:10px;font-weight:700;color:${arrc(tot.orders,prev.all.orders)}">${arr(tot.orders,prev.all.orders)} ${Math.abs(tot.orders-prev.all.orders)}</div>`:""}
        </div>
        <div style="text-align:center">
          <div style="font-size:24px;font-weight:900;color:var(--green)">${tot.bundles.toLocaleString()}</div>
          <div style="font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700">Bundles</div>
          ${prev?`<div style="font-size:10px;font-weight:700;color:${arrc(tot.bundles,prev.all.bundles)}">${arr(tot.bundles,prev.all.bundles)} ${Math.abs(tot.bundles-prev.all.bundles)}</div>`:""}
        </div>
        <div style="text-align:center">
          <div style="font-size:20px;font-weight:900;color:var(--yellow)">${tot.weight.toFixed(0)}<span style="font-size:11px">kg</span></div>
          <div style="font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700">Weight</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:20px;font-weight:900;color:var(--green)">£${tot.savings.toFixed(0)}</div>
          <div style="font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700">Saved</div>
          ${prev?`<div style="font-size:10px;font-weight:700;color:${arrc(tot.savings,prev.all.savings)}">${arr(tot.savings,prev.all.savings)} £${Math.abs(tot.savings-prev.all.savings).toFixed(0)}</div>`:""}
        </div>
      </div>
    </div>`;
  }).join("")}
  </div>

  <!-- QC CENTER vs PK ZONE HORIZONTAL TABLE -->
  <div style="background:var(--s2);border:1px solid var(--bd);border-radius:16px;overflow:hidden;box-shadow:var(--shadow);margin-bottom:24px">
    <div style="padding:18px 22px 14px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:14px">
      <div style="font-size:15px;font-weight:800;color:var(--t1)">📊 QC Center vs PK Zone — 4 Week Breakdown</div>
    </div>
    <div style="overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;min-width:700px">
      <thead>
        <tr style="background:var(--s3)">
          <th style="padding:12px 16px;text-align:left;font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:800;letter-spacing:1px;border-bottom:2px solid var(--bd);min-width:130px">Zone / Metric</th>
          ${weeks.map(w=>`<th colspan="2" style="padding:12px 8px;text-align:center;font-size:11px;color:var(--acc);font-weight:800;border-bottom:2px solid var(--acc);border-left:1px solid var(--bd)">${w.label}<div style="font-size:9px;color:var(--t3);font-weight:600;margin-top:2px">${w.range}</div></th>`).join("")}
        </tr>
        <tr style="background:var(--s3)">
          <th style="padding:6px 16px;font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700;border-bottom:1px solid var(--bd)"></th>
          ${weeks.map(()=>`<th style="padding:6px 6px;font-size:9px;color:var(--green);text-align:center;border-left:1px solid var(--bd);border-bottom:1px solid var(--bd);font-weight:700">QC</th><th style="padding:6px 6px;font-size:9px;color:var(--blue);text-align:center;border-bottom:1px solid var(--bd);font-weight:700">PK</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${[
          {label:"📦 Bundles",qcF:w=>w.qc.bundles,pkF:w=>w.pk.bundles,fmt:v=>v.toLocaleString(),col:"var(--t1)"},
          {label:"🛒 Orders",qcF:w=>w.qc.orders,pkF:w=>w.pk.orders,fmt:v=>v.toLocaleString(),col:"var(--blue)"},
          {label:"⚖️ Weight (kg)",qcF:w=>w.qc.weight,pkF:w=>w.pk.weight,fmt:v=>v.toFixed(1),col:"var(--yellow)"},
          {label:"🎁 Items",qcF:w=>w.qc.items,pkF:w=>w.pk.items,fmt:v=>v.toLocaleString(),col:"var(--purple)"},
          {label:"💰 Saved (£)",qcF:w=>w.qc.savings,pkF:w=>w.pk.savings,fmt:v=>"£"+v.toFixed(2),col:"var(--green)"},
          {label:"📊 Avg Wt/Bundle",qcF:w=>w.qc.bundles?w.qc.weight/w.qc.bundles:0,pkF:w=>w.pk.bundles?w.pk.weight/w.pk.bundles:0,fmt:v=>v.toFixed(1)+"kg",col:"var(--cyan)"},
        ].map((row,ri)=>`<tr style="background:${ri%2===0?"var(--s3)":"var(--s2)"}">
          <td style="padding:11px 16px;font-size:12px;font-weight:700;color:var(--t1);border-bottom:1px solid var(--bd)">${row.label}</td>
          ${weeks.map(w=>{
            const qv=row.qcF(w); const pv=row.pkF(w);
            return `<td style="padding:11px 8px;text-align:center;font-size:13px;font-weight:800;color:${row.col};border-left:1px solid var(--bd);border-bottom:1px solid var(--bd)">${row.fmt(qv)}</td>
                    <td style="padding:11px 8px;text-align:center;font-size:13px;font-weight:800;color:${row.col};border-bottom:1px solid var(--bd)">${row.fmt(pv)}</td>`;
          }).join("")}
        </tr>`).join("")}
        <tr style="background:rgba(139,92,246,.06)">
          <td style="padding:11px 16px;font-size:12px;font-weight:900;color:var(--acc);border-bottom:1px solid var(--bd)">🏆 TOTAL Orders</td>
          ${weeks.map(w=>{
            const tot=w.all.orders;
            return `<td colspan="2" style="padding:11px 8px;text-align:center;font-size:15px;font-weight:900;color:var(--acc);border-left:1px solid var(--bd);border-bottom:1px solid var(--bd)">${tot.toLocaleString()}</td>`;
          }).join("")}
        </tr>
      </tbody>
    </table>
    </div>
  </div>

  <!-- BAR CHARTS COMPARISON -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:24px">
    <div style="background:var(--s2);border:1px solid var(--bd);border-radius:16px;padding:20px;box-shadow:var(--shadow)">
      <div style="font-size:13px;font-weight:800;color:var(--t1);margin-bottom:16px">📦 Orders per Week</div>
      ${(()=>{
        const maxO=Math.max(...weeks.map(w=>w.all.orders),1);
        return weeks.map(w=>`
          <div style="margin-bottom:14px">
            <div style="display:flex;justify-content:space-between;font-size:11px;font-weight:700;color:var(--t2);margin-bottom:4px">
              <span>${w.label}</span><span>${w.all.orders.toLocaleString()}</span>
            </div>
            <div style="height:8px;background:var(--s3);border-radius:4px;overflow:hidden;margin-bottom:3px">
              <div style="height:100%;width:${(w.qc.orders/maxO*100).toFixed(1)}%;background:var(--green);border-radius:4px;display:inline-block"></div>
            </div>
            <div style="height:8px;background:var(--s3);border-radius:4px;overflow:hidden">
              <div style="height:100%;width:${(w.pk.orders/maxO*100).toFixed(1)}%;background:var(--blue);border-radius:4px;display:inline-block"></div>
            </div>
            <div style="display:flex;gap:12px;margin-top:3px;font-size:10px">
              <span style="color:var(--green)">QC: ${w.qc.orders}</span>
              <span style="color:var(--blue)">PK: ${w.pk.orders}</span>
            </div>
          </div>`).join("");
      })()}
    </div>
    <div style="background:var(--s2);border:1px solid var(--bd);border-radius:16px;padding:20px;box-shadow:var(--shadow)">
      <div style="font-size:13px;font-weight:800;color:var(--t1);margin-bottom:16px">💰 Savings per Week</div>
      ${(()=>{
        const maxS=Math.max(...weeks.map(w=>w.all.savings),1);
        return weeks.map(w=>`
          <div style="margin-bottom:14px">
            <div style="display:flex;justify-content:space-between;font-size:11px;font-weight:700;color:var(--t2);margin-bottom:4px">
              <span>${w.label}</span><span style="color:var(--green)">£${w.all.savings.toFixed(2)}</span>
            </div>
            <div style="height:8px;background:var(--s3);border-radius:4px;overflow:hidden;margin-bottom:3px">
              <div style="height:100%;width:${(w.qc.savings/maxS*100).toFixed(1)}%;background:var(--green);border-radius:4px;display:inline-block"></div>
            </div>
            <div style="height:8px;background:var(--s3);border-radius:4px;overflow:hidden">
              <div style="height:100%;width:${(w.pk.savings/maxS*100).toFixed(1)}%;background:var(--blue);border-radius:4px;display:inline-block"></div>
            </div>
            <div style="display:flex;gap:12px;margin-top:3px;font-size:10px">
              <span style="color:var(--green)">QC: £${w.qc.savings.toFixed(2)}</span>
              <span style="color:var(--blue)">PK: £${w.pk.savings.toFixed(2)}</span>
            </div>
          </div>`).join("");
      })()}
    </div>
  </div>`;

  cont.innerHTML=html;
}

function setRWk(offset,btn){
  document.querySelectorAll("#pane-regional .qb").forEach(b=>b.classList.remove("on"));
  if(btn)btn.classList.add("on");
  const mon=gMon(new Date());mon.setDate(mon.getDate()+offset*7);g("rws").value=fi(mon);
}
function rRegional(){
  if(!D) return;
  const ws=g("rws").value; if(!ws) return;
  const mon=new Date(ws);mon.setHours(0,0,0,0);
  const wl=`${fi(mon)} – ${fi(addD(mon,6))}`;
  const bundles=wkBundles(mon);
  const groups={"QC Center":["ECL QC Center"],"PK Zone":["ECL Zone","GE Zone"]};
  let html=`<div class="wklabel">📅 ${wl}</div>`;
  const regTotals={};
  bundles.forEach(b=>{
    const rg=b.region||"EU";
    if(!regTotals[rg])regTotals[rg]={o:0,bx:0,w:0};
    regTotals[rg].o+=b.orders.length;regTotals[rg].bx+=1;regTotals[rg].w+=(b.weight_kg||0);
  });
  const regs=Object.entries(regTotals).sort((a,b)=>b[1].o-a[1].o);
  const maxO=Math.max(...regs.map(r=>r[1].o),1);
  const barCols=["var(--blue)","var(--green)","var(--yellow)","var(--purple)","var(--cyan)","var(--orange)","var(--red)","#80cbc4","#ce93d8","#f48fb1","#ffe082","#a5d6a7"];
  let barHtml="";
  regs.slice(0,12).forEach(([rg,v],i)=>{
    const pct=(v.o/maxO*100).toFixed(1);
    barHtml+=`<div class="bar-row">
      <div class="bar-label">${rg}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${barCols[i%barCols.length]}"></div></div>
      <div class="bar-val" style="color:${barCols[i%barCols.length]}">${v.o}</div>
    </div>`;
  });
  html+=`<div class="reg-grid">
    <div class="mini-card">
      <div class="mini-title"><div class="dot" style="background:var(--blue)"></div>Orders by Region</div>
      ${barHtml||'<div style="color:var(--t3)">No data</div>'}
    </div>
    <div class="mini-card">
      <div class="mini-title"><div class="dot" style="background:var(--yellow)"></div>Week Stats</div>
      ${buildWeekStats(bundles)}
    </div>
  </div>`;
  const cont=g("regCards");
  cont.innerHTML=html; // inject summary cards first
  const groupArr=Object.entries(groups);
  let gi=0;
  function nextReg(){
    if(gi>=groupArr.length) return;
    const [gname,srcs]=groupArr[gi];
    const gb=bundles.filter(b=>srcs.includes(b.source));
    const tmp=document.createElement("div");
    tmp.innerHTML=buildRegCard(gname,gb,wl);
    cont.appendChild(tmp.firstChild);
    gi++; setTimeout(nextReg,0);
  }
  nextReg();
}

function buildWeekStats(bundles){
  const totO=bundles.reduce((a,b)=>a+b.orders.length,0);
  const totB=bundles.length;
  const totW=bundles.reduce((a,b)=>a+(b.weight_kg||0),0);
  const lt=bundles.filter(b=>(b.weight_kg||0)<20).length;
  const ge=bundles.filter(b=>(b.weight_kg||0)>=20).length;
  return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <div style="background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:28px;font-weight:900;color:var(--blue)">${totO.toLocaleString()}</div>
      <div style="font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700">Total Orders</div>
    </div>
    <div style="background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:28px;font-weight:900;color:var(--green)">${totB.toLocaleString()}</div>
      <div style="font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700">Total Boxes</div>
    </div>
    <div style="background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:24px;font-weight:900;color:var(--yellow)">${totW.toFixed(1)} kg</div>
      <div style="font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700">Total Weight</div>
    </div>
    <div style="background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:20px;font-weight:900"><span style="color:var(--purple)">${lt}</span> / <span style="color:var(--red)">${ge}</span></div>
      <div style="font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700">&lt;20 kg / 20+ kg</div>
    </div>
  </div>`;
}

function buildRegCard(gname,bundles,wl){
  const uid=(gname+"_"+wl).replace(/[\s\/\-]/g,"_");
  const totO=bundles.reduce((a,b)=>a+b.orders.length,0);
  const totB=bundles.length;
  const totW=bundles.reduce((a,b)=>a+(b.weight_kg||0),0);
  const rm={};
  bundles.forEach(b=>{
    const rg=b.region||"EU";const d=new Date(b.date_std);
    const di=d.getDay()===0?6:d.getDay()-1;
    if(!rm[rg])rm[rg]={};
    if(!rm[rg][di])rm[rg][di]={o:0,bx:0,w:0,lt:0,ge:0,list:[]};
    rm[rg][di].o+=b.orders.length;rm[rg][di].bx+=1;rm[rg][di].w+=b.weight_kg||0;
    rm[rg][di].lt+=(b.weight_kg||0)<20?1:0;rm[rg][di].ge+=(b.weight_kg||0)>=20?1:0;
    b.orders.forEach(o=>rm[rg][di].list.push({...o,date:b.date_std}));
  });
  window["RM_"+uid]=rm;
  window["RM_"+uid+"_all"]=bundles;
  const regs=Object.keys(rm).sort();
  const dt=Array.from({length:7},()=>({o:0,bx:0,w:0,lt:0,ge:0}));
  regs.forEach(rg=>[0,1,2,3,4,5,6].forEach(di=>{
    if(rm[rg][di]){dt[di].o+=rm[rg][di].o;dt[di].bx+=rm[rg][di].bx;dt[di].w+=rm[rg][di].w;dt[di].lt+=rm[rg][di].lt;dt[di].ge+=rm[rg][di].ge;}
  }));
  let rows="";
  regs.forEach(rg=>{
    rows+=`<tr><td class="rc">${rg}</td>`;
    [0,1,2,3,4,5,6].forEach(di=>{
      const v=rm[rg][di];const sep=di>0?"ds":"";
      if(!v){rows+=`<td class="dash ${sep}">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td>`;}
      else{rows+=`<td class="vo ${sep} clk" onclick="showOrd('${uid}','${rg}',${di})">${v.o}</td><td class="vb">${v.bx}</td><td class="vw">${v.w.toFixed(1)}</td><td class="vl">${v.lt}</td><td class="vg">${v.ge}</td>`;}
    });
    rows+="</tr>";
  });
  rows+=`<tr class="ttr"><td class="rc">TOTAL</td>`;
  dt.forEach((t,di)=>{
    const sep=di>0?"ds":"";
    if(!t.o){rows+=`<td class="dash ${sep}">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td><td class="dash">-</td>`;}
    else{const cc=GUEST?"":"clk",ce=GUEST?"":` onclick="showOrdDay('${uid}',${di})"`;rows+=`<td class="vo ${sep} ${cc}"${ce}>${t.o}</td><td class="vb ${cc}"${ce}>${t.bx}</td><td class="vw ${cc}"${ce}>${t.w.toFixed(1)}</td><td class="vl">${t.lt}</td><td class="vg">${t.ge}</td>`;}
  });
  rows+="</tr>";
  const totWDisp=totW<1000?totW.toFixed(1)+" kg":(totW/1000).toFixed(2)+" T";
  const nameCol=gname==="QC Center"?"var(--green)":"#7986cb";
  return `<div class="pcard">
    <div class="phdr">
      <div class="phdr-left">
        <div class="pname-row">
          <div class="pname" style="color:${nameCol}">${gname}</div>
          <div class="stars">${starsFor(4)}</div>
          ${gname==="PK Zone"?'<div class="pkbadge">👑 Region King</div>':""}
        </div>
        <div class="pname-sub">${wl}</div>
      </div>
      <div class="pstats">
        <div class="pstat" ${GUEST?"":'onclick="showAllOrd(\''+uid+'\',\'O\')"'}>
          <div class="pstat-v" style="color:var(--blue)">${totO.toLocaleString()}</div>
          <div class="pstat-l">ORDERS</div>
        </div>
        <div class="pstat" ${GUEST?"":'onclick="showAllOrd(\''+uid+'\',\'B\')"'}>
          <div class="pstat-v" style="color:var(--green)">${totB.toLocaleString()}</div>
          <div class="pstat-l">BOXES</div>
        </div>
        <div class="pstat" ${GUEST?"":'onclick="showAllOrd(\''+uid+'\',\'W\')"'}>
          <div class="pstat-v" style="color:var(--yellow)">${totWDisp}</div>
          <div class="pstat-l">WEIGHT</div>
        </div>
        <button class="csvbtn" onclick="doCSV('${uid}','${gname}','${wl}')">📋 CSV</button>
      </div>
    </div>
    <div class="tw2"><table class="mx">
      <thead>
        <tr>
          <th class="rh" rowspan="2">REGION</th>
          ${DAYS.map((d,i)=>`<th class="dh ${i>0?"ds":""}" colspan="5">${d}${FLT.includes(i)?" ✈️":""}</th>`).join("")}
        </tr>
        <tr>${DAYS.map((_,i)=>`<td class="sh ${i>0?"ds":""}">O</td><td class="sh">B</td><td class="sh">W</td><td class="sh">&lt;20</td><td class="sh">20+</td>`).join("")}</tr>
      </thead>
      <tbody>${rows}</tbody>
    </table></div>
  </div>`;
}

// ============================================================
// SHOW ORDERS MODAL
// ============================================================
function showOrd(uid,region,di){
  if(GUEST)return;
  const rm=window["RM_"+uid];
  if(!rm||!rm[region]||!rm[region][di]) return;
  const list=rm[region][di].list||[];
  g("oTit").textContent=`${region} — ${DAYS[di]} (${list.length} orders)`;
  showOrdModal(list);
}
function showOrdDay(uid,di){
  if(GUEST)return;
  const rm=window["RM_"+uid];
  if(!rm) return;
  const list=[];
  Object.values(rm).forEach(rg=>{if(rg[di])list.push(...rg[di].list);});
  g("oTit").textContent=`${DAYS[di]} — All Regions (${list.length} orders)`;
  showOrdModal(list);
}
function showAllOrd(uid,type){
  if(GUEST)return;
  const all=window["RM_"+uid+"_all"]||[];
  const list=[];
  all.forEach(b=>b.orders.forEach(o=>list.push({...o,date:b.date_std})));
  g("oTit").textContent=`All Orders — ${type} (${list.length})`;
  showOrdModal(list);
}
function showOrdModal(list){
  if(!list.length){alert("No orders.");return;}
  let h=`<div class="tw"><table class="mt"><thead><tr><th>#</th><th>Order ID</th><th>Date</th><th>Weight</th><th>Status</th></tr></thead><tbody>`;
  list.forEach((o,i)=>{
    const s=sStyle(o.status||"—");
    h+=`<tr><td style="color:var(--t3)">${i+1}</td>
      <td style="font-family:monospace;font-weight:800;color:var(--blue)">${o.order_id}</td>
      <td style="color:var(--t3)">${o.date||"—"}</td>
      <td style="color:var(--yellow)">${o.weight||"—"} kg</td>
      <td><span class="spill" style="background:${s.bg};color:${s.c}">${o.status||"—"}</span></td></tr>`;
  });
  h+="</tbody></table></div>";
  g("oBody").innerHTML=h;
  g("oMov").classList.add("open");
}

// ============================================================
// CSV EXPORT
// ============================================================
function doCSV(uid,src,week){
  const rm=window["RM_"+uid];if(!rm)return;
  let rows=[["Source","Week","Region","Day","Orders","Boxes","Weight_kg","LT20","GE20"]];
  Object.keys(rm).forEach(rg=>{
    [0,1,2,3,4,5,6].forEach(di=>{
      const v=rm[rg][di];
      if(v)rows.push([src,week,rg,DAYS[di],v.o,v.bx,v.w.toFixed(1),v.lt,v.ge]);
    });
  });
  const csv=rows.map(r=>r.join(",")).join("\n");
  const a=document.createElement("a");a.href="data:text/csv;charset=utf-8,"+encodeURIComponent(csv);
  a.download=`${src.replace(/\s/g,"_")}_${week.replace(/[\s\/\-]/g,"_")}.csv`;a.click();
}

// ============================================================
// JOURNEY MODAL
// ============================================================
async function openJ(oid){
  if(GUEST)return;
  g("jMov").classList.add("open");
  g("jBody").innerHTML="<div class='mld'></div><p style='text-align:center;color:var(--t3);font-size:12px;margin-top:8px'>Fetching journey...</p>";
  try{
    const r=await fetch("/api/nexus/order_journey/"+encodeURIComponent(oid));
    const d=await r.json();
    if(!d.success){g("jBody").innerHTML=`<div style="text-align:center;padding:30px;color:var(--t3)">${d.message}</div>`;return;}
    const tl=d.timeline,km=d.key_metrics,steps=d.step_metrics||[];
    function mc(v){if(!v||v==="N/A")return"n";const n=parseFloat(v);if(isNaN(n))return"";if(n<=1)return"";if(n<=3)return"w";return"d";}
    const cb=d.is_cancelled?`<div class="cbanner">⚠️ CANCELLED — ${tl.cancelled_at||"N/A"}</div>`:"";
    function ti(lb,v,tp){
      let dc=v?"done":"pend",vc=v?"":"pv";
      if(tp==="c"){dc=v?"can":"pend";vc=v?"cv":"pv";}
      return`<div class="tli"><div class="tld ${dc}"></div><div class="tll">${lb}</div><div class="tlv ${vc}">${v||"— Not yet"}</div></div>`;
    }
    let sh="";
    if(steps.length){sh="<div class='shd'>⏱️ Step Durations</div><div class='stp-g'>";
      steps.forEach(s=>{sh+=`<div class="stp"><div class="stpl">${s.label}</div><div class="stpv" style="color:${s.duration?"var(--t1)":"var(--t3)"}">${s.duration||"—"}</div></div>`;});
      sh+="</div>";}
    g("jBody").innerHTML=`
      <div style="font-size:16px;font-weight:800;margin-bottom:3px">📦 Order Journey</div>
      <div style="font-family:monospace;color:var(--green);margin-bottom:14px">${d.order_id}</div>
      ${cb}
      <div class="shd">⭐ Key Metrics</div>
      <div class="mg">
        <div class="mc"><div class="mv ${mc(km.qc_to_handover)}">${km.qc_to_handover||"N/A"}</div><div class="ml">QC → Handover</div></div>
        <div class="mc"><div class="mv ${mc(km.handover_to_freight)}">${km.handover_to_freight||"N/A"}</div><div class="ml">Handover → Freight</div></div>
        <div class="mc"><div class="mv ${mc(km.total_journey)}">${km.total_journey||"N/A"}</div><div class="ml">Total Journey</div></div>
      </div>
      ${sh}
      <div class="shd">🗺️ Full Timeline</div>
      <div class="tl">
        ${ti("📋 Created",tl.created_at,"n")}${ti("✅ Accepted",tl.accepted_at,"n")}
        ${ti("🚚 Pickup Ready",tl.pickup_ready_at,"n")}${ti("🔍 QC Pending",tl.qc_pending_at,"n")}
        ${ti("✅ QC Approved",tl.qc_approved_at,"n")}${ti("🤝 Handed Over",tl.handedover_at,"n")}
        ${ti("✈️ Freight",tl.freight_at,"n")}${ti("🚁 Courier",tl.courier_at,"n")}
        ${ti("📬 Delivered",tl.delivered_at,"n")}
        ${tl.cancelled_at?ti("❌ Cancelled",tl.cancelled_at,"c"):""}
      </div>`;
    // SLA check
    const slaInfo=getSLAStatus({qc_approved_at:tl.qc_approved_at,handedover_at:tl.handedover_at});
    if(slaInfo){
      const slaHtml=`<div class="sla-badge sla-${slaInfo.status}" style="display:inline-flex;margin-bottom:16px">${slaInfo.label} — QC Approved → Handover</div>`;
      g("jBody").innerHTML=g("jBody").innerHTML.replace('<div class="shd">⭐ Key Metrics</div>',slaHtml+'<div class="shd">⭐ Key Metrics</div>');
    }
  }catch(e){g("jBody").innerHTML=`<div style="color:var(--red)">Error: ${e.message}</div>`;}
}

// ============================================================
// ANALYTICS TAB
// ============================================================
const AN_COLORS=["#4d9fff","#00e676","#ffd60a","#c77dff","#ff9500","#ff453a","#5ac8fa","#69f0ae","#ffab40","#e040fb","#80cbc4","#f48fb1"];

function rAnalytics(){
  if(!D) return;
  const cont=g("analyticsBody");
  cont.innerHTML=`<div class="lw"><div class="ld"></div><p class="lp">Building analytics...</p></div>`;
  setTimeout(()=>_buildAnalytics(cont),30);
}

function _buildAnalytics(cont){
  const bundles=D.bundles||[];
  if(!bundles.length){cont.innerHTML=`<div class="empty-state"><div class="empty-icon">📊</div><div>No data available.</div></div>`;return;}

  // ── Compute all metrics ──
  const totalBundles=bundles.length;
  const totalOrders=bundles.reduce((a,b)=>a+b.orders.length,0);
  const totalWeight=bundles.reduce((a,b)=>a+(b.weight_kg||0),0);
  const totalSaved=bundles.reduce((a,b)=>a+(b.savings_gbp||0),0);

  // Source breakdown
  const srcMap={};
  bundles.forEach(b=>{
    if(!srcMap[b.source])srcMap[b.source]={bundles:0,orders:0,weight:0,saved:0};
    srcMap[b.source].bundles++;
    srcMap[b.source].orders+=b.orders.length;
    srcMap[b.source].weight+=b.weight_kg||0;
    srcMap[b.source].saved+=b.savings_gbp||0;
  });

  // Region breakdown
  const regMap={};
  bundles.forEach(b=>{
    const rg=b.region||"EU";
    if(!regMap[rg])regMap[rg]={orders:0,bundles:0,weight:0};
    regMap[rg].orders+=b.orders.length;
    regMap[rg].bundles++;
    regMap[rg].weight+=b.weight_kg||0;
  });
  const regArr=Object.entries(regMap).sort((a,b)=>b[1].orders-a[1].orders);

  // Status breakdown
  const stMap={};
  bundles.forEach(b=>b.orders.forEach(o=>{
    const st=o.status||"Unknown";
    stMap[st]=(stMap[st]||0)+1;
  }));
  const stArr=Object.entries(stMap).sort((a,b)=>b[1]-a[1]).slice(0,8);

  // Daily volume (last 30 days)
  const dayMap={};
  bundles.forEach(b=>{
    if(!dayMap[b.date_std])dayMap[b.date_std]={orders:0,bundles:0};
    dayMap[b.date_std].orders+=b.orders.length;
    dayMap[b.date_std].bundles++;
  });
  const dayArr=Object.entries(dayMap).sort((a,b)=>a[0]<b[0]?-1:1).slice(-30);

  // Weight distribution
  const wtBuckets={"<5kg":0,"5-10kg":0,"10-20kg":0,"20-30kg":0,"30kg+":0};
  bundles.forEach(b=>{
    const w=b.weight_kg||0;
    if(w<5)wtBuckets["<5kg"]++;
    else if(w<10)wtBuckets["5-10kg"]++;
    else if(w<20)wtBuckets["10-20kg"]++;
    else if(w<30)wtBuckets["20-30kg"]++;
    else wtBuckets["30kg+"]++;
  });

  // Top customers
  const custMap={};
  bundles.forEach(b=>{
    const c=b.customer||"Unknown";
    if(!custMap[c])custMap[c]={orders:0,saved:0};
    custMap[c].orders+=b.orders.length;
    custMap[c].saved+=b.savings_gbp||0;
  });
  const topCust=Object.entries(custMap).sort((a,b)=>b[1].orders-a[1].orders).slice(0,8);

  // ── Build HTML ──
  let html="";

  // Row 1: Hero KPIs
  html+=`<div class="an-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:22px">
    ${heroCard("£"+totalSaved.toLocaleString(undefined,{minimumFractionDigits:2}),"Total Savings","var(--green)","💰")}
    ${heroCard(totalBundles.toLocaleString(),"Total Bundles","var(--blue)","📦")}
    ${heroCard(totalOrders.toLocaleString(),"Total Orders","var(--yellow)","🛒")}
    ${heroCard(totalWeight.toFixed(1)+" kg","Total Weight","var(--purple)","⚖️")}
  </div>`;

  // Row 2: Source Donut + Status Donut
  html+=`<div class="an-grid-2">`;
  html+=donutCard("Orders by Source",Object.entries(srcMap).map(([k,v],i)=>({label:k,val:v.orders,color:AN_COLORS[i]})),totalOrders,"src_orders");
  html+=donutCard("Orders by Status",stArr.map(([k,v],i)=>({label:k,val:v,color:AN_COLORS[i]})),totalOrders,"st_orders");
  html+=`</div>`;

  // Row 3: Top Regions bar + Weight distribution donut
  html+=`<div class="an-grid-2">`;
  html+=barCard("Top Regions by Orders",regArr.slice(0,10).map(([k,v],i)=>({label:k,val:v.orders,color:AN_COLORS[i%AN_COLORS.length]})),"reg_orders");
  html+=donutCard("Weight Distribution",Object.entries(wtBuckets).map(([k,v],i)=>({label:k,val:v,color:AN_COLORS[i]})),totalBundles,"wt_dist");
  html+=`</div>`;

  // Row 4: Top Customers + Savings by Source
  html+=`<div class="an-grid-2">`;
  html+=barCard("Top Customers by Orders",topCust.map(([k,v],i)=>({label:k,val:v.orders,color:AN_COLORS[i%AN_COLORS.length]})),"cust_orders");
  html+=barCard("Savings by Source (£)",Object.entries(srcMap).map(([k,v],i)=>({label:k,val:Math.round(v.saved),color:AN_COLORS[i]})),"src_saved",true);
  html+=`</div>`;

  // Row 5: Daily trend
  html+=trendCard("Daily Order Volume (Last 30 Days)",dayArr);

  cont.innerHTML=html;

  // Animate donut rings after insert
  setTimeout(()=>{
    document.querySelectorAll(".donut-ring").forEach(el=>{
      el.style.strokeDashoffset=el.dataset.target;
    });
  },50);
}

function heroCard(val,label,color,icon){
  return `<div class="an-card" style="border-top:3px solid ${color}">
    <div class="an-hero">
      <div style="font-size:28px;margin-bottom:8px">${icon}</div>
      <div class="an-hero-val" style="color:${color}">${val}</div>
      <div class="an-hero-label">${label}</div>
    </div>
  </div>`;
}

function donutCard(title,items,total,uid){
  const R=70,C=2*Math.PI*R,sz=180;
  let offset=0;
  let rings="";
  items.forEach(item=>{
    const pct=total>0?item.val/total:0;
    const dash=pct*C;
    rings+=`<circle class="donut-ring" cx="90" cy="90" r="${R}"
      fill="none" stroke="${item.color}" stroke-width="22"
      stroke-dasharray="${dash} ${C-dash}"
      stroke-dashoffset="${-offset+C/4}"
      data-target="${-offset+C/4}"
      style="transition:stroke-dashoffset .8s ease;cursor:${GUEST?"default":"pointer"}"
      ${GUEST?"":` onclick="anDrillDown('${uid}','${item.label.replace(/'/g,"\'")}')"`}
    />`;
    offset+=dash;
  });
  const legendHtml=items.map(item=>{
    const pct=total>0?(item.val/total*100).toFixed(1):0;
    return `<div class="legend-item ${GUEST?"":"clk-item"}" 
      ${GUEST?"":` onclick="anDrillDown('${uid}','${item.label.replace(/'/g,"\'")}')"`}>
      <div class="legend-dot" style="background:${item.color}"></div>
      <div class="legend-label">${item.label}</div>
      <div class="legend-val">${item.val.toLocaleString()}</div>
      <div class="legend-pct">${pct}%</div>
    </div>`;
  }).join("");

  return `<div class="an-card">
    <div class="an-card-title"><div class="dot" style="background:var(--acc)"></div>${title}</div>
    <div class="donut-wrap">
      <svg class="donut-svg" width="${sz}" height="${sz}" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r="${R}" fill="none" stroke="var(--bd)" stroke-width="22"/>
        ${rings}
        <text x="90" y="86" text-anchor="middle" fill="var(--t1)" font-size="22" font-weight="900" font-family="Inter,sans-serif">${total.toLocaleString()}</text>
        <text x="90" y="104" text-anchor="middle" fill="var(--t3)" font-size="10" font-family="Inter,sans-serif">TOTAL</text>
      </svg>
      <div class="donut-legend">${legendHtml}</div>
    </div>
  </div>`;
}

function barCard(title,items,uid,isMoney=false){
  const maxV=Math.max(...items.map(i=>i.val),1);
  const rows=items.map(item=>{
    const pct=(item.val/maxV*100).toFixed(1);
    const disp=isMoney?"£"+item.val.toLocaleString():item.val.toLocaleString();
    return `<div class="an-bar-row">
      <div class="an-bar-label" title="${item.label}">${item.label}</div>
      <div class="an-bar-track" ${GUEST?"":` onclick="anDrillDown('${uid}','${item.label.replace(/'/g,"\'")}')"`}>
        <div class="an-bar-fill" style="width:${pct}%;background:${item.color}"></div>
      </div>
      <div class="an-bar-val" style="color:${item.color}">${disp}</div>
    </div>`;
  }).join("");
  return `<div class="an-card">
    <div class="an-card-title"><div class="dot" style="background:var(--yellow)"></div>${title}</div>
    ${rows}
  </div>`;
}

function trendCard(title,dayArr){
  if(!dayArr.length) return "";
  const maxV=Math.max(...dayArr.map(d=>d[1].orders),1);
  const W=800,H=120,pad=10;
  const pts=dayArr.map((d,i)=>{
    const x=pad+(i/(dayArr.length-1||1))*(W-pad*2);
    const y=H-pad-(d[1].orders/maxV)*(H-pad*2);
    return `${x},${y}`;
  }).join(" ");
  const ptsFill=`${pad},${H} `+pts+` ${W-pad},${H}`;
  // x-axis labels (every 5th)
  let labels="";
  dayArr.forEach((d,i)=>{
    if(i%5===0||i===dayArr.length-1){
      const x=pad+(i/(dayArr.length-1||1))*(W-pad*2);
      const short=d[0].slice(5);
      labels+=`<text x="${x}" y="${H+14}" text-anchor="middle" fill="var(--t4)" font-size="9" font-family="Inter,sans-serif">${short}</text>`;
    }
  });
  // Dots
  let dots="";
  dayArr.forEach((d,i)=>{
    const x=pad+(i/(dayArr.length-1||1))*(W-pad*2);
    const y=H-pad-(d[1].orders/maxV)*(H-pad*2);
    dots+=`<circle cx="${x}" cy="${y}" r="3" fill="var(--acc)" 
      ${GUEST?"":` style="cursor:pointer" onclick="anDrillDown('daily','${d[0]}')"`}/>`;
  });

  return `<div class="an-card" style="margin-bottom:24px">
    <div class="an-card-title"><div class="dot" style="background:var(--cyan)"></div>${title}</div>
    <svg width="100%" viewBox="0 0 ${W} ${H+20}" preserveAspectRatio="none" style="overflow:visible">
      <defs>
        <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--acc)" stop-opacity=".3"/>
          <stop offset="100%" stop-color="var(--acc)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <polygon points="${ptsFill}" fill="url(#tg)"/>
      <polyline points="${pts}" fill="none" stroke="var(--acc)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
      ${dots}
      ${labels}
    </svg>
  </div>`;
}

// ── Drill Down Modal ──
function anDrillDown(uid,label){
  if(GUEST) return;
  const bundles=D.bundles||[];
  let list=[];let title="";

  if(uid==="src_orders"||uid==="src_saved"){
    list=bundles.filter(b=>b.source===label).flatMap(b=>b.orders.map(o=>({...o,date:b.date_std,source:b.source,customer:b.customer})));
    title=`${label} — All Orders (${list.length})`;
  } else if(uid==="st_orders"){
    list=bundles.flatMap(b=>b.orders.filter(o=>(o.status||"Unknown")===label).map(o=>({...o,date:b.date_std,source:b.source,customer:b.customer})));
    title=`Status: ${label} (${list.length} orders)`;
  } else if(uid==="reg_orders"){
    list=bundles.filter(b=>(b.region||"EU")===label).flatMap(b=>b.orders.map(o=>({...o,date:b.date_std,source:b.source,customer:b.customer})));
    title=`Region: ${label} (${list.length} orders)`;
  } else if(uid==="wt_dist"){
    const rng={"<5kg":[0,5],"5-10kg":[5,10],"10-20kg":[10,20],"20-30kg":[20,30],"30kg+":[30,9999]};
    const r=rng[label]||[0,9999];
    list=bundles.filter(b=>(b.weight_kg||0)>=r[0]&&(b.weight_kg||0)<r[1]).flatMap(b=>b.orders.map(o=>({...o,date:b.date_std,source:b.source,customer:b.customer})));
    title=`Weight ${label} (${list.length} orders)`;
  } else if(uid==="cust_orders"){
    list=bundles.filter(b=>b.customer===label).flatMap(b=>b.orders.map(o=>({...o,date:b.date_std,source:b.source,customer:b.customer})));
    title=`Customer: ${label} (${list.length} orders)`;
  } else if(uid==="daily"){
    list=bundles.filter(b=>b.date_std===label).flatMap(b=>b.orders.map(o=>({...o,date:b.date_std,source:b.source,customer:b.customer})));
    title=`Date: ${label} (${list.length} orders)`;
  }

  if(!list.length){alert("No orders found.");return;}
  g("oTit").textContent=title;
  showOrdModal(list);
}

// ============================================================
// USER PROFILE IN SIDEBAR
// ============================================================
function initUserCard(){
  const email=typeof USER_EMAIL!=="undefined"?USER_EMAIL:"";
  if(!email) return;
  const sbEmail=g("sbEmail"); if(sbEmail) sbEmail.textContent=email;
  const sbAvatar=g("sbAvatar");
  if(sbAvatar){
    const parts=email.split("@")[0].split(/[.\-_]/);
    const initials=(parts[0]?parts[0][0]:"?").toUpperCase()+(parts[1]?parts[1][0]:"").toUpperCase();
    sbAvatar.textContent=initials||"?";
  }
}
function updateLastUpdate(){
  const el=g("sbLastUpdate");
  if(el) el.textContent="Last update: "+new Date().toLocaleString();
}

// ============================================================
// WEIGHT ESTIMATION ENGINE
// ============================================================
function estimateItemWeight(title){
  const t=(title||"").toLowerCase();
  if(/phone|laptop|tablet|electron|console|camera|speaker/.test(t)) return 0.60;
  if(/shoe|boot|sneaker|heel|trainer|loafer|sandal/.test(t)) return 0.70;
  if(/jacket|coat|blazer|overcoat|puffer|parka/.test(t)) return 0.55;
  if(/jeans|denim|trouser|pant|chino|cargo/.test(t)) return 0.48;
  if(/dress|gown|jumpsuit|playsuit|romper/.test(t)) return 0.38;
  if(/sweater|hoodie|sweatshirt|pullover|knitwear/.test(t)) return 0.42;
  if(/shirt|blouse|top|tshirt|t-shirt|polo|tunic/.test(t)) return 0.28;
  if(/skirt|shorts/.test(t)) return 0.22;
  if(/bag|handbag|purse|backpack|tote|clutch/.test(t)) return 0.45;
  if(/sock|stocking|tight|hosiery/.test(t)) return 0.08;
  if(/underwear|brief|bra|bralette|lingerie|thong|knicker|panty/.test(t)) return 0.10;
  if(/watch|jewel|necklace|ring|earring|bracelet|pendant|brooch/.test(t)) return 0.14;
  if(/hat|cap|beanie|beret|scarf|glove|mitten/.test(t)) return 0.12;
  if(/belt|tie|bow/.test(t)) return 0.15;
  if(/book|manual|guide|magazine/.test(t)) return 0.40;
  if(/toy|game|puzzle/.test(t)) return 0.35;
  return 0.30;
}

function splitBundleWeight(bundle){
  const orders=bundle.orders;
  const totalBW=bundle.weight_kg||0;
  // Use actual weights if available
  const weights=orders.map(o=>parseFloat((o.weight||"0").toString().replace(/[^0-9.]/g,""))||0);
  const knownTotal=weights.reduce((a,b)=>a+b,0);
  if(knownTotal>0.1){
    // Check if all weights are known
    const hasAll=weights.every(w=>w>0);
    if(hasAll) return weights;
    // Fill zeros with estimates scaled to remaining weight
    const knownSum=weights.filter(w=>w>0).reduce((a,b)=>a+b,0);
    const remaining=Math.max(totalBW-knownSum,0);
    const estimates=orders.map((o,i)=>{
      if(weights[i]>0) return weights[i];
      const ic=Math.max(parseInt(o.item_count)||1,1);
      return estimateItemWeight(o.title)*ic;
    });
    const estSum=estimates.filter((_,i)=>weights[i]===0).reduce((a,b)=>a+b,0);
    return orders.map((o,i)=>{
      if(weights[i]>0) return weights[i];
      const ic=Math.max(parseInt(o.item_count)||1,1);
      const raw=estimateItemWeight(o.title)*ic;
      return estSum>0?raw/estSum*remaining:remaining/orders.filter((_,j)=>weights[j]===0).length;
    });
  }
  // All zero: estimate from title + item count, scale to bundle total
  const estimates=orders.map(o=>{
    const ic=Math.max(parseInt(o.item_count)||1,1);
    return estimateItemWeight(o.title)*ic;
  });
  const estTotal=estimates.reduce((a,b)=>a+b,0);
  if(estTotal<=0) return orders.map(()=>totalBW/orders.length);
  const scale=totalBW>0?totalBW/estTotal:1;
  return estimates.map(e=>e*scale);
}

function calcBundleComparison(bundle,rm){
  const DR=4.50;
  const country=(bundle.country||"").toLowerCase();
  // Prefer server-injected rate, fallback to ratesCache, fallback to DR
  const pr=bundle.rate_gbp||rm[country]||(window._ratesCache&&window._ratesCache[country])||DR;
  const totalBW=bundle.weight_kg||0;
  const splitWeights=splitBundleWeight(bundle);
  let indivCost=0;
  const orderBreakdown=bundle.orders.map((o,i)=>{
    const w=splitWeights[i];
    const billed=Math.max(Math.ceil(w),1);
    const cost=billed*pr;
    indivCost+=cost;
    return{order_id:o.order_id,title:o.title,item_count:o.item_count,
      est_weight:w,billed_weight:billed,individual_cost:cost,
      status:o.status,weight:o.weight};
  });
  const bundleBilled=Math.max(Math.ceil(totalBW),1);
  // Prefer server-calculated values
  const bundleCost=bundle.bundle_cost!=null?bundle.bundle_cost:(bundleBilled*pr);
  const serverIndivCost=bundle.indiv_cost!=null?bundle.indiv_cost:null;
  const finalIndivCost=serverIndivCost!=null?serverIndivCost:indivCost;
  const saved=bundle.savings_gbp!=null?bundle.savings_gbp:Math.max(finalIndivCost-bundleCost,0);
  return{orderBreakdown,indivCost:finalIndivCost,bundleCost,saved,rate:pr,totalBW,bundleBilled};
}

// ============================================================
// SLA CHECKER (QC_APPROVED → HANDOVER > 3 days)
// ============================================================
function getSLAStatus(jRow){
  if(!jRow) return null;
  const qa=jRow.qc_approved_at; const hh=jRow.handedover_at;
  if(!qa) return null;
  const qaD=new Date(qa); const hhD=hh?new Date(hh):new Date();
  const days=(hhD-qaD)/(1000*60*60*24);
  if(days<0) return null;
  if(!hh && days>3) return{status:"breach",days:days.toFixed(1),label:"⚠️ "+days.toFixed(1)+"d (SLA Breach)"};
  if(days>3) return{status:"breach",days:days.toFixed(1),label:"⚠️ "+days.toFixed(1)+"d (Breached)"};
  if(days>2) return{status:"warn",days:days.toFixed(1),label:"⏳ "+days.toFixed(1)+"d"};
  return{status:"ok",days:days.toFixed(1),label:"✅ "+days.toFixed(1)+"d"};
}

// ============================================================
// ORDER SEARCH TAB
// ============================================================
async function rOrderSearch(){
  const q=(g("osq").value||"").trim().toUpperCase();
  const cont=g("osResult");
  if(!q){cont.innerHTML=`<div class="empty-state"><div class="empty-icon">🔍</div><div>Enter an Order ID above</div></div>`;return;}
  cont.innerHTML=`<div class="lw"><div class="ld"></div><p class="lp">Searching...</p></div>`;
  // Find in bundles
  let foundBundle=null; let foundOrder=null;
  (D.bundles||[]).forEach(b=>{
    b.orders.forEach(o=>{
      if(o.order_id.toUpperCase()===q){foundBundle=b;foundOrder=o;}
    });
  });
  if(!foundBundle){
    cont.innerHTML=`<div class="empty-state"><div class="empty-icon">😕</div><div>Order <b>${q}</b> not found in any bundle.<br><span style="font-size:12px;color:var(--t3)">Note: Only bundled orders are shown here.</span></div></div>`;
    return;
  }
  // Fetch journey
  let jData=null;
  try{
    const r=await fetch("/api/nexus/order_journey/"+encodeURIComponent(q));
    jData=await r.json();
  }catch(e){}
  const jRow=jData&&jData.success?jData:null;
  const tl=jRow?jRow.timeline:{};
  const rm=D.bundles?{}:(D.rates||{});
  // Get rates from first bundle's context
  const rmGlobal=window._ratesCache||{};
  const comp=calcBundleComparison(foundBundle,rmGlobal);
  const myComp=comp.orderBreakdown.find(o=>o.order_id.toUpperCase()===q)||comp.orderBreakdown[0];
  const sla=jRow?getSLAStatus({qc_approved_at:tl.qc_approved_at,handedover_at:tl.handedover_at}):null;
  const stS=sStyle(foundOrder.status||"—");

  let html=`<div class="os-result-card">
    <div class="os-header">
      <div>
        <div class="os-order-id">📦 ${q}</div>
        <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <span class="os-status-badge" style="background:${stS.bg};color:${stS.c};border-color:${stS.bd||stS.c+'44'}">${foundOrder.status||"—"}</span>
          ${sla?`<span class="sla-badge sla-${sla.status}">${sla.label} QC→Handover</span>`:""}
        </div>
      </div>
      <div style="text-align:right">
        <div style="font-size:11px;color:var(--t3)">Part of bundle</div>
        <div style="font-size:18px;font-weight:900;color:var(--acc)">${foundBundle.orders.length} orders</div>
        <div style="font-size:11px;color:var(--t3)">${foundBundle.source}</div>
      </div>
    </div>

    <div class="os-grid">
      <div class="os-info-box"><div class="os-info-label">📅 Date</div><div class="os-info-val">${foundBundle.date||"—"}</div></div>
      <div class="os-info-box"><div class="os-info-label">👤 Customer</div><div class="os-info-val">${foundBundle.customer||"—"}</div></div>
      <div class="os-info-box"><div class="os-info-label">🌍 Country</div><div class="os-info-val">${foundBundle.country||"—"}</div></div>
      <div class="os-info-box"><div class="os-info-label">🏪 Vendor</div><div class="os-info-val">${foundBundle.vendor||"—"}</div></div>
      <div class="os-info-box"><div class="os-info-label">⚖️ Est. Weight</div><div class="os-info-val">${myComp?myComp.est_weight.toFixed(2)+" kg":foundOrder.weight+" kg"}</div></div>
      <div class="os-info-box"><div class="os-info-label">📬 Tracking</div><div class="os-info-val" style="font-family:monospace;font-size:11px">${foundBundle.tid||"Pending"}</div></div>
    </div>`;

  // Timeline if available
  if(jRow&&jRow.timeline){
    const steps=[
      ["📋 Created",tl.created_at],["✅ Accepted",tl.accepted_at],
      ["🚚 Pickup",tl.pickup_ready_at],["🔍 QC Pending",tl.qc_pending_at],
      ["✅ QC Approved",tl.qc_approved_at],["🤝 Handover",tl.handedover_at],
      ["✈️ Freight",tl.freight_at],["🚁 Courier",tl.courier_at],["📬 Delivered",tl.delivered_at]
    ];
    html+=`<div class="os-bundle-title" style="margin-top:16px">🗺️ Order Journey</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">
    ${steps.map(([l,v])=>`<div style="background:${v?"rgba(34,197,94,.08)":"var(--s3)"};border:1px solid ${v?"rgba(34,197,94,.2)":"var(--bd)"};border-radius:9px;padding:8px 12px;min-width:120px">
      <div style="font-size:9px;color:var(--t3);font-weight:700;text-transform:uppercase;letter-spacing:.8px">${l}</div>
      <div style="font-size:11px;font-weight:700;color:${v?"var(--green)":"var(--t4)"};margin-top:3px">${v||"— Pending"}</div>
    </div>`).join("")}
    </div>`;
  }

  // Bundle siblings
  html+=`<div class="os-bundle-section">
    <div class="os-bundle-title">📦 All Orders in This Bundle</div>`;
  comp.orderBreakdown.forEach(o=>{
    const isSelf=o.order_id.toUpperCase()===q;
    const oSt=sStyle(o.status||"—");
    html+=`<div class="os-sibling ${isSelf?"is-self":""}">
      <div>
        <div style="display:flex;align-items:center;gap:8px">
          <span class="os-sibling-id">${o.order_id}</span>
          ${isSelf?'<span style="font-size:10px;background:rgba(139,92,246,.2);color:var(--acc);padding:2px 8px;border-radius:20px;font-weight:700">YOU</span>':""}
          <span class="spill" style="background:${oSt.bg};color:${oSt.c};border-color:${oSt.bd||oSt.c+'44'}">${o.status||"—"}</span>
        </div>
        <div class="os-sibling-detail" style="margin-top:4px">${(o.title||"").substring(0,50)} · ${o.item_count} pcs</div>
      </div>
      <div style="text-align:right">
        <div style="font-size:12px;font-weight:800;color:var(--t1)">${o.est_weight.toFixed(2)} kg</div>
        <div style="font-size:10px;color:var(--t3)">est. weight</div>
      </div>
    </div>`;
  });

  // Bundle vs individual comparison
  html+=`</div>
    <div class="os-comparison-box">
      <div class="os-comp-title">💰 Bundle vs Individual Shipping Cost</div>
      <div class="os-comp-row">
        <span class="os-comp-label">📦 Total Bundle Weight</span>
        <span class="os-comp-val" style="color:var(--blue)">${comp.totalBW.toFixed(2)} kg → billed ${comp.bundleBilled} kg</span>
      </div>
      <div class="os-comp-row">
        <span class="os-comp-label">💷 Rate (${foundBundle.country||"default"})</span>
        <span class="os-comp-val">£${comp.rate.toFixed(2)}/kg</span>
      </div>
      <div class="os-comp-row">
        <span class="os-comp-label">❌ If Shipped Individually</span>
        <span class="os-comp-val" style="color:var(--red)">£${comp.indivCost.toFixed(2)}</span>
      </div>
      <div class="os-comp-row">
        <span class="os-comp-label">✅ As Bundle</span>
        <span class="os-comp-val" style="color:var(--green)">£${comp.bundleCost.toFixed(2)}</span>
      </div>
      <div class="os-comp-row" style="border-top:1px solid rgba(34,197,94,.2);margin-top:8px;padding-top:8px">
        <span class="os-comp-label" style="font-weight:800;color:var(--t1)">🎉 Total Saved</span>
        <span class="os-comp-val" style="color:var(--green);font-size:18px">£${comp.saved.toFixed(2)}</span>
      </div>
    </div>
  </div>`;

  cont.innerHTML=html;
}

// ============================================================
// CUSTOMER INTELLIGENCE
// ============================================================
function rCustomers(){
  if(!D) return;
  const cont=g("custCards");
  if(!cont) return;
  const q=(g("custQ")?.value||"").toLowerCase();
  const sort=g("custSort")?.value||"orders";
  // Build customer map
  const custMap={};
  (D.bundles||[]).forEach(b=>{
    const cust=b.customer||"Unknown";
    if(!custMap[cust]) custMap[cust]={
      name:cust,vendor:b.vendor||"",
      orders:0,bundles:0,weight:0,saved:0,
      countries:new Set(),sources:new Set(),
      dates:[],statuses:{}
    };
    const c=custMap[cust];
    c.bundles++;
    c.dates.push(b.date_std);
    c.countries.add(b.country||"—");
    c.sources.add(b.source);
    c.saved+=b.savings_gbp||0;
    c.weight+=b.weight_kg||0;
    b.orders.forEach(o=>{
      c.orders++;
      const st=o.status||"—";
      c.statuses[st]=(c.statuses[st]||0)+1;
    });
  });
  let arr=Object.values(custMap);
  if(q) arr=arr.filter(c=>c.name.toLowerCase().includes(q)||(c.vendor||"").toLowerCase().includes(q));
  arr.sort((a,b)=>{
    if(sort==="saved") return b.saved-a.saved;
    if(sort==="weight") return b.weight-a.weight;
    return b.orders-a.orders;
  });
  if(!arr.length){cont.innerHTML=`<div class="empty-state"><div class="empty-icon">👥</div><div>No customers found</div></div>`;return;}
  const colors=["#8b5cf6","#3b82f6","#22c55e","#f59e0b","#ec4899","#06b6d4","#f97316","#a855f7"];
  let html=`<div class="cust-grid">`;
  arr.forEach((c,i)=>{
    const col=colors[i%colors.length];
    const initials=c.name.split(" ").map(w=>w[0]).join("").substring(0,2).toUpperCase();
    const dSorted=c.dates.sort(); const firstD=dSorted[0]||""; const lastD=dSorted[dSorted.length-1]||"";
    const topStatus=Object.entries(c.statuses).sort((a,b)=>b[1]-a[1])[0];
    const ctags=[...c.countries].slice(0,4).map(cn=>`<span class="cust-country-tag">🌍 ${cn}</span>`).join("");
    html+=`<div class="cust-card" onclick="showCustDetail('${c.name.replace(/'/g,"\'")}')">
      <div class="cust-avatar" style="background:linear-gradient(135deg,${col},${col}99)">${initials}</div>
      <div class="cust-name">${c.name}</div>
      <div class="cust-vendor">${c.vendor||"—"} · ${[...c.sources].join(", ")}</div>
      <div class="cust-stats">
        <div class="cust-stat"><div class="cust-stat-v" style="color:var(--blue)">${c.orders}</div><div class="cust-stat-l">📦 Orders</div></div>
        <div class="cust-stat"><div class="cust-stat-v" style="color:var(--purple)">${c.bundles}</div><div class="cust-stat-l">🗃️ Bundles</div></div>
        <div class="cust-stat"><div class="cust-stat-v" style="color:var(--yellow)">${c.weight.toFixed(1)}</div><div class="cust-stat-l">⚖️ kg</div></div>
        <div class="cust-stat"><div class="cust-stat-v" style="color:var(--t3);font-size:12px">${topStatus?topStatus[0].substring(0,10):"—"}</div><div class="cust-stat-l">📡 Top Status</div></div>
      </div>
      <div class="cust-saved"><div class="cust-saved-v">£${c.saved.toFixed(2)}</div><div class="cust-saved-l">💰 Total Saved</div></div>
      <div class="cust-countries" style="margin-top:8px">${ctags}</div>
      <div style="font-size:9px;color:var(--t4);margin-top:10px">First: ${firstD||"—"} · Last: ${lastD||"—"}</div>
    </div>`;
  });
  html+=`</div>`;
  cont.innerHTML=html;
}

function showCustDetail(name){
  if(GUEST) return;
  const bundles=(D.bundles||[]).filter(b=>b.customer===name);
  const list=bundles.flatMap(b=>b.orders.map(o=>({...o,date:b.date_std,source:b.source,customer:b.customer})));
  g("oTit").textContent=`👥 ${name} — ${list.length} orders`;
  showOrdModal(list);
}

// ============================================================
// ROUTE INTELLIGENCE
// ============================================================
function setRouteRange(days,btn){
  document.querySelectorAll("#pane-route .qb").forEach(b=>b.classList.remove("on"));
  if(btn) btn.classList.add("on");
  if(days===0){g("rtFrom").value="";g("rtTo").value="";}
  else{
    const to=new Date(); const from=new Date();
    from.setDate(from.getDate()-days);
    g("rtFrom").value=fi(from); g("rtTo").value=fi(to);
  }
  rRoute();
}
function clearRouteFilter(btn){
  g("rtFrom").value=""; g("rtTo").value=""; g("rtCountry").value="";
  document.querySelectorAll("#pane-route .qb").forEach(b=>b.classList.remove("on"));
  document.querySelector("#pane-route .qb").classList.add("on");
  rRoute();
}
function rRoute(){
  if(!D) return;
  const cont=g("routeBody");
  if(!cont) return;
  cont.innerHTML=`<div class="lw"><div class="ld"></div><p class="lp">Analysing shipping patterns...</p></div>`;
  setTimeout(()=>_buildRoute(cont),40);
}

function _buildRoute(cont){
  const DAYS_LBL=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  const FLT_DAYS=[1,3,5]; // Tue=1, Thu=3, Sat=5
  const countryMap={};

  // Apply date + country filters
  const fromV=g("rtFrom")?.value; const toV=g("rtTo")?.value;
  const cntryQ=(g("rtCountry")?.value||"").toLowerCase().trim();
  const fromD=fromV?new Date(fromV):null; if(fromD) fromD.setHours(0,0,0,0);
  const toD=toV?new Date(toV):null; if(toD) toD.setHours(23,59,59,999);
  const filteredBundles=(D.bundles||[]).filter(b=>{
    const bd=new Date(b.date_std);
    if(fromD&&bd<fromD) return false;
    if(toD&&bd>toD) return false;
    if(cntryQ&&!(b.country||"").toLowerCase().includes(cntryQ)) return false;
    return true;
  });
  filteredBundles.forEach(b=>{
    const cn=b.country||"Unknown";
    const d=new Date(b.date_std);
    const di=d.getDay()===0?6:d.getDay()-1; // Mon=0
    if(!countryMap[cn]) countryMap[cn]={days:Array.from({length:7},()=>({bundles:0,orders:0,weight:0,saved:0,list:[]})),total:0};
    const cm=countryMap[cn];
    cm.total+=b.orders.length;
    cm.days[di].bundles++;
    cm.days[di].orders+=b.orders.length;
    cm.days[di].weight+=b.weight_kg||0;
    cm.days[di].saved+=b.savings_gbp||0;
    b.orders.forEach(o=>cm.days[di].list.push({...o,date:b.date_std,customer:b.customer,source:b.source}));
  });
  // Cache for drill-down
  window._routeCountryMap=countryMap;

  const sorted=Object.entries(countryMap).sort((a,b)=>b[1].total-a[1].total).slice(0,12);
  if(!sorted.length){cont.innerHTML=`<div class="empty-state"><div class="empty-icon">🛣️</div><div>No data for selected filters</div></div>`;return;}

  // Global pattern summary
  const globalDays=Array.from({length:7},()=>({orders:0,saved:0}));
  sorted.forEach(([cn,cm])=>cm.days.forEach((d,i)=>{globalDays[i].orders+=d.orders;globalDays[i].saved+=d.saved;}));
  const bestGlobalDay=globalDays.reduce((b,d,i)=>d.orders>b.val?{i,val:d.orders}:{i:b.i,val:b.val},{i:0,val:0});

  let html=`<div style="background:var(--s2);border:1px solid rgba(139,92,246,.2);border-radius:16px;padding:22px;margin-bottom:22px;background:linear-gradient(135deg,rgba(139,92,246,.08),rgba(34,197,94,.04))">
    <div style="font-size:16px;font-weight:800;color:var(--t1);margin-bottom:6px">🌐 Global Shipping Pattern</div>
    <div style="font-size:12px;color:var(--t3);margin-bottom:16px">Based on ${(D.bundles||[]).length.toLocaleString()} bundles across all countries</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
    ${globalDays.map((d,i)=>{
      const isBest=i===bestGlobalDay.i;
      const isFlt=FLT_DAYS.includes(i);
      return `<div style="flex:1;min-width:80px;background:${isBest?"rgba(34,197,94,.12)":"var(--s3)"};border:1.5px solid ${isBest?"rgba(34,197,94,.35)":"var(--bd)"};border-radius:12px;padding:12px;text-align:center">
        <div style="font-size:11px;font-weight:800;color:${isBest?"var(--green)":"var(--t3)"}">${DAYS_LBL[i]}${isFlt?" ✈️":""}</div>
        <div style="font-size:22px;font-weight:900;color:${isBest?"var(--green)":"var(--t1)"};margin:6px 0">${d.orders}</div>
        <div style="font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700">orders</div>
        ${isBest?'<div style="font-size:9px;color:var(--green);font-weight:800;margin-top:4px">👑 BEST</div>':""}
      </div>`;
    }).join("")}
    </div>
  </div>
  <div class="route-grid">`;

  sorted.forEach(([cn,cm])=>{
    const maxO=Math.max(...cm.days.map(d=>d.orders),1);
    const bestDayIdx=cm.days.reduce((b,d,i)=>d.orders>b.val?{i,val:d.orders}:{i:b.i,val:b.val},{i:0,val:0}).i;
    const bestDay=cm.days[bestDayIdx];
    const flightDayHit=FLT_DAYS.includes(bestDayIdx);
    const totalSaved=cm.days.reduce((a,d)=>a+d.saved,0);

    const barColors=["#8b5cf6","#3b82f6","#22c55e","#f59e0b","#ec4899","#06b6d4","#f97316"];

    html+=`<div class="route-card">
      <div class="route-country">
        🌍 ${cn}
        <span style="font-size:11px;font-weight:700;color:var(--t3)">${cm.total} orders</span>
        ${flightDayHit?'<span style="font-size:10px;padding:2px 8px;background:rgba(34,197,94,.1);color:var(--green);border-radius:20px;border:1px solid rgba(34,197,94,.25);font-weight:800">✈️ Flight Day Match</span>':""}
      </div>
      <div class="route-insight">💡 Best day: ${DAYS_LBL[bestDayIdx]} — ${bestDay.orders} orders, £${bestDay.saved.toFixed(2)} saved</div>
      <div class="route-day-bars">
        ${cm.days.map((d,i)=>{
          const pct=maxO>0?Math.round(d.orders/maxO*100):0;
          const isBest=i===bestDayIdx;
          const col=isBest?"#22c55e":barColors[i%barColors.length];
          const clickable=!GUEST&&d.orders>0;
        return `<div class="route-day-row" ${clickable?`onclick="showRouteDrill('${cn.replace(/'/g,"\'")}',${i})" style="cursor:pointer"`:""}>
            <div class="route-day-label" style="color:${isBest?"var(--green)":"var(--t2)"}">${DAYS_LBL[i]}</div>
            <div class="route-day-track">
              <div class="route-day-fill" style="width:${pct}%;background:${col};${clickable?"transition:.15s":""}" class="route-day-fill">
                ${d.orders>0?`<span>${d.orders}</span>`:""}
              </div>
            </div>
            <div class="route-day-val" style="color:${isBest?"var(--green)":"var(--t2)"}">${d.orders}</div>
            ${isBest?`<span class="route-best-tag">Best</span>`:""}
          </div>`;
        }).join("")}
      </div>
      <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--bd);display:flex;justify-content:space-between">
        <div style="font-size:11px;color:var(--t3)">💰 Total saved: <b style="color:var(--green)">£${totalSaved.toFixed(2)}</b></div>
        <div style="font-size:11px;color:var(--t3)">⚖️ Total weight: <b style="color:var(--yellow)">${cm.days.reduce((a,d)=>a+d.weight,0).toFixed(1)} kg</b></div>
      </div>
    </div>`;
  });
  html+=`</div>`;
  cont.innerHTML=html;
}

// ============================================================
// CACHE RATES for client-side use
// ============================================================
function cacheRates(){
  // Use rates from API response (D.rates_map), fallback to server-injected RATES_MAP
  window._ratesCache=(D&&D.rates_map&&Object.keys(D.rates_map).length)?D.rates_map:((typeof RATES_MAP!=="undefined")?RATES_MAP:{});
}

// ============================================================
// CSS for receipt / certificate (injected once)
// ============================================================
(function(){
  const s=document.createElement("style");
  s.textContent=`
    .rcpt-card{background:var(--s2);border:1px solid var(--bd);border-radius:16px;padding:0;margin-bottom:16px;box-shadow:var(--shadow);overflow:hidden;transition:.2s;}
    .rcpt-card:hover{border-color:var(--acc);transform:translateY(-2px);box-shadow:var(--shadow2);}
    .rcpt-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;background:var(--s3);border-bottom:1px solid var(--bd);flex-wrap:wrap;gap:10px;}
    .rcpt-bid{font-size:14px;font-weight:900;font-family:monospace;color:var(--acc);}
    .rcpt-meta{font-size:11px;color:var(--t3);margin-top:2px;}
    .rcpt-body{padding:16px 20px;}
    .rcpt-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;}
    .rcpt-stat{background:var(--s3);border:1px solid var(--bd);border-radius:10px;padding:12px;text-align:center;}
    .rcpt-stat-v{font-size:16px;font-weight:900;color:var(--t1);}
    .rcpt-stat-l{font-size:9px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:3px;}
    .rcpt-orders{margin-top:10px;}
    .rcpt-order-row{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;background:var(--s3);border:1px solid var(--bd);margin-bottom:6px;}
    .rcpt-order-id{font-family:monospace;font-weight:800;color:var(--green);font-size:11px;min-width:100px;}
    .rcpt-order-title{flex:1;font-size:11px;color:var(--t2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .rcpt-order-wt{font-size:11px;font-weight:700;color:var(--t3);min-width:50px;text-align:right;}
    .rcpt-download{padding:7px 16px;background:linear-gradient(135deg,#7c3aed,#8b5cf6);border:none;border-radius:8px;color:#fff;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit;transition:.15s;}
    .rcpt-download:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(139,92,246,.4);}
    .rcpt-savings-bar{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:linear-gradient(90deg,rgba(34,197,94,.08),rgba(34,197,94,.03));border:1px solid rgba(34,197,94,.2);border-radius:10px;margin-top:10px;}
    /* CERTIFICATE */
    .cert-wrap{max-width:800px;margin:0 auto;}
    .cert-box{background:var(--s1);border:3px solid var(--acc);border-radius:24px;padding:50px;text-align:center;position:relative;overflow:hidden;box-shadow:var(--shadow2);}
    .cert-box::before{content:'';position:absolute;top:-60px;right:-60px;width:220px;height:220px;background:radial-gradient(circle,rgba(139,92,246,.15),transparent);border-radius:50%;}
    .cert-box::after{content:'';position:absolute;bottom:-60px;left:-60px;width:220px;height:220px;background:radial-gradient(circle,rgba(34,197,94,.1),transparent);border-radius:50%;}
    .cert-logo{font-size:52px;margin-bottom:12px;}
    .cert-brand{font-size:28px;font-weight:900;color:var(--acc);letter-spacing:-1px;margin-bottom:4px;}
    .cert-tagline{font-size:12px;color:var(--t3);text-transform:uppercase;letter-spacing:2px;margin-bottom:32px;}
    .cert-title{font-size:16px;color:var(--t3);text-transform:uppercase;letter-spacing:3px;margin-bottom:8px;}
    .cert-amount{font-size:64px;font-weight:900;color:var(--green);letter-spacing:-3px;line-height:1;margin-bottom:8px;}
    .cert-subtitle{font-size:14px;color:var(--t2);margin-bottom:32px;}
    .cert-quarter{font-size:22px;font-weight:800;color:var(--acc);margin-bottom:24px;}
    .cert-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0;}
    .cert-stat{background:var(--s2);border:1px solid var(--bd);border-radius:14px;padding:18px;}
    .cert-stat-v{font-size:26px;font-weight:900;color:var(--t1);}
    .cert-stat-l{font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:4px;}
    .cert-footer{font-size:11px;color:var(--t4);margin-top:24px;border-top:1px solid var(--bd);padding-top:16px;}
    /* PREDICT */
    .pred-card{background:var(--s2);border:1px solid var(--bd);border-radius:16px;padding:22px;box-shadow:var(--shadow);margin-bottom:18px;}
    .pred-zone{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:12px;display:flex;align-items:center;gap:8px;}
    .pred-row{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-radius:10px;background:var(--s3);border:1px solid var(--bd);margin-bottom:8px;}
    .pred-day{font-size:12px;font-weight:700;color:var(--t2);min-width:50px;}
    .pred-bar-wrap{flex:1;height:14px;background:var(--s1);border-radius:7px;overflow:hidden;margin:0 12px;}
    .pred-bar{height:100%;border-radius:7px;transition:.8s;}
    .pred-val{font-size:12px;font-weight:800;min-width:60px;text-align:right;}
    .pred-badge{font-size:9px;padding:2px 8px;border-radius:20px;font-weight:800;}
    @media print{
      .sidebar,.topbar,.fbar,.rcpt-download{display:none!important;}
      .main{padding:0!important;overflow:visible!important;}
      .cert-box{border:3px solid #7c3aed!important;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
    }
  `;
  document.head.appendChild(s);
})();

// ============================================================
// BUNDLE RECEIPT GENERATOR
// ============================================================
function rReceipt(){
  if(!D) return;
  const cont=g("rcptList");
  if(!cont) return;
  const q=(g("rcptQ")?.value||"").toLowerCase().trim();
  const fromV=g("rcptFrom")?.value; const toV=g("rcptTo")?.value;
  const fromD=fromV?new Date(fromV):null; if(fromD) fromD.setHours(0,0,0,0);
  const toD=toV?new Date(toV):null; if(toD) toD.setHours(23,59,59,999);

  let bundles=(D.bundles||[]).filter(b=>{
    const bd=new Date(b.date_std);
    if(fromD&&bd<fromD) return false;
    if(toD&&bd>toD) return false;
    if(q){
      const inOrders=b.orders.some(o=>o.order_id.toLowerCase().includes(q));
      const inCust=(b.customer||"").toLowerCase().includes(q);
      if(!inOrders&&!inCust) return false;
    }
    return true;
  });

  if(!bundles.length){
    cont.innerHTML=`<div class="empty-state"><div class="empty-icon">🧾</div><div>No bundles found</div></div>`;
    return;
  }

  // Limit to 50 for performance
  const total=bundles.length;
  bundles=bundles.slice(0,50);

  let html=`<div style="font-size:12px;color:var(--t3);margin-bottom:14px">Showing ${bundles.length} of ${total} bundles${total>50?" (search to filter)":""}</div>`;

  bundles.forEach((b,bi)=>{
    const oid=`RCPT-${b.date_std||"NODATE"}-${b.customer||"CUST"}`.replace(/[^A-Z0-9\-]/gi,"-").toUpperCase();
    const stS=sStyle(b.orders[0]?.status||"—");
    const savedColor=b.savings_gbp>0?"var(--green)":"var(--t3)";
    html+=`<div class="rcpt-card" id="rcpt-${bi}">
      <div class="rcpt-header">
        <div>
          <div class="rcpt-bid">📦 ${b.customer||"Unknown"} — ${b.date||"—"}</div>
          <div class="rcpt-meta">
            <span style="color:var(--green);font-weight:700">🌍 ${b.country||"Unknown Country"}</span>
            &nbsp;·&nbsp;${b.source}&nbsp;·&nbsp;
            <span style="font-family:monospace">TID: ${b.tid||"Pending"}</span>
          </div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <span style="font-size:20px;font-weight:900;color:${savedColor}">£${(b.savings_gbp||0).toFixed(2)} saved</span>
          <button class="rcpt-download" onclick="downloadReceipt(${bi})">🖨️ PDF</button>
        </div>
      </div>
      <div class="rcpt-body">
        <div class="rcpt-grid">
          <div class="rcpt-stat"><div class="rcpt-stat-v" style="color:var(--blue)">${b.orders.length}</div><div class="rcpt-stat-l">📦 Orders</div></div>
          <div class="rcpt-stat"><div class="rcpt-stat-v" style="color:var(--yellow)">${(b.weight_kg||0).toFixed(2)} kg</div><div class="rcpt-stat-l">⚖️ Total Wt</div></div>
          <div class="rcpt-stat"><div class="rcpt-stat-v" style="color:var(--purple)">${Math.max(Math.ceil(b.weight_kg||0),1)} kg</div><div class="rcpt-stat-l">💷 Billed Wt</div></div>
          <div class="rcpt-stat"><div class="rcpt-stat-v" style="color:var(--cyan);font-size:14px">${b.country||"—"}</div><div class="rcpt-stat-l">🌍 Country</div></div>
        </div>
        <div class="rcpt-orders">
        ${b.orders.map(o=>{
          const os=sStyle(o.status||"—");
          return `<div class="rcpt-order-row">
            <span class="rcpt-order-id">${o.order_id}</span>
            <span class="rcpt-order-title">${(o.title||"").substring(0,45)}</span>
            <span class="spill" style="background:${os.bg};color:${os.c};border-color:${os.bd||os.c+'44'}">${o.status||"—"}</span>
            <span class="rcpt-order-wt">${o.item_count||1} pcs · ${o.weight||0} kg</span>
          </div>`;
        }).join("")}
        </div>
        <div class="rcpt-savings-bar">
          <div>
            <div style="font-size:10px;color:var(--green);font-weight:800;text-transform:uppercase;letter-spacing:1px">💰 Shipping Savings</div>
            <div style="font-size:11px;color:var(--t3);margin-top:2px">Individual: £${(b.indiv_cost||0).toFixed(2)} → Bundle: £${(b.bundle_cost||0).toFixed(2)}</div>
          </div>
          <div style="font-size:22px;font-weight:900;color:var(--green)">£${(b.savings_gbp||0).toFixed(2)}</div>
        </div>
      </div>
    </div>`;
  });

  // Store bundles for PDF
  window._rcptBundles=bundles;
  cont.innerHTML=html;
}

function downloadReceipt(idx){
  const b=window._rcptBundles?.[idx];
  if(!b) return;
  const DR=4.50;
  const rate=b.rate_gbp||DR;
  const date=b.date||"—";
  const win=window.open("","_blank","width=700,height=900");
  win.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Bundle Receipt</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:Arial,sans-serif;background:#fff;color:#111;padding:40px;max-width:680px;margin:0 auto;}
  .header{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #7c3aed;padding-bottom:20px;margin-bottom:24px;}
  .brand{font-size:24px;font-weight:900;color:#7c3aed;letter-spacing:-1px;}
  .brand-sub{font-size:11px;color:#888;margin-top:3px;}
  .rcpt-no{font-size:13px;font-weight:700;color:#555;}
  .info-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;}
  .info-box{background:#f8f8f8;border-radius:8px;padding:14px;}
  .info-label{font-size:9px;text-transform:uppercase;font-weight:700;color:#888;margin-bottom:5px;letter-spacing:1px;}
  .info-val{font-size:14px;font-weight:700;color:#111;}
  table{width:100%;border-collapse:collapse;margin-bottom:20px;}
  th{background:#f1f0ff;padding:10px 12px;font-size:10px;text-transform:uppercase;font-weight:700;color:#555;text-align:left;border-bottom:2px solid #7c3aed;}
  td{padding:9px 12px;border-bottom:1px solid #eee;font-size:12px;color:#333;}
  .savings-box{background:linear-gradient(135deg,#f0fdf4,#f0f9ff);border:2px solid #22c55e;border-radius:12px;padding:20px;text-align:center;margin-bottom:20px;}
  .savings-amount{font-size:40px;font-weight:900;color:#16a34a;}
  .savings-label{font-size:11px;color:#555;text-transform:uppercase;letter-spacing:1px;margin-top:4px;}
  .cost-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px dashed #ddd;}
  .cost-row:last-child{border-bottom:none;}
  .footer{text-align:center;color:#888;font-size:10px;border-top:1px solid #eee;padding-top:16px;margin-top:24px;}
  @media print{body{padding:20px;}button{display:none;}}
</style>
</head><body>
<div class="header">
  <div>
    <div class="brand">🏢 Fleek 3PL</div>
    <div class="brand-sub">Bundle Intelligence Platform</div>
  </div>
  <div style="text-align:right">
    <div class="rcpt-no">Bundle Receipt</div>
    <div style="font-size:11px;color:#888">${date}</div>
    <div style="font-size:11px;color:#888">${b.source}</div>
  </div>
</div>
<div class="info-grid">
  <div class="info-box"><div class="info-label">Customer</div><div class="info-val">${b.customer||"—"}</div></div>
  <div class="info-box"><div class="info-label">Country</div><div class="info-val">${b.country||"—"}</div></div>
  <div class="info-box"><div class="info-label">Vendor</div><div class="info-val">${b.vendor||"—"}</div></div>
  <div class="info-box"><div class="info-label">Tracking ID</div><div class="info-val" style="font-size:11px">${b.tid||"Pending"}</div></div>
</div>
<table>
<tr><th>Order ID</th><th>Item / Description</th><th>Qty</th><th>Wt (kg)</th><th>Status</th></tr>
${b.orders.map(o=>`<tr><td style="font-family:monospace;font-weight:700;color:#7c3aed">${o.order_id}</td><td>${(o.title||"").substring(0,40)}</td><td>${o.item_count||1}</td><td>${o.weight||0}</td><td><span style="background:${o.status==='QC_APPROVED'||o.status==='HANDED_OVER_TO_LOGISTICS_PARTNER'?'#dcfce7':'#f3e8ff'};color:${o.status==='QC_APPROVED'||o.status==='HANDED_OVER_TO_LOGISTICS_PARTNER'?'#16a34a':'#7c3aed'};padding:3px 8px;border-radius:4px;font-size:10px;font-weight:700">${o.status||"—"}</span></td></tr>`).join("")}
</table>
<div style="margin-bottom:20px">
  <div class="cost-row"><span style="font-weight:700">Total Bundle Weight</span><span>${(b.weight_kg||0).toFixed(2)} kg</span></div>
  <div class="cost-row"><span style="font-weight:700">Billed Weight (ceil)</span><span>${Math.max(Math.ceil(b.weight_kg||0),1)} kg</span></div>
  <div class="cost-row"><span style="font-weight:700">Rate per kg</span><span>£${rate.toFixed(2)}</span></div>
  <div class="cost-row"><span style="color:#dc2626;font-weight:700">❌ If Shipped Individually</span><span style="color:#dc2626">£${(b.indiv_cost||0).toFixed(2)}</span></div>
  <div class="cost-row"><span style="color:#16a34a;font-weight:700">✅ As Bundle</span><span style="color:#16a34a">£${(b.bundle_cost||0).toFixed(2)}</span></div>
</div>
<div class="savings-box">
  <div class="savings-amount">£${(b.savings_gbp||0).toFixed(2)}</div>
  <div class="savings-label">💰 Total Shipping Saved</div>
</div>
<div class="footer">Generated by Fleek 3PL Bundling Intelligence Platform · ${new Date().toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"})}<br>This is an internal shipping cost analysis document.</div>
<script>setTimeout(()=>window.print(),300);<\/script>
</body></html>`);
  win.document.close();
}

// ============================================================
// PREDICTION
// ============================================================
function rPredict(){
  if(!D) return;
  const cont=g("predictBody");
  if(!cont) return;
  cont.innerHTML=`<div class="lw"><div class="ld"></div><p class="lp">Analysing historical patterns...</p></div>`;
  setTimeout(()=>_buildPredict(cont),60);
}

function _buildPredict(cont){
  const DAYS=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
  const FLT=[1,3,5];
  // Build weekly stats per zone per day-of-week from last 8 weeks
  const now=new Date(); now.setHours(0,0,0,0);
  const cutoff=new Date(now); cutoff.setDate(cutoff.getDate()-56); // 8 weeks

  const zones={
    "ECL QC Center":{days:Array.from({length:7},()=>({orders:[],savings:[]}))},
    "PK Zone":{days:Array.from({length:7},()=>({orders:[],savings:[]}))},
  };

  (D.bundles||[]).forEach(b=>{
    const bd=new Date(b.date_std);
    if(bd<cutoff||bd>=now) return;
    const di=bd.getDay()===0?6:bd.getDay()-1;
    const z=b.source==="ECL QC Center"?"ECL QC Center":"PK Zone";
    zones[z].days[di].orders.push(b.orders.length);
    zones[z].days[di].savings.push(b.savings_gbp||0);
  });

  const avg=(arr)=>arr.length?arr.reduce((a,b)=>a+b,0)/arr.length:0;
  const med=(arr)=>{if(!arr.length)return 0;const s=[...arr].sort((a,b)=>a-b);const m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2;};

  // Get current week Monday
  const mon=new Date(now);
  const day=mon.getDay(); mon.setDate(mon.getDate()-(day===0?6:day-1));
  const todayDi=now.getDay()===0?6:now.getDay()-1;

  let html=`
  <div style="background:linear-gradient(135deg,rgba(139,92,246,.08),rgba(34,197,94,.05));border:1px solid rgba(139,92,246,.2);border-radius:16px;padding:20px;margin-bottom:22px">
    <div style="font-size:16px;font-weight:800;color:var(--t1);margin-bottom:4px">🔮 This Week's Forecast</div>
    <div style="font-size:11px;color:var(--t3)">Based on last 8 weeks of historical data · Updates with each data refresh</div>
  </div>`;

  let totalPredOrders=0; let totalPredSavings=0;

  Object.entries(zones).forEach(([zname,zdata])=>{
    const color=zname==="ECL QC Center"?"var(--green)":"var(--blue)";
    const maxAvg=Math.max(...zdata.days.map(d=>avg(d.orders)),1);
    let weekTotalOrders=0; let weekTotalSavings=0;

    const rows=DAYS.map((dl,di)=>{
      const d=zdata.days[di];
      const dayDate=new Date(mon); dayDate.setDate(mon.getDate()+di);
      const isPast=dayDate<now;
      const isToday=di===todayDi;
      const isFlt=FLT.includes(di);
      const ordersAvg=avg(d.orders);
      const savingsAvg=avg(d.savings);
      const ordersLow=Math.max(0,Math.round(ordersAvg*0.75));
      const ordersHigh=Math.round(ordersAvg*1.25);
      weekTotalOrders+=Math.round(ordersAvg);
      weekTotalSavings+=savingsAvg;
      const pct=maxAvg>0?ordersAvg/maxAvg*100:0;
      const confidence=d.orders.length>=4?"High":d.orders.length>=2?"Medium":"Low";
      const confColor=confidence==="High"?"var(--green)":confidence==="Medium"?"var(--yellow)":"var(--red)";

      return `<div class="pred-row" style="${isToday?"border-color:var(--acc);background:rgba(139,92,246,.06)":""}${isPast?"opacity:.5":""}">
        <div class="pred-day">${dl}<div style="font-size:9px;color:var(--t4)">${dayDate.toLocaleDateString("en-GB",{day:"2-digit",month:"short"})}</div></div>
        <div class="pred-bar-wrap"><div class="pred-bar" style="width:${pct.toFixed(1)}%;background:${color}"></div></div>
        <div class="pred-val" style="color:${color}">${Math.round(ordersAvg)}<div style="font-size:9px;color:var(--t4)">${ordersLow}–${ordersHigh}</div></div>
        <div style="display:flex;gap:5px;align-items:center;min-width:110px;justify-content:flex-end">
          <span class="pred-badge" style="background:rgba(34,197,94,.1);color:var(--green)">£${savingsAvg.toFixed(0)}</span>
          ${isFlt?`<span class="pred-badge" style="background:rgba(96,165,250,.1);color:var(--blue)">✈️</span>`:""}
          ${isToday?`<span class="pred-badge" style="background:rgba(139,92,246,.15);color:var(--acc)">TODAY</span>`:""}
          <span class="pred-badge" style="background:rgba(255,255,255,.04);color:${confColor}">${confidence}</span>
        </div>
      </div>`;
    }).join("");

    totalPredOrders+=weekTotalOrders;
    totalPredSavings+=weekTotalSavings;

    html+=`<div class="pred-card">
      <div class="pred-zone" style="color:${color}">
        <div style="width:8px;height:8px;border-radius:50%;background:${color};box-shadow:0 0 6px ${color}"></div>
        ${zname}
        <span style="margin-left:auto;font-size:11px;font-weight:700;color:var(--t3)">~${weekTotalOrders} orders · ~£${weekTotalSavings.toFixed(0)} savings this week</span>
      </div>
      ${rows}
    </div>`;
  });

  html+=`<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:8px">
    <div style="background:var(--s2);border:1px solid rgba(139,92,246,.2);border-radius:14px;padding:18px;text-align:center">
      <div style="font-size:30px;font-weight:900;color:var(--acc)">${totalPredOrders}</div>
      <div style="font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:4px">📦 Expected Orders</div>
    </div>
    <div style="background:var(--s2);border:1px solid rgba(34,197,94,.2);border-radius:14px;padding:18px;text-align:center">
      <div style="font-size:30px;font-weight:900;color:var(--green)">£${totalPredSavings.toFixed(0)}</div>
      <div style="font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:4px">💰 Expected Savings</div>
    </div>
    <div style="background:var(--s2);border:1px solid rgba(96,165,250,.2);border-radius:14px;padding:18px;text-align:center">
      <div style="font-size:30px;font-weight:900;color:var(--blue)">${Math.round(totalPredOrders/7)}/day</div>
      <div style="font-size:10px;color:var(--t3);text-transform:uppercase;font-weight:700;margin-top:4px">📊 Daily Average</div>
    </div>
  </div>`;

  cont.innerHTML=html;
}

// ============================================================
// SAVINGS CERTIFICATE
// ============================================================
function rCertificate(){
  if(GUEST) return;
  const cont=g("certBody");
  if(!cont) return;
  const quarter=g("certQuarter")?.value||"Q1";
  const year=parseInt(g("certYear")?.value||"2026");
  const qMonths={Q1:[0,1,2],Q2:[3,4,5],Q3:[6,7,8],Q4:[9,10,11]};
  const months=qMonths[quarter];
  const qStart=new Date(year,months[0],1);
  const qEnd=new Date(year,months[2]+1,0);
  qEnd.setHours(23,59,59,999);

  const bundles=(D.bundles||[]).filter(b=>{
    const bd=new Date(b.date_std);
    return bd>=qStart&&bd<=qEnd;
  });

  const totalSaved=bundles.reduce((a,b)=>a+(b.savings_gbp||0),0);
  const totalOrders=bundles.reduce((a,b)=>a+b.orders.length,0);
  const totalBundles=bundles.length;
  const totalWeight=bundles.reduce((a,b)=>a+(b.weight_kg||0),0);
  const shipsSaved=totalOrders-totalBundles;
  const topCountry=Object.entries(bundles.reduce((m,b)=>{m[b.country||"—"]=(m[b.country||"—"]||0)+b.orders.length;return m;},{})).sort((a,b)=>b[1]-a[1])[0];

  const qLabel=`${quarter} ${year}`;
  const qRange=`${qStart.toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"})} – ${qEnd.toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"})}`;

  if(!totalBundles){
    cont.innerHTML=`<div class="empty-state"><div class="empty-icon">🏅</div><div>No data for ${qLabel}</div></div>`;
    return;
  }

  cont.innerHTML=`<div class="cert-wrap" id="certPrintArea">
    <div class="cert-box">
      <div class="cert-logo">🏢</div>
      <div class="cert-brand">FLEEK 3PL</div>
      <div class="cert-tagline">Bundling Intelligence Platform</div>
      <div class="cert-title">Shipping Savings Certificate</div>
      <div class="cert-amount">£${totalSaved.toLocaleString("en-GB",{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
      <div class="cert-subtitle">Total shipping costs saved through smart bundling</div>
      <div class="cert-quarter">${qLabel} · ${qRange}</div>
      <div class="cert-stats">
        <div class="cert-stat">
          <div class="cert-stat-v" style="color:var(--blue)">${totalOrders.toLocaleString()}</div>
          <div class="cert-stat-l">📦 Orders Processed</div>
        </div>
        <div class="cert-stat">
          <div class="cert-stat-v" style="color:var(--green)">${totalBundles.toLocaleString()}</div>
          <div class="cert-stat-l">🗃️ Bundles Created</div>
        </div>
        <div class="cert-stat">
          <div class="cert-stat-v" style="color:var(--yellow)">${shipsSaved.toLocaleString()}</div>
          <div class="cert-stat-l">🚚 Shipments Saved</div>
        </div>
        <div class="cert-stat">
          <div class="cert-stat-v" style="color:var(--purple)">${totalWeight.toFixed(0)} kg</div>
          <div class="cert-stat-l">⚖️ Total Weight</div>
        </div>
        <div class="cert-stat">
          <div class="cert-stat-v" style="color:var(--cyan)">£${(totalOrders>0?totalSaved/totalOrders:0).toFixed(2)}</div>
          <div class="cert-stat-l">💷 Avg Saved/Order</div>
        </div>
        <div class="cert-stat">
          <div class="cert-stat-v" style="color:var(--orange)">${topCountry?topCountry[0]:"—"}</div>
          <div class="cert-stat-l">🌍 Top Country</div>
        </div>
      </div>
      <div style="margin:20px 0;padding:16px;background:rgba(34,197,94,.07);border:1px solid rgba(34,197,94,.2);border-radius:12px">
        <div style="font-size:13px;color:var(--green);font-weight:700">💡 By bundling ${totalOrders.toLocaleString()} orders into ${totalBundles.toLocaleString()} shipments, Fleek 3PL saved the equivalent of ${shipsSaved.toLocaleString()} individual shipments — reducing both cost and carbon footprint.</div>
      </div>
      <div class="cert-footer">
        Certified by Fleek 3PL Bundling Intelligence Platform · Generated ${new Date().toLocaleDateString("en-GB",{day:"2-digit",month:"long",year:"numeric"})}<br>
        This certificate reflects automated analysis of shipping operations data.
      </div>
    </div>
  </div>`;
}

function printCertificate(){
  if(GUEST) return;
  window.print();
}

function showRouteDrill(country,dayIdx){
  const DAYS_LBL=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
  const cm=window._routeCountryMap?.[country];
  if(!cm) return;
  const dayData=cm.days[dayIdx];
  if(!dayData||!dayData.list?.length) return;
  g("oTit").textContent=`🌍 ${country} — ${DAYS_LBL[dayIdx]} (${dayData.orders} orders, £${dayData.saved.toFixed(2)} saved)`;
  showOrdModal(dayData.list);
}

function cMod(id){document.getElementById(id).classList.remove("open");}
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){cMod("jMov");cMod("oMov");return;}
  // Ctrl+F or Cmd+F on bundle tab — focus search
  if((e.ctrlKey||e.metaKey)&&e.key==="f"){
    const activePaneName=document.querySelector(".sb-tab.active")?.dataset?.pane;
    const searchInput=activePaneName==="bundle"?g("bq"):
                      activePaneName==="status"?g("sq"):
                      activePaneName==="search"?g("osq"):
                      activePaneName==="receipt"?g("rcptQ"):null;
    if(searchInput){e.preventDefault();searchInput.focus();searchInput.select();}
  }
});
window.onload=init;
</script></body></html>"""
@app.after_request
def add_float_btns(response):
    if request.path == "/" and response.content_type and "text/html" in response.content_type:
        html = response.get_data(as_text=True)
        # Bulletproof Button Logic
        btn = '''<div style="position:fixed;bottom:24px;right:24px;display:flex;flex-direction:column;gap:10px;z-index:99999">
<a href="/bundling" style="background:#10b981;color:#000;padding:10px 20px;border-radius:50px;text-decoration:none;font-weight:800;font-family:sans-serif;text-align:center;box-shadow:0 6px 18px rgba(16,185,129,.4)">📦 Bundling Intel</a>
</div>'''
        if "</body>" in html: 
            response.set_data(html.replace("</body>", btn + "</body>"))
    return response
@app.route('/debug')
def debug_sheet():
    try:
        # Token wapas add kar diya hai taake sheet access ho sakay
        headers = get_auth_headers()
        clean_id = SHEET_ID.strip()
        url = f'https://docs.google.com/spreadsheets/d/{clean_id}/export?format=csv&gid=1603070499'
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode('utf-8')
            return f"<h1>✅ SUCCESS!</h1> <p>Data length: {len(data)} characters</p> <p>First 200 chars:</p> <pre>{data[:200]}</pre>"
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"<h1>❌ ERROR PAKRA GAYA:</h1> <h2>{str(e)}</h2> <p><b>Details:</b></p> <pre>{error_details}</pre>"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
