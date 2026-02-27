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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# ============================================
# ADMIN PASSWORD - Rocket2024
# ============================================
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Rocket2024')

# ============================================
# CACHE CONFIGURATION
# ============================================
CACHE = {}
CACHE_DURATION = 300  # 5 minutes

# ============================================
# GOOGLE SHEET CONFIGURATION
# ============================================
SHEET_ID = '1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY'

# ============================================
# 🔒 LOCKED COLUMN MAPPINGS - VERIFIED FROM SCREENSHOTS
# ============================================
PROVIDERS = [
    {
        'name': 'GLOBAL EXPRESS (QC)',
        'short': 'GE QC',
        'sheet': 'GE QC Center & Zone',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'start_row': 2,
        'color': '#3B82F6',
        'group': 'GE'
    },
    {
        'name': 'GLOBAL EXPRESS (ZONE)',
        'short': 'GE ZONE',
        'sheet': 'GE QC Center & Zone',
        'date_col': 10,
        'box_col': 11,
        'weight_col': 14,
        'region_col': 16,
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
        'start_row': 2,
        'color': '#EC4899',
        'group': 'OTHER'
    }
]

INVALID_REGIONS = {'', 'N/A', '#N/A', 'COUNTRY', 'REGION', 'DESTINATION', 'ZONE', 'ORDER', 'FLEEK ID', 'DATE', 'CARTONS'}

# Achievement Badges
ACHIEVEMENTS = {
    'star_5': {'name': '5 Star Week', 'icon': '⭐', 'desc': '1500+ boxes in a week'},
    'star_4': {'name': '4 Star Week', 'icon': '🌟', 'desc': '500+ boxes in a week'},
    'champion': {'name': 'Weekly Champion', 'icon': '🏆', 'desc': 'Won the week'},
    'rocket': {'name': 'Rocket Growth', 'icon': '🚀', 'desc': '50%+ growth from last week'},
    'consistent': {'name': 'Consistent Performer', 'icon': '💪', 'desc': 'Active all 7 days'},
    'heavyweight': {'name': 'Heavyweight', 'icon': '🏋️', 'desc': '5000+ kg in a week'},
    'region_king': {'name': 'Region King', 'icon': '👑', 'desc': 'Most regions covered'},
}

