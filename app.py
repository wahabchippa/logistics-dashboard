from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from functools import wraps
import csv
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
import time
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# ============================================
# ADMIN PASSWORD (Set in Vercel Environment Variables)
# ============================================
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

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
        'sheet': 'GE QC Center & Zone',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'start_row': 2,
        'color': '#3B82F6'
    },
    {
        'name': 'GLOBAL EXPRESS (ZONE)',
        'sheet': 'GE QC Center & Zone',
        'date_col': 10,
        'box_col': 11,
        'weight_col': 14,
        'region_col': 16,
        'start_row': 2,
        'color': '#8B5CF6'
    },
    {
        'name': 'ECL LOGISTICS (QC)',
        'sheet': 'ECL QC Center & Zone',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'start_row': 3,
        'color': '#10B981'
    },
    {
        'name': 'ECL LOGISTICS (ZONE)',
        'sheet': 'ECL QC Center & Zone',
        'date_col': 10,
        'box_col': 11,
        'weight_col': 14,
        'region_col': 16,
        'start_row': 3,
        'color': '#F59E0B'
    },
    {
        'name': 'KERRY',
        'sheet': 'Kerry',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'start_row': 2,
        'color': '#EF4444'
    },
    {
        'name': 'APX',
        'sheet': 'APX',
        'date_col': 1,
        'box_col': 2,
        'weight_col': 5,
        'region_col': 7,
        'start_row': 2,
        'color': '#EC4899'
    }
]

