from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from functools import wraps
import csv
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
import time
import os
import calendar
import random

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# ============================================
# ADMIN PASSWORD & CACHE
# ============================================
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Rocket2024')
CACHE = {}
CACHE_DURATION = 300  # 5 minutes
SHEET_ID = '1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY'

# ============================================
# 🔒 LOCKED COLUMN MAPPINGS
# ============================================
PROVIDERS = [
    {'name': 'GLOBAL EXPRESS (QC)', 'short': 'GE QC', 'sheet': 'GE QC Center & Zone', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'order_col': 0, 'start_row': 2, 'color': '#3B82F6', 'group': 'GE'},
    {'name': 'GLOBAL EXPRESS (ZONE)', 'short': 'GE ZONE', 'sheet': 'GE QC Center & Zone', 'date_col': 10, 'box_col': 11, 'weight_col': 15, 'region_col': 16, 'order_col': 9, 'start_row': 2, 'color': '#8B5CF6', 'group': 'GE'},
    {'name': 'ECL LOGISTICS (QC)', 'short': 'ECL QC', 'sheet': 'ECL QC Center & Zone', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'order_col': 0, 'start_row': 3, 'color': '#10B981', 'group': 'ECL'},
    {'name': 'ECL LOGISTICS (ZONE)', 'short': 'ECL ZONE', 'sheet': 'ECL QC Center & Zone', 'date_col': 10, 'box_col': 11, 'weight_col': 14, 'region_col': 16, 'order_col': 0, 'start_row': 3, 'color': '#F59E0B', 'group': 'ECL'},
    {'name': 'KERRY', 'short': 'KERRY', 'sheet': 'Kerry', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'order_col': 0, 'start_row': 2, 'color': '#EF4444', 'group': 'OTHER'},
    {'name': 'APX', 'short': 'APX', 'sheet': 'APX', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'order_col': 0, 'start_row': 2, 'color': '#EC4899', 'group': 'OTHER'}
]

