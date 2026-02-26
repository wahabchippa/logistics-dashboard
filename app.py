from flask import Flask, render_template, jsonify
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import os
import json

app = Flask(__name__)

# Google Sheets Setup
SHEET_ID = "1V03fqI2tGbY3ImkQaoZGwJ98iyrN4z_GXRKRP023zUY"

def get_sheet_data():
    """Fetch data from Google Sheets"""
    try:
        # Try to get credentials from environment variable
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=[
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ])
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(SHEET_ID)
        else:
            # Fallback: Try public access
            client = gspread.Client(None)
            spreadsheet = client.open_by_key(SHEET_ID)
        
        return spreadsheet
    except Exception as e:
        print(f"Error: {e}")
        return None

# Provider Configurations (from your script)
PROVIDERS = [
    {"name": "GLOBAL EXPRESS (QC)", "sheet": "GE QC Center & Zone", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7},
    {"name": "GLOBAL EXPRESS (ZONES)", "sheet": "GE QC Center & Zone", "dateCol": 10, "boxCol": 11, "weightCol": 15, "regionCol": 16},
    {"name": "ECL LOGISTICS (QC)", "sheet": "ECL QC Center & Zone", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7},
    {"name": "ECL LOGISTICS (ZONES)", "sheet": "ECL QC Center & Zone", "dateCol": 10, "boxCol": 11, "weightCol": 14, "regionCol": 16},
    {"name": "KERRY LOGISTICS", "sheet": "Kerry", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 6},
    {"name": "APX EXPRESS", "sheet": "APX", "dateCol": 1, "boxCol": 2, "weightCol": 5, "regionCol": 7},
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """API endpoint to get dashboard data"""
    try:
        spreadsheet = get_sheet_data()
        if not spreadsheet:
            return jsonify({"error": "Could not connect to sheet"}), 500
        
        # Get current week start (Monday)
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        
        results = []
        for provider in PROVIDERS:
            try:
                worksheet = spreadsheet.worksheet(provider["sheet"])
                data = worksheet.get_all_values()
                
                weekly_data = {
                    "name": provider["name"],
                    "days": [{"orders": 0, "boxes": 0, "weight": 0} for _ in range(7)],
                    "total": {"orders": 0, "boxes": 0, "weight": 0}
                }
                
                for row in data[1:]:  # Skip header
                    try:
                        date_val = row[provider["dateCol"]] if provider["dateCol"] < len(row) else ""
                        if not date_val:
                            continue
                        
                        # Parse date
                        try:
                            row_date = datetime.strptime(date_val, "%d/%m/%Y")
                        except:
                            try:
                                row_date = datetime.strptime(date_val, "%Y-%m-%d")
                            except:
                                continue
                        
                        # Check if in current week
                        day_diff = (row_date - week_start).days
                        if 0 <= day_diff < 7:
                            boxes = float(row[provider["boxCol"]] or 0) if provider["boxCol"] < len(row) else 0
                            weight = float(row[provider["weightCol"]] or 0) if provider["weightCol"] < len(row) else 0
                            
                            weekly_data["days"][day_diff]["orders"] += 1
                            weekly_data["days"][day_diff]["boxes"] += boxes
                            weekly_data["days"][day_diff]["weight"] += weight
                            
                            weekly_data["total"]["orders"] += 1
                            weekly_data["total"]["boxes"] += boxes
                            weekly_data["total"]["weight"] += weight
                    except:
                        continue
                
                results.append(weekly_data)
            except Exception as e:
                print(f"Error with {provider['name']}: {e}")
                continue
        
        return jsonify({
            "week_start": week_start.strftime("%d-%b-%Y"),
            "week_end": (week_start + timedelta(days=6)).strftime("%d-%b-%Y"),
            "providers": results
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
