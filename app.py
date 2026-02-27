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
from flask import Response
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Rocket2024')

CACHE = {}
CACHE_DURATION = 300

SHEET_ID = '1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY'

PROVIDERS = [
    {
        'name': 'GLOBAL EXPRESS (QC)',
        'short': 'GE QC',
        'sheet': 'GE QC Center & Zone',        
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'order_col': 0,
        'start_row': 2,
        'color': '#3B82F6',
        'group': 'GE'
    },
    {
    'name': 'GLOBAL EXPRESS (ZONE)',
    'short': 'GE ZONE',
    'sheet': 'GE QC Center & Zone',
    'date_col': 10,       # Column K (index 10)
    'box_col': 11,        # Column L (index 11)
    'weight_col': 15,     # Column P (index 15)
    'region_col': 16,     # Column Q (index 16)
    'order_col': 9,       # Column J (index 9)
    'start_row': 2,
    'color': '#8B5CF6',
    'group': 'GE'
},
    {
        'name': 'ECL LOGISTICS (QC)',
        'short': 'ECL QC',
        'sheet': 'ECL QC Center & Zone',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'order_col': 0,
        'start_row': 3,
        'color': '#10B981',
        'group': 'ECL'
    },
    {
        'name': 'ECL LOGISTICS (ZONE)',
        'short': 'ECL ZONE',
        'sheet': 'ECL QC Center & Zone',
        'date_col': 10,
        'box_col': 11,
        'weight_col': 14,
        'region_col': 16,
        'order_col': 0,
        'start_row': 3,
        'color': '#F59E0B',
        'group': 'ECL'
    },
    {
        'name': 'KERRY',
        'short': 'KERRY',
        'sheet': 'Kerry',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'order_col': 0,
        'start_row': 2,
        'color': '#EF4444',
        'group': 'OTHER'
    },
    {
        'name': 'APX',
        'short': 'APX',
        'sheet': 'APX',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'order_col': 0,
        'start_row': 2,
        'color': '#EC4899',
        'group': 'OTHER'
    }
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

FAVICON = '''<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='gold' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%23f4d03f'/%3E%3Cstop offset='50%25' style='stop-color:%23d4a853'/%3E%3Cstop offset='100%25' style='stop-color:%23b8942d'/%3E%3C/linearGradient%3E%3C/defs%3E%3Ccircle cx='50' cy='50' r='46' fill='%230a0a0f' stroke='url(%23gold)' stroke-width='4'/%3E%3Ctext x='50' y='42' text-anchor='middle' font-family='Arial Black' font-size='24' font-weight='bold' fill='url(%23gold)'%3E3P%3C/text%3E%3Ctext x='50' y='68' text-anchor='middle' font-family='Arial' font-size='16' font-weight='bold' fill='%23d4a853'%3ELOGISTICS%3C/text%3E%3Ccircle cx='50' cy='50' r='42' fill='none' stroke='%23d4a853' stroke-width='1' opacity='0.3'/%3E%3C/svg%3E">'''

BASE_STYLES = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    body {
        font-family: 'Inter', sans-serif;
        background: #0F1218;
        color: #FFFFFF;
        min-height: 100vh;
        line-height: 1.5;
    }

    /* ===== SIDEBAR - Premium Dark ===== */
    .sidebar {
        position: fixed;
        left: 0;
        top: 0;
        height: 100vh;
        width: 280px;
        background: #0A0C12;
        border-right: 1px solid rgba(212, 175, 55, 0.15);
        padding: 28px 20px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 100;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        box-shadow: 4px 0 20px rgba(0, 0, 0, 0.5);
    }
    
    .sidebar.collapsed {
        width: 80px;
    }
    
    .sidebar-header {
        display: flex;
        align-items: center;
        gap: 14px;
        padding-bottom: 28px;
        border-bottom: 1px solid rgba(212, 175, 55, 0.2);
        margin-bottom: 28px;
    }
    
    .logo-icon {
        width: 44px;
        height: 44px;
        background: linear-gradient(145deg, #D4AF37, #B49450);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: #0A0C12;
        font-size: 20px;
        box-shadow: 0 8px 16px rgba(212, 175, 55, 0.25);
    }
    
    .logo-text {
        font-size: 20px;
        font-weight: 600;
        color: #D4AF37;
        white-space: nowrap;
        overflow: hidden;
        transition: opacity 0.3s;
        letter-spacing: 0.5px;
    }
    
    .sidebar.collapsed .logo-text {
        opacity: 0;
        width: 0;
    }
    
    .nav-section {
        margin-bottom: 24px;
    }
    
    .nav-section-title {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #9CA3AF;
        padding: 8px 16px;
        margin-bottom: 6px;
        font-weight: 500;
    }
    
    .sidebar.collapsed .nav-section-title {
        opacity: 0;
    }
    
    .nav-menu {
        display: flex;
        flex-direction: column;
        gap: 8px;
        flex-grow: 1;
    }
    
    .nav-item {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 18px;
        border-radius: 12px;
        color: #9CA3AF;
        text-decoration: none;
        transition: all 0.2s ease;
        cursor: pointer;
        position: relative;
        font-size: 14px;
        font-weight: 500;
    }
    
    .nav-item:hover {
        background: rgba(212, 175, 55, 0.1);
        color: #D4AF37;
        transform: translateX(4px);
    }
    
    .nav-item.active {
        background: linear-gradient(90deg, rgba(212, 175, 55, 0.15), transparent);
        color: #D4AF37;
        border-left: 4px solid #D4AF37;
    }
    
    .nav-item svg {
        width: 20px;
        height: 20px;
        flex-shrink: 0;
        transition: all 0.2s;
    }
    
    .nav-item.active svg {
        color: #D4AF37;
    }
    
    .nav-item span {
        white-space: nowrap;
        overflow: hidden;
        transition: opacity 0.3s;
    }
    
    .sidebar.collapsed .nav-item span {
        opacity: 0;
        width: 0;
    }
    
    .nav-item .tooltip {
        position: absolute;
        left: 70px;
        background: #1E2532;
        color: #FFFFFF;
        padding: 8px 14px;
        border-radius: 8px;
        font-size: 12px;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s;
        border: 1px solid rgba(212, 175, 55, 0.3);
        z-index: 1000;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .sidebar.collapsed .nav-item:hover .tooltip {
        opacity: 1;
    }
    
    .sidebar-toggle {
        position: absolute;
        right: -12px;
        top: 50%;
        transform: translateY(-50%);
        width: 24px;
        height: 24px;
        background: #D4AF37;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        border: 2px solid #0F1218;
        color: #0F1218;
        font-size: 12px;
        font-weight: bold;
        transition: transform 0.3s;
        box-shadow: 0 2px 8px rgba(212, 175, 55, 0.3);
    }
    
    .sidebar.collapsed .sidebar-toggle {
        transform: translateY(-50%) rotate(180deg);
    }
    
    .sidebar-footer {
        border-top: 1px solid rgba(212, 175, 55, 0.15);
        padding-top: 20px;
        margin-top: auto;
    }
    
    .logout-btn {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 18px;
        border-radius: 12px;
        color: #B76E79;
        text-decoration: none;
        transition: all 0.2s;
        cursor: pointer;
        width: 100%;
        border: none;
        background: none;
        font-family: inherit;
        font-size: 14px;
        font-weight: 500;
    }
    
    .logout-btn:hover {
        background: rgba(183, 110, 121, 0.1);
        color: #B76E79;
    }
    
    .logout-btn svg {
        width: 20px;
        height: 20px;
        flex-shrink: 0;
    }
    
    .sidebar.collapsed .logout-btn span {
        opacity: 0;
        width: 0;
    }

    /* ===== MAIN CONTENT ===== */
    .main-content {
        margin-left: 280px;
        padding: 32px;
        transition: margin-left 0.3s;
        min-height: 100vh;
        background: #0F1218;
    }
    
    .main-content.expanded {
        margin-left: 80px;
    }

    /* ===== PAGE HEADER ===== */
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 32px;
        flex-wrap: wrap;
        gap: 20px;
    }
    
    .page-title {
        font-size: 32px;
        font-weight: 600;
        color: #FFFFFF;
        letter-spacing: -0.5px;
    }
    
    .page-title span {
        color: #D4AF37;
        font-weight: 700;
        text-shadow: 0 2px 10px rgba(212, 175, 55, 0.3);
    }

    /* ===== DATE RANGE PICKER ===== */
    .date-range-picker {
        background: #1A1E26;
        border-radius: 16px;
        border: 1px solid rgba(212, 175, 55, 0.2);
        padding: 18px 22px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    }
    
    .qbtns-row {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 16px;
    }
    
    .qbtn {
        padding: 8px 16px;
        background: #252B36;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        color: #9CA3AF;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .qbtn:hover {
        border-color: #D4AF37;
        color: #D4AF37;
        background: rgba(212, 175, 55, 0.1);
    }
    
    .qbtn.active {
        background: #D4AF37;
        border-color: #D4AF37;
        color: #0F1218;
        font-weight: 600;
    }
    
    .date-inputs-row {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }
    
    .range-input {
        padding: 10px 14px;
        background: #252B36;
        border: 1px solid rgba(212, 175, 55, 0.3);
        border-radius: 10px;
        color: #FFFFFF;
        font-size: 13px;
    }
    
    .range-input:focus {
        outline: none;
        border-color: #D4AF37;
        box-shadow: 0 0 0 3px rgba(212, 175, 55, 0.2);
    }
    
    .range-sep {
        color: #9CA3AF;
        font-size: 16px;
        font-weight: 500;
    }
    
    .apply-btn {
        padding: 10px 20px;
        background: #D4AF37;
        border: none;
        border-radius: 10px;
        color: #0F1218;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .apply-btn:hover {
        background: #C5A028;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(212, 175, 55, 0.3);
    }
    
    .week-badge {
        font-size: 13px;
        color: #D4AF37;
        font-weight: 500;
        padding: 8px 16px;
        background: rgba(212, 175, 55, 0.1);
        border-radius: 10px;
        border: 1px solid rgba(212, 175, 55, 0.3);
    }

    /* ===== PROVIDER CARDS ===== */
    .provider-card {
        background: #1A1E26;
        border-radius: 20px;
        border: 1px solid rgba(212, 175, 55, 0.15);
        margin-bottom: 28px;
        overflow: hidden;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
        transition: transform 0.3s, box-shadow 0.3s;
    }
    
    .provider-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
        border-color: rgba(212, 175, 55, 0.3);
    }
    
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 24px 28px;
        border-bottom: 1px solid rgba(212, 175, 55, 0.15);
        position: relative;
        background: linear-gradient(90deg, rgba(212, 175, 55, 0.05), transparent);
    }
    
    .card-header::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 6px;
        background: linear-gradient(180deg, #D4AF37, #B49450);
        border-radius: 0 4px 4px 0;
    }
    
    .provider-info {
        display: flex;
        align-items: center;
        gap: 24px;
        flex-wrap: wrap;
    }
    
    .provider-name {
        font-size: 22px;
        font-weight: 600;
        color: #FFFFFF;
    }
    
    .star-rating {
        color: #D4AF37;
        font-size: 16px;
        letter-spacing: 3px;
        text-shadow: 0 0 10px rgba(212, 175, 55, 0.3);
    }
    
    .trend-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 30px;
        font-size: 13px;
        font-weight: 600;
    }
    
    .trend-badge.up {
        background: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .trend-badge.down {
        background: rgba(239, 68, 68, 0.15);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    .trend-badge.neutral {
        background: rgba(156, 163, 175, 0.15);
        color: #9CA3AF;
        border: 1px solid rgba(156, 163, 175, 0.3);
    }
    
    .card-stats {
        display: flex;
        gap: 32px;
    }
    
    .stat-item {
        text-align: center;
        padding: 10px 20px;
        background: #252B36;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .stat-value {
        font-size: 22px;
        font-weight: 700;
        color: #FFFFFF;
    }
    
    .stat-label {
        font-size: 12px;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }

    /* ===== DATA TABLE - Premium Grid ===== */
    .data-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 13px;
    }
    
    .data-table th {
        background: #252B36;
        padding: 16px 10px;
        text-align: center;
        font-weight: 600;
        color: #9CA3AF;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 3px solid #D4AF37;
    }
    
    .data-table th.region-col {
        text-align: left;
        padding-left: 24px;
        min-width: 150px;
        border-right: 1px solid rgba(212, 175, 55, 0.3);
    }
    
    .data-table th.day-col {
        min-width: 160px;
    }
    
    .data-table th.flight-day {
        background: #2A313E;
        color: #D4AF37;
    }
    
    .data-table td {
        padding: 14px 10px;
        text-align: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        color: #E5E7EB;
    }
    
    .data-table td.region-col {
        text-align: left;
        padding-left: 24px;
        font-weight: 600;
        color: #FFFFFF;
        background: rgba(0, 0, 0, 0.2);
        border-right: 1px solid rgba(212, 175, 55, 0.2);
    }
    
    .data-table tr:hover td {
        background: rgba(212, 175, 55, 0.05);
    }
    
    .data-table tr.total-row td {
        background: rgba(212, 175, 55, 0.15);
        font-weight: 700;
        color: #D4AF37;
        border-top: 2px solid #D4AF37;
        font-size: 14px;
    }

    /* ===== CLEAN GRID FOR NUMBERS - Premium Look ===== */
    .day-data { 
        display: flex; 
        justify-content: center; 
        gap: 2px; 
        font-size: 12px;
        border: 1px solid rgba(212, 175, 55, 0.2);
        border-radius: 8px;
        overflow: hidden;
        background: #252B36;
        margin: 2px 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    
    .day-data span,
    .day-data a {
        flex: 1;
        min-width: 38px;
        padding: 6px 2px;
        text-align: center;
        font-weight: 600;
        border-right: 1px solid rgba(212, 175, 55, 0.2);
        transition: all 0.2s ease;
        display: inline-block;
        text-decoration: none;
        color: inherit;
    }
    
    .day-data span:last-child,
    .day-data a:last-child {
        border-right: none;
    }
    
    /* Premium accent colors - slightly brighter */
    .day-data span:nth-child(1),
    .day-data a:nth-child(1) { 
        color: #60A5FA; 
        background: rgba(59, 130, 246, 0.1); 
    }
    .day-data span:nth-child(2),
    .day-data a:nth-child(2) { 
        color: #34D399; 
        background: rgba(16, 185, 129, 0.1); 
    }
    .day-data span:nth-child(3),
    .day-data a:nth-child(3) { 
        color: #FBBF24; 
        background: rgba(245, 158, 11, 0.1); 
    }
    .day-data span:nth-child(4),
    .day-data a:nth-child(4) { 
        color: #6B8E6B; 
        background: rgba(107, 142, 107, 0.1); 
    }
    .day-data span:nth-child(5),
    .day-data a:nth-child(5) { 
        color: #B76E79; 
        background: rgba(183, 110, 121, 0.1); 
    }
    
    /* Hover effect with gold */
    .day-data a:hover {
        background: rgba(212, 175, 55, 0.2);
        transform: scale(1.1);
        z-index: 2;
        box-shadow: 0 2px 8px rgba(212, 175, 55, 0.4);
        border-radius: 4px;
    }
    
    .day-data-empty { 
        color: #4B5563; 
        font-size: 14px; 
        padding: 6px;
        text-align: center;
        background: #252B36;
        border-radius: 6px;
    }

    /* ===== STATS CARDS ===== */
    .stats-row, .stats-row-5 {
        display: grid;
        gap: 20px;
        margin-bottom: 32px;
    }
    
    .stats-row {
        grid-template-columns: repeat(4, 1fr);
    }
    
    .stats-row-5 {
        grid-template-columns: repeat(5, 1fr);
    }
    
    .stat-card {
        background: #1A1E26;
        border-radius: 20px;
        border: 1px solid rgba(212, 175, 55, 0.15);
        padding: 24px;
        display: flex;
        align-items: center;
        gap: 20px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        transition: all 0.3s;
    }
    
    .stat-card:hover {
        transform: translateY(-4px);
        border-color: rgba(212, 175, 55, 0.4);
        box-shadow: 0 16px 32px rgba(212, 175, 55, 0.2);
    }
    
    .stat-icon {
        width: 60px;
        height: 60px;
        border-radius: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        background: #252B36;
        border: 1px solid rgba(212, 175, 55, 0.2);
    }
    
    .stat-content {
        flex: 1;
    }
    
    .stat-card .stat-value {
        font-size: 28px;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 4px;
    }
    
    .stat-card .stat-label {
        font-size: 14px;
        color: #9CA3AF;
    }

    /* ===== CHARTS ===== */
    .charts-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 28px;
        margin-bottom: 28px;
    }
    
    .chart-card {
        background: #1A1E26;
        border-radius: 20px;
        border: 1px solid rgba(212, 175, 55, 0.15);
        padding: 26px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
    }
    
    .chart-card.full-width {
        grid-column: span 2;
    }
    
    .chart-title {
        font-size: 18px;
        font-weight: 600;
        color: #FFFFFF;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .chart-title svg {
        color: #D4AF37;
    }

    /* ===== LEADERBOARD ===== */
    .leaderboard-table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .leaderboard-table th {
        background: #252B36;
        padding: 18px;
        text-align: left;
        font-weight: 600;
        color: #9CA3AF;
        font-size: 13px;
        text-transform: uppercase;
        border-bottom: 3px solid #D4AF37;
    }
    
    .leaderboard-table td {
        padding: 18px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .rank-badge {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 15px;
    }
    
    .rank-1 {
        background: #D4AF37;
        color: #0F1218;
        box-shadow: 0 4px 12px rgba(212, 175, 55, 0.4);
    }
    
    .rank-2 {
        background: #9CA3AF;
        color: #0F1218;
    }
    
    .rank-3 {
        background: #B76E79;
        color: #FFFFFF;
    }
    
    .rank-other {
        background: #252B36;
        color: #9CA3AF;
    }
    
    .provider-color {
        width: 4px;
        height: 36px;
        border-radius: 2px;
    }

    /* ===== KPI CARDS ===== */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 24px;
        margin-bottom: 32px;
    }
    
    .kpi-card {
        background: #1A1E26;
        border-radius: 24px;
        border: 1px solid rgba(212, 175, 55, 0.15);
        padding: 28px;
        text-align: center;
        transition: all 0.3s;
    }
    
    .kpi-card:hover {
        transform: translateY(-4px);
        border-color: rgba(212, 175, 55, 0.4);
    }
    
    .kpi-icon {
        font-size: 38px;
        margin-bottom: 16px;
    }
    
    .kpi-value {
        font-size: 34px;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 6px;
    }
    
    .kpi-label {
        font-size: 14px;
        color: #9CA3AF;
    }
    
    .kpi-trend {
        font-size: 13px;
        margin-top: 12px;
        padding: 6px 14px;
        border-radius: 30px;
        display: inline-block;
        font-weight: 600;
    }
    
    .kpi-trend.up {
        background: rgba(16, 185, 129, 0.15);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .kpi-trend.down {
        background: rgba(239, 68, 68, 0.15);
        color: #EF4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    /* ===== WINNER CARD ===== */
    .winner-card {
        background: linear-gradient(145deg, rgba(212, 175, 55, 0.15), rgba(212, 175, 55, 0.05));
        border: 2px solid rgba(212, 175, 55, 0.4);
        box-shadow: 0 16px 32px rgba(212, 175, 55, 0.2);
    }

    /* ===== COMPARISON ===== */
    .comparison-grid {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: 32px;
    }
    
    .comparison-card {
        background: #1A1E26;
        border-radius: 24px;
        border: 1px solid rgba(212, 175, 55, 0.15);
        padding: 28px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
    }
    
    .comparison-vs {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        font-weight: 800;
        color: #D4AF37;
        text-shadow: 0 4px 12px rgba(212, 175, 55, 0.4);
    }
    
    .comparison-name {
        font-size: 22px;
        font-weight: 600;
        color: #FFFFFF;
    }

    /* ===== ACHIEVEMENTS ===== */
    .achievement-badge {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 16px;
        background: rgba(212, 175, 55, 0.1);
        border: 1px solid rgba(212, 175, 55, 0.3);
        border-radius: 40px;
        font-size: 12px;
        color: #D4AF37;
        font-weight: 500;
    }

    /* ===== WHATSAPP REPORT ===== */
    .whatsapp-box {
        background: #1A1E26;
        border: 2px solid #10B981;
        border-radius: 20px;
        padding: 28px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
    }
    
    .whatsapp-title {
        font-size: 18px;
        font-weight: 600;
        color: #10B981;
    }
    
    .whatsapp-content {
        font-family: 'Courier New', monospace;
        background: #252B36;
        padding: 20px;
        border-radius: 14px;
        color: #E5E7EB;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    
    .copy-btn {
        background: #10B981;
        color: #0F1218;
        padding: 14px;
        border: none;
        border-radius: 14px;
        font-weight: 600;
        font-size: 15px;
        cursor: pointer;
        transition: all 0.3s;
        margin-top: 16px;
    }
    
    .copy-btn:hover {
        background: #0E9F6E;
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3);
    }

    /* ===== CALENDAR ===== */
    .premium-calendar {
        background: #1A1E26;
        border-radius: 24px;
        border: 1px solid rgba(212, 175, 55, 0.15);
        padding: 28px;
    }
    
    .weekday-label {
        color: #D4AF37;
        font-weight: 600;
        font-size: 13px;
    }
    
    .cal-cell {
        background: #252B36;
        border: 2px solid transparent;
        transition: all 0.3s;
    }
    
    .cal-cell:hover {
        border-color: #D4AF37;
        transform: translateY(-4px);
    }
    
    .cal-cell.level-5 {
        background: linear-gradient(145deg, rgba(212, 175, 55, 0.3), rgba(212, 175, 55, 0.1));
        border: 2px solid #D4AF37;
    }

    /* ===== DAILY REGION ===== */
    .provider-section {
        background: #1A1E26;
        border-radius: 20px;
        border: 1px solid rgba(212, 175, 55, 0.15);
        margin-bottom: 24px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    }
    
    .provider-header-dr {
        padding: 20px 24px;
        border-bottom: 1px solid rgba(212, 175, 55, 0.15);
        cursor: pointer;
        transition: background 0.3s;
    }
    
    .provider-header-dr:hover {
        background: rgba(212, 175, 55, 0.05);
    }
    
    .region-table th {
        background: rgba(212, 175, 55, 0.1);
        color: #9CA3AF;
        padding: 14px;
    }

    /* ===== RESPONSIVE ===== */
    @media (max-width: 1200px) {
        .charts-grid { grid-template-columns: 1fr; }
        .stats-row { grid-template-columns: repeat(2, 1fr); }
        .stats-row-5 { grid-template-columns: repeat(3, 1fr); }
        .kpi-grid { grid-template-columns: repeat(2, 1fr); }
        .comparison-grid { grid-template-columns: 1fr; }
        .comparison-vs { display: none; }
    }
    
    @media (max-width: 768px) {
        .sidebar { width: 80px; }
        .main-content { margin-left: 80px; padding: 20px; }
        .stats-row, .stats-row-5, .kpi-grid { grid-template-columns: 1fr; }
    }
</style>
"""
SHARED_JS = """
<script>
// ===== SHARED DATE UTILITIES =====
function getISOWeek(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}

function formatWeight(w) {
    if (w === undefined || w === null || w === 0) return '-';
    const r = Math.round(w * 10) / 10;
    return r % 1 === 0 ? Math.round(r).toString() : r.toFixed(1);
}

function fmtIso(date) { return date.toISOString().split('T')[0]; }

function fmtDisp(date, includeYear) {
    if (includeYear === false) return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function getMonday(date) {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(d.setDate(diff));
}

// ===== DATE RANGE PICKER STATE =====
let dpStart = null;
let dpEnd = null;

function dpInit(defaultPeriod) {
    defaultPeriod = defaultPeriod || 'week';
    const today = new Date(); today.setHours(0,0,0,0);
    if (defaultPeriod === 'today') {
        dpStart = new Date(today); dpEnd = new Date(today);
    } else if (defaultPeriod === '7d') {
        dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 6);
    } else if (defaultPeriod === 'week') {
        dpStart = getMonday(today); dpEnd = new Date(dpStart); dpEnd.setDate(dpEnd.getDate() + 6);
    } else if (defaultPeriod === 'month') {
        dpStart = new Date(today.getFullYear(), today.getMonth(), 1);
        dpEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    }
    document.getElementById('dpStart').value = fmtIso(dpStart);
    document.getElementById('dpEnd').value = fmtIso(dpEnd);
    document.querySelectorAll('.qbtn').forEach(b => {
        b.classList.toggle('active', b.dataset.period === defaultPeriod);
    });
    dpUpdateBadge();
}

function dpSetQuick(btn, period) {
    const today = new Date(); today.setHours(0,0,0,0);
    document.querySelectorAll('.qbtn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    switch(period) {
        case 'today': dpStart = new Date(today); dpEnd = new Date(today); break;
        case '7d': dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 6); break;
        case '15d': dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 14); break;
        case '30d': dpEnd = new Date(today); dpStart = new Date(today); dpStart.setDate(dpStart.getDate() - 29); break;
        case 'week': dpStart = getMonday(today); dpEnd = new Date(dpStart); dpEnd.setDate(dpEnd.getDate() + 6); break;
        case 'month': dpStart = new Date(today.getFullYear(), today.getMonth(), 1); dpEnd = new Date(today.getFullYear(), today.getMonth()+1, 0); break;
    }
    document.getElementById('dpStart').value = fmtIso(dpStart);
    document.getElementById('dpEnd').value = fmtIso(dpEnd);
    dpUpdateBadge();
    loadData();
}

function dpApply() {
    const sv = document.getElementById('dpStart').value;
    const ev = document.getElementById('dpEnd').value;
    if (!sv || !ev) { alert('Please select both dates'); return; }
    dpStart = new Date(sv + 'T00:00:00');
    dpEnd = new Date(ev + 'T00:00:00');
    if (dpStart > dpEnd) { alert('Start date must be before end date'); return; }
    document.querySelectorAll('.qbtn').forEach(b => b.classList.remove('active'));
    dpUpdateBadge();
    loadData();
}

function dpUpdateBadge() {
    const badge = document.getElementById('dpBadge');
    if (!badge || !dpStart || !dpEnd) return;
    const wk = getISOWeek(dpStart);
    const days = Math.round((dpEnd - dpStart) / 86400000) + 1;
    let txt = 'Week ' + wk + ' • ';
    if (days === 1) {
        txt += fmtDisp(dpStart, true);
    } else if (days <= 31 && dpStart.getFullYear() === dpEnd.getFullYear()) {
        txt += fmtDisp(dpStart, false) + ' – ' + fmtDisp(dpEnd, true);
        if (days !== 7) txt += ' (' + days + 'd)';
    } else {
        txt += fmtDisp(dpStart, true) + ' – ' + fmtDisp(dpEnd, true);
    }
    badge.textContent = txt;
}

function dpParams() {
    return 'start_date=' + fmtIso(dpStart) + '&end_date=' + fmtIso(dpEnd);
}

function getStarRating(stars) { return '★'.repeat(stars) + '☆'.repeat(5 - stars); }
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

SIDEBAR_HTML = """
<nav class="sidebar" id="sidebar">
    <div class="sidebar-toggle" onclick="toggleSidebar()">«</div>
    <div class="sidebar-header">
        <div class="logo-icon">3P</div>
        <span class="logo-text">3PL Dashboard</span>
    </div>
    <div class="nav-menu">
        <div class="nav-section">
            <div class="nav-section-title">Main</div>
            <a href="/" class="nav-item {active_dashboard}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
                <span>Dashboard</span><div class="tooltip">Dashboard</div>
            </a>
            <a href="/weekly-summary" class="nav-item {active_weekly}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                <span>Weekly Summary</span><div class="tooltip">Weekly Summary</div>
            </a>
            <a href="/daily-region" class="nav-item {active_daily_region}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                <span>Daily Region</span><div class="tooltip">Daily Region</div>
            </a>
            <a href="/flight-load" class="nav-item {active_flight}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
                <span>Flight Load</span><div class="tooltip">Flight Load</div>
            </a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">Analytics</div>
            <a href="/analytics" class="nav-item {active_analytics}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" /></svg>
                <span>Analytics</span><div class="tooltip">Analytics</div>
            </a>
            <a href="/kpi" class="nav-item {active_kpi}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
                <span>KPI Dashboard</span><div class="tooltip">KPI Dashboard</div>
            </a>
            <a href="/comparison" class="nav-item {active_comparison}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                <span>Comparison</span><div class="tooltip">Comparison</div>
            </a>
            <a href="/regions" class="nav-item {active_regions}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>Region Heatmap</span><div class="tooltip">Region Heatmap</div>
            </a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">Reports</div>
            <a href="/monthly" class="nav-item {active_monthly}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <span>Monthly Report</span><div class="tooltip">Monthly Report</div>
            </a>
            <a href="/calendar" class="nav-item {active_calendar}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <span>Calendar View</span><div class="tooltip">Calendar View</div>
            </a>
            <a href="/whatsapp" class="nav-item {active_whatsapp}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                <span>WhatsApp Report</span><div class="tooltip">WhatsApp Report</div>
            </a>
        </div>
        <div class="nav-section">
            <div class="nav-section-title">Achievements</div>
            <a href="/achievements" class="nav-item {active_achievements}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
                <span>Achievements</span><div class="tooltip">Achievements</div>
            </a>
        </div>
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
document.addEventListener('DOMContentLoaded', function() {
    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (isCollapsed) {
        document.getElementById('sidebar').classList.add('collapsed');
        document.getElementById('main-content').classList.add('expanded');
    }
});
</script>
"""

def sidebar(active):
    keys = ['dashboard','weekly','daily_region','flight','analytics','kpi','comparison','regions','monthly','calendar','whatsapp','achievements']
    kwargs = {f'active_{k}': ('active' if k == active else '') for k in keys}
    return SIDEBAR_HTML.format(**kwargs)

# ===== ROUTES =====

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid password. Please try again.'
    return render_template_string('''
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login - 3PL Dashboard</title>''' + FAVICON + BASE_STYLES + '''</head><body>
<div class="login-container"><div class="login-card">
<div class="login-logo">3P</div>
<h1 class="login-title">Welcome Back</h1>
<p class="login-subtitle">Enter your password to access the dashboard</p>
{% if error %}<div class="error-message">{{ error }}</div>{% endif %}
<form class="login-form" method="POST">
<div class="form-group"><label class="form-label">Password</label>
<input type="password" name="password" class="form-input" placeholder="Enter your password" autofocus required></div>
<button type="submit" class="login-btn">Sign In</button>
</form></div></div></body></html>''', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3PL Dashboard</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('dashboard') + '''
<main class="main-content" id="main-content">
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
    } catch(e) { document.getElementById('dashboard-content').innerHTML = '<p style="color:#ef4444;padding:20px">Error loading data: '+e.message+'</p>'; }
}

function renderProvider(provider) {
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
            const fc = flightDays.includes(i) ? ' style="background:rgba(212,168,83,0.03)"' : '';
            if (d.orders > 0) {
                // Har day ke liye exact date nikaalo (dpStart se)
const dayIndex = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(day);
const dayDate = new Date(dpStart);
dayDate.setDate(dayDate.getDate() + dayIndex);
const dateStr = fmtIso(dayDate);

rowsHtml += `<td class="day-cell"${fc}>
    <div class="day-data">
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="orders">${d.orders}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="boxes">${d.boxes}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="weight">${formatWeight(d.weight)}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="under20">${d.under20}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${dateStr}&end=${dateStr}&region=${encodeURIComponent(region)}&day=${dateStr}" class="over20">${d.over20}</a>
    </div>
</td>`;            } else {
                rowsHtml += `<td class="day-cell"${fc}><span class="day-data-empty">-</span></td>`;
            }
        });
        rowsHtml += '</tr>';
    }
    rowsHtml += '<tr class="total-row"><td class="region-col">TOTAL</td>';
    days.forEach((day,i) => {
        const t = totals[day];
        const fc = flightDays.includes(i) ? ' style="background:rgba(212,168,83,0.15)"' : '';
        rowsHtml += `<td class="day-cell"${fc}>
    <div class="day-data">
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtIso(dpStart)}&end=${fmtIso(dpEnd)}" class="orders">${t.o}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtIso(dpStart)}&end=${fmtIso(dpEnd)}" class="boxes">${t.b}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtIso(dpStart)}&end=${fmtIso(dpEnd)}" class="weight">${formatWeight(t.w)}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtIso(dpStart)}&end=${fmtIso(dpEnd)}" class="under20">${t.u}</a>
        <a href="/orders?provider=${encodeURIComponent(provider.short)}&start=${fmtIso(dpStart)}&end=${fmtIso(dpEnd)}" class="over20">${t.v}</a>
    </div>
</td>`;
    });
    rowsHtml += '</tr>';
    const subHdr = days.map((_,i) => `<th${flightDays.includes(i)?' style="background:rgba(212,168,83,0.06)"':''}><div class="sub-header"><span>O</span><span>B</span><span>W</span><span>&lt;20</span><span>20+</span></div></th>`).join('');
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
</div>
<div style="overflow-x:auto"><table class="data-table"><thead>
<tr><th class="region-col" rowspan="2">Region</th>${dayHdrs}</tr>
<tr class="sub-header-row">${subHdr}</tr>
</thead><tbody>${rowsHtml}</tbody></table></div></div>`;
}

dpInit('week');
loadData();
</script></body></html>''')

@app.route('/weekly-summary')
@login_required
def weekly_summary():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Summary - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('weekly') + '''
<main class="main-content" id="main-content">
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
        if (data.winner) {
            let achHtml = '';
            if (data.winner.achievements && data.winner.achievements.length > 0) {
                achHtml = '<div class="achievements-row" style="margin-top:12px">' + data.winner.achievements.map(a=>`<div class="achievement-badge"><span class="badge-icon">${a.icon}</span>${a.name}</div>`).join('') + '</div>';
            }
            html += `<div class="provider-card winner-card"><div class="card-header"><div class="provider-info">
<span style="font-size:32px;margin-right:12px">🏆</span><div>
<div class="provider-name" style="font-size:24px">Week Winner: ${data.winner.name}</div>
<div style="color:#d4a853;margin-top:4px">${data.winner.total_boxes.toLocaleString()} boxes • ${formatWeight(data.winner.total_weight)} kg</div>
${achHtml}</div></div></div></div>`;
        }
        html += `<div class="provider-card"><div class="card-header"><div class="provider-info"><span class="provider-name">Provider Leaderboard</span></div></div>
<table class="leaderboard-table"><thead><tr><th style="width:60px">Rank</th><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th><th style="text-align:right">Trend</th></tr></thead><tbody>`;
        data.providers.forEach((p,i) => {
            const rc = i < 3 ? 'rank-'+(i+1) : 'rank-other';
            const tc = p.trend.direction === 'up' ? 'up' : 'down';
            const ti = p.trend.direction === 'up' ? '▲' : '▼';
            html += `<tr><td><div class="rank-badge ${rc}">${i+1}</div></td><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td><td style="text-align:right;font-weight:600">${p.total_orders.toLocaleString()}</td><td style="text-align:right;font-weight:600">${p.total_boxes.toLocaleString()}</td><td style="text-align:right;font-weight:600">${formatWeight(p.total_weight)}</td><td style="text-align:right"><span class="trend-badge ${tc}">${ti} ${p.trend.percentage}%</span></td></tr>`;
        });
        html += '</tbody></table></div>';
        document.getElementById('content').innerHTML = html;
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''')