INVALID_REGIONS = {'', 'N/A', '#N/A', 'COUNTRY', 'REGION', 'DESTINATION', 'ZONE', 'ORDER', 'FLEEK ID', 'DATE', 'CARTONS'}

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
            return redirect(url_for('login'))
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
        encoded_name = urllib.parse.quote(sheet_name)
        url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8')
            rows = list(csv.reader(content.splitlines()))
            CACHE[cache_key] = (rows, current_time)
            return rows
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
    if not rows: return None
    data = {
        'name': provider['name'], 'short': provider.get('short', provider['name']), 'color': provider['color'], 'group': provider.get('group', 'OTHER'),
        'total_orders': 0, 'total_boxes': 0, 'total_weight': 0.0, 'total_under20': 0, 'total_over20': 0,
        'regions': defaultdict(lambda: {'days': {day: {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0} for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']}}),
        'daily_totals': {day: {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0} for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']},
        'active_days': set()
    }
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for row_idx, row in enumerate(rows):
        if row_idx < provider['start_row'] - 1: continue
        try:
            if len(row) <= max(provider['date_col'], provider['box_col'], provider['weight_col'], provider['region_col']): continue
            date_val = row[provider['date_col']].strip() if provider['date_col'] < len(row) else ''
            parsed_date = parse_date(date_val)
            if not parsed_date or not (week_start <= parsed_date <= week_end): continue
            region = row[provider['region_col']].strip().upper() if provider['region_col'] < len(row) else ''
            if region in INVALID_REGIONS or not region: continue
            try: boxes = int(float(row[provider['box_col']])) if row[provider['box_col']].strip() else 0
            except: boxes = 0
            try: weight = float(row[provider['weight_col']].replace(',', '')) if row[provider['weight_col']].strip() else 0.0
            except: weight = 0.0
            
            day_name = day_names[parsed_date.weekday()]
            data['total_orders'] += 1; data['total_boxes'] += boxes; data['total_weight'] += weight; data['active_days'].add(day_name)
            if weight < 20: data['total_under20'] += 1
            else: data['total_over20'] += 1
            
            data['daily_totals'][day_name]['orders'] += 1; data['daily_totals'][day_name]['boxes'] += boxes; data['daily_totals'][day_name]['weight'] += weight
            if weight < 20: data['daily_totals'][day_name]['under20'] += 1
            else: data['daily_totals'][day_name]['over20'] += 1
            
            region_data = data['regions'][region]['days'][day_name]
            region_data['orders'] += 1; region_data['boxes'] += boxes; region_data['weight'] += weight
            if weight < 20: region_data['under20'] += 1
            else: region_data['over20'] += 1
        except Exception: continue
    
    data['stars'] = get_star_rating(data['total_boxes'])
    data['active_days'] = list(data['active_days'])
    data['regions'] = dict(data['regions'])
    for region in data['regions']: data['regions'][region] = dict(data['regions'][region])
    return data

def calculate_trend(current_boxes, previous_boxes):
    if previous_boxes == 0: return {'direction': 'up', 'percentage': 100} if current_boxes > 0 else {'direction': 'neutral', 'percentage': 0}
    change = ((current_boxes - previous_boxes) / previous_boxes) * 100
    if change >= 0: return {'direction': 'up', 'percentage': round(change, 1)}
    else: return {'direction': 'down', 'percentage': round(abs(change), 1)}

def get_provider_achievements(provider_data, is_winner=False, trend=None):
    achievements = []
    if provider_data['stars'] >= 5: achievements.append(ACHIEVEMENTS['star_5'])
    elif provider_data['stars'] >= 4: achievements.append(ACHIEVEMENTS['star_4'])
    if is_winner: achievements.append(ACHIEVEMENTS['champion'])
    if trend and trend['direction'] == 'up' and trend['percentage'] >= 50: achievements.append(ACHIEVEMENTS['rocket'])
    if len(provider_data.get('active_days', [])) >= 7: achievements.append(ACHIEVEMENTS['consistent'])
    if provider_data['total_weight'] >= 5000: achievements.append(ACHIEVEMENTS['heavyweight'])
    if len(provider_data.get('regions', {})) >= 5: achievements.append(ACHIEVEMENTS['region_king'])
    return achievements

FAVICON = '''<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%234f46e5'/%3E%3Ctext x='50' y='68' font-size='48' text-anchor='middle' fill='white' font-family='Arial' font-weight='bold'%3E3PL%3C/text%3E%3C/svg%3E">'''

# ============================================
# CSS INCLUDES DYNAMIC THEMING VARIABLES
# ============================================
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
    }

    [data-theme="dark"] {
        --bg-body: #050508;
        --bg-sidebar: #0a0a0f;
        --bg-card: #0c0d12;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: rgba(255,255,255,0.05);
        --brand-color: #6366f1;
        --brand-gradient: linear-gradient(145deg, #6366f1, #8b5cf6);
        --hover-bg: rgba(255,255,255,0.02);
        --table-hdr: #0f1015;
        --cell-empty: rgba(255,255,255,0.02);
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Inter', sans-serif; background: var(--bg-body); color: var(--text-main); min-height: 100vh; font-size: 13px; line-height: 1.4; transition: background 0.3s, color 0.3s; }
    
    /* GUEST MODE RESTRICTIONS */
    body.guest-mode .day-data a, body.guest-mode .orders-link, body.guest-mode .boxes-link, body.guest-mode .weight-link, body.guest-mode .under20-link, body.guest-mode .over20-link,
    body.guest-mode .export-btn, body.guest-mode .search-box { pointer-events: none !important; text-decoration: none !important; cursor: default !important; display: none !important;}

    /* Sidebar */
    .sidebar { position: fixed; left: 0; top: 0; height: 100vh; width: 240px; background: var(--bg-sidebar); padding: 20px 16px; transition: all 0.2s ease; z-index: 100; display: flex; flex-direction: column; border-right: 1px solid var(--border-color); box-shadow: 2px 0 10px rgba(0,0,0,0.02); }
    .sidebar.collapsed { width: 70px; }
    .sidebar-header { display: flex; align-items: center; gap: 12px; padding-bottom: 20px; border-bottom: 1px solid var(--border-color); margin-bottom: 20px; }
    .logo-icon { width: 40px; height: 40px; background: var(--brand-gradient); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: #ffffff; font-size: 20px; box-shadow: 0 4px 10px rgba(79,70,229,0.2); }
    .header-titles { display: flex; flex-direction: column; }
    .header-main { font-size: 16px; font-weight: 600; color: var(--text-main); line-height: 1.2; }
    .header-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
    .sidebar.collapsed .header-main, .sidebar.collapsed .header-sub { opacity: 0; width: 0; display: none; }
    
    .nav-section { margin-bottom: 16px; }
    .nav-section-title { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); padding: 6px 12px; margin-bottom: 4px; font-weight: 600; }
    .sidebar.collapsed .nav-section-title { opacity: 0; }
    .nav-menu { display: flex; flex-direction: column; gap: 4px; flex-grow: 1; }
    .nav-item { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-radius: 10px; color: var(--text-muted); text-decoration: none; transition: all 0.2s; font-size: 13px; font-weight: 500; }
    .nav-item:hover { background: var(--hover-bg); color: var(--text-main); }
    .nav-item.active { background: rgba(79, 70, 229, 0.1); color: var(--brand-color); border-left: 4px solid var(--brand-color); }
    .nav-item svg { width: 18px; height: 18px; flex-shrink: 0; color: currentColor; }
    .sidebar.collapsed .nav-item span { opacity: 0; width: 0; }
    .sidebar-toggle { position: absolute; right: -15px; top: 50%; transform: translateY(-50%); width: 32px; height: 32px; background: var(--brand-color); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; border: 3px solid var(--bg-body); color: #ffffff; font-size: 14px; transition: 0.2s; z-index: 101; }
    .sidebar.collapsed .sidebar-toggle { transform: translateY(-50%) rotate(180deg); }
    
    .sidebar-footer { border-top: 1px solid var(--border-color); padding-top: 16px; margin-top: auto; }
    .admin-info { display: flex; align-items: center; gap: 12px; padding: 10px 12px; background: var(--hover-bg); border-radius: 12px; margin-bottom: 10px; }
    .admin-avatar { width: 36px; height: 36px; background: var(--brand-color); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 16px; }
    .admin-name { font-weight: 600; color: var(--text-main); font-size: 14px; }
    .admin-role { font-size: 11px; color: var(--text-muted); }
    .logout-btn { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-radius: 10px; color: #ef4444; text-decoration: none; font-size: 13px; font-weight: 500; }
    .logout-btn:hover { background: rgba(239,68,68,0.1); }
    .sidebar.collapsed .logout-btn span, .sidebar.collapsed .admin-info { display: none; }

    /* Main Content */
    .main-content { margin-left: 240px; padding: 20px; transition: margin-left 0.2s; min-height: 100vh; background: var(--bg-body); }
    .main-content.expanded { margin-left: 70px; }
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
    .page-title { font-size: 26px; font-weight: 700; color: var(--text-main); }
    .page-title span { color: var(--brand-color); }

    /* Top Actions & Search */
    .top-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
    .search-box { position: relative; display: flex; align-items: center; }
    .search-input { background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-main); padding: 10px 14px 10px 36px; border-radius: 8px; font-size: 13px; outline: none; transition: 0.2s; width: 260px; }
    .search-input:focus { border-color: var(--brand-color); box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }
    .search-icon { position: absolute; left: 12px; color: var(--text-muted); font-size: 14px; }
    .shortcut-hint { position: absolute; right: 12px; font-size: 10px; background: var(--hover-bg); padding: 2px 6px; border-radius: 4px; color: var(--text-muted); border: 1px solid var(--border-color); }
    .action-group { display: flex; gap: 10px; }
    .action-btn { background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-main); padding: 8px 14px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; transition: 0.2s; }
    .action-btn:hover { border-color: var(--brand-color); color: var(--brand-color); }
    
    /* Search Results Modal */
    #search-results { position: absolute; top: 100%; left: 0; width: 100%; max-width: 400px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); margin-top: 8px; z-index: 1000; display: none; max-height: 400px; overflow-y: auto; }

    /* Date Picker */
    .date-range-picker { background: var(--bg-card); border-radius: 16px; border: 1px solid var(--border-color); padding: 14px 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.02); }
    .qbtns-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
    .qbtn { padding: 5px 14px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 30px; color: var(--text-muted); font-size: 11px; font-weight: 500; cursor: pointer; transition: 0.2s; }
    .qbtn:hover { background: var(--border-color); color: var(--text-main); }
    .qbtn.active { background: var(--brand-color); border-color: var(--brand-color); color: #fff; }
    .date-inputs-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .range-input { padding: 6px 12px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 30px; color: var(--text-main); font-size: 12px; }
    .apply-btn { padding: 6px 18px; background: var(--brand-color); border: none; border-radius: 30px; color: #fff; font-size: 12px; font-weight: 600; cursor: pointer; }
    .week-badge { font-size: 12px; color: var(--brand-color); font-weight: 500; padding: 5px 14px; background: rgba(79,70,229,0.1); border-radius: 30px; }

    /* Cards & Stats */
    .provider-card { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); margin-bottom: 20px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.02); transition: transform 0.2s, box-shadow 0.2s; }
    .provider-card:hover { transform: translateY(-2px); box-shadow: 0 12px 24px rgba(79,70,229,0.08); border-color: #cbd5e1; }
    .card-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--border-color); position: relative; background: var(--bg-card); }
    .provider-info { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
    .provider-name { font-size: 20px; font-weight: 600; color: var(--text-main); }
    .card-stats { display: flex; gap: 20px; }
    .stat-item { text-align: center; padding: 6px 16px; background: var(--hover-bg); border-radius: 14px; border: 1px solid var(--border-color); }
    .stat-value { font-size: 20px; font-weight: 700; color: var(--text-main); }
    .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }

    /* Tables */
    .data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .data-table th { background: var(--table-hdr); padding: 10px 6px; text-align: center; font-weight: 600; color: var(--text-muted); font-size: 11px; text-transform: uppercase; border-bottom: 2px solid var(--brand-color); }
    .data-table th.region-col { text-align: left; padding-left: 16px; }
    .data-table td { padding: 8px 6px; text-align: center; border-bottom: 1px solid var(--border-color); color: var(--text-main); }
    .data-table td.region-col { text-align: left; padding-left: 16px; font-weight: 500; background: var(--hover-bg); }
    .data-table tr.total-row td { background: rgba(79,70,229,0.1); font-weight: 600; color: var(--brand-color); border-top: 2px solid var(--brand-color); }

    /* Day Data Grid */
    .day-data { display: flex; justify-content: center; gap: 2px; font-size: 11px; border: 1px solid var(--border-color); border-radius: 6px; overflow: hidden; background: var(--bg-body); margin: 2px 0; }
    .day-data span, .day-data a { flex: 1; min-width: 32px; padding: 4px 1px; text-align: center; font-weight: 500; border-right: 1px solid var(--border-color); color: inherit; text-decoration: none; }
    .day-data span:nth-child(1), .day-data a:nth-child(1) { color: #3b82f6; background: rgba(59,130,246,0.1); }
    .day-data span:nth-child(2), .day-data a:nth-child(2) { color: #10b981; background: rgba(16,185,129,0.1); }
    .day-data span:nth-child(3), .day-data a:nth-child(3) { color: #f59e0b; background: rgba(245,158,11,0.1); }
    .day-data span:nth-child(4), .day-data a:nth-child(4) { color: #8b5cf6; background: rgba(139,92,246,0.1); }
    .day-data span:nth-child(5), .day-data a:nth-child(5) { color: #ec4899; background: rgba(236,72,153,0.1); }
    .day-data-empty { color: var(--text-muted); font-size: 12px; padding: 4px; background: var(--cell-empty); border-radius: 4px; }
    
    .orders-link:hover, .boxes-link:hover, .weight-link:hover { color: var(--brand-color); border-bottom: 1px dashed var(--brand-color); }
    .sub-header { display: flex; justify-content: center; gap: 4px; font-size: 9px; color: var(--text-muted); }
    
    .loading { display: flex; justify-content: center; align-items: center; height: 200px; color: var(--brand-color); }
    .spinner { width: 40px; height: 40px; border: 3px solid rgba(79, 70, 229, 0.1); border-top-color: var(--brand-color); border-radius: 50%; animation: spin 1s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Other Common UI Elements */
    .kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
    .kpi-card { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); padding: 20px; text-align: center; }
    .kpi-value { font-size: 28px; font-weight: 700; color: var(--text-main); margin-bottom: 4px; }
    .kpi-label { font-size: 13px; color: var(--text-muted); }

    .charts-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px; }
    .chart-card { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); padding: 18px; }
    .chart-card.full-width { grid-column: span 2; }
    .chart-title { font-size: 16px; font-weight: 600; color: var(--text-main); margin-bottom: 16px; }
    
    .stats-row, .stats-row-5 { display: grid; gap: 16px; margin-bottom: 20px; }
    .stats-row { grid-template-columns: repeat(4, 1fr); }
    .stats-row-5 { grid-template-columns: repeat(5, 1fr); }
    .stat-card { background: var(--bg-card); border-radius: 18px; border: 1px solid var(--border-color); padding: 16px; display: flex; align-items: center; gap: 14px; cursor: pointer; transition: 0.2s;}
    .stat-card:hover { transform: translateY(-2px); border-color: var(--brand-color); box-shadow: 0 4px 12px rgba(79,70,229,0.1); }
    .stat-icon { width: 48px; height: 48px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 24px; background: var(--hover-bg); }
    
    .leaderboard-table { width: 100%; border-collapse: collapse; }
    .leaderboard-table th { background: var(--table-hdr); padding: 12px; text-align: left; color: var(--text-muted); border-bottom: 2px solid var(--brand-color); }
    .leaderboard-table td { padding: 12px; border-bottom: 1px solid var(--border-color); color: var(--text-main); }
    
    .tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
    .tab-btn { padding: 6px 18px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 40px; color: var(--text-muted); cursor: pointer; transition: 0.2s; }
    .tab-btn.active { background: var(--brand-color); border-color: var(--brand-color); color: #ffffff; }

    /* New Features Pages */
    .forecast-card { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); padding: 20px; margin-bottom: 20px; }
    .forecast-title { font-size: 18px; font-weight: 700; color: var(--text-main); margin-bottom: 14px; }
    .forecast-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-top: 14px; }
    .forecast-day { background: var(--hover-bg); border-radius: 12px; padding: 14px; text-align: center; border: 1px solid var(--border-color); }
    .forecast-day .day-name { font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; }
    .forecast-day .prediction { font-size: 16px; font-weight: 700; color: var(--brand-color); }
    .forecast-detail { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

    .logs-container { background: var(--bg-card); border-radius: 20px; border: 1px solid var(--border-color); padding: 20px; }
    .log-entry { padding: 8px 12px; border-bottom: 1px solid var(--border-color); font-family: monospace; font-size: 12px; color: var(--text-main); }
    .log-entry:last-child { border-bottom: none; }

    /* Login */
    .login-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-body); padding: 20px; }
    .login-card { background: var(--bg-card); border-radius: 24px; border: 1px solid var(--border-color); padding: 40px; width: 100%; max-width: 400px; text-align: center; }
    .form-input { width: 100%; padding: 12px 14px; background: var(--hover-bg); border: 1px solid var(--border-color); border-radius: 12px; color: var(--text-main); font-size: 14px; }
    .login-btn { width: 100%; padding: 12px; background: var(--brand-color); border: none; border-radius: 12px; color: #ffffff; font-weight: 600; cursor: pointer; margin-top: 8px; }

    /* TV Mode & Print */
    body.tv-mode { overflow-x: hidden; }
    body.tv-mode .sidebar { display: none !important; }
    body.tv-mode .main-content { margin-left: 0 !important; padding: 40px !important; }
    body.tv-mode .top-actions { display: none !important; }

    @media print {
        body { background: white !important; color: black !important; }
        .sidebar, .top-actions, .date-range-picker, .tabs, .month-selector, .view-selector { display: none !important; }
        .main-content { margin-left: 0 !important; padding: 0 !important; }
        .provider-card { border: 1px solid #ccc !important; box-shadow: none !important; break-inside: avoid; }
    }

    @media (max-width: 1200px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .stats-row-5, .forecast-grid { grid-template-columns: repeat(3, 1fr); } .kpi-grid { grid-template-columns: repeat(2, 1fr); } .comparison-grid { grid-template-columns: 1fr; } .comparison-vs { display: none; } }
    @media (max-width: 768px) { .sidebar { width: 70px; } .main-content { margin-left: 70px; padding: 15px; } .sidebar-toggle { width: 28px; height: 28px; right: -12px; } .stats-row, .stats-row-5, .kpi-grid, .forecast-grid { grid-template-columns: 1fr; } }
</style>
"""

def ACTION_BAR_HTML(role):
    if role == 'admin':
        return """
        <div class="top-actions">
            <div class="search-box">
                <span class="search-icon">🔍</span>
                <input type="text" id="global-search" class="search-input" placeholder="Search Order ID..." onkeyup="if(event.key==='Enter' && this.value.length>2) searchOrder(this.value)">
                <span class="shortcut-hint">Ctrl+/</span>
                <div id="search-results"></div>
            </div>
            <div class="action-group">
                <button class="action-btn theme-btn-text" onclick="toggleTheme()">🌗 Dark Mode</button>
                <button class="action-btn" onclick="toggleTVMode()">📺 TV Mode</button>
            </div>
        </div>
        """
    else:
        return """
        <div class="top-actions">
            <div class="action-group" style="margin-left: auto;">
                <button class="action-btn theme-btn-text" onclick="toggleTheme()">🌗 Dark Mode</button>
                <button class="action-btn" onclick="toggleTVMode()">📺 TV Mode</button>
            </div>
        </div>
        """

SIDEBAR_HTML = """
<nav class="sidebar" id="sidebar">
    <div class="sidebar-toggle" onclick="toggleSidebar()">«</div>
    <div class="sidebar-header">
        <div class="logo-icon">3P</div>
        <div class="header-titles">
            <div class="header-main">3PL Dashboard</div>
            <div class="header-sub">
                <span class="admin-name">{user_name}</span> <span class="admin-role">{user_role}</span>
            </div>
        </div>
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
            <a href="/calendar" class="nav-item {active_calendar}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <span>Calendar View</span>
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
        {forecast_link}
    </div>
    <div class="sidebar-footer">
        <a href="/logout" class="logout-btn">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            <span>Logout</span>
        </a>
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
</script>
"""

def sidebar(active, role='guest'):
    keys = ['dashboard','weekly','daily_region','flight','analytics','kpi','comparison','regions','monthly','calendar','whatsapp','achievements', 'forecast', 'logs']
    kwargs = {f'active_{k}': ('active' if k == active else '') for k in keys}
    
    if role == 'admin':
        kwargs['user_initial'] = 'A'
        kwargs['user_name'] = 'Admin'
        kwargs['user_role'] = 'Full Access'
        kwargs['forecast_link'] = f"""
        <div class="nav-section">
            <div class="nav-section-title">TOOLS</div>
            <a href="/forecast" class="nav-item {kwargs['active_forecast']}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
                <span>Load Forecast</span>
            </a>
            <a href="/logs" class="nav-item {kwargs['active_logs']}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>Activity Logs</span>
            </a>
        </div>
        """
    else:
        kwargs['user_initial'] = 'G'
        kwargs['user_name'] = 'Guest'
        kwargs['user_role'] = 'View Only'
        kwargs['forecast_link'] = ''
        
    return SIDEBAR_HTML.format(**kwargs)

# ============================================
# JAVASCRIPT (THEME, CSV EXPORT, SEARCH)
# ============================================
SHARED_JS = """
<script>
document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === '/') { e.preventDefault(); const s = document.getElementById('global-search'); if(s) s.focus(); }
    if (e.altKey && e.key === 'd') { window.location.href = '/'; }
    if (e.altKey && e.key === 't') { toggleTheme(); }
});

function toggleTheme() {
    const isDark = document.body.getAttribute('data-theme') === 'dark';
    document.body.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
    document.querySelectorAll('.theme-btn-text').forEach(e => e.innerHTML = isDark ? '🌗 Dark Mode' : '☀️ Light Mode');
}

document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('theme') === 'dark') {
        document.body.setAttribute('data-theme', 'dark');
        document.querySelectorAll('.theme-btn-text').forEach(e => e.innerHTML = '☀️ Light Mode');
    }
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        const sidebar = document.getElementById('sidebar');
        const main = document.getElementById('main-content');
        if (sidebar) sidebar.classList.add('collapsed');
        if (main) main.classList.add('expanded');
    }
});

