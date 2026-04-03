#!/bin/bash
# Real-Time Charts Enhancement Script

set -e

echo "================================================"
echo "Real-Time Charts Enhancement Installation"
echo "================================================"

cd /home/ubuntu/financial_orchestrator

# Backup original files
echo "Creating backups..."
cp paper_trading/dashboard/app.py paper_trading/dashboard/app.py.backup
cp paper_trading/dashboard/templates/index.html paper_trading/dashboard/templates/index.html.backup

# Apply changes to app.py
python3 << 'PYTHON_SCRIPT'
app_file = 'paper_trading/dashboard/app.py'

with open(app_file, 'r') as f:
    content = f.read()

if 'HistoricalDataTracker' in content:
    print("app.py already modified - skipping")
else:
    # Add imports
    content = content.replace(
        'import os\nimport sys\nfrom pathlib import Path\nfrom threading import Thread\nfrom flask import Flask, render_template, jsonify, request\nfrom loguru import logger',
        'import os\nimport sys\nimport time as time_module\nfrom pathlib import Path\nfrom threading import Thread\nfrom collections import deque\nfrom flask import Flask, render_template, jsonify, request\nfrom loguru import logger'
    )

    # Add tracker class
    tracker_class = '''
class HistoricalDataTracker:
    def __init__(self, max_points=300):
        self.max_points = max_points
        self.price_history = {s: deque(maxlen=max_points) for s in ['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT']}
        self.pnl_history = deque(maxlen=max_points)
        self.strategy_performance = {}
    
    def record_price(self, symbol, price, timestamp=None):
        if timestamp is None:
            timestamp = time_module.time()
        if symbol in self.price_history:
            self.price_history[symbol].append({'timestamp': timestamp, 'price': price})
    
    def record_pnl(self, capital, daily_pnl, timestamp=None):
        if timestamp is None:
            timestamp = time_module.time()
        self.pnl_history.append({'timestamp': timestamp, 'capital': capital, 'daily_pnl': daily_pnl})
    
    def record_strategy(self, strategy_name, pnl, timestamp=None):
        if timestamp is None:
            timestamp = time_module.time()
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = deque(maxlen=100)
        self.strategy_performance[strategy_name].append({'timestamp': timestamp, 'pnl': pnl})
    
    def get_price_history(self):
        return {s: list(h) for s, h in self.price_history.items()}
    
    def get_pnl_history(self):
        return list(self.pnl_history)
    
    def get_strategy_performance(self):
        result = {}
        for strategy, history in self.strategy_performance.items():
            entries = list(history)
            result[strategy] = {'total_pnl': sum(e['pnl'] for e in entries), 'trade_count': len(entries)}
        return result

data_tracker = HistoricalDataTracker(max_points=300)
'''
    content = content.replace('app = Flask(__name__)', tracker_class + '\napp = Flask(__name__)')

    # Add endpoints
    endpoints = '''
@app.route('/api/prices/history')
def api_prices_history():
    return jsonify(data_tracker.get_price_history())

@app.route('/api/pnl/history')
def api_pnl_history():
    return jsonify(data_tracker.get_pnl_history())

@app.route('/api/strategies/performance')
def api_strategies_performance():
    return jsonify(data_tracker.get_strategy_performance())

@app.route('/api/record/price', methods=['POST'])
def api_record_price():
    data = request.get_json()
    if data.get('symbol') and data.get('price'):
        data_tracker.record_price(data['symbol'], data['price'])
    return jsonify({'status': 'recorded'})

@app.route('/api/record/pnl', methods=['POST'])
def api_record_pnl():
    data = request.get_json()
    data_tracker.record_pnl(data.get('capital', 0), data.get('daily_pnl', 0))
    return jsonify({'status': 'recorded'})

@app.route('/api/record/strategy', methods=['POST'])
def api_record_strategy():
    data = request.get_json()
    if data.get('strategy'):
        data_tracker.record_strategy(data['strategy'], data.get('pnl', 0))
    return jsonify({'status': 'recorded'})

'''
    content = content.replace('def run_dashboard(', endpoints + '\ndef run_dashboard(')

    with open(app_file, 'w') as f:
        f.write(content)
    print("Updated app.py")

PYTHON_SCRIPT

# Update HTML
python3 << 'PYTHON_SCRIPT'
html_file = 'paper_trading/dashboard/templates/index.html'

with open(html_file, 'r') as f:
    content = f.read()

if 'priceChart' in content:
    print("index.html already modified - skipping")