@app.route('/daily-region')
@login_required
def daily_region():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Region - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('daily_region') + '''
<main class="main-content" id="main-content">
<div class="page-header">
    <h1 class="page-title">Daily <span>Region Summary</span></h1>
    ''' + DATE_PICKER_HTML('today') + '''
</div>
<div class="stats-row-5">
<div class="stat-card"><div class="stat-icon" style="background:rgba(59,130,246,0.1)">📦</div><div class="stat-content"><div class="stat-value" id="t-orders">-</div><div class="stat-label">Total Orders</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(16,185,129,0.1)">📮</div><div class="stat-content"><div class="stat-value" id="t-boxes">-</div><div class="stat-label">Total Boxes</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(245,158,11,0.1)">⚖️</div><div class="stat-content"><div class="stat-value" id="t-weight">-</div><div class="stat-label">Total Weight</div></div></div>
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
    header.classList.toggle('open');
    body.classList.toggle('open');
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
            document.getElementById('content').innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><h3>No Data</h3><p>No shipments for selected period</p></div>';
            return;
        }
        const medals = ['🥇','🥈','🥉'];
        let html = '';
        data.providers.forEach((provider, idx) => {
            html += `<div class="provider-section">
<div class="provider-header-dr" id="hdr-${idx}" onclick="toggleProvider(${idx})">
<div class="provider-header-left">
<div class="provider-color-bar" style="background:${provider.color}"></div>
<div class="provider-header-info"><h3>${provider.name}</h3><span>${provider.regions.length} regions</span></div>
</div>
<div class="provider-header-stats">
<div class="header-stat"><div class="header-stat-val">${provider.orders}</div><div class="header-stat-lbl">Orders</div></div>
<div class="header-stat"><div class="header-stat-val">${provider.boxes}</div><div class="header-stat-lbl">Boxes</div></div>
<div class="header-stat"><div class="header-stat-val">${formatWeight(provider.weight)}</div><div class="header-stat-lbl">Weight</div></div>
<span class="toggle-icon">▼</span>
</div></div>
<div class="provider-body" id="bdy-${idx}">`;
            if (provider.regions.length > 0) {
                html += '<table class="region-table"><thead><tr><th>Region</th><th>Orders</th><th>Boxes</th><th>Weight</th><th>&lt;20 kg</th><th>20+ kg</th></tr></thead><tbody>';
                provider.regions.forEach((rg,i) => {
                    const medal = i < 3 ? `<span class="medal">${medals[i]}</span>` : '';
                    html += `<tr><td>${medal}${rg.name}</td><td>${rg.orders}</td><td>${rg.boxes}</td><td>${formatWeight(rg.weight)}</td><td style="color:#22c55e">${rg.under20}</td><td style="color:#ef4444">${rg.over20}</td></tr>`;
                });
                html += '</tbody></table>';
            } else {
                html += '<p style="color:#64748b;text-align:center;padding:20px">No data</p>';
            }
            html += '</div></div>';
        });
        document.getElementById('content').innerHTML = html;
        if (data.providers.length > 0) toggleProvider(0);
    } catch(e) { document.getElementById('content').innerHTML = '<div class="empty-state"><div class="empty-state-icon">❌</div><h3>Error</h3><p>'+e.message+'</p></div>'; }
}
dpInit('today'); loadData();
</script></body></html>''')

