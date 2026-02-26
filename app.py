from flask import Flask, render_template_string, jsonify
import requests
import csv
from io import StringIO
from datetime import datetime, timedelta

app = Flask(__name__)

# Google Sheet Published CSV URLs
SHEET_ID = "1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY"

def get_sheet_url(sheet_name):
    """Get CSV URL for a specific sheet tab"""
    encoded_name = sheet_name.replace(" ", "%20").replace("&", "%26")
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_name}"

PROVIDERS = [
    {"name": "GLOBAL EXPRESS (QC)", "sheet": "GE QC Center & Zone", "dateCol": 1, "boxCol": 2, "weightCol": 5},
    {"name": "GLOBAL EXPRESS (ZONES)", "sheet": "GE QC Center & Zone", "dateCol": 10, "boxCol": 11, "weightCol": 15},
    {"name": "ECL LOGISTICS (QC)", "sheet": "ECL QC Center & Zone", "dateCol": 1, "boxCol": 2, "weightCol": 5},
    {"name": "ECL LOGISTICS (ZONES)", "sheet": "ECL QC Center & Zone", "dateCol": 10, "boxCol": 11, "weightCol": 14},
    {"name": "KERRY LOGISTICS", "sheet": "Kerry", "dateCol": 1, "boxCol": 2, "weightCol": 5},
    {"name": "APX EXPRESS", "sheet": "APX", "dateCol": 1, "boxCol": 2, "weightCol": 5},
]

def fetch_sheet_data(sheet_name):
    """Fetch CSV data from published Google Sheet"""
    try:
        url = get_sheet_url(sheet_name)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        reader = csv.reader(StringIO(response.text))
        return list(reader)
    except Exception as e:
        print(f"Error fetching {sheet_name}: {e}")
        return []

def parse_date(date_str):
    """Parse date from various formats"""
    if not date_str or date_str.strip() == "":
        return None
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    return None

