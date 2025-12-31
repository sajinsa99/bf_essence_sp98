#!/usr/bin/env python3
"""
Essence Tracker - Fetch and monitor fuel prices from prix-carburants.gouv.fr
Stores data in a flat JSON database and serves a web interface on port 9000
Supports multiple stations via YAML configuration file
"""

import json
import os
import sys
import signal
import atexit
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import logging
import yaml

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SCRIPT_DIR = Path(__file__).parent
DB_FILE = SCRIPT_DIR / "prices.json"
CONFIG_FILE = SCRIPT_DIR / "config.yaml"

app = Flask(__name__)

def load_config():
    """Load configuration from YAML file"""
    if not CONFIG_FILE.exists():
        logger.error(f"Config file not found: {CONFIG_FILE}")
        sys.exit(1)
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded config from {CONFIG_FILE}")
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        sys.exit(1)

# Load config once at startup
CONFIG = load_config()
PORT = CONFIG.get('server', {}).get('port', 9000)
STATIONS_CONFIG = CONFIG.get('stations', {})

class PriceTracker:
    def __init__(self, db_path):
        self.db_path = db_path
        self.data = self.load_db()
    
    def load_db(self):
        """Load database from JSON file"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading database: {e}")
                return []
        return []
    
    def save_db(self):
        """Save database to JSON file"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.info(f"Database saved with {len(self.data)} entries")
        except Exception as e:
            logger.error(f"Error saving database: {e}")
    
    def add_price(self, price, postal_code, station_name, fuel_type="SP98"):
        """Add or update price entry"""
        now = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Remove today's entry for this station if it exists (override)
        self.data = [
            e for e in self.data 
            if not (e['date'].startswith(today_str) and 
                   e['station'] == station_name and 
                   e['postal'] == postal_code)
        ]
        
        entry = {
            "date": now,
            "price": price,
            "fuel": fuel_type,
            "postal": postal_code,
            "station": station_name,
            "location": "Courbevoie"  # Can be made dynamic if needed
        }
        
        self.data.append(entry)
        self.data.sort(key=lambda x: x['date'])
        self.save_db()
        logger.info(f"Added price entry: €{price}/L for {station_name} on {now}")
        return entry
    
    def get_latest(self):
        """Get latest price entry"""
        return self.data[-1] if self.data else None
    
    def get_history(self):
        """Get all price history"""
        return self.data

def fetch_price_selenium():
    """Fetch price using Selenium (for JavaScript-heavy site)"""
    logger.info("Starting Selenium browser...")
    
    try:
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Chrome driver initialized")
        
        driver.get("https://www.prix-carburants.gouv.fr/")
        wait = WebDriverWait(driver, 15)
        
        # Wait for page to load and JavaScript to execute
        time.sleep(4)
        
        # Find and fill postal code input
        logger.info("Looking for postal code input...")
        postal_input = None
        try:
            # Try multiple selectors for postal input
            selectors = [
                "input[placeholder*='postal']",
                "input[placeholder*='code']",
                "input[type='text'][id*='postal']",
                "input[type='text'][id*='commune']",
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        postal_input = elements[0]
                        break
                except:
                    pass
            
            # If no specific selector found, try all text inputs
            if not postal_input:
                text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                if text_inputs:
                    postal_input = text_inputs[0]
            
            if postal_input:
                postal_input.clear()
                postal_input.send_keys(TARGET_POSTAL)
                logger.info(f"Entered postal code: {TARGET_POSTAL}")
                time.sleep(2)
                
                # Try to trigger search or press Enter
                postal_input.send_keys("\n")
                time.sleep(3)
        except Exception as e:
            logger.warning(f"Could not fill postal code: {e}")
        
        # Wait for results to load
        logger.info("Waiting for search results...")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Extract price data
        price = None
        try:
            page_source = driver.page_source
            
            # Look for station in page
            if TARGET_STATION in page_source or "RELAIS" in page_source:
                logger.info(f"Found station reference in page")
                
                # Look for price patterns - SP98 prices typically 1.5-2.5
                # Strategy: Find all numbers that look like prices
                import re
                price_pattern = r'1\.[0-9]{2,3}'
                matches = re.findall(price_pattern, page_source)
                
                if matches:
                    # Get the most common price (likely the correct one for this station)
                    prices = [float(m) for m in set(matches)]
                    prices.sort()
                    
                    # SP98 is typically more expensive, take higher prices first
                    for p in reversed(prices):
                        if 1.5 < p < 2.5:  # Reasonable range for fuel prices
                            price = p
                            logger.info(f"Extracted price from page source: €{price}/L")
                            break
                
                # Alternative: Look for elements with price text
                if not price:
                    price_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '€')]")
                    if price_elements:
                        for elem in price_elements[:10]:  # Check first 10 matches
                            text = elem.text.strip()
                            if text and '€' in text:
                                try:
                                    # Extract price (e.g., "1.895" from "1.895 €/L")
                                    price_str = text.split('€')[0].strip().split()[-1]
                                    p = float(price_str)
                                    if 1.5 < p < 2.5:
                                        price = p
                                        logger.info(f"Extracted price from element: €{price}/L")
                                        break
                                except:
                                    pass
            else:
                logger.warning(f"Station not found in page source")
        
        except Exception as e:
            logger.warning(f"Error during price extraction: {e}")
        
        driver.quit()
        return price
        
    except Exception as e:
        logger.warning(f"Selenium error: {e}")
        logger.info("Install ChromeDriver with: brew install chromedriver")
        return None

