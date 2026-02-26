HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>G-OPS 3PL Executive Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #111827;
            --bg-card: #1a1f35;
            --bg-card-hover: #242b45;
            --border-color: #2a3352;
            --accent-gold: #f5b942;
            --accent-gold-dim: #c9962e;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --text-primary: #ffffff;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --sidebar-width: 260px;
            --sidebar-collapsed: 70px;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            background-image: 
                radial-gradient(ellipse at top left, rgba(245, 185, 66, 0.05) 0%, transparent 50%),
                radial-gradient(ellipse at bottom right, rgba(59, 130, 246, 0.05) 0%, transparent 50%);
        }
        
        /* Sidebar */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            position: fixed;
            height: 100vh;
            display: flex;
            flex-direction: column;
            z-index: 100;
            transition: width 0.3s ease;
        }
        
        .sidebar.collapsed {
            width: var(--sidebar-collapsed);
        }
        
        .sidebar-header {
            padding: 24px;
            border-bottom: 1px solid var(--border-color);
            background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-secondary) 100%);
            display: flex;
            align-items: center;
            justify-content: space-between;
            min-height: 90px;
        }
        
        .sidebar.collapsed .sidebar-header {
            padding: 16px;
            justify-content: center;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            overflow: hidden;
        }
        
        .logo-icon {
            min-width: 42px;
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-gold-dim) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 15px rgba(245, 185, 66, 0.3);
        }
        
        .logo-text {
            white-space: nowrap;
            transition: opacity 0.2s ease;
        }
        
        .sidebar.collapsed .logo-text {
            opacity: 0;
            width: 0;
            display: none;
        }
        
        .logo-text h1 {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
        }
        
        .logo-text p {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Toggle Button */
        .sidebar-toggle {
            position: absolute;
            right: -14px;
            top: 32px;
            width: 28px;
            height: 28px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 12px;
            transition: all 0.2s ease;
            z-index: 101;
        }
        
        .sidebar-toggle:hover {
            background: var(--accent-gold);
            color: var(--bg-primary);
            border-color: var(--accent-gold);
            transform: scale(1.1);
        }
        
        .sidebar.collapsed .sidebar-toggle {
            transform: rotate(180deg);
        }
        
        .sidebar.collapsed .sidebar-toggle:hover {
            transform: rotate(180deg) scale(1.1);
        }
        
        .nav-section {
            padding: 20px 12px;
            flex: 1;
            overflow-y: auto;
        }
        
        .nav-label {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-muted);
            padding: 0 12px;
            margin-bottom: 12px;
            white-space: nowrap;
            transition: opacity 0.2s ease;
        }
        
        .sidebar.collapsed .nav-label {
            opacity: 0;
            height: 0;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            padding: 14px 16px;
            color: var(--text-secondary);
            text-decoration: none;
            border-radius: 10px;
            margin-bottom: 6px;
            transition: all 0.2s ease;
            font-size: 14px;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
        }
        
        .sidebar.collapsed .nav-item {
            justify-content: center;
            padding: 14px;
        }
        
        .nav-item:hover {
            background: var(--bg-card);
            color: var(--text-primary);
        }
        
        .nav-item.active {
            background: linear-gradient(135deg, rgba(245, 185, 66, 0.15) 0%, rgba(245, 185, 66, 0.05) 100%);
            color: var(--accent-gold);
            border: 1px solid rgba(245, 185, 66, 0.2);
        }
        
        .nav-icon {
            min-width: 20px;
            width: 20px;
            text-align: center;
            font-size: 16px;
        }
        
        .nav-text {
            margin-left: 12px;
            transition: opacity 0.2s ease;
        }
        
        .sidebar.collapsed .nav-text {
            opacity: 0;
            width: 0;
            margin: 0;
            display: none;
        }
        
        /* Tooltip for collapsed sidebar */
        .nav-item {
            position: relative;
        }
        
        .nav-item::after {
            content: attr(data-tooltip);
            position: absolute;
            left: 100%;
            top: 50%;
            transform: translateY(-50%);
            background: var(--bg-card);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            white-space: nowrap;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
            margin-left: 10px;
            border: 1px solid var(--border-color);
            z-index: 1000;
        }
        
        .sidebar.collapsed .nav-item:hover::after {
            opacity: 1;
        }
        
        /* Main Content */
        .main-content {
            margin-left: var(--sidebar-width);
            flex: 1;
            min-height: 100vh;
            transition: margin-left 0.3s ease;
        }
        
        body.sidebar-collapsed .main-content {
            margin-left: var(--sidebar-collapsed);
        }
        
        .header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            padding: 28px 32px;
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 50;
            backdrop-filter: blur(10px);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary) 0%, var(--text-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .header p {
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 4px;
        }
        
        .week-selector {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .week-input-group {
            display: flex;
            align-items: center;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 4px;
        }
        
        .week-input-group label {
            padding: 0 12px;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
        }
        
        .week-input-group input {
            background: var(--bg-secondary);
            border: none;
            color: var(--text-primary);
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
        }
        
        .week-display {
            background: linear-gradient(135deg, rgba(245, 185, 66, 0.1) 0%, rgba(245, 185, 66, 0.05) 100%);
            border: 1px solid rgba(245, 185, 66, 0.2);
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            color: var(--accent-gold);
        }
        
        .container {
            padding: 28px;
        }
        
        /* Provider Card */
        .provider-card {
            background: var(--bg-card);
            border-radius: 16px;
            margin-bottom: 28px;
            border: 1px solid var(--border-color);
            overflow: hidden;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }
        
        .provider-card:hover {
            border-color: rgba(245, 185, 66, 0.3);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
        }
        
        .provider-header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }
        
        .provider-title {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .provider-name {
            font-size: 16px;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .provider-name::before {
            content: '';
            width: 4px;
            height: 20px;
            background: var(--accent-gold);
            border-radius: 2px;
        }
        
        .rating {
            display: flex;
            gap: 3px;
        }
        
        .star {
            font-size: 14px;
            color: var(--border-color);
        }
        
        .star.filled {
            color: var(--accent-gold);
            text-shadow: 0 0 10px rgba(245, 185, 66, 0.5);
        }
        
        .trend {
            font-size: 12px;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 20px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .trend.up {
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        
        .trend.down {
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .provider-stats {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .stat-badge {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-secondary);
        }
        
        .stat-badge.primary {
            background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-gold-dim) 100%);
            color: var(--bg-primary);
            border: none;
            font-weight: 700;
            box-shadow: 0 4px 15px rgba(245, 185, 66, 0.3);
        }
        
        /* Table Styles */
        .table-wrapper {
            overflow-x: auto;
            padding: 0;
        }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 1400px;
        }
        
        .data-table th {
            background: var(--bg-secondary);
            padding: 12px 8px;
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
        }
        
        .data-table th.day-header {
            background: var(--bg-card);
            color: var(--text-secondary);
            font-size: 11px;
        }
        
        .data-table th.flight-day {
            background: linear-gradient(135deg, rgba(245, 185, 66, 0.1) 0%, rgba(245, 185, 66, 0.05) 100%);
            color: var(--accent-gold);
        }
        
        .data-table th.region-col {
            text-align: left;
            padding-left: 20px;
            min-width: 140px;
        }
        
        .data-table td {
            padding: 10px 8px;
            text-align: center;
            font-size: 12px;
            font-weight: 500;
            border-bottom: 1px solid rgba(42, 51, 82, 0.5);
            color: var(--text-secondary);
        }
        
        .data-table td.region-col {
            text-align: left;
            padding-left: 20px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .data-table td.flight-col {
            background: rgba(245, 185, 66, 0.03);
        }
        
        .data-table td.has-value {
            color: var(--text-primary);
        }
        
        .data-table tbody tr {
            transition: background 0.2s ease;
        }
        
        .data-table tbody tr:hover {
            background: rgba(255, 255, 255, 0.02);
        }
        
        .data-table .total-row {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, rgba(245, 185, 66, 0.05) 100%);
        }
        
        .data-table .total-row td {
            color: var(--accent-gold);
            font-weight: 700;
            border-top: 2px solid var(--accent-gold);
            padding: 14px 8px;
        }
        
        /* Summary Section */
        .summary-section {
            margin-top: 28px;
        }
        
        .summary-card {
            background: var(--bg-card);
            border-radius: 16px;
            border: 1px solid var(--border-color);
            overflow: hidden;
        }
        
        .summary-header {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .summary-header h2 {
            font-size: 16px;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .summary-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .summary-table th {
            background: var(--bg-secondary);
            padding: 14px 12px;
            font-size: 11px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .summary-table th.flight {
            background: linear-gradient(135deg, rgba(245, 185, 66, 0.1) 0%, rgba(245, 185, 66, 0.05) 100%);
            color: var(--accent-gold);
        }
        
        .summary-table td {
            padding: 14px 12px;
            text-align: center;
            font-size: 13px;
            font-weight: 500;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }
        
        .summary-table td:first-child {
            text-align: left;
            padding-left: 20px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .summary-table .winner {
            background: linear-gradient(135deg, rgba(245, 185, 66, 0.1) 0%, rgba(245, 185, 66, 0.02) 100%);
        }
        
        .summary-table .winner td:first-child {
            color: var(--accent-gold);
        }
        
        .summary-table .winner td:first-child::before {
            content: '🏆 ';
        }
        
        .grand-total-cell {
            background: var(--bg-secondary) !important;
            color: var(--accent-gold) !important;
            font-weight: 700 !important;
        }
        
        /* Loading & Error States */
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 80px;
            color: var(--text-muted);
        }
        
        .loading-spinner {
            width: 48px;
            height: 48px;
            border: 3px solid var(--border-color);
            border-top-color: var(--accent-gold);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 16px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: var(--accent-red);
            padding: 24px;
            border-radius: 12px;
            text-align: center;
            margin: 28px;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .sidebar {
                width: var(--sidebar-collapsed);
            }
            .sidebar .logo-text,
            .sidebar .nav-label,
            .sidebar .nav-text {
                display: none;
            }
            .sidebar .nav-item {
                justify-content: center;
                padding: 14px;
            }
            .main-content {
                margin-left: var(--sidebar-collapsed);
            }
            .header-content {
                flex-direction: column;
                gap: 16px;
                align-items: flex-start;
            }
            .week-selector {
                width: 100%;
                flex-wrap: wrap;
            }
            .provider-header {
                flex-direction: column;
                align-items: flex-start;
            }
            .sidebar-toggle {
                display: none;
            }
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-secondary); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    </style>
</head>
<body>
    <nav class="sidebar" id="sidebar">
        <div class="sidebar-toggle" id="sidebarToggle" onclick="toggleSidebar()">
            <span>«</span>
        </div>
        <div class="sidebar-header">
            <div class="logo">
                <div class="logo-icon">📦</div>
                <div class="logo-text">
                    <h1>G-OPS 3PL</h1>
                    <p>Executive Portal</p>
                </div>
            </div>
        </div>
        <div class="nav-section">
            <div class="nav-label">Navigation</div>
            <a href="/" class="nav-item {{ 'active' if page == 'dashboard' else '' }}" data-tooltip="Dashboard">
                <span class="nav-icon">📊</span>
                <span class="nav-text">Dashboard</span>
            </a>
            <a href="/weekly-summary" class="nav-item {{ 'active' if page == 'weekly' else '' }}" data-tooltip="Weekly Summary">
                <span class="nav-icon">📈</span>
                <span class="nav-text">Weekly Summary</span>
            </a>
            <a href="/flight-load" class="nav-item {{ 'active' if page == 'flight' else '' }}" data-tooltip="Flight Load">
                <span class="nav-icon">✈️</span>
                <span class="nav-text">Flight Load</span>
            </a>
        </div>
    </nav>

    <main class="main-content">
        <header class="header">
            <div class="header-content">
                <div>
                    <h1>{% if page == 'dashboard' %}Executive Dashboard{% elif page == 'weekly' %}Weekly Performance{% else %}Flight Load Analysis{% endif %}</h1>
                    <p>{% if page == 'dashboard' %}Real-time 3PL performance metrics{% elif page == 'weekly' %}Weekly summary with winner highlight{% else %}Consolidated flight shipments{% endif %}</p>
                </div>
                <div class="week-selector">
                    <div class="week-input-group">
                        <label>📅 WEEK</label>
                        <input type="date" id="weekStart" onchange="loadPage()">
                    </div>
                    <div class="week-display" id="weekInfo">Loading...</div>
                </div>
            </div>
        </header>

        <div class="container" id="mainContent">
            <div class="loading">
                <div class="loading-spinner"></div>
                <p>Loading data...</p>
            </div>
        </div>
    </main>

    <script>
        const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
        const FLIGHT_DAYS = [1, 3, 5];
        const COLS = ['O', 'B', 'W', '<20', '20+'];
        
        // Sidebar Toggle
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const toggle = document.getElementById('sidebarToggle');
            sidebar.classList.toggle('collapsed');
            document.body.classList.toggle('sidebar-collapsed');
            
            // Save state to localStorage
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        }
        
        // Restore sidebar state
        if (localStorage.getItem('sidebarCollapsed') === 'true') {
            document.getElementById('sidebar').classList.add('collapsed');
            document.body.classList.add('sidebar-collapsed');
        }
        
        // Set default week
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
        
        async function loadDashboard() {
            const weekStart = document.getElementById('weekStart').value;
            const container = document.getElementById('mainContent');
            container.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>Loading data...</p></div>';
            
            try {
                const response = await fetch('/api/dashboard?week_start=' + weekStart);
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                document.getElementById('weekInfo').textContent = data.week_start + ' → ' + data.week_end;
                renderDashboard(data);
            } catch (error) {
                container.innerHTML = '<div class="error"><h3>⚠️ Error Loading Data</h3><p>' + error.message + '</p></div>';
            }
        }
        
        function renderStars(rating) {
            let stars = '';
            for (let i = 1; i <= 5; i++) {
                stars += '<span class="star ' + (i <= rating ? 'filled' : '') + '">★</span>';
            }
            return stars;
        }
        
        function formatValue(val, type) {
            if (!val || val === 0) return '-';
            if (type === 'weight') return val.toFixed(1);
            if (type === 'boxes') return Math.round(val).toLocaleString();
            return val;
        }
        
        function renderDashboard(data) {
            let html = '';
            
            data.providers.forEach(provider => {
                const regions = Object.keys(provider.regions).sort();
                
                html += '<div class="provider-card">';
                html += '<div class="provider-header">';
                html += '<div class="provider-title">';
                html += '<span class="provider-name">' + provider.name + '</span>';
                html += '<div class="rating">' + renderStars(provider.rating) + '</div>';
                html += '<span class="trend ' + provider.trend.class + '">' + provider.trend.icon + ' ' + provider.trend.text + '</span>';
                html += '</div>';
                html += '<div class="provider-stats">';
                html += '<span class="stat-badge">Orders: ' + provider.grand_total.orders.toLocaleString() + '</span>';
                html += '<span class="stat-badge">Boxes: ' + Math.round(provider.grand_total.boxes).toLocaleString() + '</span>';
                html += '<span class="stat-badge primary">Weight: ' + provider.grand_total.weight.toFixed(1) + ' kg</span>';
                html += '</div></div>';
                
                html += '<div class="table-wrapper"><table class="data-table">';
                html += '<thead><tr><th class="region-col" rowspan="2">REGION</th>';
                DAYS.forEach((day, i) => {
                    const isFlightDay = FLIGHT_DAYS.includes(i);
                    html += '<th colspan="5" class="day-header ' + (isFlightDay ? 'flight-day' : '') + '">' + day + (isFlightDay ? ' ✈️' : '') + '</th>';
                });
                html += '</tr><tr>';
                DAYS.forEach((day, i) => {
                    const isFlightDay = FLIGHT_DAYS.includes(i);
                    COLS.forEach(col => {
                        html += '<th class="' + (isFlightDay ? 'flight-day' : '') + '">' + col + '</th>';
                    });
                });
                html += '</tr></thead><tbody>';
                
                regions.forEach(region => {
                    const rdata = provider.regions[region];
                    html += '<tr><td class="region-col">' + region + '</td>';
                    rdata.days.forEach((d, i) => {
                        const isFlightDay = FLIGHT_DAYS.includes(i);
                        const cls = isFlightDay ? 'flight-col' : '';
                        html += '<td class="' + cls + (d.orders ? ' has-value' : '') + '">' + formatValue(d.orders) + '</td>';
                        html += '<td class="' + cls + (d.boxes ? ' has-value' : '') + '">' + formatValue(d.boxes, 'boxes') + '</td>';
                        html += '<td class="' + cls + (d.weight ? ' has-value' : '') + '">' + formatValue(d.weight, 'weight') + '</td>';
                        html += '<td class="' + cls + (d.under20 ? ' has-value' : '') + '">' + formatValue(d.under20) + '</td>';
                        html += '<td class="' + cls + (d.over20 ? ' has-value' : '') + '">' + formatValue(d.over20) + '</td>';
                    });
                    html += '</tr>';
                });
                
                html += '<tr class="total-row"><td class="region-col">TOTAL</td>';
                provider.day_totals.forEach((d, i) => {
                    const isFlightDay = FLIGHT_DAYS.includes(i);
                    const cls = isFlightDay ? 'flight-col' : '';
                    html += '<td class="' + cls + '">' + d.orders + '</td>';
                    html += '<td class="' + cls + '">' + Math.round(d.boxes).toLocaleString() + '</td>';
                    html += '<td class="' + cls + '">' + d.weight.toFixed(1) + '</td>';
                    html += '<td class="' + cls + '">' + d.under20 + '</td>';
                    html += '<td class="' + cls + '">' + d.over20 + '</td>';
                });
                html += '</tr></tbody></table></div></div>';
            });
            
            document.getElementById('mainContent').innerHTML = html;
        }
        
        async function loadWeekly() {
            const weekStart = document.getElementById('weekStart').value;
            const container = document.getElementById('mainContent');
            container.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>Loading data...</p></div>';
            
            try {
                const response = await fetch('/api/weekly-summary?week_start=' + weekStart);
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                document.getElementById('weekInfo').textContent = data.week_start + ' → ' + data.week_end;
                
                let html = '<div class="summary-section"><div class="summary-card">';
                html += '<div class="summary-header"><span>📊</span><h2>Weekly Performance Summary</h2></div>';
                html += '<div class="table-wrapper"><table class="summary-table">';
                html += '<thead><tr><th>Provider</th>';
                DAYS.forEach((day, i) => {
                    const isFlightDay = FLIGHT_DAYS.includes(i);
                    html += '<th colspan="3" class="' + (isFlightDay ? 'flight' : '') + '">' + day + (isFlightDay ? ' ✈️' : '') + '</th>';
                });
                html += '<th colspan="3">TOTAL</th></tr>';
                html += '<tr><th></th>';
                for (let i = 0; i < 8; i++) html += '<th>Ord</th><th>Box</th><th>KG</th>';
                html += '</tr></thead><tbody>';
                
                data.providers.forEach(p => {
                    html += '<tr class="' + (p.is_winner ? 'winner' : '') + '">';
                    html += '<td>' + p.name + '</td>';
                    p.days.forEach(d => {
                        html += '<td>' + formatValue(d.orders) + '</td>';
                        html += '<td>' + formatValue(d.boxes, 'boxes') + '</td>';
                        html += '<td>' + formatValue(d.weight, 'weight') + '</td>';
                    });
                    html += '<td class="grand-total-cell">' + p.total.orders + '</td>';
                    html += '<td class="grand-total-cell">' + Math.round(p.total.boxes).toLocaleString() + '</td>';
                    html += '<td class="grand-total-cell">' + p.total.weight.toFixed(1) + '</td>';
                    html += '</tr>';
                });
                
                html += '</tbody></table></div></div></div>';
                container.innerHTML = html;
            } catch (error) {
                container.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + error.message + '</p></div>';
            }
        }
        
        async function loadFlight() {
            const weekStart = document.getElementById('weekStart').value;
            const container = document.getElementById('mainContent');
            container.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>Loading data...</p></div>';
            
            try {
                const response = await fetch('/api/flight-load?week_start=' + weekStart);
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                document.getElementById('weekInfo').textContent = data.week_start + ' → ' + data.week_end;
                
                let html = '<div class="summary-section"><div class="summary-card">';
                html += '<div class="summary-header"><span>✈️</span><h2>Consolidated Flight Load</h2></div>';
                html += '<div class="table-wrapper"><table class="summary-table">';
                html += '<thead><tr><th>Provider</th>';
                html += '<th colspan="3" class="flight">TUE Flight (Mon+Tue)</th>';
                html += '<th colspan="3" class="flight">THU Flight (Wed+Thu)</th>';
                html += '<th colspan="3" class="flight">SAT Flight (Fri+Sat)</th>';
                html += '<th colspan="3">TOTAL</th></tr>';
                html += '<tr><th></th>';
                for (let i = 0; i < 4; i++) html += '<th>Ord</th><th>Box</th><th>KG</th>';
                html += '</tr></thead><tbody>';
                
                data.providers.forEach(p => {
                    html += '<tr><td>' + p.name + '</td>';
                    html += '<td>' + formatValue(p.tue_flight.orders) + '</td>';
                    html += '<td>' + formatValue(p.tue_flight.boxes, 'boxes') + '</td>';
                    html += '<td>' + formatValue(p.tue_flight.weight, 'weight') + '</td>';
                    html += '<td>' + formatValue(p.thu_flight.orders) + '</td>';
                    html += '<td>' + formatValue(p.thu_flight.boxes, 'boxes') + '</td>';
                    html += '<td>' + formatValue(p.thu_flight.weight, 'weight') + '</td>';
                    html += '<td>' + formatValue(p.sat_flight.orders) + '</td>';
                    html += '<td>' + formatValue(p.sat_flight.boxes, 'boxes') + '</td>';
                    html += '<td>' + formatValue(p.sat_flight.weight, 'weight') + '</td>';
                    html += '<td class="grand-total-cell">' + p.total.orders + '</td>';
                    html += '<td class="grand-total-cell">' + Math.round(p.total.boxes).toLocaleString() + '</td>';
                    html += '<td class="grand-total-cell">' + p.total.weight.toFixed(1) + '</td>';
                    html += '</tr>';
                });
                
                html += '</tbody></table></div></div></div>';
                container.innerHTML = html;
            } catch (error) {
                container.innerHTML = '<div class="error"><h3>⚠️ Error</h3><p>' + error.message + '</p></div>';
            }
        }
        
        // Initial load
        loadPage();
    </script>
</body>
</html>
'''