function toggleTVMode() {
    document.body.classList.toggle('tv-mode');
    if (document.body.classList.contains('tv-mode') && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen();
    } else if (document.exitFullscreen) {
        document.exitFullscreen();
    }
}

function exportTableToCSV(filename) {
    let csv = [];
    let rows = document.querySelectorAll("table tr");
    for (let i = 0; i < rows.length; i++) {
        let row = [], cols = rows[i].querySelectorAll("td, th");
        for (let j = 0; j < cols.length; j++) {
            let data = cols[j].innerText.replace(/(\\r\\n|\\n|\\r)/gm, "").replace(/"/g, '""');
            row.push('"' + data + '"');
        }
        csv.push(row.join(","));
    }
    if(csv.length <= 1) { alert("No table data to export."); return; }
    let csvFile = new Blob([csv.join("\\n")], {type: "text/csv"});
    let dl = document.createElement("a");
    dl.download = filename; dl.href = window.URL.createObjectURL(csvFile);
    dl.style.display = "none"; document.body.appendChild(dl); dl.click();
}

async function searchOrder(q) {
    const resBox = document.getElementById('search-results');
    if(!q) { resBox.style.display = 'none'; return; }
    resBox.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted)">Searching...</div>';
    resBox.style.display = 'block';
    try {
        const r = await fetch('/api/search?q=' + encodeURIComponent(q));
        const data = await r.json();
        if(data.length === 0) {
            resBox.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted)">No orders found</div>';
            return;
        }
        let html = '';
        data.forEach(item => {
            html += `<div style="padding:12px 16px; border-bottom:1px solid var(--border-color); cursor:pointer;" onmouseover="this.style.background='var(--hover-bg)'" onmouseout="this.style.background='transparent'">
                <div style="font-weight:600; color:var(--text-main); display:flex; justify-content:space-between;"><span>#${item.order_id}</span> <span style="color:${item.color}">${item.provider}</span></div>
                <div style="font-size:11px; color:var(--text-muted); display:flex; gap:10px; margin-top:4px;"><span>📅 ${item.date}</span><span>📍 ${item.region}</span><span>⚖️ ${item.weight}kg</span></div>
            </div>`;
        });
        resBox.innerHTML = html;
    } catch(e) {
        resBox.innerHTML = '<div style="padding:15px;text-align:center;color:red">Error searching</div>';
    }
}
document.addEventListener('click', e => {
    if(!e.target.closest('.search-box')) {
        const b = document.getElementById('search-results');
        if(b) b.style.display = 'none';
    }
});