def fetch_price_alternative():
    """Fallback: Try using requests with a mock price for demo"""
    logger.info("Using alternative fetch method...")
    
    try:
        # Try direct API if available
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        # Attempt to access the site
        response = requests.get("https://www.prix-carburants.gouv.fr/", headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info("Successfully connected to prix-carburants.gouv.fr")
            # Would need more sophisticated parsing here
            return None
        
    except Exception as e:
        logger.warning(f"Alternative fetch failed: {e}")
    
    return None

def fetch_price_for_station(postal_code, station_name):
    """Fetch price for a specific station"""
    logger.info(f"Fetching price for {station_name} in {postal_code}")
    
    # Try Selenium first (more reliable for JS-heavy sites)
    price = fetch_price_selenium_station(postal_code, station_name)
    
    if price is None:
        logger.warning(f"Could not fetch price for {station_name}")
    
    return price

def fetch_price_selenium_station(postal_code, station_name):
    """Fetch price using Selenium for a specific station"""
    logger.info(f"Starting Selenium browser for {station_name}...")
    
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Chrome driver initialized")
        
        driver.get("https://www.prix-carburants.gouv.fr/")
        wait = WebDriverWait(driver, 15)
        
        # Wait for page to load and JavaScript to execute
        time.sleep(4)
        
        # Find and fill postal code input
        logger.info(f"Looking for postal code input...")
        postal_input = None
        try:
            # Try multiple selectors for postal input
            selectors = [
                "input[placeholder*='postal']",
                "input[placeholder*='code']",
                "input[type='text'][id*='postal']",
                "input[type='text'][id*='commune']",
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        postal_input = elements[0]
                        break
                except:
                    pass
            
            # If no specific selector found, try all text inputs
            if not postal_input:
                text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                if text_inputs:
                    postal_input = text_inputs[0]
            
            if postal_input:
                postal_input.clear()
                postal_input.send_keys(postal_code)
                logger.info(f"Entered postal code: {postal_code}")
                time.sleep(2)
                
                # Try to trigger search or press Enter
                postal_input.send_keys("\n")
                time.sleep(3)
        except Exception as e:
            logger.warning(f"Could not fill postal code: {e}")
        
        # Wait for results to load
        logger.info("Waiting for search results...")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Extract price data for this specific station
        price = None
        try:
            page_source = driver.page_source
            
            # Look for station in page (use shortened name)
            station_short = station_name.split("|")[0].strip()
            
            if station_short in page_source or station_name in page_source:
                logger.info(f"Found station reference: {station_name}")
                
                # Look for price patterns - SP98 prices typically 1.5-2.5
                import re
                price_pattern = r'1\.[0-9]{2,3}'
                matches = re.findall(price_pattern, page_source)
                
                if matches:
                    prices = [float(m) for m in set(matches)]
                    prices.sort()
                    
                    # SP98 is typically more expensive, take higher prices first
                    for p in reversed(prices):
                        if 1.5 < p < 2.5:  # Reasonable range for fuel prices
                            price = p
                            logger.info(f"Extracted price for {station_name}: €{price}/L")
                            break
                
                # Alternative: Look for elements with price text
                if not price:
                    price_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '€')]")
                    if price_elements:
                        for elem in price_elements[:10]:  # Check first 10 matches
                            text = elem.text.strip()
                            if text and '€' in text:
                                try:
                                    price_str = text.split('€')[0].strip().split()[-1]
                                    p = float(price_str)
                                    if 1.5 < p < 2.5:
                                        price = p
                                        logger.info(f"Extracted price from element: €{price}/L")
                                        break
                                except:
                                    pass
            else:
                logger.warning(f"Station '{station_name}' not found in page source")
        
        except Exception as e:
            logger.warning(f"Error during price extraction: {e}")
        
        driver.quit()
        return price
        
    except Exception as e:
        logger.warning(f"Selenium error: {e}")
        logger.info("Install ChromeDriver with: brew install chromedriver")
        return None