INVALID_REGIONS = {'', 'N/A', '#N/A', 'COUNTRY', 'REGION', 'DESTINATION', 'ZONE', 'ORDER', 'FLEEK ID', 'DATE', 'CARTONS'}

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
        'color': provider['color'],
        'total_orders': 0,
        'total_boxes': 0,
        'total_weight': 0.0,
        'regions': defaultdict(lambda: {
            'days': {day: {'orders': 0, 'boxes': 0, 'weight': 0.0, 'under20': 0, 'over20': 0} 
                    for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']}
        })
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
        width: 260px;
        background: linear-gradient(180deg, #0a0a0f 0%, #0c0d12 100%);
        border-right: 1px solid rgba(212, 168, 83, 0.1);
        padding: 24px 16px;
        transition: all 0.3s ease;
        z-index: 100;
        display: flex;
        flex-direction: column;
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
    
    .nav-menu {
        display: flex;
        flex-direction: column;
        gap: 8px;
        flex-grow: 1;
    }
    
    .nav-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        border-radius: 8px;
        color: #64748b;
        text-decoration: none;
        transition: all 0.2s;
        cursor: pointer;
        position: relative;
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
        width: 20px;
        height: 20px;
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
        padding: 12px 16px;
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
        width: 20px;
        height: 20px;
        flex-shrink: 0;
    }
    
    .sidebar.collapsed .logout-btn span {
        opacity: 0;
        width: 0;
    }
    
    /* Main Content */
    .main-content {
        margin-left: 260px;
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
    
    .card-stats {
        display: flex;
        gap: 24px;
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
    }
    
    .stat-icon svg {
        width: 24px;
        height: 24px;
    }
    
    .stat-content {
        flex: 1;
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
    
    /* Responsive */
    @media (max-width: 768px) {
        .sidebar {
            width: 70px;
        }
        
        .sidebar .logo-text,
        .sidebar .nav-item span,
        .sidebar .logout-btn span {
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
    }
</style>
"""

SIDEBAR_HTML = """
<nav class="sidebar" id="sidebar">
    <div class="sidebar-toggle" onclick="toggleSidebar()">«</div>
    
    <div class="sidebar-header">
        <div class="logo-icon">3P</div>
        <span class="logo-text">3PL Dashboard</span>
    </div>
    
    <div class="nav-menu">
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
        
        <a href="/flight-load" class="nav-item {active_flight}">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
            <span>Flight Load</span>
            <div class="tooltip">Flight Load</div>
        </a>
        
        <a href="/analytics" class="nav-item {active_analytics}">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
            </svg>
            <span>Analytics</span>
            <div class="tooltip">Analytics</div>
        </a>
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
    ''' + SIDEBAR_HTML.format(active_dashboard='active', active_weekly='', active_flight='', active_analytics='') + '''
    
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
            const trendClass = provider.trend.direction === 'up' ? 'up' : 'down';
            const trendIcon = provider.trend.direction === 'up' ? '▲' : '▼';
            
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
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='active', active_flight='', active_analytics='') + '''
    
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
                    html += `
                        <div class="provider-card winner-card">
                            <div class="card-header">
                                <div class="provider-info">
                                    <span style="font-size: 32px; margin-right: 12px;">🏆</span>
                                    <div>
                                        <div class="provider-name" style="font-size: 24px;">Week Winner: ${data.winner.name}</div>
                                        <div style="color: #d4a853; margin-top: 4px;">${data.winner.total_boxes.toLocaleString()} boxes • ${data.winner.total_weight.toLocaleString(undefined, {maximumFractionDigits: 1})} kg</div>
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
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_flight='active', active_analytics='') + '''
    
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
    ''' + SIDEBAR_HTML.format(active_dashboard='', active_weekly='', active_flight='', active_analytics='active') + '''
    
    <main class="main-content" id="main-content">
        <div class="page-header">
            <h1 class="page-title">Analytics & <span>Insights</span></h1>
            
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
        
        <!-- Stats Row -->
        <div class="stats-row" id="stats-row">
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(59, 130, 246, 0.1);">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="#3B82F6">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                </div>
                <div class="stat-content">
                    <div class="stat-value" id="total-orders">0</div>
                    <div class="stat-label">Total Orders</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(16, 185, 129, 0.1);">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="#10B981">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                    </svg>
                </div>
                <div class="stat-content">
                    <div class="stat-value" id="total-boxes">0</div>
                    <div class="stat-label">Total Boxes</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(212, 168, 83, 0.1);">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="#d4a853">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                    </svg>
                </div>
                <div class="stat-content">
                    <div class="stat-value" id="total-weight">0</div>
                    <div class="stat-label">Total Weight (kg)</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(139, 92, 246, 0.1);">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="#8B5CF6">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                </div>
                <div class="stat-content">
                    <div class="stat-value" id="total-providers">6</div>
                    <div class="stat-label">Active Providers</div>
                </div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Provider Performance (Boxes)
                </div>
                <div class="chart-container">
                    <canvas id="providerBarChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <div class="chart-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
                    </svg>
                    Weight Distribution by Provider
                </div>
                <div class="chart-container">
                    <canvas id="weightPieChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card full-width">
                <div class="chart-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                    </svg>
                    Daily Orders Trend
                </div>
                <div class="chart-container">
                    <canvas id="dailyLineChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <div class="chart-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Orders vs Boxes Comparison
                </div>
                <div class="chart-container">
                    <canvas id="comparisonChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <div class="chart-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Top Regions by Orders
                </div>
                <div class="chart-container">
                    <canvas id="regionDoughnutChart"></canvas>
                </div>
            </div>
        </div>
    </main>
    
    ''' + SIDEBAR_SCRIPT + '''
    
    <script>
        let currentWeekStart = getMonday(new Date());
        let charts = {};
        
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
        Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
        
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
            loadAnalytics();
        }
        
        function updateWeekDisplay() {
            const endDate = new Date(currentWeekStart);
            endDate.setDate(endDate.getDate() + 6);
            document.getElementById('week-display').textContent = 
                formatDisplayDate(currentWeekStart) + ' - ' + formatDisplayDate(endDate);
        }
        
        function destroyCharts() {
            Object.values(charts).forEach(chart => {
                if (chart) chart.destroy();
            });
            charts = {};
        }
        
        async function loadAnalytics() {
            updateWeekDisplay();
            destroyCharts();
            
            try {
                const response = await fetch('/api/dashboard?week_start=' + formatDate(currentWeekStart));
                const data = await response.json();
                
                let totalOrders = 0;
                let totalBoxes = 0;
                let totalWeight = 0;
                
                const providerNames = [];
                const providerBoxes = [];
                const providerWeights = [];
                const providerColors = [];
                const providerOrders = [];
                
                const dailyData = {Mon: 0, Tue: 0, Wed: 0, Thu: 0, Fri: 0, Sat: 0, Sun: 0};
                const regionData = {};
                
                data.providers.forEach(p => {
                    totalOrders += p.total_orders;
                    totalBoxes += p.total_boxes;
                    totalWeight += p.total_weight;
                    
                    providerNames.push(p.name.replace('GLOBAL EXPRESS', 'GE').replace('ECL LOGISTICS', 'ECL'));
                    providerBoxes.push(p.total_boxes);
                    providerWeights.push(p.total_weight);
                    providerColors.push(p.color);
                    providerOrders.push(p.total_orders);
                    
                    Object.values(p.regions).forEach(region => {
                        Object.entries(region.days).forEach(([day, d]) => {
                            dailyData[day] += d.orders;
                        });
                    });
                    
                    Object.entries(p.regions).forEach(([regionName, regionInfo]) => {
                        if (!regionData[regionName]) regionData[regionName] = 0;
                        Object.values(regionInfo.days).forEach(d => {
                            regionData[regionName] += d.orders;
                        });
                    });
                });
                
                document.getElementById('total-orders').textContent = totalOrders.toLocaleString();
                document.getElementById('total-boxes').textContent = totalBoxes.toLocaleString();
                document.getElementById('total-weight').textContent = totalWeight.toLocaleString(undefined, {maximumFractionDigits: 1});
                
                charts.providerBar = new Chart(document.getElementById('providerBarChart'), {
                    type: 'bar',
                    data: {
                        labels: providerNames,
                        datasets: [{
                            label: 'Boxes',
                            data: providerBoxes,
                            backgroundColor: providerColors.map(c => c + '99'),
                            borderColor: providerColors,
                            borderWidth: 2,
                            borderRadius: 8,
                            borderSkipped: false
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
                
                charts.weightPie = new Chart(document.getElementById('weightPieChart'), {
                    type: 'pie',
                    data: {
                        labels: providerNames,
                        datasets: [{
                            data: providerWeights,
                            backgroundColor: providerColors.map(c => c + 'CC'),
                            borderColor: '#0a0a0f',
                            borderWidth: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: { padding: 15, usePointStyle: true, pointStyle: 'circle' }
                            }
                        }
                    }
                });
                
                charts.dailyLine = new Chart(document.getElementById('dailyLineChart'), {
                    type: 'line',
                    data: {
                        labels: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                        datasets: [{
                            label: 'Orders',
                            data: Object.values(dailyData),
                            borderColor: '#d4a853',
                            backgroundColor: 'rgba(212, 168, 83, 0.1)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: '#d4a853',
                            pointBorderColor: '#0a0a0f',
                            pointBorderWidth: 2,
                            pointRadius: 6,
                            pointHoverRadius: 8
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
                
                charts.comparison = new Chart(document.getElementById('comparisonChart'), {
                    type: 'bar',
                    data: {
                        labels: providerNames,
                        datasets: [
                            {
                                label: 'Orders',
                                data: providerOrders,
                                backgroundColor: 'rgba(59, 130, 246, 0.7)',
                                borderColor: '#3B82F6',
                                borderWidth: 2,
                                borderRadius: 6
                            },
                            {
                                label: 'Boxes',
                                data: providerBoxes,
                                backgroundColor: 'rgba(16, 185, 129, 0.7)',
                                borderColor: '#10B981',
                                borderWidth: 2,
                                borderRadius: 6
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'top',
                                labels: { padding: 15, usePointStyle: true }
                            }
                        },
                        scales: {
                            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
                
                const sortedRegions = Object.entries(regionData)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 6);
                
                const regionColors = ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#EC4899'];
                
                charts.regionDoughnut = new Chart(document.getElementById('regionDoughnutChart'), {
                    type: 'doughnut',
                    data: {
                        labels: sortedRegions.map(r => r[0]),
                        datasets: [{
                            data: sortedRegions.map(r => r[1]),
                            backgroundColor: regionColors.map(c => c + 'CC'),
                            borderColor: '#0a0a0f',
                            borderWidth: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '60%',
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: { padding: 12, usePointStyle: true, pointStyle: 'circle' }
                            }
                        }
                    }
                });
                
            } catch (error) {
                console.error('Error loading analytics:', error);
            }
        }
        
        loadAnalytics();
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
    
    for provider in PROVIDERS:
        current_data = process_provider_data(provider, week_start, week_end)
        previous_data = process_provider_data(provider, prev_week_start, prev_week_end)
        
        if current_data:
            prev_boxes = previous_data['total_boxes'] if previous_data else 0
            current_data['trend'] = calculate_trend(current_data['total_boxes'], prev_boxes)
            providers_data.append(current_data)
    
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
    
    winner = providers_data[0] if providers_data else None
    
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