# ============================================
# LOGIN DECORATOR
# ============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_week_range(date=None):
    if date is None:
        date = datetime.now()
    monday = date - timedelta(days=date.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday

def parse_date(date_str):
    if not date_str or str(date_str).strip() in ['', '#N/A', 'N/A', 'DATE']:
        return None
    
    date_str = str(date_str).strip()
    
    formats = [
        '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y',
        '%m/%d/%Y', '%Y/%m/%d', '%d.%m.%Y', '%d-%b-%Y'
    ]
    
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
    if boxes >= 1500:
        return 5
    elif boxes >= 500:
        return 4
    elif boxes >= 100:
        return 3
    else:
        return 2

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
            
            # Track weight categories at provider level
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

# ============================================
# FAVICON - Premium 3PL Gold Badge
# ============================================
FAVICON = '''<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cdefs%3E%3ClinearGradient id='gold' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E%3Cstop offset='0%25' style='stop-color:%23f4d03f'/%3E%3Cstop offset='50%25' style='stop-color:%23d4a853'/%3E%3Cstop offset='100%25' style='stop-color:%23b8942d'/%3E%3C/linearGradient%3E%3C/defs%3E%3Ccircle cx='50' cy='50' r='46' fill='%230a0a0f' stroke='url(%23gold)' stroke-width='4'/%3E%3Ctext x='50' y='42' text-anchor='middle' font-family='Arial Black' font-size='24' font-weight='bold' fill='url(%23gold)'%3E3P%3C/text%3E%3Ctext x='50' y='68' text-anchor='middle' font-family='Arial' font-size='16' font-weight='bold' fill='%23d4a853'%3ELOGISTICS%3C/text%3E%3Ccircle cx='50' cy='50' r='42' fill='none' stroke='%23d4a853' stroke-width='1' opacity='0.3'/%3E%3C/svg%3E">'''

# ============================================
# HTML TEMPLATES
# ============================================

BASE_STYLES = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    body {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background: #050508;
        color: #e2e8f0;
        min-height: 100vh;
    }
    
    /* Sidebar */
    .sidebar {
        position: fixed;
        left: 0;
        top: 0;
        height: 100vh;
        width: 280px;
        background: linear-gradient(180deg, #0a0a0f 0%, #0c0d12 100%);
        border-right: 1px solid rgba(212, 168, 83, 0.1);
        padding: 24px 16px;
        transition: all 0.3s ease;
        z-index: 100;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
    
    .sidebar.collapsed {
        width: 70px;
    }
    
    .sidebar-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding-bottom: 24px;
        border-bottom: 1px solid rgba(212, 168, 83, 0.1);
        margin-bottom: 24px;
    }
    
    .logo-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #d4a853 0%, #b8942d 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: #0a0a0f;
        font-size: 18px;
        flex-shrink: 0;
    }
    
    .logo-text {
        font-size: 18px;
        font-weight: 700;
        color: #d4a853;
        white-space: nowrap;
        overflow: hidden;
        transition: opacity 0.3s;
    }
    
    .sidebar.collapsed .logo-text {
        opacity: 0;
        width: 0;
    }
    
    .nav-section {
        margin-bottom: 16px;
    }
    
    .nav-section-title {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #64748b;
        padding: 8px 16px;
        margin-bottom: 4px;
    }
    
    .sidebar.collapsed .nav-section-title {
        opacity: 0;
    }
    
    .nav-menu {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex-grow: 1;
    }
    
    .nav-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        border-radius: 8px;
        color: #64748b;
        text-decoration: none;
        transition: all 0.2s;
        cursor: pointer;
        position: relative;
        font-size: 14px;
    }
    
    .nav-item:hover {
        background: rgba(212, 168, 83, 0.1);
        color: #d4a853;
    }
    
    .nav-item.active {
        background: rgba(212, 168, 83, 0.15);
        color: #d4a853;
    }
    
    .nav-item svg {
        width: 18px;
        height: 18px;
        flex-shrink: 0;
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
        background: #1a1b23;
        color: #e2e8f0;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s;
        border: 1px solid rgba(212, 168, 83, 0.2);
        z-index: 1000;
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
        background: #d4a853;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        border: 2px solid #0a0a0f;
        color: #0a0a0f;
        font-size: 12px;
        font-weight: bold;
        transition: transform 0.3s;
    }
    
    .sidebar.collapsed .sidebar-toggle {
        transform: translateY(-50%) rotate(180deg);
    }
    
    .sidebar-footer {
        border-top: 1px solid rgba(212, 168, 83, 0.1);
        padding-top: 16px;
        margin-top: auto;
    }
    
    .logout-btn {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 16px;
        border-radius: 8px;
        color: #ef4444;
        text-decoration: none;
        transition: all 0.2s;
        cursor: pointer;
        width: 100%;
        border: none;
        background: none;
        font-family: inherit;
        font-size: 14px;
    }
    
    .logout-btn:hover {
        background: rgba(239, 68, 68, 0.1);
    }
    
    .logout-btn svg {
        width: 18px;
        height: 18px;
        flex-shrink: 0;
    }
    
    .sidebar.collapsed .logout-btn span {
        opacity: 0;
        width: 0;
    }
    
    /* Main Content */
    .main-content {
        margin-left: 280px;
        padding: 24px;
        transition: margin-left 0.3s;
        min-height: 100vh;
    }
    
    .main-content.expanded {
        margin-left: 70px;
    }
    
    /* Header */
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
        flex-wrap: wrap;
        gap: 16px;
    }
    
    .page-title {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
    }
    
    .page-title span {
        color: #d4a853;
    }
    
    /* Week Selector */
    .week-selector {
        display: flex;
        align-items: center;
        gap: 12px;
        background: #0c0d12;
        padding: 8px 16px;
        border-radius: 12px;
        border: 1px solid rgba(212, 168, 83, 0.2);
    }
    
    .week-btn {
        background: none;
        border: none;
        color: #d4a853;
        cursor: pointer;
        padding: 8px;
        border-radius: 6px;
        transition: background 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .week-btn:hover {
        background: rgba(212, 168, 83, 0.1);
    }
    
    .week-display {
        font-size: 14px;
        font-weight: 500;
        color: #e2e8f0;
        min-width: 200px;
        text-align: center;
    }
    
    /* Cards */
    .provider-card {
        background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 24px;
        overflow: hidden;
    }
    
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 24px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        position: relative;
    }
    
    .card-header::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
    }
    
    .provider-info {
        display: flex;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
    }
    
    .provider-name {
        font-size: 18px;
        font-weight: 600;
        color: #ffffff;
    }
    
    .star-rating {
        color: #d4a853;
        font-size: 14px;
        letter-spacing: 2px;
    }
    
    .trend-badge {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    
    .trend-badge.up {
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
    }
    
    .trend-badge.down {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
    }
    
    .trend-badge.neutral {
        background: rgba(100, 116, 139, 0.1);
        color: #94a3b8;
    }
    
    .card-stats {
        display: flex;
        gap: 24px;
        flex-wrap: wrap;
    }
    
    .stat-item {
        text-align: center;
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 8px;
    }
    
    .stat-value {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
    }
    
    .stat-label {
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Data Table */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }
    
    .data-table th {
        background: rgba(212, 168, 83, 0.05);
        padding: 12px 8px;
        text-align: center;
        font-weight: 600;
        color: #94a3b8;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .data-table th.region-col {
        text-align: left;
        padding-left: 24px;
        min-width: 120px;
    }
    
    .data-table th.flight-day {
        background: rgba(212, 168, 83, 0.1);
        color: #d4a853;
    }
    
    .data-table td {
        padding: 10px 8px;
        text-align: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        color: #94a3b8;
    }
    
    .data-table td.region-col {
        text-align: left;
        padding-left: 24px;
        font-weight: 500;
        color: #e2e8f0;
    }
    
    .data-table tr:hover td {
        background: rgba(212, 168, 83, 0.03);
    }
    
    .data-table tr.total-row td {
        background: rgba(212, 168, 83, 0.08);
        font-weight: 600;
        color: #d4a853;
        border-top: 2px solid rgba(212, 168, 83, 0.2);
    }
    
    .sub-header {
        font-size: 9px;
        color: #64748b;
        display: flex;
        justify-content: center;
        gap: 4px;
    }
    
    .sub-header span {
        min-width: 24px;
    }
    
    .day-data {
        display: flex;
        justify-content: center;
        gap: 4px;
        font-size: 12px;
    }
    
    .day-data span {
        min-width: 24px;
    }
    
    /* Chart Styles */
    .charts-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 24px;
        margin-bottom: 24px;
    }
    
    @media (max-width: 1200px) {
        .charts-grid {
            grid-template-columns: 1fr;
        }
    }
    
    .chart-card {
        background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 24px;
    }
    
    .chart-card.full-width {
        grid-column: span 2;
    }
    
    @media (max-width: 1200px) {
        .chart-card.full-width {
            grid-column: span 1;
        }
    }
    
    .chart-title {
        font-size: 16px;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .chart-title svg {
        color: #d4a853;
    }
    
    .chart-container {
        height: 300px;
        position: relative;
    }
    
    .chart-card.full-width .chart-container {
        height: 350px;
    }
    
    /* Stats Cards */
    .stats-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    
    @media (max-width: 1200px) {
        .stats-row {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    @media (max-width: 600px) {
        .stats-row {
            grid-template-columns: 1fr;
        }
    }
    
    .stat-card {
        background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 20px;
        display: flex;
        align-items: center;
        gap: 16px;
    }
    
    .stat-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    
    .stat-icon svg {
        width: 24px;
        height: 24px;
    }
    
    .stat-content {
        flex: 1;
        min-width: 0;
    }
    
    .stat-card .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 4px;
    }
    
    .stat-card .stat-label {
        font-size: 13px;
        color: #64748b;
        text-transform: none;
        letter-spacing: normal;
    }
    
    /* Winner Card */
    .winner-card {
        background: linear-gradient(135deg, rgba(212, 168, 83, 0.1) 0%, rgba(212, 168, 83, 0.05) 100%);
        border: 1px solid rgba(212, 168, 83, 0.3);
    }
    
    /* Loading */
    .loading {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
        color: #d4a853;
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(212, 168, 83, 0.1);
        border-top-color: #d4a853;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    /* Login Styles */
    .login-container {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #050508;
        padding: 20px;
    }
    
    .login-card {
        background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
        border-radius: 20px;
        border: 1px solid rgba(212, 168, 83, 0.2);
        padding: 40px;
        width: 100%;
        max-width: 400px;
        text-align: center;
    }
    
    .login-logo {
        width: 80px;
        height: 80px;
        background: linear-gradient(135deg, #d4a853 0%, #b8942d 100%);
        border-radius: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 24px;
        font-weight: 700;
        color: #0a0a0f;
        font-size: 28px;
    }
    
    .login-title {
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 8px;
    }
    
    .login-subtitle {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 32px;
    }
    
    .login-form {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }
    
    .form-group {
        text-align: left;
    }
    
    .form-label {
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: #94a3b8;
        margin-bottom: 8px;
    }
    
    .form-input {
        width: 100%;
        padding: 14px 16px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(212, 168, 83, 0.2);
        border-radius: 10px;
        color: #e2e8f0;
        font-size: 15px;
        font-family: inherit;
        transition: all 0.2s;
    }
    
    .form-input:focus {
        outline: none;
        border-color: #d4a853;
        background: rgba(212, 168, 83, 0.05);
    }
    
    .form-input::placeholder {
        color: #64748b;
    }
    
    .login-btn {
        width: 100%;
        padding: 14px;
        background: linear-gradient(135deg, #d4a853 0%, #b8942d 100%);
        border: none;
        border-radius: 10px;
        color: #0a0a0f;
        font-size: 15px;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
        transition: all 0.2s;
        margin-top: 8px;
    }
    
    .login-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(212, 168, 83, 0.3);
    }
    
    .error-message {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 8px;
        padding: 12px;
        color: #ef4444;
        font-size: 13px;
        margin-bottom: 16px;
    }
    
    /* Leaderboard Table */
    .leaderboard-table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .leaderboard-table th {
        background: rgba(212, 168, 83, 0.05);
        padding: 16px;
        text-align: left;
        font-weight: 600;
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .leaderboard-table td {
        padding: 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .leaderboard-table tr:hover td {
        background: rgba(212, 168, 83, 0.03);
    }
    
    .rank-badge {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 14px;
    }
    
    .rank-1 {
        background: linear-gradient(135deg, #d4a853 0%, #b8942d 100%);
        color: #0a0a0f;
    }
    
    .rank-2 {
        background: linear-gradient(135deg, #94a3b8 0%, #64748b 100%);
        color: #0a0a0f;
    }
    
    .rank-3 {
        background: linear-gradient(135deg, #cd7f32 0%, #a0522d 100%);
        color: #ffffff;
    }
    
    .rank-other {
        background: rgba(255, 255, 255, 0.1);
        color: #94a3b8;
    }
    
    .provider-cell {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .provider-color {
        width: 4px;
        height: 32px;
        border-radius: 2px;
    }
    
    /* KPI Cards */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    
    @media (max-width: 1200px) {
        .kpi-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    @media (max-width: 768px) {
        .kpi-grid {
            grid-template-columns: 1fr;
        }
    }
    
    .kpi-card {
        background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 24px;
        text-align: center;
    }
    
    .kpi-icon {
        font-size: 32px;
        margin-bottom: 12px;
    }
    
    .kpi-value {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 4px;
    }
    
    .kpi-label {
        font-size: 13px;
        color: #64748b;
    }
    
    .kpi-trend {
        font-size: 12px;
        margin-top: 8px;
        padding: 4px 8px;
        border-radius: 12px;
        display: inline-block;
    }
    
    .kpi-trend.up {
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
    }
    
    .kpi-trend.down {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
    }
    
    /* Calendar Styles */
    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 8px;
        margin-top: 16px;
    }
    
    .calendar-header {
        text-align: center;
        font-size: 12px;
        font-weight: 600;
        color: #64748b;
        padding: 8px;
    }
    
    .calendar-day {
        aspect-ratio: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s;
        position: relative;
    }
    
    .calendar-day:hover {
        transform: scale(1.1);
    }
    
    .calendar-day.empty {
        background: transparent;
        cursor: default;
    }
    
    .calendar-day.empty:hover {
        transform: none;
    }
    
    .calendar-day.level-0 {
        background: rgba(255, 255, 255, 0.05);
        color: #64748b;
    }
    
    .calendar-day.level-1 {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
    }
    
    .calendar-day.level-2 {
        background: rgba(16, 185, 129, 0.4);
        color: #10b981;
    }
    
    .calendar-day.level-3 {
        background: rgba(16, 185, 129, 0.6);
        color: #ffffff;
    }
    
    .calendar-day.level-4 {
        background: rgba(212, 168, 83, 0.8);
        color: #0a0a0f;
    }
    
    .calendar-day.level-5 {
        background: linear-gradient(135deg, #d4a853 0%, #b8942d 100%);
        color: #0a0a0f;
        font-weight: 700;
    }
    
    .calendar-day .day-number {
        font-weight: 600;
    }
    
    .calendar-day .day-boxes {
        font-size: 9px;
        opacity: 0.8;
    }
    
    /* Comparison Grid */
    .comparison-grid {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: 24px;
        align-items: start;
    }
    
    @media (max-width: 1000px) {
        .comparison-grid {
            grid-template-columns: 1fr;
        }
    }
    
    .comparison-card {
        background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 24px;
    }
    
    .comparison-vs {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        font-weight: 700;
        color: #d4a853;
        padding: 20px;
    }
    
    @media (max-width: 1000px) {
        .comparison-vs {
            display: none;
        }
    }
    
    .comparison-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .comparison-color {
        width: 8px;
        height: 40px;
        border-radius: 4px;
    }
    
    .comparison-name {
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
    }
    
    .comparison-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    }
    
    .comparison-stat-label {
        color: #64748b;
        font-size: 14px;
    }
    
    .comparison-stat-value {
        color: #ffffff;
        font-size: 18px;
        font-weight: 600;
    }
    
    .winner-indicator {
        color: #10b981;
        font-size: 12px;
        margin-left: 8px;
    }
    
    /* Achievement Badges */
    .achievements-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 12px;
    }
    
    .achievement-badge {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        background: rgba(212, 168, 83, 0.1);
        border: 1px solid rgba(212, 168, 83, 0.2);
        border-radius: 20px;
        font-size: 11px;
        color: #d4a853;
    }
    
    .achievement-badge .badge-icon {
        font-size: 14px;
    }
    
    /* WhatsApp Report */
    .whatsapp-box {
        background: #0c0d12;
        border: 1px solid rgba(37, 211, 102, 0.3);
        border-radius: 12px;
        padding: 20px;
        margin-top: 16px;
    }
    
    .whatsapp-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(37, 211, 102, 0.2);
    }
    
    .whatsapp-icon {
        font-size: 24px;
    }
    
    .whatsapp-title {
        font-size: 16px;
        font-weight: 600;
        color: #25D366;
    }
    
    .whatsapp-content {
        font-family: 'Courier New', monospace;
        font-size: 13px;
        line-height: 1.6;
        color: #e2e8f0;
        white-space: pre-wrap;
        background: rgba(255, 255, 255, 0.03);
        padding: 16px;
        border-radius: 8px;
    }
    
    .copy-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        width: 100%;
        padding: 12px;
        margin-top: 12px;
        background: #25D366;
        border: none;
        border-radius: 8px;
        color: #ffffff;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .copy-btn:hover {
        background: #128C7E;
    }
    
    /* Month Selector */
    .month-selector {
        display: flex;
        align-items: center;
        gap: 12px;
        background: #0c0d12;
        padding: 8px 16px;
        border-radius: 12px;
        border: 1px solid rgba(212, 168, 83, 0.2);
    }
    
    .month-display {
        font-size: 14px;
        font-weight: 500;
        color: #e2e8f0;
        min-width: 150px;
        text-align: center;
    }
    
    /* Heatmap */
    .heatmap-container {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 12px;
        margin-top: 16px;
    }
    
    .heatmap-item {
        background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.05);
        transition: all 0.2s;
    }
    
    .heatmap-item:hover {
        transform: translateY(-2px);
        border-color: rgba(212, 168, 83, 0.3);
    }
    
    .heatmap-region {
        font-size: 14px;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 8px;
    }
    
    .heatmap-value {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 4px;
    }
    
    .heatmap-label {
        font-size: 11px;
        color: #64748b;
    }
    
    /* Tab System */
    .tabs {
        display: flex;
        gap: 8px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }
    
    .tab-btn {
        padding: 10px 20px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        color: #94a3b8;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .tab-btn:hover {
        background: rgba(212, 168, 83, 0.1);
        border-color: rgba(212, 168, 83, 0.2);
    }
    
    .tab-btn.active {
        background: rgba(212, 168, 83, 0.15);
        border-color: rgba(212, 168, 83, 0.3);
        color: #d4a853;
    }
    
    .tab-content {
        display: none;
    }
    
    .tab-content.active {
        display: block;
    }
    
    /* View Selector for Analytics */
    .view-selector {
        display: flex;
        gap: 8px;
        background: #0c0d12;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid rgba(212, 168, 83, 0.2);
    }
    
    .view-btn {
        padding: 10px 20px;
        background: transparent;
        border: none;
        border-radius: 8px;
        color: #64748b;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .view-btn:hover {
        color: #d4a853;
    }
    
    .view-btn.active {
        background: linear-gradient(135deg, #d4a853 0%, #b8942d 100%);
        color: #0a0a0f;
    }
    
    /* Stats Row 5 columns */
    .stats-row-5 {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    
    @media (max-width: 1200px) {
        .stats-row-5 {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    
    @media (max-width: 768px) {
        .stats-row-5 {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .sidebar {
            width: 70px;
        }
        
        .sidebar .logo-text,
        .sidebar .nav-item span,
        .sidebar .logout-btn span,
        .sidebar .nav-section-title {
            display: none;
        }
        
        .main-content {
            margin-left: 70px;
        }
        
        .page-header {
            flex-direction: column;
            align-items: flex-start;
        }
        
        .card-header {
            flex-direction: column;
            gap: 16px;
            align-items: flex-start;
        }
        
        .card-stats {
            width: 100%;
            justify-content: space-between;
        }
        
        .stats-row {
            grid-template-columns: 1fr;
        }
        
        .kpi-grid {
            grid-template-columns: 1fr;
        }
    }
</style>
"""

# ============================================
# UPDATED SIDEBAR HTML - WITH DAILY REGION TAB
# ============================================
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
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
                <span>Dashboard</span>
                <div class="tooltip">Dashboard</div>
            </a>
            
            <a href="/weekly-summary" class="nav-item {active_weekly}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <span>Weekly Summary</span>
                <div class="tooltip">Weekly Summary</div>
            </a>
            
            <a href="/daily-region" class="nav-item {active_daily_region}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span>Daily Region</span>
                <div class="tooltip">Daily Region Summary</div>
            </a>
            
            <a href="/flight-load" class="nav-item {active_flight}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                <span>Flight Load</span>
                <div class="tooltip">Flight Load</div>
            </a>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">Analytics</div>
            <a href="/analytics" class="nav-item {active_analytics}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                </svg>
                <span>Analytics</span>
                <div class="tooltip">Analytics</div>
            </a>
            
            <a href="/kpi" class="nav-item {active_kpi}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
                <span>KPI Dashboard</span>
                <div class="tooltip">KPI Dashboard</div>
            </a>
            
            <a href="/comparison" class="nav-item {active_comparison}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <span>Comparison</span>
                <div class="tooltip">Comparison</div>
            </a>
            
            <a href="/regions" class="nav-item {active_regions}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Region Heatmap</span>
                <div class="tooltip">Region Heatmap</div>
            </a>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">Reports</div>
            <a href="/monthly" class="nav-item {active_monthly}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span>Monthly Report</span>
                <div class="tooltip">Monthly Report</div>
            </a>
            
            <a href="/calendar" class="nav-item {active_calendar}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span>Calendar View</span>
                <div class="tooltip">Calendar View</div>
            </a>
            
            <a href="/whatsapp" class="nav-item {active_whatsapp}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <span>WhatsApp Report</span>
                <div class="tooltip">WhatsApp Report</div>
            </a>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">Achievements</div>
            <a href="/achievements" class="nav-item {active_achievements}">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
                <span>Achievements</span>
                <div class="tooltip">Achievements</div>
            </a>
        </div>
    </div>
    
    <div class="sidebar-footer">
        <a href="/logout" class="logout-btn">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
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

# ============================================
# ROUTES
# ============================================

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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - 3PL Dashboard</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="login-logo">3P</div>
            <h1 class="login-title">Welcome Back</h1>
            <p class="login-subtitle">Enter your password to access the dashboard</p>
            
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
            
            <form class="login-form" method="POST">
                <div class="form-group">
                    <label class="form-label">Password</label>
                    <input type="password" name="password" class="form-input" placeholder="Enter your password" autofocus required>
                </div>
                <button type="submit" class="login-btn">Sign In</button>
            </form>
        </div>
    </div>
</body>
</html>
    ''', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3PL Dashboard</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='active', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Provider <span>Dashboard</span></h1>
            
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="dashboard-content">
            <div class="loading">
                <div class="spinner"></div>
            </div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) {
            return date.toISOString().split('T')[0];
        }
        
        function formatDisplayDate(date) {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadDashboard();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = 
                formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        function getStarRating(stars) {
            return '★'.repeat(stars) + '☆'.repeat(5 - stars);
        }
        
        function renderProvider(provider) {
            const trendClass = provider.trend.direction === 'up' ? 'up' : (provider.trend.direction === 'down' ? 'down' : 'neutral');
            const trendIcon = provider.trend.direction === 'up' ? '▲' : (provider.trend.direction === 'down' ? '▼' : '–');
            
            let achievementsHtml = '';
            if (provider.achievements && provider.achievements.length > 0) {
                achievementsHtml = '<div class="achievements-row">';
                provider.achievements.forEach(a => {
                    achievementsHtml += `<div class="achievement-badge"><span class="badge-icon">${a.icon}</span>${a.name}</div>`;
                });
                achievementsHtml += '</div>';
            }
            
            let regionsHtml = '';
            const totals = { Mon: {o:0,b:0,w:0}, Tue: {o:0,b:0,w:0}, Wed: {o:0,b:0,w:0}, Thu: {o:0,b:0,w:0}, Fri: {o:0,b:0,w:0}, Sat: {o:0,b:0,w:0}, Sun: {o:0,b:0,w:0} };
            
            const sortedRegions = Object.keys(provider.regions).sort();
            
            for (const region of sortedRegions) {
                const days = provider.regions[region].days;
                regionsHtml += '<tr>';
                regionsHtml += '<td class="region-col">' + region + '</td>';
                
                for (const day of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']) {
                    const d = days[day];
                    totals[day].o += d.orders;
                    totals[day].b += d.boxes;
                    totals[day].w += d.weight;
                    
                    if (d.orders > 0) {
                        regionsHtml += '<td><div class="day-data"><span>' + d.orders + '</span><span>' + d.boxes + '</span><span>' + d.weight.toFixed(1) + '</span><span>' + d.under20 + '</span><span>' + d.over20 + '</span></div></td>';
                    } else {
                        regionsHtml += '<td>-</td>';
                    }
                }
                regionsHtml += '</tr>';
            }
            
            regionsHtml += '<tr class="total-row">';
            regionsHtml += '<td class="region-col">TOTAL</td>';
            for (const day of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']) {
                const t = totals[day];
                regionsHtml += '<td><div class="day-data"><span>' + t.o + '</span><span>' + t.b + '</span><span>' + t.w.toFixed(1) + '</span><span>-</span><span>-</span></div></td>';
            }
            regionsHtml += '</tr>';
            
            return `
                <div class="provider-card">
                    <div class="card-header" style="--provider-color: ${provider.color}">
                        <style>.provider-card .card-header::before { background: ${provider.color}; }</style>
                        <div class="provider-info">
                            <span class="provider-name">${provider.name}</span>
                            <span class="star-rating">${getStarRating(provider.stars)}</span>
                            <span class="trend-badge ${trendClass}">${trendIcon} ${provider.trend.percentage}%</span>
                            ${achievementsHtml}
                        </div>
                        <div class="card-stats">
                            <div class="stat-item">
                                <div class="stat-value">${provider.total_orders.toLocaleString()}</div>
                                <div class="stat-label">Orders</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${provider.total_boxes.toLocaleString()}</div>
                                <div class="stat-label">Boxes</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value">${provider.total_weight.toLocaleString(undefined, {minimumFractionDigits: 1, maximumFractionDigits: 1})} kg</div>
                                <div class="stat-label">Weight</div>
                            </div>
                        </div>
                    </div>
                    
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th class="region-col">Region</th>
                                <th>MON</th>
                                <th class="flight-day">TUE ✈️</th>
                                <th>WED</th>
                                <th class="flight-day">THU ✈️</th>
                                <th>FRI</th>
                                <th class="flight-day">SAT ✈️</th>
                                <th>SUN</th>
                            </tr>
                            <tr>
                                <th></th>
                                ${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(() => '<th><div class="sub-header"><span>O</span><span>B</span><span>W</span><span><20</span><span>20+</span></div></th>').join('')}
                            </tr>
                        </thead>
                        <tbody>
                            ${regionsHtml}
                        </tbody>
                    </table>
                </div>
            `;
        }
        
        async function loadDashboard() {
            updateWeekDisplay();
            document.getElementById('dashboard-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/dashboard?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                let html = '';
                for (const provider of data.providers) {
                    html += renderProvider(provider);
                }
                
                document.getElementById('dashboard-content').innerHTML = html;
            } catch (error) {
                document.getElementById('dashboard-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadDashboard();
    </script>
</body>
</html>
    ''')

@app.route('/weekly-summary')
@login_required
def weekly_summary():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Summary - 3PL Dashboard</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='active', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Weekly <span>Summary</span></h1>
            
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="summary-content">
            <div class="loading">
                <div class="spinner"></div>
            </div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) {
            return date.toISOString().split('T')[0];
        }
        
        function formatDisplayDate(date) {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadSummary();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = 
                formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        async function loadSummary() {
            updateWeekDisplay();
            document.getElementById('summary-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/weekly-summary?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                let html = '';
                if (data.winner) {
                    let achievementsHtml = '';
                    if (data.winner.achievements && data.winner.achievements.length > 0) {
                        achievementsHtml = '<div class="achievements-row" style="margin-top: 12px;">';
                        data.winner.achievements.forEach(a => {
                            achievementsHtml += `<div class="achievement-badge"><span class="badge-icon">${a.icon}</span>${a.name}</div>`;
                        });
                        achievementsHtml += '</div>';
                    }
                    
                    html += `
                        <div class="provider-card winner-card">
                            <div class="card-header">
                                <div class="provider-info">
                                    <span style="font-size: 32px; margin-right: 12px;">🏆</span>
                                    <div>
                                        <div class="provider-name" style="font-size: 24px;">Week Winner: ${data.winner.name}</div>
                                        <div style="color: #d4a853; margin-top: 4px;">${data.winner.total_boxes.toLocaleString()} boxes • ${data.winner.total_weight.toLocaleString(undefined, {maximumFractionDigits: 1})} kg</div>
                                        ${achievementsHtml}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                html += `
                    <div class="provider-card">
                        <div class="card-header">
                            <div class="provider-info">
                                <span class="provider-name">Provider Leaderboard</span>
                            </div>
                        </div>
                        <table class="leaderboard-table">
                            <thead>
                                <tr>
                                    <th style="width: 60px;">Rank</th>
                                    <th>Provider</th>
                                    <th style="text-align: right;">Orders</th>
                                    <th style="text-align: right;">Boxes</th>
                                    <th style="text-align: right;">Weight (kg)</th>
                                    <th style="text-align: right;">Trend</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                data.providers.forEach((p, i) => {
                    const rankClass = i < 3 ? 'rank-' + (i + 1) : 'rank-other';
                    const trendClass = p.trend.direction === 'up' ? 'up' : 'down';
                    const trendIcon = p.trend.direction === 'up' ? '▲' : '▼';
                    
                    html += `
                        <tr>
                            <td><div class="rank-badge ${rankClass}">${i + 1}</div></td>
                            <td>
                                <div class="provider-cell">
                                    <div class="provider-color" style="background: ${p.color}"></div>
                                    <span>${p.name}</span>
                                </div>
                            </td>
                            <td style="text-align: right; font-weight: 600;">${p.total_orders.toLocaleString()}</td>
                            <td style="text-align: right; font-weight: 600;">${p.total_boxes.toLocaleString()}</td>
                            <td style="text-align: right; font-weight: 600;">${p.total_weight.toLocaleString(undefined, {maximumFractionDigits: 1})}</td>
                            <td style="text-align: right;"><span class="trend-badge ${trendClass}">${trendIcon} ${p.trend.percentage}%</span></td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table></div>';
                
                document.getElementById('summary-content').innerHTML = html;
            } catch (error) {
                document.getElementById('summary-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadSummary();
    </script>
</body>
</html>
    ''')

# ============================================
# 🆕 NEW ROUTE: DAILY REGION SUMMARY
# ============================================
@app.route('/daily-region')
@login_required
def daily_region():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Region Summary - 3PL Dashboard</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
    <style>
        .date-picker-container {
            display: flex;
            align-items: center;
            gap: 12px;
            background: #0c0d12;
            padding: 8px 16px;
            border-radius: 12px;
            border: 1px solid rgba(212, 168, 83, 0.2);
        }
        
        .date-input {
            padding: 10px 14px;
            border-radius: 8px;
            border: 1px solid rgba(212, 168, 83, 0.3);
            background: rgba(255,255,255,0.05);
            color: #f8fafc;
            font-size: 14px;
            font-family: inherit;
        }
        
        .date-input:focus {
            outline: none;
            border-color: #d4a853;
        }
        
        .load-btn {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            background: linear-gradient(135deg, #d4a853, #b8942d);
            color: #0a0a0f;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .load-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(212, 168, 83, 0.3);
        }
        
        .provider-section {
            background: linear-gradient(145deg, #0c0d12 0%, #0a0a0f 100%);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            margin-bottom: 20px;
            overflow: hidden;
        }
        
        .provider-header {
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .provider-header:hover {
            background: rgba(255,255,255,0.02);
        }
        
        .provider-header-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .provider-color-bar {
            width: 4px;
            height: 36px;
            border-radius: 2px;
        }
        
        .provider-header-info h3 {
            font-size: 16px;
            font-weight: 600;
            color: #fff;
            margin-bottom: 2px;
        }
        
        .provider-header-info span {
            font-size: 12px;
            color: #64748b;
        }
        
        .provider-header-stats {
            display: flex;
            gap: 20px;
        }
        
        .header-stat {
            text-align: center;
        }
        
        .header-stat-val {
            font-size: 16px;
            font-weight: 700;
            color: #d4a853;
        }
        
        .header-stat-lbl {
            font-size: 10px;
            color: #64748b;
            text-transform: uppercase;
        }
        
        .provider-body {
            padding: 0 20px 20px;
            display: none;
        }
        
        .provider-body.open {
            display: block;
        }
        
        .region-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        
        .region-table th {
            background: rgba(212, 168, 83, 0.08);
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            color: #94a3b8;
            font-size: 11px;
            text-transform: uppercase;
        }
        
        .region-table th:not(:first-child) {
            text-align: right;
        }
        
        .region-table td {
            padding: 10px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        
        .region-table td:not(:first-child) {
            text-align: right;
        }
        
        .region-table tr:hover td {
            background: rgba(212, 168, 83, 0.03);
        }
        
        .medal {
            font-size: 16px;
            margin-right: 6px;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #64748b;
        }
        
        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }
        
        .toggle-icon {
            color: #d4a853;
            transition: transform 0.3s;
        }
        
        .provider-header.open .toggle-icon {
            transform: rotate(180deg);
        }
    </style>
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='active', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Daily <span>Region Summary</span></h1>
            
            <div class="date-picker-container">
                <input type="date" id="date-picker" class="date-input">
                <button class="load-btn" onclick="loadData()">🔍 Load Data</button>
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div class="stats-row-5" id="summary-cards">
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(59, 130, 246, 0.1); font-size: 24px;">📦</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-orders">-</div>
                    <div class="stat-label">Total Orders</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(16, 185, 129, 0.1); font-size: 24px;">📮</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-boxes">-</div>
                    <div class="stat-label">Total Boxes</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(245, 158, 11, 0.1); font-size: 24px;">⚖️</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-weight">-</div>
                    <div class="stat-label">Total Weight</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(34, 197, 94, 0.1); font-size: 24px;">🪶</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-under20">-</div>
                    <div class="stat-label">&lt;20 kg</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(239, 68, 68, 0.1); font-size: 24px;">🏋️</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-over20">-</div>
                    <div class="stat-label">20+ kg</div>
                </div>
            </div>
        </div>
        
        <div id="content">
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <h3>Select a Date</h3>
                <p>Choose a date and click "Load Data" to see region-wise breakdown by provider</p>
            </div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        // Set today's date as default
        document.getElementById('date-picker').value = new Date().toISOString().split('T')[0];
        
        function toggleProvider(id) {
            const header = document.getElementById('header-' + id);
            const body = document.getElementById('body-' + id);
            header.classList.toggle('open');
            body.classList.toggle('open');
        }
        
        async function loadData() {
            const date = document.getElementById('date-picker').value;
            if (!date) {
                alert('Please select a date');
                return;
            }
            
            document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/daily-region-summary?date=' + date);
                const data = await response.json();
                
                // Update summary cards
                document.getElementById('total-orders').textContent = data.totals.orders.toLocaleString();
                document.getElementById('total-boxes').textContent = data.totals.boxes.toLocaleString();
                document.getElementById('total-weight').textContent = data.totals.weight.toFixed(1) + ' kg';
                document.getElementById('total-under20').textContent = data.totals.under20.toLocaleString();
                document.getElementById('total-over20').textContent = data.totals.over20.toLocaleString();
                
                if (data.totals.orders === 0) {
                    document.getElementById('content').innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">📭</div>
                            <h3>No Data Found</h3>
                            <p>No shipments recorded for ${data.date_display}</p>
                        </div>
                    `;
                    return;
                }
                
                let html = '<h3 style="color: #d4a853; margin-bottom: 16px;">📊 ' + data.date_display + '</h3>';
                
                const medals = ['🥇', '🥈', '🥉'];
                
                data.providers.forEach((provider, idx) => {
                    html += `
                        <div class="provider-section">
                            <div class="provider-header" id="header-${idx}" onclick="toggleProvider(${idx})">
                                <div class="provider-header-left">
                                    <div class="provider-color-bar" style="background: ${provider.color}"></div>
                                    <div class="provider-header-info">
                                        <h3>${provider.name}</h3>
                                        <span>${provider.regions.length} regions</span>
                                    </div>
                                </div>
                                <div class="provider-header-stats">
                                    <div class="header-stat">
                                        <div class="header-stat-val">${provider.orders}</div>
                                        <div class="header-stat-lbl">Orders</div>
                                    </div>
                                    <div class="header-stat">
                                        <div class="header-stat-val">${provider.boxes}</div>
                                        <div class="header-stat-lbl">Boxes</div>
                                    </div>
                                    <div class="header-stat">
                                        <div class="header-stat-val">${provider.weight.toFixed(1)}</div>
                                        <div class="header-stat-lbl">Weight</div>
                                    </div>
                                    <span class="toggle-icon">▼</span>
                                </div>
                            </div>
                            <div class="provider-body" id="body-${idx}">
                    `;
                    
                    if (provider.regions.length > 0) {
                        html += `
                            <table class="region-table">
                                <thead>
                                    <tr>
                                        <th>Region</th>
                                        <th>Orders</th>
                                        <th>Boxes</th>
                                        <th>Weight</th>
                                        <th>&lt;20 kg</th>
                                        <th>20+ kg</th>
                                    </tr>
                                </thead>
                                <tbody>
                        `;
                        
                        provider.regions.forEach((r, i) => {
                            const medal = i < 3 ? `<span class="medal">${medals[i]}</span>` : '';
                            html += `
                                <tr>
                                    <td>${medal}${r.name}</td>
                                    <td>${r.orders}</td>
                                    <td>${r.boxes}</td>
                                    <td>${r.weight.toFixed(1)}</td>
                                    <td style="color: #22c55e;">${r.under20}</td>
                                    <td style="color: #ef4444;">${r.over20}</td>
                                </tr>
                            `;
                        });
                        
                        html += '</tbody></table>';
                    } else {
                        html += '<p style="color: #64748b; text-align: center; padding: 20px;">No data for this provider</p>';
                    }
                    
                    html += '</div></div>';
                });
                
                document.getElementById('content').innerHTML = html;
                
                // Auto-expand first provider
                if (data.providers.length > 0) {
                    toggleProvider(0);
                }
                
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('content').innerHTML = '<div class="empty-state"><div class="empty-state-icon">❌</div><h3>Error</h3><p>Failed to load data</p></div>';
            }
        }
        
        // Load data for today on page load
        loadData();
    </script>
</body>
</html>
    ''')

@app.route('/flight-load')
@login_required
def flight_load():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flight Load - 3PL Dashboard</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='active', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Flight <span>Load</span></h1>
            
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="flight-content">
            <div class="loading">
                <div class="spinner"></div>
            </div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) {
            return date.toISOString().split('T')[0];
        }
        
        function formatDisplayDate(date) {
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadFlightData();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = 
                formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        async function loadFlightData() {
            updateWeekDisplay();
            document.getElementById('flight-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/flight-load?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                let html = '';
                
                for (const flight of data.flights) {
                    html += `
                        <div class="provider-card">
                            <div class="card-header">
                                <div class="provider-info">
                                    <span style="font-size: 24px; margin-right: 12px;">✈️</span>
                                    <span class="provider-name">${flight.name}</span>
                                </div>
                                <div class="card-stats">
                                    <div class="stat-item">
                                        <div class="stat-value">${flight.total_orders.toLocaleString()}</div>
                                        <div class="stat-label">Orders</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-value">${flight.total_boxes.toLocaleString()}</div>
                                        <div class="stat-label">Boxes</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-value">${flight.total_weight.toLocaleString(undefined, {maximumFractionDigits: 1})} kg</div>
                                        <div class="stat-label">Weight</div>
                                    </div>
                                </div>
                            </div>
                            <table class="leaderboard-table">
                                <thead>
                                    <tr>
                                        <th>Provider</th>
                                        <th style="text-align: right;">Orders</th>
                                        <th style="text-align: right;">Boxes</th>
                                        <th style="text-align: right;">Weight (kg)</th>
                                    </tr>
                                </thead>
                                <tbody>
                    `;
                    
                    for (const p of flight.providers) {
                        html += `
                            <tr>
                                <td>
                                    <div class="provider-cell">
                                        <div class="provider-color" style="background: ${p.color}"></div>
                                        <span>${p.name}</span>
                                    </div>
                                </td>
                                <td style="text-align: right;">${p.orders.toLocaleString()}</td>
                                <td style="text-align: right;">${p.boxes.toLocaleString()}</td>
                                <td style="text-align: right;">${p.weight.toLocaleString(undefined, {maximumFractionDigits: 1})}</td>
                            </tr>
                        `;
                    }
                    
                    html += '</tbody></table></div>';
                }
                
                document.getElementById('flight-content').innerHTML = html;
            } catch (error) {
                document.getElementById('flight-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadFlightData();
    </script>
</body>
</html>
    ''')

# ============================================
# 🆕 UPDATED ANALYTICS PAGE - WITH VIEW SELECTOR + WEIGHT CHARTS
# ============================================
@app.route('/analytics')
@login_required
def analytics():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analytics - 3PL Dashboard</title>
    ''' + FAVICON + '''
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='active', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Analytics & <span>Insights</span></h1>
            
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <!-- View Selector -->
                <div class="view-selector">
                    <button class="view-btn active" id="btn-daily" onclick="changeView('daily')">📅 Daily</button>
                    <button class="view-btn" id="btn-weekly" onclick="changeView('weekly')">📊 Weekly</button>
                    <button class="view-btn" id="btn-monthly" onclick="changeView('monthly')">📈 Monthly</button>
                </div>
                
                <!-- Period Navigator -->
                <div class="week-selector">
                    <button class="week-btn" onclick="changePeriod(-1)">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                        </svg>
                    </button>
                    <span class="week-display" id="period-display">Loading...</span>
                    <button class="week-btn" onclick="changePeriod(1)">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
        
        <!-- 5 Stats Cards -->
        <div class="stats-row-5" id="stats-row">
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(59, 130, 246, 0.1); font-size: 24px;">📋</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-orders">0</div>
                    <div class="stat-label">Total Orders</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(16, 185, 129, 0.1); font-size: 24px;">📦</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-boxes">0</div>
                    <div class="stat-label">Total Boxes</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(212, 168, 83, 0.1); font-size: 24px;">⚖️</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-weight">0</div>
                    <div class="stat-label">Total Weight (kg)</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(34, 197, 94, 0.1); font-size: 24px;">🪶</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-under20">0</div>
                    <div class="stat-label">Light (&lt;20 kg)</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(239, 68, 68, 0.1); font-size: 24px;">🏋️</div>
                <div class="stat-content">
                    <div class="stat-value" id="total-over20">0</div>
                    <div class="stat-label">Heavy (20+ kg)</div>
                </div>
            </div>
        </div>
        
        <!-- Charts Grid -->
        <div class="charts-grid">
            <!-- Trend Chart - Full Width -->
            <div class="chart-card full-width">
                <div class="chart-title">📈 Orders & Boxes Trend</div>
                <div class="chart-container">
                    <canvas id="trendChart"></canvas>
                </div>
            </div>
            
            <!-- Provider Performance -->
            <div class="chart-card">
                <div class="chart-title">🏆 Provider Performance</div>
                <div class="chart-container">
                    <canvas id="providerChart"></canvas>
                </div>
            </div>
            
            <!-- Top Regions -->
            <div class="chart-card">
                <div class="chart-title">🌍 Top Regions</div>
                <div class="chart-container">
                    <canvas id="regionChart"></canvas>
                </div>
            </div>
            
            <!-- Weight by Region - NEW -->
            <div class="chart-card">
                <div class="chart-title">📊 Weight Categories by Region</div>
                <div class="chart-container">
                    <canvas id="weightRegionChart"></canvas>
                </div>
            </div>
            
            <!-- Weight by Provider - NEW -->
            <div class="chart-card">
                <div class="chart-title">📊 Weight Categories by 3PL</div>
                <div class="chart-container">
                    <canvas id="weightProviderChart"></canvas>
                </div>
            </div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentView = 'daily';
        let periodOffset = 0;
        let charts = {};
        
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function changeView(view) {
            currentView = view;
            periodOffset = 0;
            
            document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('btn-' + view).classList.add('active');
            
            loadAnalytics();
        }
        
        function changePeriod(direction) {
            periodOffset += direction;
            loadAnalytics();
        }
        
        function updatePeriodDisplay() {
            const now = new Date();
            let display = '';
            
            if (currentView === 'daily') {
                const date = new Date(now);
                date.setDate(date.getDate() + periodOffset);
                display = date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
            } else if (currentView === 'weekly') {
                const monday = getMonday(now);
                monday.setDate(monday.getDate() + (periodOffset * 7));
                const sunday = new Date(monday);
                sunday.setDate(sunday.getDate() + 6);
                display = monday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' - ' + 
                         sunday.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            } else {
                const date = new Date(now.getFullYear(), now.getMonth() + periodOffset, 1);
                display = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
            }
            
            document.getElementById('period-display').textContent = display;
        }
        
        function destroyCharts() {
            Object.values(charts).forEach(chart => chart && chart.destroy());
            charts = {};
        }
        
        async function loadAnalytics() {
            updatePeriodDisplay();
            destroyCharts();
            
            try {
                const response = await fetch(`/api/analytics-data?view=${currentView}&offset=${periodOffset}`);
                const data = await response.json();
                
                // Update stats
                document.getElementById('total-orders').textContent = data.totals.orders.toLocaleString();
                document.getElementById('total-boxes').textContent = data.totals.boxes.toLocaleString();
                document.getElementById('total-weight').textContent = data.totals.weight.toLocaleString(undefined, {maximumFractionDigits: 1});
                document.getElementById('total-under20').textContent = data.totals.under20.toLocaleString();
                document.getElementById('total-over20').textContent = data.totals.over20.toLocaleString();
                
                // Trend Chart
                charts.trend = new Chart(document.getElementById('trendChart'), {
                    type: 'line',
                    data: {
                        labels: data.trend.labels,
                        datasets: [
                            {
                                label: 'Orders',
                                data: data.trend.orders,
                                borderColor: '#3b82f6',
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                fill: true,
                                tension: 0.4,
                                pointRadius: 4
                            },
                            {
                                label: 'Boxes',
                                data: data.trend.boxes,
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                fill: true,
                                tension: 0.4,
                                pointRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: {
                            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
                
                // Provider Chart
                charts.provider = new Chart(document.getElementById('providerChart'), {
                    type: 'doughnut',
                    data: {
                        labels: data.providers.map(p => p.name),
                        datasets: [{
                            data: data.providers.map(p => p.boxes),
                            backgroundColor: data.providers.map(p => p.color + 'CC'),
                            borderColor: '#0a0a0f',
                            borderWidth: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '60%',
                        plugins: { legend: { position: 'right', labels: { padding: 12, usePointStyle: true } } }
                    }
                });
                
                // Region Chart
                const topRegions = data.regions.slice(0, 8);
                charts.region = new Chart(document.getElementById('regionChart'), {
                    type: 'bar',
                    data: {
                        labels: topRegions.map(r => r.name),
                        datasets: [{
                            label: 'Boxes',
                            data: topRegions.map(r => r.boxes),
                            backgroundColor: '#d4a85399',
                            borderColor: '#d4a853',
                            borderWidth: 2,
                            borderRadius: 6
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                            y: { grid: { display: false } }
                        }
                    }
                });
                
                // Weight by Region Chart - NEW
                const weightRegions = data.regions.slice(0, 6);
                charts.weightRegion = new Chart(document.getElementById('weightRegionChart'), {
                    type: 'bar',
                    data: {
                        labels: weightRegions.map(r => r.name),
                        datasets: [
                            {
                                label: '<20 kg',
                                data: weightRegions.map(r => r.under20),
                                backgroundColor: 'rgba(34, 197, 94, 0.7)',
                                borderColor: '#22c55e',
                                borderWidth: 1,
                                borderRadius: 4
                            },
                            {
                                label: '20+ kg',
                                data: weightRegions.map(r => r.over20),
                                backgroundColor: 'rgba(239, 68, 68, 0.7)',
                                borderColor: '#ef4444',
                                borderWidth: 1,
                                borderRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: {
                            x: { stacked: true, grid: { display: false } },
                            y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } }
                        }
                    }
                });
                
                // Weight by Provider Chart - NEW
                charts.weightProvider = new Chart(document.getElementById('weightProviderChart'), {
                    type: 'bar',
                    data: {
                        labels: data.providers.map(p => p.name),
                        datasets: [
                            {
                                label: '<20 kg',
                                data: data.providers.map(p => p.under20),
                                backgroundColor: 'rgba(34, 197, 94, 0.7)',
                                borderColor: '#22c55e',
                                borderWidth: 1,
                                borderRadius: 4
                            },
                            {
                                label: '20+ kg',
                                data: data.providers.map(p => p.over20),
                                backgroundColor: 'rgba(239, 68, 68, 0.7)',
                                borderColor: '#ef4444',
                                borderWidth: 1,
                                borderRadius: 4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'top' } },
                        scales: {
                            x: { grid: { display: false } },
                            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } }
                        }
                    }
                });
                
            } catch (error) {
                console.error('Error:', error);
            }
        }
        
        loadAnalytics();
    </script>
</body>
</html>
    ''')

@app.route('/kpi')
@login_required
def kpi_dashboard():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KPI Dashboard - 3PL</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='active', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">KPI <span>Dashboard</span></h1>
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="kpi-content">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) { return date.toISOString().split('T')[0]; }
        function formatDisplayDate(date) { return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadKPI();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        async function loadKPI() {
            updateWeekDisplay();
            document.getElementById('kpi-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/kpi?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                let html = '<div class="kpi-grid">';
                
                const kpis = [
                    { icon: '📦', label: 'Total Boxes', value: data.total_boxes.toLocaleString(), trend: data.boxes_trend },
                    { icon: '📋', label: 'Total Orders', value: data.total_orders.toLocaleString(), trend: data.orders_trend },
                    { icon: '⚖️', label: 'Total Weight', value: data.total_weight.toLocaleString(undefined, {maximumFractionDigits: 1}) + ' kg', trend: data.weight_trend },
                    { icon: '📊', label: 'Avg Boxes/Day', value: data.avg_boxes_per_day.toFixed(0), trend: null },
                    { icon: '📈', label: 'Avg Weight/Order', value: data.avg_weight_per_order.toFixed(2) + ' kg', trend: null },
                    { icon: '🌍', label: 'Active Regions', value: data.active_regions, trend: null },
                    { icon: '🏆', label: 'Top Provider', value: data.top_provider, trend: null },
                    { icon: '🗺️', label: 'Top Region', value: data.top_region, trend: null },
                    { icon: '📅', label: 'Best Day', value: data.best_day, trend: null }
                ];
                
                kpis.forEach(kpi => {
                    let trendHtml = '';
                    if (kpi.trend) {
                        const trendClass = kpi.trend.direction === 'up' ? 'up' : 'down';
                        const trendIcon = kpi.trend.direction === 'up' ? '▲' : '▼';
                        trendHtml = `<div class="kpi-trend ${trendClass}">${trendIcon} ${kpi.trend.percentage}% vs last week</div>`;
                    }
                    
                    html += `
                        <div class="kpi-card">
                            <div class="kpi-icon">${kpi.icon}</div>
                            <div class="kpi-value">${kpi.value}</div>
                            <div class="kpi-label">${kpi.label}</div>
                            ${trendHtml}
                        </div>
                    `;
                });
                
                html += '</div>';
                document.getElementById('kpi-content').innerHTML = html;
            } catch (error) {
                document.getElementById('kpi-content').innerHTML = '<p style="color: #ef4444;">Error loading KPI data</p>';
            }
        }
        
        loadKPI();
    </script>
</body>
</html>
    ''')

@app.route('/comparison')
@login_required
def comparison():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Provider Comparison - 3PL</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='active', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Provider <span>Comparison</span></h1>
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('ge-ecl')">GE vs ECL</button>
            <button class="tab-btn" onclick="showTab('qc-zone')">QC vs ZONE</button>
            <button class="tab-btn" onclick="showTab('all')">All Providers</button>
        </div>
        
        <div id="comparison-content">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        let currentData = null;
        let currentTab = 'ge-ecl';
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) { return date.toISOString().split('T')[0]; }
        function formatDisplayDate(date) { return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadComparison();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        function showTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            renderComparison();
        }
        
        function renderComparisonCard(p1, p2) {
            const stats = ['total_orders', 'total_boxes', 'total_weight'];
            const labels = ['Orders', 'Boxes', 'Weight (kg)'];
            
            let statsHtml1 = '', statsHtml2 = '';
            
            stats.forEach((stat, i) => {
                const v1 = p1[stat];
                const v2 = p2[stat];
                const winner1 = v1 > v2 ? '<span class="winner-indicator">👑</span>' : '';
                const winner2 = v2 > v1 ? '<span class="winner-indicator">👑</span>' : '';
                const formatted1 = stat === 'total_weight' ? v1.toLocaleString(undefined, {maximumFractionDigits: 1}) : v1.toLocaleString();
                const formatted2 = stat === 'total_weight' ? v2.toLocaleString(undefined, {maximumFractionDigits: 1}) : v2.toLocaleString();
                
                statsHtml1 += `<div class="comparison-stat"><span class="comparison-stat-label">${labels[i]}</span><span class="comparison-stat-value">${formatted1}${winner1}</span></div>`;
                statsHtml2 += `<div class="comparison-stat"><span class="comparison-stat-label">${labels[i]}</span><span class="comparison-stat-value">${formatted2}${winner2}</span></div>`;
            });
            
            return `
                <div class="comparison-grid">
                    <div class="comparison-card">
                        <div class="comparison-header">
                            <div class="comparison-color" style="background: ${p1.color}"></div>
                            <div class="comparison-name">${p1.short || p1.name}</div>
                        </div>
                        ${statsHtml1}
                    </div>
                    <div class="comparison-vs">VS</div>
                    <div class="comparison-card">
                        <div class="comparison-header">
                            <div class="comparison-color" style="background: ${p2.color}"></div>
                            <div class="comparison-name">${p2.short || p2.name}</div>
                        </div>
                        ${statsHtml2}
                    </div>
                </div>
            `;
        }
        
        function renderComparison() {
            if (!currentData) return;
            
            let html = '';
            const providers = currentData.providers;
            
            if (currentTab === 'ge-ecl') {
                const geProviders = providers.filter(p => p.group === 'GE');
                const eclProviders = providers.filter(p => p.group === 'ECL');
                
                const geTotal = {
                    name: 'GLOBAL EXPRESS',
                    short: 'GE Total',
                    color: '#3B82F6',
                    total_orders: geProviders.reduce((s, p) => s + p.total_orders, 0),
                    total_boxes: geProviders.reduce((s, p) => s + p.total_boxes, 0),
                    total_weight: geProviders.reduce((s, p) => s + p.total_weight, 0)
                };
                
                const eclTotal = {
                    name: 'ECL LOGISTICS',
                    short: 'ECL Total',
                    color: '#10B981',
                    total_orders: eclProviders.reduce((s, p) => s + p.total_orders, 0),
                    total_boxes: eclProviders.reduce((s, p) => s + p.total_boxes, 0),
                    total_weight: eclProviders.reduce((s, p) => s + p.total_weight, 0)
                };
                
                html = '<h3 style="color: #d4a853; margin-bottom: 20px;">Global Express vs ECL Logistics</h3>';
                html += renderComparisonCard(geTotal, eclTotal);
                
            } else if (currentTab === 'qc-zone') {
                const qcProviders = providers.filter(p => p.name.includes('QC'));
                const zoneProviders = providers.filter(p => p.name.includes('ZONE'));
                
                const qcTotal = {
                    name: 'QC Center',
                    short: 'QC Total',
                    color: '#8B5CF6',
                    total_orders: qcProviders.reduce((s, p) => s + p.total_orders, 0),
                    total_boxes: qcProviders.reduce((s, p) => s + p.total_boxes, 0),
                    total_weight: qcProviders.reduce((s, p) => s + p.total_weight, 0)
                };
                
                const zoneTotal = {
                    name: 'Zone',
                    short: 'Zone Total',
                    color: '#F59E0B',
                    total_orders: zoneProviders.reduce((s, p) => s + p.total_orders, 0),
                    total_boxes: zoneProviders.reduce((s, p) => s + p.total_boxes, 0),
                    total_weight: zoneProviders.reduce((s, p) => s + p.total_weight, 0)
                };
                
                html = '<h3 style="color: #d4a853; margin-bottom: 20px;">QC Center vs Zone</h3>';
                html += renderComparisonCard(qcTotal, zoneTotal);
                
            } else {
                html = `
                    <div class="provider-card">
                        <table class="leaderboard-table">
                            <thead>
                                <tr>
                                    <th>Provider</th>
                                    <th style="text-align: right;">Orders</th>
                                    <th style="text-align: right;">Boxes</th>
                                    <th style="text-align: right;">Weight</th>
                                    <th style="text-align: right;">Avg/Order</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                providers.sort((a, b) => b.total_boxes - a.total_boxes).forEach(p => {
                    const avgPerOrder = p.total_orders > 0 ? (p.total_weight / p.total_orders).toFixed(2) : 0;
                    html += `
                        <tr>
                            <td><div class="provider-cell"><div class="provider-color" style="background: ${p.color}"></div>${p.short || p.name}</div></td>
                            <td style="text-align: right;">${p.total_orders.toLocaleString()}</td>
                            <td style="text-align: right;">${p.total_boxes.toLocaleString()}</td>
                            <td style="text-align: right;">${p.total_weight.toLocaleString(undefined, {maximumFractionDigits: 1})}</td>
                            <td style="text-align: right;">${avgPerOrder} kg</td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table></div>';
            }
            
            document.getElementById('comparison-content').innerHTML = html;
        }
        
        async function loadComparison() {
            updateWeekDisplay();
            document.getElementById('comparison-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/dashboard?week_start=' + formatDate(currentWeekStart));
                currentData = await response.json();
                renderComparison();
            } catch (error) {
                document.getElementById('comparison-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadComparison();
    </script>
</body>
</html>
    ''')

@app.route('/regions')
@login_required
def regions():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Region Heatmap - 3PL</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='active', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Region <span>Heatmap</span></h1>
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="regions-content">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) { return date.toISOString().split('T')[0]; }
        function formatDisplayDate(date) { return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadRegions();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        function getHeatColor(value, max) {
            const ratio = value / max;
            if (ratio >= 0.8) return '#10b981';
            if (ratio >= 0.6) return '#34d399';
            if (ratio >= 0.4) return '#d4a853';
            if (ratio >= 0.2) return '#f59e0b';
            return '#64748b';
        }
        
        async function loadRegions() {
            updateWeekDisplay();
            document.getElementById('regions-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/regions?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                const maxOrders = Math.max(...data.regions.map(r => r.orders));
                
                let html = '<div class="heatmap-container">';
                
                data.regions.forEach(region => {
                    const color = getHeatColor(region.orders, maxOrders);
                    html += `
                        <div class="heatmap-item" style="border-color: ${color}40;">
                            <div class="heatmap-region">${region.name}</div>
                            <div class="heatmap-value" style="color: ${color}">${region.orders}</div>
                            <div class="heatmap-label">orders</div>
                            <div class="heatmap-label" style="margin-top: 4px;">${region.boxes} boxes • ${region.weight.toFixed(1)} kg</div>
                        </div>
                    `;
                });
                
                html += '</div>';
                document.getElementById('regions-content').innerHTML = html;
            } catch (error) {
                document.getElementById('regions-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadRegions();
    </script>
</body>
</html>
    ''')

@app.route('/monthly')
@login_required
def monthly_report():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monthly Report - 3PL</title>
    ''' + FAVICON + '''
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='active', active_calendar='', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Monthly <span>Report</span></h1>
            <div class="month-selector">
                <button class="week-btn" onclick="changeMonth(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="month-display" id="month-display">Loading...</span>
                <button class="week-btn" onclick="changeMonth(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="monthly-content">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentDate = new Date();
        let chart = null;
        
        function formatMonth(date) {
            return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        }
        
        function changeMonth(direction) {
            currentDate.setMonth(currentDate.getMonth() + direction);
            loadMonthly();
        }
        
        async function loadMonthly() {
            document.getElementById('month-display').textContent = formatMonth(currentDate);
            document.getElementById('monthly-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            const year = currentDate.getFullYear();
            const month = currentDate.getMonth() + 1;
            
            try {
                const response = await fetch(`/api/monthly?year=${year}&month=${month}`);
                const data = await response.json();
                
                let html = `
                    <div class="stats-row">
                        <div class="stat-card">
                            <div class="stat-icon" style="background: rgba(59, 130, 246, 0.1);">📋</div>
                            <div class="stat-content">
                                <div class="stat-value">${data.total_orders.toLocaleString()}</div>
                                <div class="stat-label">Total Orders</div>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon" style="background: rgba(16, 185, 129, 0.1);">📦</div>
                            <div class="stat-content">
                                <div class="stat-value">${data.total_boxes.toLocaleString()}</div>
                                <div class="stat-label">Total Boxes</div>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon" style="background: rgba(212, 168, 83, 0.1);">⚖️</div>
                            <div class="stat-content">
                                <div class="stat-value">${data.total_weight.toLocaleString(undefined, {maximumFractionDigits: 1})} kg</div>
                                <div class="stat-label">Total Weight</div>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon" style="background: rgba(139, 92, 246, 0.1);">📊</div>
                            <div class="stat-content">
                                <div class="stat-value">${data.avg_per_day.toFixed(0)}</div>
                                <div class="stat-label">Avg Orders/Day</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="charts-grid">
                        <div class="chart-card full-width">
                            <div class="chart-title">Weekly Breakdown</div>
                            <div class="chart-container">
                                <canvas id="weeklyChart"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <div class="provider-card">
                        <div class="card-header">
                            <div class="provider-info">
                                <span class="provider-name">Provider Monthly Summary</span>
                            </div>
                        </div>
                        <table class="leaderboard-table">
                            <thead>
                                <tr>
                                    <th>Provider</th>
                                    <th style="text-align: right;">Orders</th>
                                    <th style="text-align: right;">Boxes</th>
                                    <th style="text-align: right;">Weight (kg)</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                data.providers.forEach(p => {
                    html += `
                        <tr>
                            <td><div class="provider-cell"><div class="provider-color" style="background: ${p.color}"></div>${p.name}</div></td>
                            <td style="text-align: right;">${p.orders.toLocaleString()}</td>
                            <td style="text-align: right;">${p.boxes.toLocaleString()}</td>
                            <td style="text-align: right;">${p.weight.toLocaleString(undefined, {maximumFractionDigits: 1})}</td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table></div>';
                
                document.getElementById('monthly-content').innerHTML = html;
                
                if (chart) chart.destroy();
                chart = new Chart(document.getElementById('weeklyChart'), {
                    type: 'bar',
                    data: {
                        labels: data.weeks.map(w => w.label),
                        datasets: [{
                            label: 'Boxes',
                            data: data.weeks.map(w => w.boxes),
                            backgroundColor: '#d4a85399',
                            borderColor: '#d4a853',
                            borderWidth: 2,
                            borderRadius: 8
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
                
            } catch (error) {
                document.getElementById('monthly-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadMonthly();
    </script>
</body>
</html>
    ''')

@app.route('/calendar')
@login_required
def calendar_view():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Calendar View - 3PL Dashboard</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
    <style>
        .premium-calendar {
            background: linear-gradient(145deg, #0c0d12, #0a0a0f);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.05);
            padding: 24px;
        }
        
        .calendar-weekdays {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 8px;
            margin-bottom: 12px;
        }
        
        .weekday-label {
            text-align: center;
            font-size: 12px;
            font-weight: 700;
            color: #d4a853;
            padding: 8px;
            text-transform: uppercase;
        }
        
        .calendar-days-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 8px;
        }
        
        .cal-cell {
            min-height: 80px;
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            padding: 10px;
            cursor: pointer;
            transition: all 0.3s;
            border: 2px solid transparent;
        }
        
        .cal-cell:hover {
            border-color: rgba(212, 168, 83, 0.5);
            transform: translateY(-2px);
        }
        
        .cal-cell.empty {
            background: transparent;
            cursor: default;
            border: none;
        }
        
        .cal-cell.level-0 { background: rgba(100, 116, 139, 0.15); }
        .cal-cell.level-1 { background: rgba(34, 197, 94, 0.15); }
        .cal-cell.level-2 { background: rgba(34, 197, 94, 0.25); }
        .cal-cell.level-3 { background: rgba(251, 191, 36, 0.2); }
        .cal-cell.level-4 { background: rgba(251, 191, 36, 0.35); }
        .cal-cell.level-5 { background: linear-gradient(135deg, rgba(251, 191, 36, 0.5), rgba(217, 119, 6, 0.4)); border-color: #d4a853; }
        
        .cal-day-num {
            font-size: 16px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 4px;
        }
        
        .cal-stat {
            font-size: 10px;
            color: #94a3b8;
        }
    </style>
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='active', active_whatsapp='', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Calendar <span>View</span></h1>
            <div class="month-selector">
                <button class="week-btn" onclick="changeMonth(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="month-display" id="month-display">Loading...</span>
                <button class="week-btn" onclick="changeMonth(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div class="stats-row-5" id="month-stats">
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(59, 130, 246, 0.1); font-size: 24px;">📦</div>
                <div class="stat-content">
                    <div class="stat-value" id="stat-orders">-</div>
                    <div class="stat-label">Orders</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(16, 185, 129, 0.1); font-size: 24px;">📮</div>
                <div class="stat-content">
                    <div class="stat-value" id="stat-boxes">-</div>
                    <div class="stat-label">Boxes</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(245, 158, 11, 0.1); font-size: 24px;">⚖️</div>
                <div class="stat-content">
                    <div class="stat-value" id="stat-weight">-</div>
                    <div class="stat-label">Weight</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(34, 197, 94, 0.1); font-size: 24px;">🪶</div>
                <div class="stat-content">
                    <div class="stat-value" id="stat-light">-</div>
                    <div class="stat-label">&lt;20 kg</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(239, 68, 68, 0.1); font-size: 24px;">🏋️</div>
                <div class="stat-content">
                    <div class="stat-value" id="stat-heavy">-</div>
                    <div class="stat-label">20+ kg</div>
                </div>
            </div>
        </div>
        
        <div class="premium-calendar">
            <div class="calendar-weekdays">
                <div class="weekday-label">Mon</div>
                <div class="weekday-label">Tue</div>
                <div class="weekday-label">Wed</div>
                <div class="weekday-label">Thu</div>
                <div class="weekday-label">Fri</div>
                <div class="weekday-label">Sat</div>
                <div class="weekday-label">Sun</div>
            </div>
            <div class="calendar-days-grid" id="calendar-grid">
                <div class="loading"><div class="spinner"></div></div>
            </div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentDate = new Date();
        
        function formatMonth(date) {
            return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        }
        
        function changeMonth(direction) {
            currentDate.setMonth(currentDate.getMonth() + direction);
            loadCalendar();
        }
        
        function getLevel(boxes, max) {
            if (boxes === 0) return 0;
            const ratio = boxes / max;
            if (ratio >= 0.8) return 5;
            if (ratio >= 0.6) return 4;
            if (ratio >= 0.4) return 3;
            if (ratio >= 0.2) return 2;
            return 1;
        }
        
        async function loadCalendar() {
            document.getElementById('month-display').textContent = formatMonth(currentDate);
            document.getElementById('calendar-grid').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            const year = currentDate.getFullYear();
            const month = currentDate.getMonth() + 1;
            
            try {
                const response = await fetch(`/api/calendar?year=${year}&month=${month}`);
                const data = await response.json();
                
                document.getElementById('stat-orders').textContent = data.totals.orders.toLocaleString();
                document.getElementById('stat-boxes').textContent = data.totals.boxes.toLocaleString();
                document.getElementById('stat-weight').textContent = data.totals.weight.toFixed(1) + ' kg';
                document.getElementById('stat-light').textContent = data.totals.under20.toLocaleString();
                document.getElementById('stat-heavy').textContent = data.totals.over20.toLocaleString();
                
                let html = '';
                const maxBoxes = data.max_boxes || 1;
                
                for (let i = 0; i < data.first_weekday; i++) {
                    html += '<div class="cal-cell empty"></div>';
                }
                
                data.days.forEach(day => {
                    const level = getLevel(day.boxes, maxBoxes);
                    html += `
                        <div class="cal-cell level-${level}">
                            <div class="cal-day-num">${day.day}</div>
                            <div class="cal-stat">📦 ${day.orders} | 📮 ${day.boxes}</div>
                        </div>
                    `;
                });
                
                document.getElementById('calendar-grid').innerHTML = html;
                
            } catch (error) {
                document.getElementById('calendar-grid').innerHTML = '<p style="color: #ef4444;">Error loading calendar</p>';
            }
        }
        
        loadCalendar();
    </script>
</body>
</html>
    ''')

@app.route('/whatsapp')
@login_required
def whatsapp_report():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Report - 3PL</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='active', active_achievements='') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">WhatsApp <span>Report</span></h1>
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="whatsapp-content">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) { return date.toISOString().split('T')[0]; }
        function formatDisplayDate(date) { return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadWhatsApp();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                const btn = document.querySelector('.copy-btn');
                btn.innerHTML = '✓ Copied!';
                setTimeout(() => { btn.innerHTML = '📋 Copy to Clipboard'; }, 2000);
            });
        }
        
        async function loadWhatsApp() {
            updateWeekDisplay();
            document.getElementById('whatsapp-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/whatsapp?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                const html = `
                    <div class="whatsapp-box">
                        <div class="whatsapp-header">
                            <span class="whatsapp-icon">📱</span>
                            <span class="whatsapp-title">Weekly Report - Ready to Share</span>
                        </div>
                        <div class="whatsapp-content" id="report-text">${data.report}</div>
                        <button class="copy-btn" onclick="copyToClipboard(document.getElementById('report-text').textContent)">
                            📋 Copy to Clipboard
                        </button>
                    </div>
                `;
                
                document.getElementById('whatsapp-content').innerHTML = html;
            } catch (error) {
                document.getElementById('whatsapp-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadWhatsApp();
    </script>
</body>
</html>
    ''')

@app.route('/achievements')
@login_required
def achievements_page():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Achievements - 3PL</title>
    ''' + FAVICON + '''
    ''' + BASE_STYLES + '''
</head>
<body>
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_daily_region='', active_flight='', active_analytics='', active_kpi='', active_comparison='', active_regions='', active_monthly='', active_calendar='', active_whatsapp='', active_achievements='active') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Provider <span>Achievements</span></h1>
            <div class="week-selector">
                <button class="week-btn" onclick="changeWeek(-1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                    </svg>
                </button>
                <span class="week-display" id="week-display">Loading...</span>
                <button class="week-btn" onclick="changeWeek(1)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                </button>
            </div>
        </div>
        
        <div id="achievements-content">
            <div class="loading"><div class="spinner"></div></div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(date) {
            const d = new Date(date);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) { return date.toISOString().split('T')[0]; }
        function formatDisplayDate(date) { return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
        
        function changeWeek(direction) {
            currentWeekStart.setDate(currentWeekStart.getDate() + (direction * 7));
            loadAchievements();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        async function loadAchievements() {
            updateWeekDisplay();
            document.getElementById('achievements-content').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            try {
                const response = await fetch('/api/dashboard?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                let html = '';
                
                data.providers.forEach(p => {
                    const achievements = p.achievements || [];
                    
                    html += `
                        <div class="provider-card" style="margin-bottom: 16px;">
                            <div class="card-header">
                                <div class="provider-info">
                                    <div class="provider-color" style="background: ${p.color}; width: 8px; height: 40px; border-radius: 4px;"></div>
                                    <span class="provider-name">${p.name}</span>
                                    <span style="color: #64748b; font-size: 14px;">${p.total_boxes.toLocaleString()} boxes</span>
                                </div>
                            </div>
                            <div style="padding: 20px;">
                                ${achievements.length > 0 ? `
                                    <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                                        ${achievements.map(a => `
                                            <div style="background: rgba(212, 168, 83, 0.1); border: 1px solid rgba(212, 168, 83, 0.2); border-radius: 12px; padding: 16px; text-align: center; min-width: 120px;">
                                                <div style="font-size: 32px; margin-bottom: 8px;">${a.icon}</div>
                                                <div style="font-size: 14px; font-weight: 600; color: #d4a853;">${a.name}</div>
                                                <div style="font-size: 11px; color: #64748b; margin-top: 4px;">${a.desc}</div>
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : `
                                    <div style="color: #64748b; text-align: center; padding: 20px;">
                                        No achievements this week. Keep pushing! 💪
                                    </div>
                                `}
                            </div>
                        </div>
                    `;
                });
                
                document.getElementById('achievements-content').innerHTML = html;
            } catch (error) {
                document.getElementById('achievements-content').innerHTML = '<p style="color: #ef4444;">Error loading data</p>';
            }
        }
        
        loadAchievements();
    </script>
</body>
</html>
    ''')

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/dashboard')
def api_dashboard():
    week_start_str = request.args.get('week_start')
    
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d')
    else:
        week_start, _ = get_week_range()
    
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = prev_week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    providers_data = []
    max_boxes = 0
    winner_idx = 0
    
    for idx, provider in enumerate(PROVIDERS):
        current_data = process_provider_data(provider, week_start, week_end)
        previous_data = process_provider_data(provider, prev_week_start, prev_week_end)
        
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
    
    return jsonify({
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'providers': providers_data
    })

@app.route('/api/weekly-summary')
def api_weekly_summary():
    week_start_str = request.args.get('week_start')
    
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d')
    else:
        week_start, _ = get_week_range()
    
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = prev_week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    providers_data = []
    
    for provider in PROVIDERS:
        current_data = process_provider_data(provider, week_start, week_end)
        previous_data = process_provider_data(provider, prev_week_start, prev_week_end)
        
        if current_data:
            prev_boxes = previous_data['total_boxes'] if previous_data else 0
            current_data['trend'] = calculate_trend(current_data['total_boxes'], prev_boxes)
            providers_data.append(current_data)
    
    providers_data.sort(key=lambda x: x['total_boxes'], reverse=True)
    
    winner = None
    if providers_data and providers_data[0]['total_boxes'] > 0:
        winner = providers_data[0]
        winner['achievements'] = get_provider_achievements(winner, True, winner['trend'])
    
    return jsonify({
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'winner': winner,
        'providers': providers_data
    })

@app.route('/api/flight-load')
def api_flight_load():
    week_start_str = request.args.get('week_start')
    
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d')
    else:
        week_start, _ = get_week_range()
    
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    providers_data = []
    for provider in PROVIDERS:
        data = process_provider_data(provider, week_start, week_end)
        if data:
            providers_data.append(data)
    
    flights = [
        {'name': 'Tuesday Flight (Mon + Tue)', 'days': ['Mon', 'Tue']},
        {'name': 'Thursday Flight (Wed + Thu)', 'days': ['Wed', 'Thu']},
        {'name': 'Saturday Flight (Fri + Sat)', 'days': ['Fri', 'Sat']}
    ]
    
    flight_data = []
    
    for flight in flights:
        flight_info = {
            'name': flight['name'],
            'total_orders': 0,
            'total_boxes': 0,
            'total_weight': 0,
            'providers': []
        }
        
        for provider in providers_data:
            provider_flight = {
                'name': provider['name'],
                'color': provider['color'],
                'orders': 0,
                'boxes': 0,
                'weight': 0
            }
            
            for region_data in provider['regions'].values():
                for day in flight['days']:
                    day_data = region_data['days'].get(day, {})
                    provider_flight['orders'] += day_data.get('orders', 0)
                    provider_flight['boxes'] += day_data.get('boxes', 0)
                    provider_flight['weight'] += day_data.get('weight', 0)
            
            flight_info['total_orders'] += provider_flight['orders']
            flight_info['total_boxes'] += provider_flight['boxes']
            flight_info['total_weight'] += provider_flight['weight']
            flight_info['providers'].append(provider_flight)
        
        flight_info['providers'].sort(key=lambda x: x['boxes'], reverse=True)
        flight_data.append(flight_info)
    
    return jsonify({
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat(),
        'flights': flight_data
    })

# ============================================
# 🆕 NEW API: DAILY REGION SUMMARY
# ============================================
@app.route('/api/daily-region-summary')
def api_daily_region_summary():
    date_str = request.args.get('date')
    
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        return jsonify({'error': 'Invalid date format'}), 400
    
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    result = {
        'date': date_str,
        'date_display': target_date.strftime('%d %b %Y'),
        'totals': {
            'orders': 0,
            'boxes': 0,
            'weight': 0.0,
            'under20': 0,
            'over20': 0
        },
        'providers': []
    }
    
    for provider in PROVIDERS:
        provider_data = {
            'name': provider['short'],
            'color': provider['color'],
            'orders': 0,
            'boxes': 0,
            'weight': 0.0,
            'under20': 0,
            'over20': 0,
            'regions': {}
        }
        
        rows = fetch_sheet_data(provider['sheet'])
        if not rows:
            result['providers'].append(provider_data)
            continue
        
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
                
                if not (day_start <= parsed_date <= day_end):
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
                
                # Update provider totals
                provider_data['orders'] += 1
                provider_data['boxes'] += boxes
                provider_data['weight'] += weight
                
                if weight < 20:
                    provider_data['under20'] += 1
                else:
                    provider_data['over20'] += 1
                
                # Update region data
                if region not in provider_data['regions']:
                    provider_data['regions'][region] = {
                        'name': region,
                        'orders': 0,
                        'boxes': 0,
                        'weight': 0.0,
                        'under20': 0,
                        'over20': 0
                    }
                
                provider_data['regions'][region]['orders'] += 1
                provider_data['regions'][region]['boxes'] += boxes
                provider_data['regions'][region]['weight'] += weight
                
                if weight < 20:
                    provider_data['regions'][region]['under20'] += 1
                else:
                    provider_data['regions'][region]['over20'] += 1
                    
            except Exception as e:
                continue
        
        # Convert regions to sorted list
        regions_list = list(provider_data['regions'].values())
        regions_list.sort(key=lambda x: x['boxes'], reverse=True)
        provider_data['regions'] = regions_list
        
        # Update totals
        result['totals']['orders'] += provider_data['orders']
        result['totals']['boxes'] += provider_data['boxes']
        result['totals']['weight'] += provider_data['weight']
        result['totals']['under20'] += provider_data['under20']
        result['totals']['over20'] += provider_data['over20']
        
        result['providers'].append(provider_data)
    
    # Sort providers by boxes
    result['providers'].sort(key=lambda x: x['boxes'], reverse=True)
    
    return jsonify(result)

# ============================================
# 🆕 NEW API: ANALYTICS DATA (DAILY/WEEKLY/MONTHLY)
# ============================================
@app.route('/api/analytics-data')
def api_analytics_data():
    view = request.args.get('view', 'daily')
    offset = int(request.args.get('offset', 0))
    
    now = datetime.now()
    
    # Calculate date range based on view
    if view == 'daily':
        target_date = now + timedelta(days=offset)
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        # For trend, get last 7 days
        trend_start = start_date - timedelta(days=6)
        trend_dates = [(trend_start + timedelta(days=i)) for i in range(7)]
    elif view == 'weekly':
        monday = now - timedelta(days=now.weekday())
        monday = monday + timedelta(weeks=offset)
        start_date = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
        trend_dates = None  # Will use day names
    else:  # monthly
        year = now.year
        month = now.month + offset
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        trend_dates = None  # Will use week numbers
    
    # Initialize result
    result = {
        'totals': {
            'orders': 0,
            'boxes': 0,
            'weight': 0.0,
            'under20': 0,
            'over20': 0
        },
        'trend': {
            'labels': [],
            'orders': [],
            'boxes': []
        },
        'providers': [],
        'regions': []
    }
    
    # Aggregate data
    provider_data = {}
    region_data = {}
    trend_data = defaultdict(lambda: {'orders': 0, 'boxes': 0})
    
    for provider in PROVIDERS:
        pkey = provider['short']
        provider_data[pkey] = {
            'name': provider['short'],
            'color': provider['color'],
            'orders': 0,
            'boxes': 0,
            'weight': 0.0,
            'under20': 0,
            'over20': 0
        }
        
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
                
                if not parsed_date:
                    continue
                
                if not (start_date <= parsed_date <= end_date):
                    # Check if in trend range for daily view
                    if view == 'daily' and trend_dates:
                        trend_start_check = trend_dates[0].replace(hour=0, minute=0, second=0)
                        trend_end_check = trend_dates[-1].replace(hour=23, minute=59, second=59)
                        if not (trend_start_check <= parsed_date <= trend_end_check):
                            continue
                    else:
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
                
                # Only count in totals if within main date range
                if start_date <= parsed_date <= end_date:
                    result['totals']['orders'] += 1
                    result['totals']['boxes'] += boxes
                    result['totals']['weight'] += weight
                    
                    if weight < 20:
                        result['totals']['under20'] += 1
                    else:
                        result['totals']['over20'] += 1
                    
                    provider_data[pkey]['orders'] += 1
                    provider_data[pkey]['boxes'] += boxes
                    provider_data[pkey]['weight'] += weight
                    
                    if weight < 20:
                        provider_data[pkey]['under20'] += 1
                    else:
                        provider_data[pkey]['over20'] += 1
                    
                    if region not in region_data:
                        region_data[region] = {
                            'name': region,
                            'orders': 0,
                            'boxes': 0,
                            'weight': 0.0,
                            'under20': 0,
                            'over20': 0
                        }
                    
                    region_data[region]['orders'] += 1
                    region_data[region]['boxes'] += boxes
                    region_data[region]['weight'] += weight
                    
                    if weight < 20:
                        region_data[region]['under20'] += 1
                    else:
                        region_data[region]['over20'] += 1
                
                # Trend data
                if view == 'daily':
                    date_key = parsed_date.strftime('%b %d')
                elif view == 'weekly':
                    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                    date_key = day_names[parsed_date.weekday()]
                else:
                    week_num = (parsed_date.day - 1) // 7 + 1
                    date_key = f'Week {week_num}'
                
                trend_data[date_key]['orders'] += 1
                trend_data[date_key]['boxes'] += boxes
                    
            except Exception as e:
                continue
    
    # Build trend labels based on view
    if view == 'daily':
        result['trend']['labels'] = [(trend_start + timedelta(days=i)).strftime('%b %d') for i in range(7)]
    elif view == 'weekly':
        result['trend']['labels'] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    else:
        weeks_in_month = ((end_date.day - 1) // 7) + 1
        result['trend']['labels'] = [f'Week {i+1}' for i in range(weeks_in_month)]
    
    for label in result['trend']['labels']:
        result['trend']['orders'].append(trend_data[label]['orders'])
        result['trend']['boxes'].append(trend_data[label]['boxes'])
    
    # Convert to lists and sort
    result['providers'] = list(provider_data.values())
    result['providers'].sort(key=lambda x: x['boxes'], reverse=True)
    
    result['regions'] = list(region_data.values())
    result['regions'].sort(key=lambda x: x['boxes'], reverse=True)
    
    return jsonify(result)

@app.route('/api/kpi')
def api_kpi():
    week_start_str = request.args.get('week_start')
    
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d')
    else:
        week_start, _ = get_week_range()
    
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = prev_week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    total_orders = 0
    total_boxes = 0
    total_weight = 0
    prev_orders = 0
    prev_boxes = 0
    prev_weight = 0
    all_regions = set()
    daily_totals = defaultdict(int)
    provider_totals = {}
    
    for provider in PROVIDERS:
        current_data = process_provider_data(provider, week_start, week_end)
        previous_data = process_provider_data(provider, prev_week_start, prev_week_end)
        
        if current_data:
            total_orders += current_data['total_orders']
            total_boxes += current_data['total_boxes']
            total_weight += current_data['total_weight']
            all_regions.update(current_data['regions'].keys())
            provider_totals[current_data['name']] = current_data['total_boxes']
            
            for day, data in current_data['daily_totals'].items():
                daily_totals[day] += data['orders']
        
        if previous_data:
            prev_orders += previous_data['total_orders']
            prev_boxes += previous_data['total_boxes']
            prev_weight += previous_data['total_weight']
    
    best_day = max(daily_totals, key=daily_totals.get) if daily_totals else 'N/A'
    top_provider = max(provider_totals, key=provider_totals.get) if provider_totals else 'N/A'
    
    return jsonify({
        'total_orders': total_orders,
        'total_boxes': total_boxes,
        'total_weight': total_weight,
        'avg_boxes_per_day': total_boxes / 7,
        'avg_weight_per_order': total_weight / total_orders if total_orders > 0 else 0,
        'active_regions': len(all_regions),
        'top_provider': top_provider.replace('GLOBAL EXPRESS', 'GE').replace('ECL LOGISTICS', 'ECL'),
        'top_region': 'UAE',
        'best_day': best_day,
        'boxes_trend': calculate_trend(total_boxes, prev_boxes),
        'orders_trend': calculate_trend(total_orders, prev_orders),
        'weight_trend': calculate_trend(total_weight, prev_weight)
    })

@app.route('/api/regions')
def api_regions():
    week_start_str = request.args.get('week_start')
    
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d')
    else:
        week_start, _ = get_week_range()
    
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    region_data = defaultdict(lambda: {'orders': 0, 'boxes': 0, 'weight': 0})
    
    for provider in PROVIDERS:
        data = process_provider_data(provider, week_start, week_end)
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
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    total_orders = 0
    total_boxes = 0
    total_weight = 0
    provider_totals = defaultdict(lambda: {'orders': 0, 'boxes': 0, 'weight': 0, 'color': '#64748b'})
    weeks_data = []
    
    current = first_day
    week_num = 1
    while current <= last_day:
        week_start = current - timedelta(days=current.weekday())
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        week_boxes = 0
        for provider in PROVIDERS:
            data = process_provider_data(provider, week_start, week_end)
            if data:
                total_orders += data['total_orders']
                total_boxes += data['total_boxes']
                total_weight += data['total_weight']
                week_boxes += data['total_boxes']
                
                provider_totals[data['name']]['orders'] += data['total_orders']
                provider_totals[data['name']]['boxes'] += data['total_boxes']
                provider_totals[data['name']]['weight'] += data['total_weight']
                provider_totals[data['name']]['color'] = data['color']
        
        weeks_data.append({
            'label': f'Week {week_num}',
            'boxes': week_boxes
        })
        
        current = week_start + timedelta(days=7)
        week_num += 1
    
    providers = [{'name': k, **v} for k, v in provider_totals.items()]
    providers.sort(key=lambda x: x['boxes'], reverse=True)
    
    days_in_month = (last_day - first_day).days + 1
    
    return jsonify({
        'total_orders': total_orders,
        'total_boxes': total_boxes,
        'total_weight': total_weight,
        'avg_per_day': total_orders / days_in_month if days_in_month > 0 else 0,
        'weeks': weeks_data,
        'providers': providers
    })

@app.route('/api/calendar')
def api_calendar():
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    _, num_days = calendar.monthrange(year, month)
    first_day = datetime(year, month, 1)
    first_weekday = first_day.weekday()
    
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    days_data = {}
    for day in range(1, num_days + 1):
        days_data[day] = {
            'day': day,
            'date': f'{year}-{month:02d}-{day:02d}',
            'weekday': day_names[(first_weekday + day - 1) % 7],
            'orders': 0,
            'boxes': 0,
            'weight': 0.0,
            'under20': 0,
            'over20': 0
        }
    
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
                
                if not parsed_date:
                    continue
                
                if not (month_start <= parsed_date <= month_end):
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
                
                days_data[day]['orders'] += 1
                days_data[day]['boxes'] += boxes
                days_data[day]['weight'] += weight
                
                if weight < 20:
                    days_data[day]['under20'] += 1
                else:
                    days_data[day]['over20'] += 1
                    
            except Exception as e:
                continue
    
    total_orders = sum(d['orders'] for d in days_data.values())
    total_boxes = sum(d['boxes'] for d in days_data.values())
    total_weight = sum(d['weight'] for d in days_data.values())
    total_under20 = sum(d['under20'] for d in days_data.values())
    total_over20 = sum(d['over20'] for d in days_data.values())
    max_boxes = max((d['boxes'] for d in days_data.values()), default=1)
    
    return jsonify({
        'year': year,
        'month': month,
        'month_name': first_day.strftime('%B %Y'),
        'first_weekday': first_weekday,
        'total_days': num_days,
        'totals': {
            'orders': total_orders,
            'boxes': total_boxes,
            'weight': total_weight,
            'under20': total_under20,
            'over20': total_over20
        },
        'max_boxes': max_boxes,
        'days': list(days_data.values())
    })

@app.route('/api/daily-summary')
def api_daily_summary():
    date_str = request.args.get('date')
    
    if not date_str:
        return jsonify({'error': 'Date required'}), 400
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        return jsonify({'error': 'Invalid date format'}), 400
    
    day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    result = {
        'date': date_str,
        'weekday': day_names[target_date.weekday()],
        'orders': 0,
        'boxes': 0,
        'weight': 0.0,
        'under20': 0,
        'over20': 0,
        'regions': {}
    }
    
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
                
                if not parsed_date:
                    continue
                
                if not (day_start <= parsed_date <= day_end):
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
                
                result['orders'] += 1
                result['boxes'] += boxes
                result['weight'] += weight
                
                if weight < 20:
                    result['under20'] += 1
                else:
                    result['over20'] += 1
                
                if region not in result['regions']:
                    result['regions'][region] = {
                        'name': region,
                        'orders': 0,
                        'boxes': 0,
                        'weight': 0.0,
                        'under20': 0,
                        'over20': 0
                    }
                
                result['regions'][region]['orders'] += 1
                result['regions'][region]['boxes'] += boxes
                result['regions'][region]['weight'] += weight
                
                if weight < 20:
                    result['regions'][region]['under20'] += 1
                else:
                    result['regions'][region]['over20'] += 1
                    
            except Exception as e:
                continue
    
    regions_list = list(result['regions'].values())
    regions_list.sort(key=lambda x: x['boxes'], reverse=True)
    result['regions'] = regions_list
    
    return jsonify(result)

@app.route('/api/whatsapp')
def api_whatsapp():
    week_start_str = request.args.get('week_start')
    
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d')
    else:
        week_start, _ = get_week_range()
    
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    providers_data = []
    total_orders = 0
    total_boxes = 0
    total_weight = 0
    
    for provider in PROVIDERS:
        data = process_provider_data(provider, week_start, week_end)
        if data:
            providers_data.append(data)
            total_orders += data['total_orders']
            total_boxes += data['total_boxes']
            total_weight += data['total_weight']
    
    providers_data.sort(key=lambda x: x['total_boxes'], reverse=True)
    
    date_range = f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
    
    report = f"""📊 *3PL Weekly Report*
📅 {date_range}

━━━━━━━━━━━━━━━━━━━━

🏆 *PROVIDER RANKING*

"""
    
    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣']
    for i, p in enumerate(providers_data):
        short_name = p['name'].replace('GLOBAL EXPRESS', 'GE').replace('ECL LOGISTICS', 'ECL')
        report += f"{medals[i]} *{short_name}*\n"
        report += f"   📦 {p['total_boxes']:,} boxes | ⚖️ {p['total_weight']:,.1f} kg\n\n"
    
    report += f"""━━━━━━━━━━━━━━━━━━━━

📈 *WEEKLY TOTALS*

📋 Orders: *{total_orders:,}*
📦 Boxes: *{total_boxes:,}*
⚖️ Weight: *{total_weight:,.1f} kg*

━━━━━━━━━━━━━━━━━━━━
_Generated by 3PL Dashboard_"""
    
    return jsonify({'report': report})

@app.route('/api/clear-cache')
def clear_cache():
    global CACHE
    CACHE = {}
    return jsonify({'status': 'success', 'message': 'Cache cleared'})

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    app.run(debug=True)
