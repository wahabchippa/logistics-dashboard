from flask import Flask, render_template_string, jsonify, request
from datetime import datetime, timedelta
import requests
import csv
from io import StringIO

app = Flask(__name__)

# DIRECT PUBLISHED CSV LINKS - YEH KAAM KARENGE!
PROVIDERS = [
    {
        "name": "GLOBAL EXPRESS (QC)", 
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQjCPd8bUpx59Sit8gMMXjVKhIFA_f-W9Q4mkBSWulOTg4RGahcVXSD4xZiYBAcAH6eO40aEQ9IEEXj/pub?gid=710036753&single=true&output=csv",
        "dateCol": 0, "boxCol": 1, "weightCol": 4, "regionCol": 6, "startRow": 2
    },
    {
        "name": "GLOBAL EXPRESS (ZONES)", 
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQjCPd8bUpx59Sit8gMMXjVKhIFA_f-W9Q4mkBSWulOTg4RGahcVXSD4xZiYBAcAH6eO40aEQ9IEEXj/pub?gid=10726393&single=true&output=csv",
        "dateCol": 0, "boxCol": 1, "weightCol": 4, "regionCol": 6, "startRow": 2
    },
    {
        "name": "ECL LOGISTICS (QC)", 
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCiZ1MdPMyVAzBqmBmp3Ch8sfefOp_kfPk2RSfMv3bxRD_qccuwaoM7WTVsieKJbA3y3DF41tUxb3T/pub?gid=0&single=true&output=csv",
        "dateCol": 0, "boxCol": 1, "weightCol": 4, "regionCol": 6, "startRow": 3
    },
    {
        "name": "ECL LOGISTICS (ZONES)", 
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCiZ1MdPMyVAzBqmBmp3Ch8sfefOp_kfPk2RSfMv3bxRD_qccuwaoM7WTVsieKJbA3y3DF41tUxb3T/pub?gid=928309568&single=true&output=csv",
        "dateCol": 0, "boxCol": 1, "weightCol": 4, "regionCol": 6, "startRow": 3
    },
    {
        "name": "KERRY LOGISTICS", 
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vTZyLyZpVJz9sV5eT4Srwo_KZGnYggpRZkm2ILLYPQKSpTKkWfP9G5759h247O4QEflKCzlQauYsLKI/pub?gid=0&single=true&output=csv",
        "dateCol": 0, "boxCol": 1, "weightCol": 4, "regionCol": 6, "startRow": 2
    },
    {
        "name": "APX EXPRESS", 
        "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vRDEzAMUwnFZ7aoThGoMERtxxsll2kfEaSpa9ksXIx6sqbdMncts6Go2d5mKKabepbNXDSoeaUlk-mP/pub?gid=0&single=true&output=csv",
        "dateCol": 0, "boxCol": 1, "weightCol": 4, "regionCol": 6, "startRow": 2
    },
]