@app.route('/flight-load')
@login_required
def flight_load():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flight Load - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('flight') + '''
<main class="main-content" id="main-content">
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
        for (const flight of data.flights) {
            html += `<div class="provider-card"><div class="card-header"><div class="provider-info"><span style="font-size:24px;margin-right:12px">✈️</span><span class="provider-name">${flight.name}</span></div>
<div class="card-stats">
<div class="stat-item"><div class="stat-value">${flight.total_orders.toLocaleString()}</div><div class="stat-label">Orders</div></div>
<div class="stat-item"><div class="stat-value">${flight.total_boxes.toLocaleString()}</div><div class="stat-label">Boxes</div></div>
<div class="stat-item"><div class="stat-value">${formatWeight(flight.total_weight)} kg</div><div class="stat-label">Weight</div></div>
</div></div>
<table class="leaderboard-table"><thead><tr><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th></tr></thead><tbody>`;
            for (const p of flight.providers) {
                html += `<tr><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div><span>${p.name}</span></div></td><td style="text-align:right">${p.orders.toLocaleString()}</td><td style="text-align:right">${p.boxes.toLocaleString()}</td><td style="text-align:right">${formatWeight(p.weight)}</td></tr>`;
            }
            html += '</tbody></table></div>';
        }
        document.getElementById('content').innerHTML = html;
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''')