function getISOWeek(date) { const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())); const dayNum = d.getUTCDay() || 7; d.setUTCDate(d.getUTCDate() + 4 - dayNum); const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1)); return Math.ceil((((d - yearStart) / 86400000) + 1) / 7); }
function formatWeight(w) { if (w === undefined || w === null || w === 0) return '-'; const r = Math.round(w * 10) / 10; return r % 1 === 0 ? Math.round(r).toString() : r.toFixed(1); }
function fmtLocal(date) { const y = date.getFullYear(); const m = String(date.getMonth() + 1).padStart(2, '0'); const d = String(date.getDate()).padStart(2, '0'); return `${y}-${m}-${d}`; }
function fmtDisp(date, includeYear) { if (includeYear === false) return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
function getMonday(date) { const d = new Date(date); const day = d.getDay(); const diff = d.getDate() - day + (day === 0 ? -6 : 1); return new Date(d.setDate(diff)); }

let dpStart = null; let dpEnd = null;
function dpInit(defaultPeriod) {
    defaultPeriod = defaultPeriod || 'week';
    const today = new Date(); today.setHours(0,0,0,0);
    if (defaultPeriod === 'today') { dpStart = new Date(today); dpEnd = new Date(today); } 
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
    dpUpdateBadge(); if(typeof loadData === 'function') loadData();
}
function dpApply() {
    const sv = document.getElementById('dpStart').value; const ev = document.getElementById('dpEnd').value;
    if (!sv || !ev) { alert('Please select both dates'); return; }
    dpStart = new Date(sv + 'T00:00:00'); dpEnd = new Date(ev + 'T00:00:00');
    if (dpStart > dpEnd) { alert('Start date must be before end date'); return; }
    document.querySelectorAll('.qbtn').forEach(b => b.classList.remove('active'));
    dpUpdateBadge(); if(typeof loadData === 'function') loadData();
}
function dpUpdateBadge() {
    const badge = document.getElementById('dpBadge');
    if (!badge || !dpStart || !dpEnd) return;
    const wk = getISOWeek(dpStart); const days = Math.round((dpEnd - dpStart) / 86400000) + 1;
    let txt = 'Week ' + wk + ' • ';
    if (days === 1) { txt += fmtDisp(dpStart, true); } 
    else if (days <= 31 && dpStart.getFullYear() === dpEnd.getFullYear()) { txt += fmtDisp(dpStart, false) + ' – ' + fmtDisp(dpEnd, true); if (days !== 7) txt += ' (' + days + 'd)'; } 
    else { txt += fmtDisp(dpStart, true) + ' – ' + fmtDisp(dpEnd, true); }
    badge.textContent = txt;
}
function dpParams() { return 'start_date=' + fmtLocal(dpStart) + '&end_date=' + fmtLocal(dpEnd); }
function getStarRating(stars) { return '★'.repeat(stars) + '☆'.repeat(5 - stars); }

function navigateToOrders(provider, start, end, region, day) {
    let url = `/orders?provider=${encodeURIComponent(provider)}&start=${start}&end=${end}`;
    if (region) url += `&region=${encodeURIComponent(region)}`;
    if (day) url += `&day=${day}`;
    window.location.href = url;
}
</script>
"""

# ===== ROUTES =====

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'guest':
            session['logged_in'] = True
            session['role'] = 'guest'
            return redirect(url_for('dashboard'))
        else:
            if request.form.get('password') == ADMIN_PASSWORD:
                session['logged_in'] = True
                session['role'] = 'admin'
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid admin password. Please try again.'
                
    return render_template_string('''
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login - 3PL Dashboard</title>{{ favicon|safe }}''' + BASE_STYLES + '''</head><body>
<div class="login-container">
    <div class="login-card">
        <div class="login-logo">3P</div>
        <h1 class="login-title">Welcome Back</h1>
        <p class="login-subtitle">Access your 3PL Dashboard</p>
        {% if error %}<div class="error-message">{{ error }}</div>{% endif %}
        <form class="login-form" method="POST">
            <div class="form-group">
                <label class="form-label">Admin Password</label>
                <input type="password" name="password" class="form-input" placeholder="Enter password" autofocus>
            </div>
            <button type="submit" name="action" value="admin" class="login-btn">Sign In as Admin</button>
            <div style="margin: 15px 0; color: var(--text-muted); font-size: 12px; font-weight: 600;">OR</div>
            <button type="submit" name="action" value="guest" class="login-btn guest-btn" style="background: var(--hover-bg); color: var(--text-main); border: 1px solid var(--border-color); box-shadow: none;">Continue as Guest (View Only)</button>
        </form>
    </div>
</div></body></html>''', error=error, favicon=FAVICON)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
async function loadData() {
    document.getElementById('dashboard-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const response = await fetch('/api/dashboard?' + dpParams());
        const data = await response.json();
        let html = '';
        for (const provider of data.providers) { html += renderProvider(provider); }
        document.getElementById('dashboard-content').innerHTML = html || '<div class="empty-state"><div class="empty-state-icon">📭</div><h3>No data for selected period</h3></div>';
    } catch(e) { document.getElementById('dashboard-content').innerHTML = '<p style="color:#ef4444;padding:20px">Error loading data</p>'; }
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
    const totals = {}; days.forEach(d => totals[d] = {o:0,b:0,w:0,u:0,v:0});
    let rowsHtml = '';
    Object.keys(provider.regions).sort().forEach(region => {
        const rd = provider.regions[region].days;
        rowsHtml += `<tr><td class="region-col">${region}</td>`;
        days.forEach((day, i) => {
            const d = rd[day];
            totals[day].o += d.orders; totals[day].b += d.boxes; totals[day].w += d.weight;
            totals[day].u += d.under20; totals[day].v += d.over20;
            const fc = flightDays.includes(i) ? ' style="background:var(--hover-bg)"' : '';
            if (d.orders > 0) {
                const dayDate = new Date(dpStart); dayDate.setDate(dayDate.getDate() + i);
                const dateStr = fmtLocal(dayDate);
                if (canClick) {
                    rowsHtml += `<td class="day-cell"${fc}><div class="day-data">
                        <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '${region}', '${dateStr}')" class="orders-link">${d.orders}</a>
                        <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '${region}', '${dateStr}')" class="boxes-link">${d.boxes}</a>
                        <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '${region}', '${dateStr}')" class="weight-link">${formatWeight(d.weight)}</a>
                        <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '${region}', '${dateStr}')" class="under20-link">${d.under20}</a>
                        <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '${region}', '${dateStr}')" class="over20-link">${d.over20}</a>
                    </div></td>`;
                } else {
                    rowsHtml += `<td class="day-cell"${fc}><div class="day-data"><span>${d.orders}</span><span>${d.boxes}</span><span>${formatWeight(d.weight)}</span><span>${d.under20}</span><span>${d.over20}</span></div></td>`;
                }
            } else { rowsHtml += `<td class="day-cell"${fc}><span class="day-data-empty">-</span></td>`; }
        });
        rowsHtml += '</tr>';
    });
    
    rowsHtml += '<tr class="total-row"><td class="region-col">TOTAL</td>';
    days.forEach((day, i) => {
        const t = totals[day];
        const fc = flightDays.includes(i) ? ' style="background:var(--hover-bg)"' : '';
        if (canClick && t.o > 0) {
            const dayDate = new Date(dpStart); dayDate.setDate(dayDate.getDate() + i);
            const dateStr = fmtLocal(dayDate);
            rowsHtml += `<td class="day-cell"${fc}><div class="day-data">
                <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '', '${dateStr}')" class="orders-link">${t.o}</a>
                <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '', '${dateStr}')" class="boxes-link">${t.b}</a>
                <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '', '${dateStr}')" class="weight-link">${formatWeight(t.w)}</a>
                <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '', '${dateStr}')" class="under20-link">${t.u}</a>
                <a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', '${dateStr}', '${dateStr}', '', '${dateStr}')" class="over20-link">${t.v}</a>
            </div></td>`;
        } else {
            rowsHtml += `<td class="day-cell"${fc}><div class="day-data"><span>${t.o}</span><span>${t.b}</span><span>${formatWeight(t.w)}</span></div></td>`;
        }
    });
    rowsHtml += '</tr>';
    
    const subHdr = days.map(() => `<th><div class="sub-header"><span>O</span><span>B</span><span>W</span><span>&lt;20</span><span>20+</span></div></th>`).join('');
    const dayHdrs = days.map((d,i) => `<th>${d}${flightDays.includes(i)?' ✈️':''}</th>`).join('');
    
    return `<div class="provider-card">
        <div class="card-header" style="border-left: 4px solid ${provider.color};">
        <div class="provider-info"><span class="provider-name">${provider.name}</span><span class="star-rating">${getStarRating(provider.stars)}</span><span class="trend-badge ${trendClass}">${trendIcon} ${provider.trend.percentage}%</span>${achHtml}</div>
        <div class="card-stats">
            <div class="stat-item"><div class="stat-value">${provider.total_orders.toLocaleString()}</div><div class="stat-label">Orders</div></div>
            <div class="stat-item"><div class="stat-value">${provider.total_boxes.toLocaleString()}</div><div class="stat-label">Boxes</div></div>
            <div class="stat-item"><div class="stat-value">${formatWeight(provider.total_weight)} kg</div><div class="stat-label">Weight</div></div>
        </div></div>
        <div style="overflow-x:auto"><table class="data-table"><thead><tr><th class="region-col" rowspan="2">Region</th>${dayHdrs}</tr><tr class="sub-header-row">${subHdr}</tr></thead><tbody>${rowsHtml}</tbody></table></div></div>`;
}

dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
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
<div class="provider-name" style="font-size:24px">Top Performer: ${data.winner.name}</div>
<div style="color:var(--brand-color);margin-top:4px">${data.winner.total_boxes.toLocaleString()} boxes • ${formatWeight(data.winner.total_weight)} kg</div>
${achHtml}</div></div></div></div>`;
        }
        html += `<div class="provider-card"><div class="card-header"><div class="provider-info"><span class="provider-name">Provider Leaderboard</span></div></div>
<table class="leaderboard-table"><thead><tr><th style="width:60px">Rank</th><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th><th style="text-align:right">Trend</th></tr></thead><tbody>`;
        data.providers.forEach((p,i) => {
            const rc = i < 3 ? 'rank-'+(i+1) : 'rank-other';
            const tc = p.trend.direction === 'up' ? 'up' : 'down';
            const ti = p.trend.direction === 'up' ? '▲' : '▼';
            if (canClick) {
                html += `<tr><td><div class="rank-badge ${rc}">${i+1}</div></td>
                    <td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td>
                    <td style="text-align:right;font-weight:600"><a href="javascript:void(0)" onclick="navigateToOrders('${p.short}', fmtLocal(dpStart), fmtLocal(dpEnd))" class="orders-link">${p.total_orders.toLocaleString()}</a></td>
                    <td style="text-align:right;font-weight:600"><a href="javascript:void(0)" onclick="navigateToOrders('${p.short}', fmtLocal(dpStart), fmtLocal(dpEnd))" class="boxes-link">${p.total_boxes.toLocaleString()}</a></td>
                    <td style="text-align:right;font-weight:600"><a href="javascript:void(0)" onclick="navigateToOrders('${p.short}', fmtLocal(dpStart), fmtLocal(dpEnd))" class="weight-link">${formatWeight(p.total_weight)}</a></td>
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
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:red">Error</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

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
<div class="stats-row-5">
<div class="stat-card" onclick="if('{{ role }}'==='admin') navigateToOrders('all', fmtLocal(dpStart), fmtLocal(dpEnd))" style="cursor:{{ 'pointer' if role == 'admin' else 'default' }}"><div class="stat-icon" style="background:rgba(59,130,246,0.1)">📦</div><div class="stat-content"><div class="stat-value" id="t-orders">-</div><div class="stat-label">Total Orders</div></div></div>
<div class="stat-card" onclick="if('{{ role }}'==='admin') navigateToOrders('all', fmtLocal(dpStart), fmtLocal(dpEnd))" style="cursor:{{ 'pointer' if role == 'admin' else 'default' }}"><div class="stat-icon" style="background:rgba(16,185,129,0.1)">📮</div><div class="stat-content"><div class="stat-value" id="t-boxes">-</div><div class="stat-label">Total Boxes</div></div></div>
<div class="stat-card" onclick="if('{{ role }}'==='admin') navigateToOrders('all', fmtLocal(dpStart), fmtLocal(dpEnd))" style="cursor:{{ 'pointer' if role == 'admin' else 'default' }}"><div class="stat-icon" style="background:rgba(245,158,11,0.1)">⚖️</div><div class="stat-content"><div class="stat-value" id="t-weight">-</div><div class="stat-label">Total Weight</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(34,197,94,0.1)">🪶</div><div class="stat-content"><div class="stat-value" id="t-under20">-</div><div class="stat-label">&lt;20 kg</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(239,68,68,0.1)">🏋️</div><div class="stat-content"><div class="stat-value" id="t-over20">-</div><div class="stat-label">20+ kg</div></div></div>
</div>
<div id="content"><div class="empty-state"><div class="empty-state-icon">📅</div><h3>Select a date range above</h3></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
function toggleProvider(id) {
    const header = document.getElementById('hdr-'+id);
    const body = document.getElementById('bdy-'+id);
    if(body.style.display === 'none') { body.style.display = 'block'; } else { body.style.display = 'none'; }
}
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/daily-region-summary?' + dpParams());
        const data = await r.json();
        document.getElementById('t-orders').textContent = data.totals.orders.toLocaleString();
        document.getElementById('t-boxes').textContent = data.totals.boxes.toLocaleString();
        document.getElementById('t-weight').textContent = formatWeight(data.totals.weight) + ' kg';
        document.getElementById('t-under20').textContent = data.totals.under20.toLocaleString();
        document.getElementById('t-over20').textContent = data.totals.over20.toLocaleString();
        if (data.totals.orders === 0) {
            document.getElementById('content').innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><h3>No Data Found</h3></div>';
            return;
        }
        
        const role = '{{ role }}';
        const canClick = role === 'admin';
        const medals = ['🥇','🥈','🥉'];
        let html = '';
        data.providers.forEach((provider, idx) => {
            html += `<div class="provider-card">
<div class="card-header" style="border-left: 4px solid ${provider.color}; cursor:pointer;" onclick="toggleProvider(${idx})" id="hdr-${idx}">
<div class="provider-info"><span class="provider-name">${provider.name}</span></div>
<div class="card-stats"><div class="stat-item"><div class="stat-value">${provider.orders}</div><div class="stat-label">Orders</div></div><div class="stat-item"><div class="stat-value">${provider.boxes}</div><div class="stat-label">Boxes</div></div></div></div>
<div id="bdy-${idx}" style="display:${idx===0?'block':'none'}">
<div style="overflow-x:auto; padding: 0 18px 18px;">
<table class="data-table"><thead><tr><th class="region-col">Region</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight</th><th><span style="color:#10b981">&lt;20 kg</span></th><th><span style="color:#ef4444">20+ kg</span></th></tr></thead><tbody>`;
            provider.regions.forEach((rg,i) => {
                const medal = i < 3 ? `<span class="medal" style="margin-right:8px">${medals[i]}</span>` : '';
                if (canClick) {
                    html += `<tr><td class="region-col">${medal}${rg.name}</td>
                        <td style="text-align:right"><a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', fmtLocal(dpStart), fmtLocal(dpEnd), '${rg.name}')" class="orders-link" style="font-weight:600; color:var(--brand-color)">${rg.orders}</a></td>
                        <td style="text-align:right"><a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', fmtLocal(dpStart), fmtLocal(dpEnd), '${rg.name}')" class="boxes-link" style="font-weight:600; color:var(--brand-color)">${rg.boxes}</a></td>
                        <td style="text-align:right"><a href="javascript:void(0)" onclick="navigateToOrders('${provider.short}', fmtLocal(dpStart), fmtLocal(dpEnd), '${rg.name}')" class="weight-link" style="font-weight:600; color:var(--brand-color)">${formatWeight(rg.weight)}</a></td>
                        <td style="color:#10b981; font-weight:600; background:rgba(16,185,129,0.05)">${rg.under20}</td>
                        <td style="color:#ef4444; font-weight:600; background:rgba(239,68,68,0.05)">${rg.over20}</td></tr>`;
                } else {
                    html += `<tr><td class="region-col">${medal}${rg.name}</td>
                        <td style="font-weight:600; color:var(--text-main); text-align:right">${rg.orders}</td>
                        <td style="font-weight:600; color:var(--text-main); text-align:right">${rg.boxes}</td>
                        <td style="font-weight:600; color:var(--text-main); text-align:right">${formatWeight(rg.weight)}</td>
                        <td style="color:#10b981; font-weight:600; background:rgba(16,185,129,0.05)">${rg.under20}</td>
                        <td style="color:#ef4444; font-weight:600; background:rgba(239,68,68,0.05)">${rg.over20}</td></tr>`;
                }
            });
            html += '</tbody></table></div></div></div>';
        });
        document.getElementById('content').innerHTML = html;
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:red">Error loading data</p>'; }
}
dpInit('today'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
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
</div></div>
<div style="overflow-x:auto"><table class="data-table"><thead><tr><th class="region-col">Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th></tr></thead><tbody>`;
            for (const p of flight.providers) {
                if (canClick) {
                    html += `<tr><td class="region-col"><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td>
                        <td style="text-align:right"><a href="javascript:void(0)" onclick="navigateToOrders('${p.name}', fmtLocal(dpStart), fmtLocal(dpEnd))" class="orders-link">${p.orders.toLocaleString()}</a></td>
                        <td style="text-align:right"><a href="javascript:void(0)" onclick="navigateToOrders('${p.name}', fmtLocal(dpStart), fmtLocal(dpEnd))" class="boxes-link">${p.boxes.toLocaleString()}</a></td>
                        <td style="text-align:right"><a href="javascript:void(0)" onclick="navigateToOrders('${p.name}', fmtLocal(dpStart), fmtLocal(dpEnd))" class="weight-link">${formatWeight(p.weight)}</a></td></tr>`;
                } else {
                    html += `<tr><td class="region-col"><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td>
                        <td style="text-align:right">${p.orders.toLocaleString()}</td>
                        <td style="text-align:right">${p.boxes.toLocaleString()}</td>
                        <td style="text-align:right">${formatWeight(p.weight)}</td></tr>`;
                }
            }
            html += '</tbody></table></div></div>';
        }
        document.getElementById('content').innerHTML = html;
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:red">Error loading data</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''', role=role, favicon=FAVICON)

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
<div class="