def safe_float(val):
    """Safely convert to float"""
    try:
        clean = str(val).replace(',', '').replace(' ', '').strip()
        if clean == "" or clean == "-" or clean == "N/A":
            return 0
        return float(clean)
    except:
        return 0

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    """API endpoint to get dashboard data"""
    try:
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        
        sheet_cache = {}
        results = []
        
        for provider in PROVIDERS:
            sheet_name = provider["sheet"]
            
            if sheet_name not in sheet_cache:
                sheet_cache[sheet_name] = fetch_sheet_data(sheet_name)
            
            data = sheet_cache[sheet_name]
            
            weekly_data = {
                "name": provider["name"],
                "days": [{"orders": 0, "boxes": 0, "weight": 0} for _ in range(7)],
                "total": {"orders": 0, "boxes": 0, "weight": 0}
            }
            
            for row in data[1:]:
                try:
                    if provider["dateCol"] >= len(row):
                        continue
                    
                    date_val = row[provider["dateCol"]]
                    row_date = parse_date(date_val)
                    
                    if not row_date:
                        continue
                    
                    day_diff = (row_date - week_start).days
                    
                    if 0 <= day_diff < 7:
                        boxes = safe_float(row[provider["boxCol"]]) if provider["boxCol"] < len(row) else 0
                        weight = safe_float(row[provider["weightCol"]]) if provider["weightCol"] < len(row) else 0
                        
                        weekly_data["days"][day_diff]["orders"] += 1
                        weekly_data["days"][day_diff]["boxes"] += boxes
                        weekly_data["days"][day_diff]["weight"] += weight
                        
                        weekly_data["total"]["orders"] += 1
                        weekly_data["total"]["boxes"] += boxes
                        weekly_data["total"]["weight"] += weight
                except:
                    continue
            
            results.append(weekly_data)
        
        return jsonify({
            "week_start": week_start.strftime("%d-%b-%Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d-%b-%Y"),
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
        body { font-family: 'Segoe UI', sans-serif; background: #0B1120; color: #fff; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #0B1120, #1E293B); padding: 20px; border-bottom: 3px solid #FBBF24; text-align: center; }
        .header h1 { color: #FBBF24; font-size: 24px; letter-spacing: 3px; }
        .header p { color: #94A3B8; font-size: 13px; margin-top: 5px; }
        .week-selector { background: #1E293B; padding: 15px 20px; display: flex; align-items: center; gap: 15px; }
        .week-selector label { color: #94A3B8; }
        .week-info { color: #FBBF24; margin-left: auto; font-weight: bold; }
        .container { padding: 20px; }
        .provider-card { background: #1E293B; border-radius: 10px; margin-bottom: 20px; overflow: hidden; border: 1px solid #334155; }
        .provider-header { background: #0F172A; padding: 12px 15px; border-bottom: 2px solid #FBBF24; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .provider-name { color: #FBBF24; font-weight: 700; }
        .provider-stats { display: flex; gap: 10px; flex-wrap: wrap; }
        .stat-badge { background: #334155; padding: 4px 10px; border-radius: 15px; font-size: 12px; }
        .stat-badge.highlight { background: #FBBF24; color: #0B1120; font-weight: 700; }
        .data-table { width: 100%; border-collapse: collapse; }
        .data-table th { background: #0F172A; padding: 10px; font-size: 11px; color: #94A3B8; text-transform: uppercase; }
        .data-table th.flight-day { background: #1E293B; color: #FBBF24; }
        .data-table td { padding: 10px; text-align: center; font-size: 13px; border-bottom: 1px solid #334155; }
        .data-table td.flight-day { background: rgba(251, 191, 36, 0.1); }
        .summary-section { margin-top: 30px; }
        .summary-header { background: #0B1120; padding: 12px 15px; border: 2px solid #FBBF24; border-bottom: none; border-radius: 10px 10px 0 0; }
        .summary-header h2 { color: #FBBF24; font-size: 16px; }
        .summary-table { width: 100%; border-collapse: collapse; background: #1E293B; border: 2px solid #FBBF24; border-top: none; }
        .summary-table th { background: #0F172A; padding: 8px; color: #94A3B8; font-size: 10px; }
        .summary-table th.flight { color: #FBBF24; }
        .summary-table td { padding: 8px; text-align: center; font-size: 12px; border-bottom: 1px solid #334155; }
        .summary-table .winner { background: rgba(251, 191, 36, 0.2); }
        .summary-table .winner td:first-child { color: #FBBF24; font-weight: 700; }
        .grand-total { background: #0F172A !important; color: #FBBF24 !important; font-weight: 700 !important; }
        .flight-section { margin-top: 30px; }
        .loading { text-align: center; padding: 50px; color: #94A3B8; }
        .loading-spinner { width: 40px; height: 40px; border: 3px solid #334155; border-top: 3px solid #FBBF24; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .error { background: #7F1D1D; color: #FCA5A5; padding: 20px; border-radius: 8px; text-align: center; margin: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>✦ GLOBAL LOGISTICS EXECUTIVE PORTAL ✦</h1>
        <p>3PL Weekly Performance Dashboard</p>
    </div>
    <div class="week-selector">
        <label>📅 CURRENT WEEK:</label>
        <span class="week-info" id="weekInfo">Loading...</span>
    </div>
    <div class="container" id="mainContent">
        <div class="loading">
            <div class="loading-spinner"></div>
            <p>Loading data from Google Sheets...</p>
        </div>
    </div>
    <script>
        const DAYS = ['MON', 'TUE ✈️', 'WED', 'THU ✈️', 'FRI', 'SAT ✈️', 'SUN'];
        const FLIGHT_DAYS = [1, 3, 5];
        
        async function loadData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                document.getElementById('weekInfo').textContent = data.week_start + ' → ' + data.week_end;
                renderDashboard(data);
            } catch (error) {
                document.getElementById('mainContent').innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + error.message + '</p></div>';
            }
        }
        
        function renderDashboard(data) {
            let html = '';
            
            // Provider Cards
            data.providers.forEach(p => {
                html += '<div class="provider-card"><div class="provider-header"><span class="provider-name">✦ ' + p.name + '</span><div class="provider-stats"><span class="stat-badge">Orders: ' + p.total.orders + '</span><span class="stat-badge">Boxes: ' + p.total.boxes.toFixed(0) + '</span><span class="stat-badge highlight">Weight: ' + p.total.weight.toFixed(1) + ' kg</span></div></div><table class="data-table"><thead><tr><th>Metric</th>';
                DAYS.forEach((d, i) => { html += '<th class="' + (FLIGHT_DAYS.includes(i) ? 'flight-day' : '') + '">' + d + '</th>'; });
                html += '<th>TOTAL</th></tr></thead><tbody>';
                
                // Orders row
                html += '<tr><td><strong>Orders</strong></td>';
                p.days.forEach((d, i) => { html += '<td class="' + (FLIGHT_DAYS.includes(i) ? 'flight-day' : '') + '">' + (d.orders || '-') + '</td>'; });
                html += '<td><strong>' + p.total.orders + '</strong></td></tr>';
                
                // Boxes row
                html += '<tr><td><strong>Boxes</strong></td>';
                p.days.forEach((d, i) => { html += '<td class="' + (FLIGHT_DAYS.includes(i) ? 'flight-day' : '') + '">' + (d.boxes ? d.boxes.toFixed(0) : '-') + '</td>'; });
                html += '<td><strong>' + p.total.boxes.toFixed(0) + '</strong></td></tr>';
                
                // Weight row
                html += '<tr><td><strong>Weight (kg)</strong></td>';
                p.days.forEach((d, i) => { html += '<td class="' + (FLIGHT_DAYS.includes(i) ? 'flight-day' : '') + '">' + (d.weight ? d.weight.toFixed(1) : '-') + '</td>'; });
                html += '<td><strong>' + p.total.weight.toFixed(1) + '</strong></td></tr>';
                
                html += '</tbody></table></div>';
            });
            
            // Weekly Summary with Winner
            const maxW = Math.max(...data.providers.map(p => p.total.weight));
            html += '<div class="summary-section"><div class="summary-header"><h2>📊 WEEKLY PERFORMANCE SUMMARY (🏆 HIGHEST WEIGHT WINNER)</h2></div><table class="summary-table"><thead><tr><th>Provider</th>';
            DAYS.forEach((d, i) => { html += '<th colspan="3" class="' + (FLIGHT_DAYS.includes(i) ? 'flight' : '') + '">' + d + '</th>'; });
            html += '<th colspan="3">GRAND TOTAL</th></tr><tr><th></th>';
            for(let i=0; i<8; i++) { html += '<th>Ord</th><th>Box</th><th>KG</th>'; }
            html += '</tr></thead><tbody>';
            
            data.providers.forEach(p => {
                const isWinner = p.total.weight === maxW && maxW > 0;
                html += '<tr class="' + (isWinner ? 'winner' : '') + '"><td>' + (isWinner ? '🏆 ' : '') + p.name + '</td>';
                p.days.forEach(d => { 
                    html += '<td>' + (d.orders || '-') + '</td><td>' + (d.boxes ? d.boxes.toFixed(0) : '-') + '</td><td>' + (d.weight ? d.weight.toFixed(1) : '-') + '</td>'; 
                });
                html += '<td class="grand-total">' + p.total.orders + '</td><td class="grand-total">' + p.total.boxes.toFixed(0) + '</td><td class="grand-total">' + p.total.weight.toFixed(1) + '</td></tr>';
            });
            html += '</tbody></table></div>';
            
            // Flight Consolidation
            html += '<div class="flight-section"><div class="summary-header"><h2>✈️ CONSOLIDATED FLIGHT LOAD (PRE-FLIGHT + FLIGHT DAY)</h2></div><table class="summary-table"><thead><tr><th>Provider</th><th colspan="3">✈️ TUE FLIGHT</th><th colspan="3">✈️ THU FLIGHT</th><th colspan="3">✈️ SAT FLIGHT</th><th colspan="3">TOTAL LOAD</th></tr><tr><th></th><th>Ord</th><th>Box</th><th>KG</th><th>Ord</th><th>Box</th><th>KG</th><th>Ord</th><th>Box</th><th>KG</th><th>Ord</th><th>Box</th><th>KG</th></tr></thead><tbody>';
            
            data.providers.forEach(p => {
                const tue = { o: p.days[0].orders + p.days[1].orders, b: p.days[0].boxes + p.days[1].boxes, w: p.days[0].weight + p.days[1].weight };
                const thu = { o: p.days[2].orders + p.days[3].orders, b: p.days[2].boxes + p.days[3].boxes, w: p.days[2].weight + p.days[3].weight };
                const sat = { o: p.days[4].orders + p.days[5].orders, b: p.days[4].boxes + p.days[5].boxes, w: p.days[4].weight + p.days[5].weight };
                const tot = { o: tue.o + thu.o + sat.o, b: tue.b + thu.b + sat.b, w: tue.w + thu.w + sat.w };
                
                html += '<tr><td>' + p.name + '</td>';
                html += '<td>' + (tue.o || '-') + '</td><td>' + (tue.b ? tue.b.toFixed(0) : '-') + '</td><td>' + (tue.w ? tue.w.toFixed(1) : '-') + '</td>';
                html += '<td>' + (thu.o || '-') + '</td><td>' + (thu.b ? thu.b.toFixed(0) : '-') + '</td><td>' + (thu.w ? thu.w.toFixed(1) : '-') + '</td>';
                html += '<td>' + (sat.o || '-') + '</td><td>' + (sat.b ? sat.b.toFixed(0) : '-') + '</td><td>' + (sat.w ? sat.w.toFixed(1) : '-') + '</td>';
                html += '<td class="grand-total">' + tot.o + '</td><td class="grand-total">' + tot.b.toFixed(0) + '</td><td class="grand-total">' + tot.w.toFixed(1) + '</td></tr>';
            });
            html += '</tbody></table></div>';
            
            document.getElementById('mainContent').innerHTML = html;
        }
        
        loadData();
    </script>
</body>
</html>'''

if __name__ == '__main__':
    app.run(debug=True)