@app.route('/analytics')
@login_required
def analytics():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Analytics - 3PL</title>''' + FAVICON + '''<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>''' + BASE_STYLES + '''</head><body>
''' + sidebar('analytics') + '''
<main class="main-content" id="main-content">
<div class="page-header">
    <h1 class="page-title">Analytics & <span>Insights</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div class="stats-row-5">
<div class="stat-card"><div class="stat-icon" style="background:rgba(59,130,246,0.1)">📋</div><div class="stat-content"><div class="stat-value" id="t-orders">0</div><div class="stat-label">Total Orders</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(16,185,129,0.1)">📦</div><div class="stat-content"><div class="stat-value" id="t-boxes">0</div><div class="stat-label">Total Boxes</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(212,168,83,0.1)">⚖️</div><div class="stat-content"><div class="stat-value" id="t-weight">0</div><div class="stat-label">Total Weight (kg)</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(34,197,94,0.1)">🪶</div><div class="stat-content"><div class="stat-value" id="t-under20">0</div><div class="stat-label">Light (&lt;20 kg)</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(239,68,68,0.1)">🏋️</div><div class="stat-content"><div class="stat-value" id="t-over20">0</div><div class="stat-label">Heavy (20+ kg)</div></div></div>
</div>
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
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';

function destroyCharts() { Object.values(charts).forEach(c => c && c.destroy()); charts = {}; }