def fetch_all_prices():
    """Fetch prices for all configured stations"""
    logger.info("Starting price fetch for all configured stations...")
    tracker = PriceTracker(DB_FILE)
    
    total_fetched = 0
    for postal_code, stations in STATIONS_CONFIG.items():
        logger.info(f"\nFetching prices for postal code {postal_code}...")
        
        for station_config in stations:
            station_name = station_config.get('name')
            fuel_type = station_config.get('fuel', 'SP98')
            
            price = fetch_price_for_station(postal_code, station_name)
            
            if price is not None:
                tracker.add_price(price, postal_code, station_name, fuel_type)
                total_fetched += 1
            else:
                logger.warning(f"Failed to fetch price for {station_name}")
    
    logger.info(f"\n✓ Fetch complete. Updated {total_fetched} station(s)")

# Flask routes
@app.route('/')
def index():
    tracker = PriceTracker(DB_FILE)
    history = tracker.get_history()
    
    # Group data by station
    stations_data = {}
    for entry in history:
        station_name = entry.get('station', 'Unknown')
        if station_name not in stations_data:
            stations_data[station_name] = []
        stations_data[station_name].append(entry)
    
    # Calculate overall stats
    if history:
        latest = history[-1]
        all_prices = [e['price'] for e in history]
        min_price = min(all_prices)
        max_price = max(all_prices)
    else:
        latest = None
        min_price = None
        max_price = None
    
    # Build station checkboxes
    station_checkboxes = ""
    for station_name in sorted(stations_data.keys()):
        station_checkboxes += f'<label style="margin-right: 20px;"><input type="checkbox" class="station-filter" value="{station_name}" checked> {station_name}</label>'
    
    # Build table rows for all entries
    table_rows = ""
    for e in reversed(history):
        table_rows += f'<tr class="table-row" data-station="{e.get("station", "Unknown")}"><td><span class="station-label">{e.get("station", "Unknown")}</span></td><td><span class="timestamp">{e["date"]}</span></td><td><span class="price">€{e["price"]:.3f}</span></td><td>{e["fuel"]}</td><td>{e.get("postal", "N/A")}</td></tr>'
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Multi-Station SP98 Price Tracker</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            header {
                background: #2c3e50;
                color: white;
                padding: 30px;
                text-align: center;
            }
            header h1 { font-size: 28px; margin-bottom: 10px; }
            header p { opacity: 0.9; font-size: 14px; }
            .content { padding: 30px; }
            .controls {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
                border-left: 4px solid #667eea;
            }
            .controls-label {
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 15px;
                display: block;
            }
            .station-filters {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }
            .station-filters label {
                display: flex;
                align-items: center;
                cursor: pointer;
                user-select: none;
            }
            .station-filters input[type="checkbox"] {
                margin-right: 8px;
                width: 18px;
                height: 18px;
                cursor: pointer;
            }
            .refresh-btn {
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            }
            .refresh-btn:hover { background: #764ba2; }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }
            .stat-label { font-size: 11px; color: #666; text-transform: uppercase; margin-bottom: 5px; }
            .stat-value { font-size: 22px; font-weight: bold; color: #2c3e50; }
            .chart-container {
                position: relative;
                height: 400px;
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
            }
            .table-container {
                overflow-x: auto;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #e0e0e0;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
                color: #2c3e50;
            }
            tr:hover { background: #f8f9fa; }
            tr.hidden { display: none; }
            .price { font-weight: bold; color: #27ae60; font-size: 16px; }
            .timestamp { color: #7f8c8d; font-size: 12px; }
            .station-label { font-weight: 600; color: #2c3e50; }
            .no-data { text-align: center; color: #7f8c8d; padding: 40px; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>⛽ SP98 Price Tracker</h1>
                <p>All stations evolution</p>
            </header>
            <div class="content">
                <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
                """ + (f"""
                <div class="controls">
                    <span class="controls-label">Filter by Station:</span>
                    <div class="station-filters">
                        {station_checkboxes}
                    </div>
                </div>
                
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-label">Current Price</div>
                        <div class="stat-value">€{latest['price']:.3f}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Last Updated</div>
                        <div class="stat-value">{latest['date'].split('T')[0]}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total Records</div>
                        <div class="stat-value">{len(history)}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Min / Max</div>
                        <div class="stat-value">€{min_price:.3f} / €{max_price:.3f}</div>
                    </div>
                </div>
                
                <div class="chart-container">
                    <canvas id="priceChart"></canvas>
                </div>
                
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Station</th>
                                <th>Date</th>
                                <th>Price</th>
                                <th>Fuel</th>
                                <th>Postal</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
                
                <script>
                    const allStationsData = {json.dumps({station: [{"x": e['date'].split('T')[0], "y": e['price']} for e in station_history] for station, station_history in stations_data.items()})};
                    
                    const colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a'];
                    let chart = null;
                    
                    function getSelectedStations() {{
                        const selected = [];
                        document.querySelectorAll('.station-filter:checked').forEach(cb => {{
                            selected.push(cb.value);
                        }});
                        return selected;
                    }}
                    
                    function updateChart() {{
                        const selectedStations = getSelectedStations();
                        const datasets = [];
                        
                        Object.keys(allStationsData).sort().forEach((station, idx) => {{
                            if (selectedStations.includes(station)) {{
                                const data = allStationsData[station];
                                const color = colors[idx % colors.length];
                                datasets.push({{
                                    label: station,
                                    data: data.map(d => d.y),
                                    borderColor: color,
                                    backgroundColor: color + '1a',
                                    borderWidth: 2,
                                    tension: 0.4,
                                    fill: false,
                                    pointBackgroundColor: color,
                                    pointBorderColor: '#fff',
                                    pointBorderWidth: 2,
                                    pointRadius: 5
                                }});
                            }}
                        }});
                        
                        if (datasets.length > 0) {{
                            const allDates = [];
                            selectedStations.forEach(station => {{
                                allStationsData[station].forEach(d => {{
                                    if (!allDates.includes(d.x)) allDates.push(d.x);
                                }});
                            }});
                            allDates.sort();
                            
                            if (chart) {{
                                chart.data.labels = allDates;
                                chart.data.datasets = datasets;
                                chart.update();
                            }} else {{
                                const ctx = document.getElementById('priceChart').getContext('2d');
                                chart = new Chart(ctx, {{
                                    type: 'line',
                                    data: {{
                                        labels: allDates,
                                        datasets: datasets
                                    }},
                                    options: {{
                                        responsive: true,
                                        maintainAspectRatio: false,
                                        plugins: {{
                                            legend: {{
                                                display: true,
                                                labels: {{ font: {{ size: 12 }} }}
                                            }}
                                        }},
                                        scales: {{
                                            y: {{
                                                beginAtZero: false,
                                                ticks: {{ callback: d => '€' + d.toFixed(2) }}
                                            }}
                                        }}
                                    }}
                                }});
                            }}
                        }}
                    }}
                    
                    function updateTable() {{
                        const selectedStations = getSelectedStations();
                        document.querySelectorAll('.table-row').forEach(row => {{
                            const station = row.getAttribute('data-station');
                            if (selectedStations.includes(station)) {{
                                row.classList.remove('hidden');
                            }} else {{
                                row.classList.add('hidden');
                            }}
                        }});
                    }}
                    
                    // Add event listeners to checkboxes
                    document.querySelectorAll('.station-filter').forEach(checkbox => {{
                        checkbox.addEventListener('change', () => {{
                            updateChart();
                            updateTable();
                        }});
                    }});
                    
                    // Initialize chart and table
                    updateChart();
                    updateTable();
                </script>
                """ if history else "<div class='no-data'>No price data yet. Run: ./bf_essence_sp98.sh fetch</div>") + f"""
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

    return render_template_string(html)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--fetch':
        # Fetch mode - fetch all stations
        fetch_all_prices()
        sys.exit(0)
    
    # Server mode
    tracker = PriceTracker(DB_FILE)
    logger.info(f"Starting HTTP server on port {PORT}")
    logger.info(f"Database: {DB_FILE}")
    logger.info(f"Config: {CONFIG_FILE}")
    logger.info(f"Current entries: {len(tracker.data)}")
    
    # Log configured stations
    for postal, stations in STATIONS_CONFIG.items():
        logger.info(f"  Postal {postal}: {len(stations)} station(s)")
        for station in stations:
            logger.info(f"    - {station['name']} ({station.get('fuel', 'SP98')})")
    
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