else:
    # Add Chart.js CDN
    content = content.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
    )

    # Add chart CSS
    chart_css = '''
        .chart-container { position: relative; height: 300px; width: 100%; }
        .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .chart-card { background: #1e2a3a; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); }
        .chart-card h2 { font-size: 16px; color: #888; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }
    </style>'''
    content = content.replace('    </style>', chart_css)

    # Add charts HTML
    charts_html = '''
        <div class="chart-card">
            <h2>📈 Live Price Chart</h2>
            <div class="chart-container"><canvas id="priceChart"></canvas></div>
        </div>
        <div class="chart-row">
            <div class="chart-card">
                <h2>💰 P&L History</h2>
                <div class="chart-container"><canvas id="pnlChart"></canvas></div>
            </div>
            <div class="chart-card">
                <h2>📊 Strategy Performance</h2>
                <div class="chart-container"><canvas id="strategyChart"></canvas></div>
            </div>
        </div>
        
        <div class="card">
            <h2>📋 Positions</h2>'''
    content = content.replace('<div class="card">\n            <h2>📋 Positions</h2>', charts_html)

    # Add chart JavaScript
    chart_js = '''
const chartColors = {'BTCUSDT':'#F7931A','ETHUSDT':'#627EEA','SOLUSDT':'#9945FF','BNBUSDT':'#F0B90B'};
Chart.defaults.color = '#888';
Chart.defaults.borderColor = '#333';

const priceChart = new Chart(document.getElementById('priceChart').getContext('2d'), {
    type: 'line', data: { labels: [], datasets: Object.keys(chartColors).map(s => ({label:s,data:[],borderColor:chartColors[s],borderWidth:2,pointRadius:0,tension:0.3,fill:false})) },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { x: { display: true }, y: { display: true } } }
});

const pnlChart = new Chart(document.getElementById('pnlChart').getContext('2d'), {
    type: 'line', data: { labels: [], datasets: [{ label: 'Capital', data: [], borderColor: '#00C853', backgroundColor: 'rgba(0,200,83,0.1)', fill: true, borderWidth: 2, pointRadius: 0, tension: 0.3 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
});

const strategyChart = new Chart(document.getElementById('strategyChart').getContext('2d'), {
    type: 'bar', data: { labels: [], datasets: [{ label: 'P&L', data: [], backgroundColor: [] }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
});

async function updateCharts() {
    try {
        const [prices, pnl, strategies] = await Promise.all([
            fetch('/api/prices/history').then(r=>r.json()),
            fetch('/api/pnl/history').then(r=>r.json()),
            fetch('/api/strategies/performance').then(r=>r.json())
        ]);
        
        const symbols = Object.keys(prices);
        if (symbols.length > 0 && prices[symbols[0]].length > 0) {
            priceChart.data.labels = prices[symbols[0]].map(p=>new Date(p.timestamp*1000).toLocaleTimeString());
            symbols.forEach((s,i) => { if(priceChart.data.datasets[i]) priceChart.data.datasets[i].data = prices[s].map(p=>p.price); });
            priceChart.update('none');
        }
        
        if (pnl.length > 0) {
            pnlChart.data.labels = pnl.map(p=>new Date(p.timestamp*1000).toLocaleTimeString());
            pnlChart.data.datasets[0].data = pnl.map(p=>p.capital);
            pnlChart.update('none');
        }
        
        const stratNames = Object.keys(strategies);
        if (stratNames.length > 0) {
            strategyChart.data.labels = stratNames;
            strategyChart.data.datasets[0].data = stratNames.map(s=>strategies[s].total_pnl);
            strategyChart.data.datasets[0].backgroundColor = stratNames.map(s=>strategies[s].total_pnl>=0?'#00C853':'#FF1744');
            strategyChart.update('none');
        }
    } catch(e) { console.error('Chart update error:', e); }
}

updateCharts();
setInterval(updateCharts, 2000);

function recordChartData(status, positions) {
    if (positions) {
        Object.entries(positions).forEach(([symbol, pos]) => {
            if (pos.price) fetch('/api/record/price', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,price:pos.price})}).catch(()=>{});
        });
    }
    if (status && status.capital !== undefined) {
        fetch('/api/record/pnl', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({capital:status.capital,daily_pnl:status.daily_pnl||0})}).catch(()=>{});
    }
}
'''
    content = content.replace('    </script>', chart_js + '\n    </script>')

    # Hook into fetchData
    content = content.replace(
        "(health.overall_status || 'unknown').toUpperCase();",
        "(health.overall_status || 'unknown').toUpperCase();\n                \n                // Record data for charts\n                recordChartData(status, positions);"
    )

    with open(html_file, 'w') as f:
        f.write(content)
    print("Updated index.html")

PYTHON_SCRIPT

echo ""
echo "================================================"
echo "Installation Complete!"
echo "================================================"
echo ""
echo "Restart the paper trading system to see charts:"
echo "  pkill -f run_paper_trading.py"
echo "  python run_paper_trading.py"
echo ""