def fetch_sheet_data(url):
    """Fetch CSV data from published Google Sheet"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        reader = csv.reader(StringIO(response.text))
        return list(reader)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

def parse_date(date_str):
    """Parse date from various formats"""
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
    """Safely convert to float"""
    try:
        clean = str(val).replace(',', '').replace(' ', '').strip()
        if clean == "" or clean == "-" or clean.upper() in ["N/A", "#N/A", "NA"]:
            return 0
        return float(clean)
    except:
        return 0

def safe_int(val):
    """Safely convert to int"""
    return int(safe_float(val))

def is_valid_region(region):
    """Check if region value is valid"""
    if not region:
        return False
    region = str(region).strip().upper()
    invalid = ["", "N/A", "#N/A", "COUNTRY", "REGION", "NA", "-", "DESTINATION"]
    return region not in invalid and len(region) > 0

def get_rating(total_boxes):
    """Get star rating based on total boxes"""
    if total_boxes >= 1500:
        return "★★★★★"
    elif total_boxes >= 500:
        return "★★★★☆"
    elif total_boxes >= 100:
        return "★★★☆☆"
    else:
        return "★★☆☆☆"

def get_trend(current_boxes, previous_boxes):
    """Get trend indicator - CORRECT LOGIC"""
    if current_boxes >= previous_boxes:
        return {"text": "UP", "class": "trend-up"}
    else:
        return {"text": "DOWN", "class": "trend-down"}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>G-OPS 3PL Executive Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0B1120;
            color: #E5E7EB;
            min-height: 100vh;
        }
        
        .container {
            display: flex;
            min-height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            width: 220px;
            background: #111827;
            border-right: 1px solid #1F2937;
            padding: 20px 0;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }
        
        .logo {
            padding: 0 20px 20px;
            border-bottom: 1px solid #1F2937;
            margin-bottom: 20px;
        }
        
        .logo h1 {
            color: #FBBF24;
            font-size: 18px;
            font-weight: 700;
        }
        
        .logo p {
            color: #6B7280;
            font-size: 12px;
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 20px;
            color: #9CA3AF;
            text-decoration: none;
            transition: all 0.2s;
            cursor: pointer;
            border-left: 3px solid transparent;
        }
        
        .nav-item:hover, .nav-item.active {
            background: #1F2937;
            color: #FBBF24;
            border-left-color: #FBBF24;
        }
        
        .nav-item svg {
            width: 20px;
            height: 20px;
            margin-right: 12px;
        }
        
        /* Main Content */
        .main {
            flex: 1;
            margin-left: 220px;
            padding: 20px;
            overflow-x: auto;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .date-selector {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .date-selector label {
            color: #9CA3AF;
            font-size: 14px;
        }
        
        .date-selector input {
            background: #1F2937;
            border: 1px solid #374151;
            color: #E5E7EB;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
        }
        
        .week-display {
            color: #FBBF24;
            font-size: 16px;
            font-weight: 600;
        }
        
        /* Provider Card */
        .provider-card {
            background: #111827;
            border: 1px solid #1F2937;
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: hidden;
        }
        
        .provider-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            background: linear-gradient(90deg, #1F2937 0%, #111827 100%);
            border-bottom: 1px solid #1F2937;
        }
        
        .provider-title {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .provider-name {
            color: #FBBF24;
            font-size: 16px;
            font-weight: 700;
        }
        
        .rating {
            color: #FBBF24;
            font-size: 14px;
        }
        
        .trend-up {
            background: #065F46;
            color: #10B981;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .trend-down {
            background: #7F1D1D;
            color: #EF4444;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .provider-totals {
            display: flex;
            gap: 20px;
            color: #9CA3AF;
            font-size: 13px;
        }
        
        .provider-totals span {
            color: #E5E7EB;
            font-weight: 600;
        }
        
        /* Data Table */
        .data-table {
            width: 100%;
            overflow-x: auto;
        }
        
        .data-table table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        
        .data-table th, .data-table td {
            padding: 8px 6px;
            text-align: center;
            border-bottom: 1px solid #1F2937;
        }
        
        .data-table th {
            background: #1F2937;
            color: #9CA3AF;
            font-weight: 500;
            font-size: 11px;
            text-transform: uppercase;
        }
        
        .day-header {
            background: #1F2937 !important;
            color: #E5E7EB !important;
            font-weight: 600 !important;
        }
        
        .flight-day {
            background: #1E3A5F !important;
            color: #60A5FA !important;
        }
        
        .flight-day::after {
            content: " ✈";
        }
        
        .region-col {
            text-align: left !important;
            padding-left: 15px !important;
            color: #9CA3AF;
            font-weight: 500;
        }
        
        .total-row {
            background: #0D1422;
            font-weight: 600;
        }
        
        .total-row td {
            color: #FBBF24 !important;
        }
        
        .total-label {
            color: #FBBF24 !important;
            text-align: left !important;
            padding-left: 15px !important;
        }
        
        .zero-val {
            color: #4B5563;
        }
        
        .has-val {
            color: #E5E7EB;
        }
        
        .weight-val {
            color: #60A5FA;
        }
        
        /* Loading */
        .loading {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 200px;
            color: #FBBF24;
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid #1F2937;
            border-top-color: #FBBF24;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .sidebar {
                width: 60px;
            }
            .sidebar .logo h1, .sidebar .logo p, .nav-item span {
                display: none;
            }
            .main {
                margin-left: 60px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="logo">
                <h1>✦ G-OPS 3PL</h1>
                <p>Executive Portal</p>
            </div>
            <nav>
                <a class="nav-item active" data-page="dashboard">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path>
                    </svg>
                    <span>Dashboard</span>
                </a>
                <a class="nav-item" data-page="weekly">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                    <span>Weekly Summary</span>
                </a>
                <a class="nav-item" data-page="flight">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                    </svg>
                    <span>Flight Load</span>
                </a>
            </nav>
        </aside>
        
        <!-- Main Content -->
        <main class="main">
            <div class="header">
                <div class="date-selector">
                    <label>📅 SELECT WEEK START:</label>
                    <input type="date" id="weekStart">
                </div>
                <div class="week-display" id="weekDisplay"></div>
            </div>
            
            <div id="content">
                <div class="loading">
                    <div class="spinner"></div>
                </div>
            </div>
        </main>
    </div>
    
    <script>
        // Initialize
        let currentWeekStart = getMonday(new Date());
        
        function getMonday(d) {
            d = new Date(d);
            const day = d.getDay();
            const diff = d.getDate() - day + (day === 0 ? -6 : 1);
            return new Date(d.setDate(diff));
        }
        
        function formatDate(date) {
            const d = new Date(date);
            return d.toISOString().split('T')[0];
        }
        
        function formatDisplayDate(date) {
            const d = new Date(date);
            const day = d.getDate();
            const month = d.toLocaleString('en-US', { month: 'short' });
            return `${day}-${month}`;
        }
        
        // Set date picker
        document.getElementById('weekStart').value = formatDate(currentWeekStart);
        
        // Date change handler
        document.getElementById('weekStart').addEventListener('change', function() {
            currentWeekStart = getMonday(new Date(this.value));
            this.value = formatDate(currentWeekStart);
            loadData();
        });
        
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', function() {
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                this.classList.add('active');
                loadData();
            });
        });
        
        function loadData() {
            const content = document.getElementById('content');
            content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
            
            const weekStart = formatDate(currentWeekStart);
            const weekEnd = formatDate(new Date(currentWeekStart.getTime() + 6 * 24 * 60 * 60 * 1000));
            
            document.getElementById('weekDisplay').textContent = `${formatDisplayDate(currentWeekStart)}-${formatDisplayDate(new Date(currentWeekStart.getTime() + 6 * 24 * 60 * 60 * 1000))}`;
            
            fetch(`/api/data?week_start=${weekStart}`)
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        content.innerHTML = `<div class="loading" style="color: #EF4444;">${data.error}</div>`;
                        return;
                    }
                    renderDashboard(data);
                })
                .catch(err => {
                    content.innerHTML = `<div class="loading" style="color: #EF4444;">Error loading data: ${err.message}</div>`;
                });
        }
        
        function renderDashboard(data) {
            const content = document.getElementById('content');
            const days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
            const flightDays = [1, 3, 5]; // TUE, THU, SAT (0-indexed from MON)
            
            let html = '';
            
            data.providers.forEach(provider => {
                const totalOrders = provider.totals.orders;
                const totalBoxes = provider.totals.boxes;
                const totalWeight = provider.totals.weight.toFixed(1);
                
                html += `
                <div class="provider-card">
                    <div class="provider-header">
                        <div class="provider-title">
                            <span class="provider-name">✦ ${provider.name}</span>
                            <span class="rating">RATING: ${provider.rating}</span>
                            <span class="${provider.trend.class}">🚀 ${provider.trend.text}</span>
                        </div>
                        <div class="provider-totals">
                            Orders: <span>${totalOrders}</span> | Boxes: <span>${totalBoxes}</span>
                        </div>
                    </div>
                    <div class="data-table">
                        <table>
                            <thead>
                                <tr>
                                    <th class="region-col" rowspan="2">ACTIVE REGIONS</th>
                                    ${days.map((day, i) => `
                                        <th colspan="5" class="day-header ${flightDays.includes(i) ? 'flight-day' : ''}">${day}</th>
                                    `).join('')}
                                </tr>
                                <tr>
                                    ${days.map(() => `
                                        <th>O</th>
                                        <th>B</th>
                                        <th>W</th>
                                        <th>&lt;20</th>
                                        <th>20+</th>
                                    `).join('')}
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                // Region rows
                provider.regions.forEach(region => {
                    html += `<tr><td class="region-col">${region.name}</td>`;
                    region.days.forEach(day => {
                        const oClass = day.orders > 0 ? 'has-val' : 'zero-val';
                        const bClass = day.boxes > 0 ? 'has-val' : 'zero-val';
                        const wClass = day.weight > 0 ? 'weight-val' : 'zero-val';
                        const u20Class = day.under20 > 0 ? 'has-val' : 'zero-val';
                        const o20Class = day.over20 > 0 ? 'has-val' : 'zero-val';
                        html += `
                            <td class="${oClass}">${day.orders}</td>
                            <td class="${bClass}">${day.boxes}</td>
                            <td class="${wClass}">${day.weight.toFixed(1)}</td>
                            <td class="${u20Class}">${day.under20}</td>
                            <td class="${o20Class}">${day.over20}</td>
                        `;
                    });
                    html += `</tr>`;
                });
                
                // Total row
                html += `<tr class="total-row"><td class="total-label">📊 TOTAL SUMMARY</td>`;
                provider.day_totals.forEach(day => {
                    html += `
                        <td>${day.orders}</td>
                        <td>${day.boxes}</td>
                        <td>${day.weight.toFixed(1)}</td>
                        <td>${day.under20}</td>
                        <td>${day.over20}</td>
                    `;
                });
                html += `</tr>`;
                
                html += `
                            </tbody>
                        </table>
                    </div>
                </div>
                `;
            });
            
            content.innerHTML = html;
        }
        
        // Initial load
        loadData();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    """API endpoint to get dashboard data"""
    try:
        week_start_str = request.args.get('week_start')
        if week_start_str:
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d')
        else:
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
        
        week_end = week_start + timedelta(days=6)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)
        
        results = []
        
        for provider in PROVIDERS:
            # Fetch data using direct URL
            data = fetch_sheet_data(provider["url"])
            
            # Initialize data structures
            regions_data = {}
            day_totals = [{"orders": 0, "boxes": 0, "weight": 0, "under20": 0, "over20": 0} for _ in range(7)]
            totals = {"orders": 0, "boxes": 0, "weight": 0}
            prev_week_boxes = 0
            current_week_boxes = 0
            
            # Process rows (skip header rows based on startRow)
            start_row = provider.get("startRow", 2)
            for row in data[start_row:]:
                try:
                    # Check if row has enough columns
                    max_col = max(provider["dateCol"], provider["boxCol"], provider["weightCol"], provider["regionCol"])
                    if len(row) <= max_col:
                        continue
                    
                    # Get values
                    date_val = row[provider["dateCol"]] if provider["dateCol"] < len(row) else ""
                    box_val = row[provider["boxCol"]] if provider["boxCol"] < len(row) else "0"
                    weight_val = row[provider["weightCol"]] if provider["weightCol"] < len(row) else "0"
                    region_val = row[provider["regionCol"]] if provider["regionCol"] < len(row) else ""
                    
                    # Parse date
                    row_date = parse_date(date_val)
                    if not row_date:
                        continue
                    
                    # Parse values
                    boxes = safe_int(box_val)
                    weight = safe_float(weight_val)
                    
                    # Skip invalid data
                    if boxes <= 0 and weight <= 0:
                        continue
                    
                    # Check if valid region
                    if not is_valid_region(region_val):
                        region_val = "OTHER"
                    else:
                        region_val = str(region_val).strip().upper()
                    
                    # Previous week calculation
                    if prev_week_start <= row_date <= prev_week_end:
                        prev_week_boxes += boxes
                    
                    # Current week calculation
                    if week_start <= row_date <= week_end:
                        current_week_boxes += boxes
                        day_idx = (row_date - week_start).days
                        
                        if 0 <= day_idx < 7:
                            # Initialize region if not exists
                            if region_val not in regions_data:
                                regions_data[region_val] = [{"orders": 0, "boxes": 0, "weight": 0, "under20": 0, "over20": 0} for _ in range(7)]
                            
                            # Update region data
                            regions_data[region_val][day_idx]["orders"] += 1
                            regions_data[region_val][day_idx]["boxes"] += boxes
                            regions_data[region_val][day_idx]["weight"] += weight
                            
                            # Weight category
                            if weight < 20:
                                regions_data[region_val][day_idx]["under20"] += 1
                            else:
                                regions_data[region_val][day_idx]["over20"] += 1
                            
                            # Update day totals
                            day_totals[day_idx]["orders"] += 1
                            day_totals[day_idx]["boxes"] += boxes
                            day_totals[day_idx]["weight"] += weight
                            if weight < 20:
                                day_totals[day_idx]["under20"] += 1
                            else:
                                day_totals[day_idx]["over20"] += 1
                            
                            # Update totals
                            totals["orders"] += 1
                            totals["boxes"] += boxes
                            totals["weight"] += weight
                
                except Exception as e:
                    continue
            
            # Convert regions_data to list
            regions_list = []
            for region_name, days in sorted(regions_data.items()):
                regions_list.append({
                    "name": region_name,
                    "days": days
                })
            
            # Calculate rating and trend
            rating = get_rating(current_week_boxes)
            trend = get_trend(current_week_boxes, prev_week_boxes)
            
            results.append({
                "name": provider["name"],
                "regions": regions_list,
                "day_totals": day_totals,
                "totals": totals,
                "rating": rating,
                "trend": trend
            })
        
        return jsonify({
            "providers": results,
            "week_start": week_start.strftime('%Y-%m-%d'),
            "week_end": week_end.strftime('%Y-%m-%d')
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