async function loadData() {
    destroyCharts();
    try {
        const r = await fetch('/api/analytics-data?' + dpParams());
        const data = await r.json();
        document.getElementById('t-orders').textContent = data.totals.orders.toLocaleString();
        document.getElementById('t-boxes').textContent = data.totals.boxes.toLocaleString();
        document.getElementById('t-weight').textContent = formatWeight(data.totals.weight);
        document.getElementById('t-under20').textContent = data.totals.under20.toLocaleString();
        document.getElementById('t-over20').textContent = data.totals.over20.toLocaleString();
        charts.trend = new Chart(document.getElementById('trendChart'), { type:'line', data:{ labels:data.trend.labels, datasets:[{label:'Orders',data:data.trend.orders,borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,0.1)',fill:true,tension:0.4,pointRadius:4},{label:'Boxes',data:data.trend.boxes,borderColor:'#10b981',backgroundColor:'rgba(16,185,129,0.1)',fill:true,tension:0.4,pointRadius:4}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top'}},scales:{y:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.05)'}},x:{grid:{display:false}}}}});
        charts.provider = new Chart(document.getElementById('providerChart'), { type:'doughnut', data:{labels:data.providers.map(p=>p.name),datasets:[{data:data.providers.map(p=>p.boxes),backgroundColor:data.providers.map(p=>p.color+'CC'),borderColor:'#0a0a0f',borderWidth:3}]}, options:{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{legend:{position:'right',labels:{padding:12,usePointStyle:true}}}}});
        const topR = data.regions.slice(0,8);
        charts.region = new Chart(document.getElementById('regionChart'), { type:'bar', data:{labels:topR.map(r=>r.name),datasets:[{label:'Boxes',data:topR.map(r=>r.boxes),backgroundColor:'#d4a85399',borderColor:'#d4a853',borderWidth:2,borderRadius:6}]}, options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.05)'}},y:{grid:{display:false}}}}});
        const wR = data.regions.slice(0,6);
        charts.weightRegion = new Chart(document.getElementById('weightRegionChart'), { type:'bar', data:{labels:wR.map(r=>r.name),datasets:[{label:'<20 kg',data:wR.map(r=>r.under20),backgroundColor:'rgba(34,197,94,0.7)',borderColor:'#22c55e',borderWidth:1,borderRadius:4},{label:'20+ kg',data:wR.map(r=>r.over20),backgroundColor:'rgba(239,68,68,0.7)',borderColor:'#ef4444',borderWidth:1,borderRadius:4}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top'}},scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,beginAtZero:true,grid:{color:'rgba(255,255,255,0.05)'}}}}});
        charts.weightProvider = new Chart(document.getElementById('weightProviderChart'), { type:'bar', data:{labels:data.providers.map(p=>p.name),datasets:[{label:'<20 kg',data:data.providers.map(p=>p.under20),backgroundColor:'rgba(34,197,94,0.7)',borderColor:'#22c55e',borderWidth:1,borderRadius:4},{label:'20+ kg',data:data.providers.map(p=>p.over20),backgroundColor:'rgba(239,68,68,0.7)',borderColor:'#ef4444',borderWidth:1,borderRadius:4}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top'}},scales:{x:{grid:{display:false}},y:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.05)'}}}}});
    } catch(e) { console.error(e); }
}
dpInit('week'); loadData();
</script></body></html>''')

@app.route('/kpi')
@login_required
def kpi_dashboard():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KPI Dashboard - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('kpi') + '''
<main class="main-content" id="main-content">
<div class="page-header">
    <h1 class="page-title">KPI <span>Dashboard</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
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
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''')

@app.route('/comparison')
@login_required
def comparison():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparison - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('comparison') + '''
<main class="main-content" id="main-content">
<div class="page-header">
    <h1 class="page-title">Provider <span>Comparison</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div class="tabs">
<button class="tab-btn active" onclick="showTab(this,'ge-ecl')">GE vs ECL</button>
<button class="tab-btn" onclick="showTab(this,'qc-zone')">QC vs ZONE</button>
<button class="tab-btn" onclick="showTab(this,'all')">All Providers</button>
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
let curTab = 'ge-ecl'; let curData = null;
function showTab(btn, tab) {
    curTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderComparison();
}
function renderCard(p1, p2) {
    const stats = ['total_orders','total_boxes','total_weight'];
    const labels = ['Orders','Boxes','Weight (kg)'];
    let s1='',s2='';
    stats.forEach((s,i) => {
        const v1=p1[s], v2=p2[s];
        const w1 = v1>v2 ? '<span class="winner-indicator">👑</span>' : '';
        const w2 = v2>v1 ? '<span class="winner-indicator">👑</span>' : '';
        const f1 = s==='total_weight' ? formatWeight(v1) : v1.toLocaleString();
        const f2 = s==='total_weight' ? formatWeight(v2) : v2.toLocaleString();
        s1+=`<div class="comparison-stat"><span class="comparison-stat-label">${labels[i]}</span><span class="comparison-stat-value">${f1}${w1}</span></div>`;
        s2+=`<div class="comparison-stat"><span class="comparison-stat-label">${labels[i]}</span><span class="comparison-stat-value">${f2}${w2}</span></div>`;
    });
    return `<div class="comparison-grid"><div class="comparison-card"><div class="comparison-header"><div class="comparison-color" style="background:${p1.color}"></div><div class="comparison-name">${p1.short||p1.name}</div></div>${s1}</div><div class="comparison-vs">VS</div><div class="comparison-card"><div class="comparison-header"><div class="comparison-color" style="background:${p2.color}"></div><div class="comparison-name">${p2.short||p2.name}</div></div>${s2}</div></div>`;
}
function renderComparison() {
    if (!curData) return;
    const ps = curData.providers; let html = '';
    if (curTab === 'ge-ecl') {
        const ge = ps.filter(p=>p.group==='GE'); const ecl = ps.filter(p=>p.group==='ECL');
        const geT = {name:'GE Total',short:'GE Total',color:'#3B82F6',total_orders:ge.reduce((s,p)=>s+p.total_orders,0),total_boxes:ge.reduce((s,p)=>s+p.total_boxes,0),total_weight:ge.reduce((s,p)=>s+p.total_weight,0)};
        const eclT = {name:'ECL Total',short:'ECL Total',color:'#10B981',total_orders:ecl.reduce((s,p)=>s+p.total_orders,0),total_boxes:ecl.reduce((s,p)=>s+p.total_boxes,0),total_weight:ecl.reduce((s,p)=>s+p.total_weight,0)};
        html = '<h3 style="color:#d4a853;margin-bottom:20px">Global Express vs ECL Logistics</h3>'+renderCard(geT,eclT);
    } else if (curTab === 'qc-zone') {
        const qc = ps.filter(p=>p.name.includes('QC')); const zn = ps.filter(p=>p.name.includes('ZONE'));
        const qcT = {short:'QC Total',color:'#8B5CF6',total_orders:qc.reduce((s,p)=>s+p.total_orders,0),total_boxes:qc.reduce((s,p)=>s+p.total_boxes,0),total_weight:qc.reduce((s,p)=>s+p.total_weight,0)};
        const znT = {short:'Zone Total',color:'#F59E0B',total_orders:zn.reduce((s,p)=>s+p.total_orders,0),total_boxes:zn.reduce((s,p)=>s+p.total_boxes,0),total_weight:zn.reduce((s,p)=>s+p.total_weight,0)};
        html = '<h3 style="color:#d4a853;margin-bottom:20px">QC Center vs Zone</h3>'+renderCard(qcT,znT);
    } else {
        html = '<div class="provider-card"><table class="leaderboard-table"><thead><tr><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight</th><th style="text-align:right">Avg/Order</th></tr></thead><tbody>';
        ps.sort((a,b)=>b.total_boxes-a.total_boxes).forEach(p => {
            const avg = p.total_orders>0 ? (p.total_weight/p.total_orders).toFixed(1) : 0;
            html+=`<tr><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div>${p.short||p.name}</div></td><td style="text-align:right">${p.total_orders.toLocaleString()}</td><td style="text-align:right">${p.total_boxes.toLocaleString()}</td><td style="text-align:right">${formatWeight(p.total_weight)}</td><td style="text-align:right">${avg} kg</td></tr>`;
        });
        html += '</tbody></table></div>';
    }
    document.getElementById('content').innerHTML = html;
}
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/dashboard?' + dpParams());
        curData = await r.json();
        renderComparison();
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''')

@app.route('/regions')
@login_required
def regions():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Region Heatmap - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('regions') + '''
<main class="main-content" id="main-content">
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
    if(r>=0.8) return '#10b981'; if(r>=0.6) return '#34d399';
    if(r>=0.4) return '#d4a853'; if(r>=0.2) return '#f59e0b'; return '#64748b';
}
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/regions?' + dpParams());
        const data = await r.json();
        const mx = Math.max(...data.regions.map(r=>r.orders)) || 1;
        let html = '<div class="heatmap-container">';
        data.regions.forEach(rg => {
            const c = heatColor(rg.orders,mx);
            html+=`<div class="heatmap-item" style="border-color:${c}40"><div class="heatmap-region">${rg.name}</div><div class="heatmap-value" style="color:${c}">${rg.orders}</div><div class="heatmap-label">orders</div><div class="heatmap-label" style="margin-top:4px">${rg.boxes} boxes • ${formatWeight(rg.weight)} kg</div></div>`;
        });
        html += '</div>';
        document.getElementById('content').innerHTML = html;
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''')

@app.route('/monthly')
@login_required
def monthly_report():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monthly Report - 3PL</title>''' + FAVICON + '''<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>''' + BASE_STYLES + '''</head><body>
''' + sidebar('monthly') + '''
<main class="main-content" id="main-content">
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
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/monthly?' + dpParams());
        const data = await r.json();
        let html = `<div class="stats-row">
<div class="stat-card"><div class="stat-icon" style="background:rgba(59,130,246,0.1)">📋</div><div class="stat-content"><div class="stat-value">${data.total_orders.toLocaleString()}</div><div class="stat-label">Total Orders</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(16,185,129,0.1)">📦</div><div class="stat-content"><div class="stat-value">${data.total_boxes.toLocaleString()}</div><div class="stat-label">Total Boxes</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(212,168,83,0.1)">⚖️</div><div class="stat-content"><div class="stat-value">${formatWeight(data.total_weight)} kg</div><div class="stat-label">Total Weight</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(139,92,246,0.1)">📊</div><div class="stat-content"><div class="stat-value">${Math.round(data.avg_per_day)}</div><div class="stat-label">Avg Orders/Day</div></div></div>
</div>
<div class="charts-grid"><div class="chart-card full-width"><div class="chart-title">Weekly Breakdown</div><div class="chart-container"><canvas id="weeklyChart"></canvas></div></div></div>
<div class="provider-card"><div class="card-header"><div class="provider-info"><span class="provider-name">Provider Monthly Summary</span></div></div>
<table class="leaderboard-table"><thead><tr><th>Provider</th><th style="text-align:right">Orders</th><th style="text-align:right">Boxes</th><th style="text-align:right">Weight (kg)</th></tr></thead><tbody>`;
        data.providers.forEach(p => {
            html+=`<tr><td><div class="provider-cell"><div class="provider-color" style="background:${p.color}"></div>${p.name}</div></td><td style="text-align:right">${p.orders.toLocaleString()}</td><td style="text-align:right">${p.boxes.toLocaleString()}</td><td style="text-align:right">${formatWeight(p.weight)}</td></tr>`;
        });
        html += '</tbody></table></div>';
        document.getElementById('content').innerHTML = html;
        if (chart) chart.destroy();
        chart = new Chart(document.getElementById('weeklyChart'), { type:'bar', data:{labels:data.weeks.map(w=>w.label),datasets:[{label:'Boxes',data:data.weeks.map(w=>w.boxes),backgroundColor:'#d4a85399',borderColor:'#d4a853',borderWidth:2,borderRadius:8}]}, options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,grid:{color:'rgba(255,255,255,0.05)'}},x:{grid:{display:false}}}}});
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error: '+e.message+'</p>'; }
}
dpInit('month'); loadData();
</script></body></html>''')

@app.route('/calendar')
@login_required
def calendar_view():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Calendar View - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('calendar') + '''
<main class="main-content" id="main-content">
<div class="page-header">
    <h1 class="page-title">Calendar <span>View</span></h1>
    ''' + DATE_PICKER_HTML('month') + '''
</div>
<div class="stats-row-5">
<div class="stat-card"><div class="stat-icon" style="background:rgba(59,130,246,0.1);font-size:24px">📦</div><div class="stat-content"><div class="stat-value" id="s-orders">-</div><div class="stat-label">Orders</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(16,185,129,0.1);font-size:24px">📮</div><div class="stat-content"><div class="stat-value" id="s-boxes">-</div><div class="stat-label">Boxes</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(245,158,11,0.1);font-size:24px">⚖️</div><div class="stat-content"><div class="stat-value" id="s-weight">-</div><div class="stat-label">Weight</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(34,197,94,0.1);font-size:24px">🪶</div><div class="stat-content"><div class="stat-value" id="s-light">-</div><div class="stat-label">&lt;20 kg</div></div></div>
<div class="stat-card"><div class="stat-icon" style="background:rgba(239,68,68,0.1);font-size:24px">🏋️</div><div class="stat-content"><div class="stat-value" id="s-heavy">-</div><div class="stat-label">20+ kg</div></div></div>
</div>
<div class="premium-calendar">
<div class="calendar-weekdays"><div class="weekday-label">Mon</div><div class="weekday-label">Tue</div><div class="weekday-label">Wed</div><div class="weekday-label">Thu</div><div class="weekday-label">Fri</div><div class="weekday-label">Sat</div><div class="weekday-label">Sun</div></div>
<div class="calendar-days-grid" id="cal-grid"><div class="loading"><div class="spinner"></div></div></div>
</div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
function getLevel(b,mx) { if(!b) return 0; const r=b/mx; if(r>=0.8) return 5; if(r>=0.6) return 4; if(r>=0.4) return 3; if(r>=0.2) return 2; return 1; }
async function loadData() {
    document.getElementById('cal-grid').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/calendar?' + dpParams());
        const data = await r.json();
        document.getElementById('s-orders').textContent = data.totals.orders.toLocaleString();
        document.getElementById('s-boxes').textContent = data.totals.boxes.toLocaleString();
        document.getElementById('s-weight').textContent = formatWeight(data.totals.weight)+' kg';
        document.getElementById('s-light').textContent = data.totals.under20.toLocaleString();
        document.getElementById('s-heavy').textContent = data.totals.over20.toLocaleString();
        let html = '';
        for(let i=0;i<data.first_weekday;i++) html+='<div class="cal-cell empty"></div>';
        data.days.forEach(d => {
            const lv = getLevel(d.boxes, data.max_boxes||1);
            html+=`<div class="cal-cell level-${lv}"><div class="cal-day-num">${d.day}</div><div class="cal-stat">📦${d.orders}|📮${d.boxes}</div></div>`;
        });
        document.getElementById('cal-grid').innerHTML = html;
    } catch(e) { document.getElementById('cal-grid').innerHTML = '<p style="color:#ef4444">Error</p>'; }
}
dpInit('month'); loadData();
</script></body></html>''')

@app.route('/whatsapp')
@login_required
def whatsapp_report():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WhatsApp Report - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('whatsapp') + '''
<main class="main-content" id="main-content">
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
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/whatsapp?' + dpParams());
        const data = await r.json();
        document.getElementById('content').innerHTML = `<div class="whatsapp-box"><div class="whatsapp-header"><span class="whatsapp-icon">📱</span><span class="whatsapp-title">Report - Ready to Share</span></div><div class="whatsapp-content" id="report-text">${data.report}</div><button class="copy-btn" onclick="copyText(document.getElementById('report-text').textContent)">📋 Copy to Clipboard</button></div>`;
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''')

@app.route('/achievements')
@login_required
def achievements_page():
    return render_template_string('''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Achievements - 3PL</title>''' + FAVICON + BASE_STYLES + '''</head><body>
''' + sidebar('achievements') + '''
<main class="main-content" id="main-content">
<div class="page-header">
    <h1 class="page-title">Provider <span>Achievements</span></h1>
    ''' + DATE_PICKER_HTML('week') + '''
</div>
<div id="content"><div class="loading"><div class="spinner"></div></div></div>
</main>
''' + SIDEBAR_SCRIPT + SHARED_JS + '''
<script>
async function loadData() {
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    try {
        const r = await fetch('/api/dashboard?' + dpParams());
        const data = await r.json();
        let html = '';
        data.providers.forEach(p => {
            const ach = p.achievements || [];
            html+=`<div class="provider-card" style="margin-bottom:16px"><div class="card-header"><div class="provider-info"><div style="background:${p.color};width:8px;height:40px;border-radius:4px"></div><span class="provider-name">${p.name}</span><span style="color:#64748b;font-size:14px">${p.total_boxes.toLocaleString()} boxes</span></div></div>
<div style="padding:20px">${ach.length>0?'<div style="display:flex;flex-wrap:wrap;gap:12px">'+ach.map(a=>`<div style="background:rgba(212,168,83,0.1);border:1px solid rgba(212,168,83,0.2);border-radius:12px;padding:16px;text-align:center;min-width:120px"><div style="font-size:32px;margin-bottom:8px">${a.icon}</div><div style="font-size:14px;font-weight:600;color:#d4a853">${a.name}</div><div style="font-size:11px;color:#64748b;margin-top:4px">${a.desc}</div></div>`).join('')+'</div>':'<div style="color:#64748b;text-align:center;padding:20px">No achievements this period 💪</div>'}</div></div>`;
        });
        document.getElementById('content').innerHTML = html;
    } catch(e) { document.getElementById('content').innerHTML = '<p style="color:#ef4444">Error</p>'; }
}
dpInit('week'); loadData();
</script></body></html>''')

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

@app.route('/api/calendar')
def api_calendar():
    start_date, end_date = parse_date_range(request)
    year = start_date.year; month = start_date.month
    _, num_days = calendar.monthrange(year, month)
    first_day = datetime(year, month, 1)
    first_weekday = first_day.weekday()
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    days_data = {}
    for day in range(1, num_days + 1):
        days_data[day] = {'day': day, 'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0}
    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, num_days, 23, 59, 59)
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
                if not parsed_date or not (month_start <= parsed_date <= month_end):
                    continue
                day = parsed_date.day
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
                days_data[day]['orders'] += 1; days_data[day]['boxes'] += boxes; days_data[day]['weight'] += weight
                if weight < 20: days_data[day]['under20'] += 1
                else: days_data[day]['over20'] += 1
            except:
                continue
    return jsonify({
        'year': year, 'month': month, 'first_weekday': first_weekday,
        'totals': {'orders': sum(d['orders'] for d in days_data.values()), 'boxes': sum(d['boxes'] for d in days_data.values()), 'weight': sum(d['weight'] for d in days_data.values()), 'under20': sum(d['under20'] for d in days_data.values()), 'over20': sum(d['over20'] for d in days_data.values())},
        'max_boxes': max((d['boxes'] for d in days_data.values()), default=1),
        'days': list(days_data.values())
    })

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
@app.route('/orders')
@login_required
def order_details():
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
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Order Details - {{ provider_short }}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    ''' + FAVICON + '''
    <style>
        body { background: #050508; color: #e2e8f0; font-family: 'Plus Jakarta Sans', sans-serif; padding: 20px; }
        h1 { color: #d4a853; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #0f1015; color: #94a3b8; padding: 10px; text-align: left; }
        td { padding: 8px 10px; border-bottom: 1px solid #1e1e2a; }
        tr:hover { background: #1a1b23; }
        .back-btn { display: inline-block; margin-bottom: 20px; padding: 8px 16px; background: #d4a853; color: #0a0a0f; text-decoration: none; border-radius: 6px; }
        .stats { display: flex; gap: 20px; margin-bottom: 20px; }
        .stat-box { background: #0c0d12; padding: 15px; border-radius: 8px; border-left: 4px solid #d4a853; }
    </style>
</head>
<body>
    <a href="javascript:history.back()" class="back-btn">← Back</a>
    <h1>Orders - {{ provider_short }}</h1>
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
</body>
</html>
    ''', orders=orders, provider_short=provider_short, region=region, day=day)
if __name__ == '__main__':
    app.run(debug=True)












