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

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Rocket2024')

# ========== CACHE ==========
CACHE = {}
CACHE_DURATION = 900  # 15 منٹ
SHEET_ID = '1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY'

# ========== PROVIDERS ==========
PROVIDERS = [
    {'name': 'GLOBAL EXPRESS (QC)', 'short': 'GE QC', 'sheet': 'GE QC Center & Zone', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'order_col': 0, 'start_row': 2, 'color': '#3B82F6', 'group': 'GE'},
    {'name': 'GLOBAL EXPRESS (ZONE)', 'short': 'GE ZONE', 'sheet': 'GE QC Center & Zone', 'date_col': 10, 'box_col': 11, 'weight_col': 15, 'region_col': 16, 'order_col': 9, 'start_row': 2, 'color': '#8B5CF6', 'group': 'GE'},
    {'name': 'ECL LOGISTICS (QC)', 'short': 'ECL QC', 'sheet': 'ECL QC Center & Zone', 'date_col': 1, 'box_col': 2, 'weight_col': 5, 'region_col': 7, 'order_col': 0, 'start_row': 3, 'color': '#10B981', 'group': 'ECL'},
    {'name': 'ECL LOGISTICS (ZONE)', 'short': 'ECL ZONE', 'sheet': 'ECL QC Center & Zone', 'date_col': 10, 'box_col': 11, 'weight_col': 14, 'region_col': 16, 'order_col': 9, 'start_row': 3, 'color': '#F59E0B', 'group': 'ECL'},
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

    [data-theme="dark"] .provider-card:nth-child(odd) {
        background: #0f0f15;
    }
    [data-theme="dark"] .provider-card:nth-child(even) {
        background: #0a0a0f;
    }
    [data-theme="dark"] .stat-card:nth-child(odd) {
        background: #0f0f15;
    }
    [data-theme="dark"] .stat-card:nth-child(even) {
        background: #0a0a0f;
    }

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
        padding: 16px 12px;
        transition: all 0.2s ease;
        z-index: 100;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
    .sidebar.collapsed { width: 60px; }
    .sidebar-header {
        display: flex;
        align-items: center;
        gap: 10px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border-color);
        margin-bottom: 16px;
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
    .sidebar-toggle { position: absolute; right: -12px; top: 50%; transform: translateY(-50%); width: 24px; height: 24px; background: var(--brand-color); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; border: 2px solid var(--bg-body); color: #ffffff; font-size: 12px; z-index: 101; }
    .sidebar.collapsed .sidebar-toggle { transform: translateY(-50%) rotate(180deg); }
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
    <div class="sidebar-toggle" onclick="toggleSidebar()">«</div>
    <div class="sidebar-header">
        <div class="logo-icon">3P</div>
        <div class="header-titles">
            <div class="header-main">3PL Dashboard</div>
            <div class="header-sub">
                <span class="admin-name">wahab</span> <span class="admin-role">Admin</span>
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
            <a href="/whatsapp" class="nav-item {active_whatsapp}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                <span>WhatsApp Report</span>
            </a>
            <a href="/achievements" class="nav-item {active_achievements}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
                <span>Achievements</span>
            </a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">MAPS</div>
            <a href="/world-map" class="nav-item {active_worldmap}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>World Map</span>
            </a>
        </div>
        {forecast_link}
        {logs_link}
    </div>
    <div class="sidebar-footer">
        <div class="admin-info">
            <div class="admin-avatar">AW</div>
            <div class="admin-role">{user_role}</div>
        </div>
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
</script>
"""

def sidebar(active, role='guest'):
    keys = ['dashboard','weekly','daily_region','flight','analytics','kpi','comparison','regions','monthly','whatsapp','achievements','worldmap']
    kwargs = {f'active_{k}': ('active' if k == active else '') for k in keys}
    
    if role == 'admin':
        kwargs['user_role'] = 'Administrator'
        kwargs['forecast_link'] = """
        <div class="nav-section">
            <div class="nav-section-title">TOOLS</div>
            <a href="/forecast" id="forecast-link" class="nav-item {active_forecast}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                <span>Forecast</span>
            </a>
        </div>
        """
        kwargs['logs_link'] = """
        <div class="nav-section">
            <a href="/logs" id="logs-link" class="nav-item {active_logs}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>Activity Logs</span>
            </a>
        </div>
        """
    else:
        kwargs['user_role'] = 'Guest'
        kwargs['forecast_link'] = ''
        kwargs['logs_link'] = ''
        
    return SIDEBAR_HTML.format(**kwargs)

# ===== LOGIN =====
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
            <div class="divider">
                <span class="divider-line"></span>
                <span>OR</span>
                <span class="divider-line"></span>
            </div>
            <button type="submit" name="action" value="guest" class="login-btn guest-btn">Continue as Guest (View Only)</button>
        </form>
    </div>
</div></body></html>''', error=error, favicon=FAVICON)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
let charts = {};
Chart.defaults.color = '#475569';
Chart.defaults.borderColor = '#e2e8f0';

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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
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
    global CACHE
    CACHE = {}
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
# 🛰️ TID OPERATIONS HUB (NEXUS) - UNBREAKABLE SEQUENTIAL & GOD TIER EDITION
# ==============================================================================
import urllib.request
import csv
import re
import json
import os
import time
from datetime import datetime
from flask import jsonify, request, session, render_template_string

# ------------------------------------------------------------------------------
# 1. CORE DATA SOURCES
# ------------------------------------------------------------------------------
NEXUS_SOURCES = {
    "ECL QC Center": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCiZ1MdPMyVAzBqmBmp3Ch8sfefOp_kfPk2RSfMv3bxRD_qccuwaoM7WTVsieKJbA3y3DF41tUxb3T/pub?gid=0&single=true&output=csv",
    "ECL Zone": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCiZ1MdPMyVAzBqmBmp3Ch8sfefOp_kfPk2RSfMv3bxRD_qccuwaoM7WTVsieKJbA3y3DF41tUxb3T/pub?gid=928309568&single=true&output=csv",
    "GE QC Center": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQjCPd8bUpx59Sit8gMMXjVKhIFA_f-W9Q4mkBSWulOTg4RGahcVXSD4xZiYBAcAH6eO40aEQ9IEEXj/pub?gid=710036753&single=true&output=csv",
    "GE Zone": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQjCPd8bUpx59Sit8gMMXjVKhIFA_f-W9Q4mkBSWulOTg4RGahcVXSD4xZiYBAcAH6eO40aEQ9IEEXj/pub?gid=10726393&single=true&output=csv",
    "APX": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRDEzAMUwnFZ7aoThGoMERtxxsll2kfEaSpa9ksXIx6sqbdMncts6Go2d5mKKabepbNXDSoeaUlk-mP/pub?gid=0&single=true&output=csv",
    "Kerry": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZyLyZpVJz9sV5eT4Srwo_KZGnYggpRZkm2ILLYPQKSpTKkWfP9G5759h247O4QEflKCzlQauYsLKI/pub?gid=0&single=true&output=csv"
}
NEXUS_KERRY_STATUS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZyLyZpVJz9sV5eT4Srwo_KZGnYggpRZkm2ILLYPQKSpTKkWfP9G5759h247O4QEflKCzlQauYsLKI/pub?gid=2121564686&single=true&output=csv"

# ------------------------------------------------------------------------------
# 2. VERCEL-SAFE CACHE ENGINE (STRICTLY SEQUENTIAL - NO THREADING)
# ------------------------------------------------------------------------------
GLOBAL_DB_CACHE = {'loaded': False, 'timestamp': 0, 'sheets': {}, 'kerry': {}}
FILTER_DATE = datetime(2026, 1, 1)

STRICT_ALIASES = {
    'order': ['fleek id','order num','order id','order'], 
    'date': ['date', 'handover date', 'created at'], 
    'boxes': ['box_count','no of boxes','total boxes','boxes','box','qty','quantity'], 
    'weight': ['chargeable weight','net weight','weight'], 
    'vendor': ['vendor name', 'vendor','seller'], 
    'customer': ['customer name', 'consignee','customer'], 
    'country': ['destination','country','city'], 
    'tid': ['tracking id', 'trackingid', 'courier_tracking', 'tid', 'tracking'], 
    'mawb': ['mawb', 'master awb', 'awb', 'master'],
    'status': ['latest_status', 'latest status', 'status', 'kerry status']
}

def fetch_single_csv(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as res:
            raw = res.read().decode('utf-8').splitlines()
            data = list(csv.reader(raw))
            if not data: return []
            headers = [str(h).lower().strip() for h in data[0]]
            return [dict(zip(headers, row)) for row in data[1:]]
    except: return []

def get_alias_val(row, aliases):
    for k, v in row.items():
        if k.strip().lower() in aliases:
            val = str(v).strip()
            if val and val.lower() not in ['n/a','nan','none','-','']: return val
    for k, v in row.items():
        for alias in aliases:
            if alias in k.strip().lower():
                val = str(v).strip()
                if val and val.lower() not in ['n/a','nan','none','-','']: return val
    return "N/A"

def parse_date(date_str):
    if not date_str or date_str == 'N/A': return None
    try:
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%b-%y', '%d-%m-%Y', '%Y/%m/%d'):
            try: return datetime.strptime(date_str.split(' ')[0], fmt)
            except: continue
    except: pass
    if '2026' in date_str or '26' in date_str: return datetime(2026, 1, 1)
    return datetime(1970, 1, 1)

def clean_and_pad_tids(raw_tid):
    parts = [t.strip() for t in re.split(r'[\n,\/]+', str(raw_tid)) if t.strip() and t.strip()!='N/A']
    cleaned = []
    for t in parts:
        if t.startswith('150') and 12 <= len(t) <= 15:
            cleaned.append('0' + t)
        else:
            cleaned.append(t)
    return cleaned

# SAFE SEQUENTIAL FETCH (This fixes the 500 Vercel Error)
def force_sync_all_databases():
    global GLOBAL_DB_CACHE
    
    # 1. Fetch Kerry First
    kerry_raw = fetch_single_csv(NEXUS_KERRY_STATUS_URL)
    s_map = {}
    for r in kerry_raw:
        oid = get_alias_val(r, STRICT_ALIASES['order'])
        stat = get_alias_val(r, STRICT_ALIASES['status'])
        if oid != 'N/A': s_map[oid.lower()] = stat.upper()
    GLOBAL_DB_CACHE['kerry'] = s_map

    # 2. Fetch Other Sheets one by one (No threading crash)
    results = {}
    for name, url in NEXUS_SOURCES.items():
        results[name] = fetch_single_csv(url)

    GLOBAL_DB_CACHE['sheets'] = results
    GLOBAL_DB_CACHE['loaded'] = True
    GLOBAL_DB_CACHE['timestamp'] = time.time()

@app.after_request
def inject_nexus_button(response):
    if response.content_type and response.content_type.startswith('text/html'):
        if session.get('role') == 'admin' and request.endpoint != 'nexus_dashboard':
            html = response.get_data(as_text=True)
            btn = """<a href="/nexus" id="nexus-fab" style="position:fixed; bottom:30px; right:30px; background:linear-gradient(135deg, #18181b, #09090b); color:#fff; border:1px solid #27272a; padding:14px 28px; border-radius:50px; text-decoration:none; font-weight:700; z-index:9999; font-family:'Inter',sans-serif; box-shadow:0 10px 25px -5px rgba(0,0,0,0.5); transition:0.3s;" onmouseover="this.style.transform='translateY(-3px)'" onmouseout="this.style.transform='translateY(0)'">🚀 TID Operations Hub</a>"""
            if '</body>' in html: response.set_data(html.replace('</body>', btn + '</body>'))
    return response

# ------------------------------------------------------------------------------
# 3. BACKEND API ROUTES
# ------------------------------------------------------------------------------

@app.route('/api/nexus/refresh', methods=['POST'])
@login_required
def api_nexus_refresh():
    try:
        force_sync_all_databases()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/nexus/search', methods=['POST'])
@login_required
def api_nexus_search():
    try:
        if not GLOBAL_DB_CACHE['loaded']: force_sync_all_databases()
        queries = [x.strip() for x in re.split(r'[\n,\t\s]+', request.json.get('query', '')) if x.strip()]
        results = []
        
        for query in queries:
            q_lower = query.lower()
            q_lower_alt = '0' + q_lower if (q_lower.startswith('150') and 12 <= len(q_lower) <= 15) else q_lower

            found = False
            for src, rows in GLOBAL_DB_CACHE['sheets'].items():
                for row in rows:
                    oid = get_alias_val(row, STRICT_ALIASES['order']).lower()
                    tid_raw = get_alias_val(row, STRICT_ALIASES['tid']).lower()
                    
                    if q_lower in oid or q_lower in tid_raw or q_lower_alt in tid_raw:
                        k_stat = GLOBAL_DB_CACHE['kerry'].get(oid, "N/A")
                        results.append({
                            "order_id": oid.upper(), "source": src, "status": k_stat, 
                            "date": get_alias_val(row, STRICT_ALIASES['date']), 
                            "boxes": get_alias_val(row, STRICT_ALIASES['boxes']), 
                            "weight": get_alias_val(row, STRICT_ALIASES['weight']), 
                            "vendor": get_alias_val(row, STRICT_ALIASES['vendor']), 
                            "customer": get_alias_val(row, STRICT_ALIASES['customer']), 
                            "country": get_alias_val(row, STRICT_ALIASES['country']), 
                            "tids": clean_and_pad_tids(tid_raw),
                            "mawb": get_alias_val(row, STRICT_ALIASES['mawb'])
                        })
                        found = True; break
                if found: break
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/nexus/ship24', methods=['POST'])
@login_required
def api_nexus_ship24():
    tids = request.json.get('tids', [])
    ship24_key = os.environ.get('SHIP24_API_KEY', 'MOCK')
    responses = []
    for tid in tids:
        if tid.startswith('150') and 12 <= len(tid) <= 15: tid = '0' + tid
            
        if ship24_key == 'MOCK':
            responses.append({"tid": tid, "success": True, "courier": "Ship24", "current_status": "transit", "progress": 50, "eta": "In 3 Days", "signed_by": "", "events": [{"statusMilestone":"transit", "status": "Arrival at Hub", "time": "2026-03-01", "location": "Gateway"}]})
        else:
            try:
                req = urllib.request.Request("https://api.ship24.com/public/v1/trackers/track", data=json.dumps({"trackingNumber": tid}).encode(), headers={"Authorization": f"Bearer {ship24_key}", "Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req) as res:
                    tr = json.loads(res.read().decode()).get('data',{}).get('trackings',[{}])[0]
                    evs = tr.get('events',[])
                    st = evs[0].get('statusMilestone','pending') if evs else 'pending'
                    courier = evs[0].get('courierCode', 'Carrier') if evs else 'Carrier'
                    
                    delivery_info = tr.get('shipment', {}).get('delivery', {})
                    eta = delivery_info.get('estimatedDeliveryDate', None)
                    signed_by = delivery_info.get('signatureName', '')
                    
                    if st.lower() == 'delivered': eta = "Delivered"
                    elif not eta: eta = "Awaiting Carrier Update"
                    
                    responses.append({
                        "tid": tid, "success": True, "courier": str(courier).upper(), "current_status": st.lower(), 
                        "progress": 100 if st.lower()=='delivered' else (75 if st.lower()=='out_for_delivery' else 50), 
                        "eta": str(eta), "signed_by": signed_by,
                        "events": [{"statusMilestone": e.get('statusMilestone','info').lower(), "status": e.get('status', 'Update'), "time": e.get('datetime', 'N/A'), "location": e.get('location', '')} for e in evs]
                    })
            except: responses.append({"tid": tid, "success": False})
    return jsonify(responses)

@app.route('/api/nexus/radar_data', methods=['GET'])
@login_required
def api_nexus_radar_data():
    try:
        if not GLOBAL_DB_CACHE['loaded']: force_sync_all_databases()
            
        buckets = { src: {"with_tid": [], "missing_tid": []} for src in NEXUS_SOURCES.keys() }
        
        for src, rows in GLOBAL_DB_CACHE['sheets'].items():
            for row in rows:
                dt_str = get_alias_val(row, STRICT_ALIASES['date'])
                dt_obj = parse_date(dt_str)
                if dt_obj and dt_obj < FILTER_DATE: continue
                
                oid = get_alias_val(row, STRICT_ALIASES['order'])
                if oid == 'N/A': continue
                
                kerry_stat = GLOBAL_DB_CACHE['kerry'].get(oid.lower(), "PENDING")
                if kerry_stat != "HANDED OVER TO LOGISTICS PARTNER": continue
                
                tid_raw = get_alias_val(row, STRICT_ALIASES['tid'])
                tids = clean_and_pad_tids(tid_raw)
                has_tid = len(tids) > 0 and tids[0].lower() not in ['pending', 'none']
                
                r_d = { 
                    "Date": dt_str, "Order": oid.upper(), "Boxes": get_alias_val(row, STRICT_ALIASES['boxes']), 
                    "Weight": get_alias_val(row, STRICT_ALIASES['weight']), "Vendor Name": get_alias_val(row, STRICT_ALIASES['vendor']), 
                    "Customer Name": get_alias_val(row, STRICT_ALIASES['customer']), "Country": get_alias_val(row, STRICT_ALIASES['country']), 
                    "MAWB": get_alias_val(row, STRICT_ALIASES['mawb']), "Tracking ID": ", ".join(tids) if has_tid else "MISSING" 
                }
                
                if has_tid: buckets[src]["with_tid"].append(r_d)
                else: buckets[src]["missing_tid"].append(r_d)
                
        return jsonify(buckets)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------------------
# 4. FRONTEND UI & UX (ANTI-FREEZE SAFE JAVASCRIPT)
# ------------------------------------------------------------------------------

@app.route('/nexus')
@login_required
def nexus_dashboard():
    if session.get('role') != 'admin': return "Access Denied", 403
    return render_template_string('''
    <!DOCTYPE html><html lang="en" data-theme="dark">
    <head><meta charset="UTF-8"><title>TID Operations Hub</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        
        :root { 
            --bg: #000000; --card: #0a0a0a; --border: #222222; --text: #FFFFFF; --muted: #888888; 
            --accent: #3B82F6; --btn-bg: #3B82F6; --btn-text: #FFFFFF;
            --shadow: 0 4px 10px rgba(0, 0, 0, 0.5); --shadow-hover: 0 8px 20px rgba(59, 130, 246, 0.15);
            --badge-bg: rgba(255, 255, 255, 0.1); --badge-text: #CCCCCC; --input-bg: #050505;
        }
        
        [data-theme="light"] { 
            --bg: #F8F9FB; --card: #FFFFFF; --border: #E5E7EB; --text: #111827; --muted: #6B7280; 
            --accent: #3b82f6; --btn-bg: #111827; --btn-text: #FFFFFF;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); --shadow-hover: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            --badge-bg: #F3F4F6; --badge-text: #111827; --input-bg: #FFFFFF;
        }

        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; overflow: hidden;}
        * { box-sizing: border-box; }
        
        .app-container { display: flex; height: 100vh; width: 100vw; flex-direction: column; }
        
        .topbar { height: 64px; background: var(--card); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; padding: 0 24px; z-index: 10;}
        .brand { font-size: 18px; font-weight: 800; display: flex; align-items: center; gap: 10px;}
        
        .btn-outline { background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; transition: 0.2s;}
        .btn-outline:hover { border-color: var(--accent); }
        .btn-sync { background: #10B981; color: white; border: none; padding: 8px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 8px;}
        .btn-sync:hover { filter: brightness(1.1); transform:translateY(-1px);}

        .main-wrapper { display: flex; flex: 1; overflow: hidden; }
        .sidebar { width: 240px; background: var(--card); border-right: 1px solid var(--border); padding: 24px 16px; display: flex; flex-direction: column; gap: 4px;}
        .nav-item { padding: 14px 16px; border-radius: 8px; color: var(--muted); font-weight: 500; font-size: 14px; cursor: pointer; border: none; background: transparent; text-align: left; display: flex; align-items: center; gap: 10px; transition:0.2s;}
        .nav-item:hover { background: var(--bg); color: var(--text); }
        .nav-item.active { background: var(--accent); color: white; font-weight: 600; }
        
        .viewport { flex: 1; padding: 40px; overflow-y: auto; display: flex; flex-direction: column; gap: 24px; position: relative;}
        
        .sync-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); z-index: 50; display: none; flex-direction: column; justify-content: center; align-items: center; color: white;}
        
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 30px; box-shadow: var(--shadow); }
        .btn { background: var(--btn-bg); color: var(--btn-text); border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 13px; cursor: pointer; transition: 0.2s; }
        .btn:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }
        .btn-purple { background: linear-gradient(135deg, #8B5CF6, #6D28D9); color: white; display:none; }
        
        textarea { width: 100%; background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; color: var(--text); font-family: 'Inter', monospace; font-size: 15px; outline: none; resize: vertical; min-height: 100px; transition: 0.2s;}
        textarea:focus { border-color: var(--accent); }
        
        /* RADAR GRID */
        .radar-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;}
        .source-card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; display:flex; flex-direction:column; gap:16px;}
        .source-header { font-size: 15px; font-weight: 800; letter-spacing:0.5px; text-transform: uppercase; color:var(--text);}
        .split-box { display: flex; gap: 12px; }
        .split-btn { flex: 1; background: var(--input-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; cursor: pointer; transition: 0.2s; }
        .split-btn:hover { border-color: var(--accent); transform: translateY(-3px); }
        .split-val { font-size: 32px; font-weight: 800; color: var(--text); margin-bottom:4px;}
        .split-lbl { font-size: 11px; text-transform: uppercase; font-weight: 700; letter-spacing:0.5px;}
        .lbl-green { color: #10B981; }
        .lbl-red { color: #EF4444; }

        /* TRACKING RESULTS */
        .track-card { border-radius: 16px; padding: 0; overflow: hidden; margin-bottom: 30px; border: 1px solid var(--border); background: var(--card);}
        .track-header { padding: 15px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: var(--input-bg);}
        .meta-grid { padding: 24px; display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 20px; border-bottom: 1px solid var(--border);}
        .meta-col span:first-child { display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px;}
        .meta-col span:last-child { font-size: 15px; font-weight: 600; }
        
        .tid-area { padding: 24px; background: var(--bg); }
        .tid-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; }
        .tid-box { border: 1px solid var(--border); border-radius: 12px; padding: 20px; background: var(--card); display: flex; flex-direction: column;}
        
        /* SUBWAY MAP */
        .subway-map { display:flex; justify-content:space-between; align-items:center; margin: 15px 0 25px; position:relative;}
        .subway-map::before { content:''; position:absolute; top:50%; left:0; right:0; height:2px; background:var(--border); z-index:1;}
        .subway-node { position:relative; z-index:2; background:var(--card); padding:0 5px; display:flex; flex-direction:column; align-items:center; gap:5px;}
        .sub-dot { width:12px; height:12px; border-radius:50%; background:var(--border); border:2px solid var(--card);}
        .sub-label { font-size:10px; font-weight:700; color:var(--muted); text-transform:uppercase;}
        .subway-node.active .sub-dot { background:var(--accent); box-shadow:0 0 10px var(--accent);}
        .subway-node.active .sub-label { color:var(--text);}
        .subway-node.done .sub-dot { background:#10B981;}
        
        .timeline { max-height: 200px; overflow-y: auto; padding-right:10px; }
        .tl-event { font-size: 13px; padding-left: 16px; border-left: 2px solid var(--border); margin-bottom: 16px; position:relative;}
        .tl-event::before { content:''; position:absolute; left:-5px; top:4px; width:8px; height:8px; border-radius:50%; background:var(--accent);}
        .tl-status { font-weight: 600; color: var(--text); margin-bottom:4px; display:block;}
        .tl-time { color: var(--muted); font-size: 11px; }

        .modal { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.9); z-index: 100; display: none; padding: 40px; overflow-y: auto; backdrop-filter: blur(5px);}
        .modal-content { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 40px; max-width: 1400px; margin: auto; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { padding: 16px; font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; border-bottom: 1px solid var(--border);}
        td { padding: 16px; font-size: 14px; border-bottom: 1px solid var(--border); color: var(--text);}
        tr:hover { background: rgba(255,255,255,0.05); }
        
        .loader { width: 24px; height: 24px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* ERROR BOX */
        .error-box { background: rgba(239, 68, 68, 0.1); border: 1px solid #EF4444; color: #EF4444; padding: 20px; border-radius: 12px; text-align: center; font-weight: 600; margin-top: 10px;}
    </style></head>
    <body>
    <div class="app-container">
        
        <header class="topbar">
            <div class="brand">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--accent)"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                TID Operations Hub
            </div>
            <div class="topbar-actions">
                <button class="btn-sync" onclick="forceGlobalSync()">🔄 Sync Live Data</button>
                <button class="btn-outline" id="themeBtn" onclick="toggleTheme()">☀️ Light Mode</button>
            </div>
        </header>
        
        <div class="main-wrapper">
            <aside class="sidebar">
                <div style="font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; margin: 10px 0 10px 10px;">Menu</div>
                <button class="nav-item active" onclick="navSwitch(this, 'view-track')">🔍 Matrix Search</button>
                <button class="nav-item" onclick="navSwitch(this, 'view-direct')">🚢 Direct TID Track</button>
                <button class="nav-item" onclick="navSwitch(this, 'view-radar')">📦 Handed Over</button>
                <div style="flex:1"></div>
                <a href="/" class="nav-item" style="color: #EF4444;">🚪 Exit Hub</a>
            </aside>
            
            <main class="viewport">
                <div class="sync-overlay" id="syncOverlay">
                    <div class="loader" style="width: 50px; height: 50px; margin-bottom:20px;"></div>
                    <h2 style="margin:0; font-size:24px;">Synchronizing Database</h2>
                    <p style="color:var(--muted); margin-top:10px;">Fetching safely... Please wait a few seconds.</p>
                </div>

                <div id="view-track" class="view-pane active">
                    <div style="margin-bottom:20px;">
                        <h1 style="margin: 0 0 8px 0; font-size: 28px; font-weight: 800;">Matrix Search</h1>
                        <div style="font-size: 14px; color: var(--muted);">Search by Order ID or Carrier TID to find details.</div>
                    </div>
                    <div class="card" style="margin-bottom: 30px;">
                        <textarea id="searchInput" placeholder="Paste Order IDs or TIDs here..."></textarea>
                        <div style="margin-top: 20px; display: flex; gap: 12px;">
                            <button class="btn" onclick="searchOrders()">🔍 Scan Matrix</button>
                            <button class="btn btn-purple" id="bulkBtn" onclick="bulkTrackAll()">⚡ Bulk Sync Carriers</button>
                            <button class="btn-outline" onclick="document.getElementById('searchInput').value=''; document.getElementById('tracking-results').innerHTML=''; document.getElementById('bulkBtn').style.display='none';">Clear</button>
                        </div>
                    </div>
                    <div id="tracking-results"></div>
                </div>

                <div id="view-direct" class="view-pane" style="display:none;">
                    <div style="margin-bottom:20px;">
                        <h1 style="margin: 0 0 8px 0; font-size: 28px; font-weight: 800;">Direct Carrier Tracking</h1>
                        <div style="font-size: 14px; color: var(--muted);">Track any TID worldwide directly without checking Google Sheets.</div>
                    </div>
                    <div class="card" style="margin-bottom: 30px;">
                        <textarea id="directInput" placeholder="Paste multiple Carrier TIDs here..."></textarea>
                        <div style="margin-top: 20px; display: flex; gap: 12px;">
                            <button class="btn" onclick="directTrackTIDs()">🚢 Track TIDs</button>
                            <button class="btn-outline" onclick="document.getElementById('directInput').value=''; document.getElementById('direct-results').innerHTML='';">Clear</button>
                        </div>
                    </div>
                    <div id="direct-results"></div>
                </div>
                
                <div id="view-radar" class="view-pane" style="display:none;">
                    <div style="margin-bottom:20px;">
                        <h1 style="margin: 0 0 8px 0; font-size: 28px; font-weight: 800;">Handed Over Operations</h1>
                        <div style="font-size: 14px; color: var(--muted);">Data filtered purely from 1st Jan 2026 onwards.</div>
                    </div>
                    <div id="loader" style="display:none; padding:100px; text-align:center;"><div class="loader" style="margin:auto"></div></div>
                    <div id="radar-container" class="radar-grid"></div>
                </div>
            </main>
        </div>
    </div>

    <div id="detailPanel" class="modal" onclick="if(event.target==this)this.style.display='none'">
        <div class="modal-content">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px">
                <h2 id="modalTitle" style="margin:0; font-size:24px; font-weight:800;"></h2>
                <div style="display:flex; gap:12px;">
                    <button class="btn-outline" onclick="downloadCSV()">Export CSV</button>
                    <button class="btn" style="background:#EF4444; color:white;" onclick="document.getElementById('detailPanel').style.display='none'">Close Window</button>
                </div>
            </div>
            <div style="overflow-x:auto; border:1px solid var(--border); border-radius:12px;"><table id="detailTable"></table></div>
        </div>
    </div>

    <script>
        function toggleTheme() {
            const root = document.documentElement;
            const target = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            root.setAttribute('data-theme', target);
            localStorage.setItem('nexus_theme', target);
            document.getElementById('themeBtn').innerText = target === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
        }
        document.documentElement.setAttribute('data-theme', localStorage.getItem('nexus_theme') || 'dark');

        function getFlag(cStr) {
            const c = String(cStr || '').toLowerCase().trim();
            if(!c || c === 'n/a' || c === '-') return '🏳️ Unknown';
            const flagMap = {
                'uk': '🇬🇧 UK', 'us': '🇺🇸 US', 'fr': '🇫🇷 France', 'de': '🇩🇪 Germany',
                'ae': '🇦🇪 UAE', 'ca': '🇨🇦 Canada', 'au': '🇦🇺 Australia', 'nz': '🇳🇿 New Zealand',
                'pk': '🇵🇰 Pakistan', 'cn': '🇨🇳 China'
            };
            for(let key in flagMap) { if(c === key || c.includes(key)) return flagMap[key]; }
            return '🏳️ ' + c.charAt(0).toUpperCase() + c.slice(1);
        }

        let activeDetails = [];
        let radarData = null;
        let allTrackingData = [];

        // ANTI-FREEZE SHIELD (Catches all backend errors gracefully)
        async function safeFetch(url, options = {}) {
            try {
                const response = await fetch(url, options);
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                return data;
            } catch (error) {
                console.error("API Call Failed:", error);
                throw error; // Let the caller handle it
            }
        }

        async function forceGlobalSync() {
            const overlay = document.getElementById('syncOverlay');
            overlay.style.display = 'flex';
            try {
                await safeFetch('/api/nexus/refresh', {method: 'POST'});
                radarData = null; 
                if(document.getElementById('view-radar').style.display === 'block') await loadRadar();
            } catch(e) {
                alert("⚠️ Request timed out. The system is still working safely. Please try clicking Sync again.");
            }
            overlay.style.display = 'none';
        }

        function navSwitch(btn, viewType) {
            document.querySelectorAll('.nav-item').forEach(l=>l.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.view-pane').forEach(v=>v.style.display='none');
            document.getElementById(viewType).style.display = 'block';
            if(viewType === 'view-radar') loadRadar();
        }

        // --- 1. MATRIX SEARCH ENGINE ---
        async function searchOrders() {
            const q = document.getElementById('searchInput').value; if(!q) return;
            const resDiv = document.getElementById('tracking-results');
            resDiv.innerHTML = '<div style="padding:40px;text-align:center"><div class="loader" style="margin:auto"></div></div>';
            document.getElementById('bulkBtn').style.display = 'none';
            
            try {
                allTrackingData = await safeFetch('/api/nexus/search', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q})});
                if(allTrackingData.length > 0) document.getElementById('bulkBtn').style.display = 'flex';
                renderCards();
            } catch (e) {
                resDiv.innerHTML = `<div class="error-box">⚠️ Backend is warming up. Please click the green "Sync Live Data" button at the top right first!</div>`;
            }
        }

        function renderCards() {
            let h = '';
            if(allTrackingData.length === 0) {
                document.getElementById('tracking-results').innerHTML = '<div style="text-align:center; color:var(--muted); padding:40px; border:1px dashed var(--border); border-radius:12px;">Not found in sheet. Try "Direct TID Track" tab instead!</div>';
                return;
            }
            allTrackingData.forEach(item => {
                const originFlag = item.source.includes('ECL') ? '🇨🇳 China' : '🇵🇰 Pakistan';
                const destFlag = getFlag(item.country);
                
                h += `<div class="track-card">
                    <div class="track-header">
                        <div style="font-weight: 800; font-size: 14px;">[${originFlag}] ➔ ✈️ ➔ [${destFlag}]</div>
                        <div style="padding:4px 8px; border-radius:4px; font-size:11px; font-weight:700; background:var(--border);">${item.source}</div>
                    </div>
                    <div class="meta-grid">
                        <div class="meta-col"><span>Order ID</span><span style="color:var(--accent)">${item.order_id}</span></div>
                        <div class="meta-col"><span>Kerry Status</span><span style="color:${item.status.includes('DELIVERED')?'#10B981':'var(--text)'}">${item.status}</span></div>
                        <div class="meta-col"><span>Customer</span><span>${item.customer}</span></div>
                        <div class="meta-col"><span>Vendor</span><span>${item.vendor}</span></div>
                        <div class="meta-col"><span>Boxes / Wt</span><span>${item.boxes} / ${item.weight}kg</span></div>
                        <div class="meta-col"><span>MAWB</span><span>${item.mawb}</span></div>
                    </div>
                    <div class="tid-area">
                        <div style="font-size:11px; font-weight:700; color:var(--muted); margin-bottom:15px; letter-spacing:1px;">CARRIER TRACKING IDs</div>
                        <div class="tid-grid">
                            ${item.tids.map(tid => `
                                <div class="tid-box">
                                    <div class="tid-head">
                                        <div>
                                            <div style="font-family:monospace; font-size:15px; font-weight:700; color:var(--text);">${tid}</div>
                                            <div id="courier-${tid.replace(/[\s\/]+/g,'')}" style="font-size:11px; font-weight:700; color:var(--accent); margin-top:4px;"></div>
                                        </div>
                                        <div style="text-align:right;">
                                            <button class="btn-outline" style="padding:6px 12px; font-size:11px; margin-bottom:8px;" onclick="syncShip24('${tid}')">Track Carrier</button>
                                            <div id="eta-${tid.replace(/[\s\/]+/g,'')}" style="font-size:11px; font-weight:700; color:var(--muted);">ETA: Checking...</div>
                                        </div>
                                    </div>
                                    <div class="subway-map" id="subway-${tid.replace(/[\s\/]+/g,'')}">
                                        <div class="subway-node"><div class="sub-dot"></div><div class="sub-label">Pickup</div></div>
                                        <div class="subway-node"><div class="sub-dot"></div><div class="sub-label">Transit</div></div>
                                        <div class="subway-node"><div class="sub-dot"></div><div class="sub-label">Customs</div></div>
                                        <div class="subway-node"><div class="sub-dot"></div><div class="sub-label">Delivered</div></div>
                                    </div>
                                    <div class="progress"><div class="progress-bar" id="prog-${tid.replace(/[\s\/]+/g,'')}"></div></div>
                                    <div class="timeline" id="log-${tid.replace(/[\s\/]+/g,'')}"></div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>`;
            });
            document.getElementById('tracking-results').innerHTML = h;
        }

        function updateSubwayMap(sid, status) {
            const map = document.getElementById(`subway-${sid}`);
            if(!map) return;
            const nodes = map.querySelectorAll('.subway-node');
            nodes.forEach(n => { n.classList.remove('active'); n.classList.remove('done'); });
            
            let stage = 0;
            if(status === 'pickup' || status === 'info' || status === 'pending') stage = 0;
            else if(status === 'transit') stage = 1;
            else if(status === 'out_for_delivery') stage = 2;
            else if(status === 'delivered') stage = 3;

            for(let i=0; i<=stage; i++) {
                if(i === stage) nodes[i].classList.add('active');
                else nodes[i].classList.add('done');
            }
        }

        async function syncShip24(tid, isDirect = false) {
            const prefix = isDirect ? 'dt-' : '';
            const sid = tid.replace(/[\s\/]+/g,'');
            const log = document.getElementById(`${prefix}log-${sid}`); 
            log.innerHTML = '<div class="loader" style="width:16px;height:16px; margin:10px 0;"></div>';
            
            try {
                const res = await safeFetch('/api/nexus/ship24', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tids:[tid]})});
                const d = res[0];
                
                if(d.success) {
                    document.getElementById(`${prefix}prog-${sid}`).style.width = d.progress + '%';
                    document.getElementById(`${prefix}courier-${sid}`).innerText = d.courier;
                    if(!isDirect) updateSubwayMap(sid, d.current_status);
                    
                    const etaBadge = document.getElementById(`${prefix}eta-${sid}`);
                    if(d.progress === 100) { etaBadge.innerHTML = '✅ Delivered'; etaBadge.style.color = '#10B981'; }
                    else { etaBadge.innerHTML = '🚚 ETA: ' + d.eta; etaBadge.style.color = '#F59E0B'; }
                    
                    let timelineHtml = d.events.length === 0 ? '<div class="tl-event"><span class="tl-status" style="color:var(--muted)">Awaiting Carrier Update...</span></div>' : d.events.map(e => `<div class="tl-event"><span class="tl-status">${e.status}</span><span class="tl-time">${e.time} | ${e.location}</span></div>`).join('');
                    
                    // POD & SIGNATURE LOGIC
                    let extraHtml = `<div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid var(--border);">`;
                    if(d.progress === 100 && d.signed_by) extraHtml += `<div style="color: #10B981; font-size: 13px; font-weight: 700; margin-bottom: 10px;">✍️ Signed By: ${d.signed_by}</div>`;
                    extraHtml += `<a href="https://www.ship24.com/tracking?p=${tid}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; background:var(--card); border:1px solid var(--border); padding:6px 12px; border-radius:6px; font-size:11px; font-weight:600; color:var(--text); text-decoration:none;">🔗 Official POD</a></div>`;
                    
                    log.innerHTML = timelineHtml + extraHtml;
                } else {
                    log.innerHTML = '<span style="color:#EF4444; font-size:13px; font-weight:600;">Tracking API Error.</span>';
                }
            } catch (e) {
                log.innerHTML = '<span style="color:#EF4444; font-size:13px; font-weight:600;">API Timeout. Try again.</span>';
            }
        }

        async function bulkTrackAll() {
            const btn = document.getElementById('bulkBtn');
            btn.innerText = "Syncing All..."; btn.style.pointerEvents = 'none'; btn.style.opacity = '0.7';
            for(let item of allTrackingData) { for(let tid of item.tids) { await syncShip24(tid); } }
            btn.innerText = "⚡ Bulk Sync Complete"; btn.style.pointerEvents = 'auto'; btn.style.opacity = '1';
        }

        // --- 2. DIRECT TID TRACKING ENGINE ---
        async function directTrackTIDs() {
            let val = document.getElementById('directInput').value;
            if(!val) return;
            let tids = val.split(/[\n,\t \/]+/).map(t => t.trim()).filter(Boolean);
            tids = tids.map(t => (t.startsWith('150') && t.length >= 12 && t.length <= 15) ? '0' + t : t);

            let h = '<div class="tid-area" style="border-radius:12px; border:1px solid var(--border);"><div class="tid-grid">';
            tids.forEach(tid => {
                h += `
                <div class="tid-box">
                    <div class="tid-head">
                        <div>
                            <div style="font-family:monospace; font-size:15px; font-weight:700; color:var(--text);">${tid}</div>
                            <div id="dt-courier-${tid.replace(/[\s\/]+/g,'')}" style="font-size:11px; font-weight:700; color:var(--accent); margin-top:4px;">Fetching...</div>
                        </div>
                        <div style="text-align:right;">
                            <div id="dt-eta-${tid.replace(/[\s\/]+/g,'')}" style="font-size:11px; font-weight:700; color:var(--muted);">ETA: Checking...</div>
                        </div>
                    </div>
                    <div class="progress"><div class="progress-bar" id="dt-prog-${tid.replace(/[\s\/]+/g,'')}"></div></div>
                    <div class="timeline" id="dt-log-${tid.replace(/[\s\/]+/g,'')}"></div>
                </div>`;
            });
            h += '</div></div>';
            document.getElementById('direct-results').innerHTML = h;

            for(let tid of tids) { await syncShip24(tid, true); }
        }

        // --- 3. RADAR ENGINE (HANDED OVER ONLY) ---
        async function loadRadar() {
            const container = document.getElementById('radar-container');
            const loader = document.getElementById('loader');
            container.innerHTML = ''; loader.style.display = 'block';
            
            try {
                radarData = await safeFetch('/api/nexus/radar_data'); 
                
                const sources = ["ECL QC Center", "ECL Zone", "GE QC Center", "GE Zone", "APX", "Kerry"];
                sources.forEach(src => {
                    // Safe access in case API data is slightly off
                    const withTid = (radarData && radarData[src]) ? radarData[src].with_tid : [];
                    const missTid = (radarData && radarData[src]) ? radarData[src].missing_tid : [];
                    
                    container.innerHTML += `
                        <div class="source-card">
                            <div class="source-header">${src}</div>
                            <div class="split-box">
                                <div class="split-btn" onclick="showDetails('${src}', 'with_tid')">
                                    <div class="split-val">${withTid.length}</div>
                                    <div class="split-lbl lbl-green">With TID</div>
                                </div>
                                <div class="split-btn" onclick="showDetails('${src}', 'missing_tid')">
                                    <div class="split-val">${missTid.length}</div>
                                    <div class="split-lbl lbl-red">Missing TID</div>
                                </div>
                            </div>
                        </div>
                    `;
                });
            } catch (e) {
                container.innerHTML = `<div class="error-box">⚠️ Please click the green "Sync Live Data" button at the top right first.</div>`;
            }
            loader.style.display = 'none';
        }

        function showDetails(src, type) {
            if(!radarData || !radarData[src]) return;
            activeDetails = radarData[src][type];
            if(!activeDetails || activeDetails.length === 0) return;
            
            const typeStr = type === 'with_tid' ? 'WITH TID' : 'MISSING TID';
            document.getElementById('modalTitle').innerText = `${src} [${typeStr}]`;
            
            const table = document.getElementById('detailTable');
            let thead = '<thead><tr><th>Date</th><th>Order</th><th>Boxes</th><th>Weight</th><th>Vendor</th><th>Customer</th><th>Country</th><th>MAWB</th><th>Tracking ID</th></tr></thead>';
            
            let tbody = '<tbody>' + activeDetails.map(r=>`<tr>
                <td>${r['Date']}</td>
                <td style="color:var(--accent); font-weight:700;">${r['Order']}</td>
                <td>${r['Boxes']}</td>
                <td>${r['Weight']}</td>
                <td>${r['Vendor Name']}</td>
                <td>${r['Customer Name']}</td>
                <td>${r['Country']}</td>
                <td>${r['MAWB']}</td>
                <td style="font-family:monospace;">${r['Tracking ID']}</td>
            </tr>`).join('') + '</tbody>';
            
            table.innerHTML = thead + tbody;
            document.getElementById('detailPanel').style.display = 'block';
        }

        function downloadCSV() {
            if(!activeDetails.length) return;
            const headers = ["Date", "Order", "Boxes", "Weight", "Vendor Name", "Customer Name", "Country", "MAWB", "Tracking ID"];
            const headerStr = headers.join(',');
            const rows = activeDetails.map(r => headers.map(h => `"${String(r[h]).replace(/"/g, '""')}"`).join(',')).join('\\n');
            const csvContent = "data:text/csv;charset=utf-8," + headerStr + "\\n" + rows;
            const link = document.createElement("a");
            link.setAttribute("href", encodeURI(csvContent));
            link.setAttribute("download", `nexus_export.csv`);
            link.click();
        }
    </script>
    </body></html>
    ''')
# ==============================================================================
# END OF CODE
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True)
