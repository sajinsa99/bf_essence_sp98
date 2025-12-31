# ⛽ Essence SP98 Price Tracker

Monitor fuel prices for multiple stations across different postal codes.

Fetches real prices from [prix-carburants.gouv.fr](https://www.prix-carburants.gouv.fr/), stores them in a flat JSON database with history, and provides a web interface to visualize price evolution.

## Features

- ✅ **Multi-station tracking** - Monitor multiple stations per postal code
- ✅ **Station filtering** - Toggle stations on/off in the web interface
- ✅ **Unified dashboard** - Single graph and table showing all stations together
- ✅ **YAML configuration** - Easy to add/remove stations
- ✅ **Automatic price fetching** from prix-carburants.gouv.fr using Selenium
- ✅ **Flat JSON database** with full price history
- ✅ **Automatic daily override** - one price per station per day
- ✅ **HTTP server on port 9000** with web dashboard
- ✅ **Interactive price charts** with multi-line comparison
- ✅ **Simple bash control script** (start/stop/status/fetch)
- ✅ **Zero configuration** - virtual environment auto-setup

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/brunofablet/gh/bf_essence_sp98

# Automatic setup (recommended)
./setup.sh

# Or manual setup
pip3 install -r requirements.txt
brew install chromedriver  # For real price fetching
chmod +x bf_essence_sp98.sh essence_tracker.py
```

### 2. Start the Server

```bash
./bf_essence_sp98.sh start
```

Access the dashboard at: **http://localhost:9000**

### 3. Fetch Prices

```bash
./bf_essence_sp98.sh fetch
```

This connects to prix-carburants.gouv.fr, searches for the station, extracts the SP98 price, and stores it in the database.

## Commands Reference

```bash
./bf_essence_sp98.sh start      # Start HTTP server on :9000
./bf_essence_sp98.sh stop       # Stop server
./bf_essence_sp98.sh status     # Show server status and DB entries
./bf_essence_sp98.sh fetch      # Fetch current price and update DB
./bf_essence_sp98.sh restart    # Restart server
```

## Database Format

Prices are stored in `prices.json` as a flat JSON array:

```json
[
  {
    "date": "2025-12-30T20:52:10.427964",
    "price": 1.895,
    "fuel": "SP98",
    "postal": "92400",
    "station": "RELAIS DE L'ALMA | TotalEnergies",
    "location": "Courbevoie"
  }
]
```

Each day's fetch **overwrites the previous day's price** (one entry per day maximum).

## Web Dashboard

The HTTP server provides:

- **Station Filtering**: Checkboxes to toggle stations on/off (all selected by default)
- **Unified Price Chart**: Interactive line graph with all selected stations plotted together
- **Unified Price Table**: Detailed history for all selected stations with station name, timestamp, price, fuel type, and postal code
- **Statistics**: Current price, last updated date, total records, min/max prices

The chart and table update dynamically as you select/deselect stations, making it easy to compare prices across locations.

Accessible at: http://localhost:9000

## Automation (Optional)

To automatically fetch prices every day at 8 AM, add to crontab:

```bash
crontab -e
```

Add this line:
```
0 8 * * * /Users/brunofablet/gh/bf_essence_sp98/bf_essence_sp98.sh fetch
```

Other useful schedules:
```bash
0 12 * * *  # Noon
0 18 * * *  # 6 PM
*/6 * * * * # Every 6 hours
```

## Configuration

Create or edit `config.yaml` to add/remove stations:

```yaml
stations:
  "92400":  # Courbevoie
    - name: "RELAIS DE L'ALMA | TotalEnergies"
      fuel: "SP98"
    - name: "RELAIS COURBEVOIE VERDUN | TotalEnergies Access"
      fuel: "SP98"
  
  "75001":  # Paris (example)
    - name: "STATION NAME | BRAND"
      fuel: "SP98"
    - name: "ANOTHER STATION | BRAND"
      fuel: "SP95"

server:
  port: 9000
  host: "0.0.0.0"
```

Edit `essence_tracker.py` to customize behavior (optional):

```python
STATIONS_CONFIG = CONFIG.get('stations', {})  # Loads from config.yaml
PORT = CONFIG.get('server', {}).get('port', 9000)
```

Or edit `bf_essence_sp98.sh` to change port:

## Logs & Files

- `essence_tracker.log` - Server and fetch logs
- `.server.pid` - Process ID of running server
- `prices.json` - Price database
- `venv/` - Python virtual environment (auto-created)

## System Requirements

- **OS**: macOS (or Linux with minor adjustments)
- **Python**: 3.7 or higher
- **ChromeDriver**: Required for price fetching
  ```bash
  brew install chromedriver
  ```
- **Disk space**: ~50 MB (including venv)

## Troubleshooting

### Port 9000 Already in Use

Edit both `PORT` variables in `essence_tracker.py` and `bf_essence_sp98.sh` to use a different port (e.g., 9001).

### ChromeDriver Not Found

```bash
brew install chromedriver
```

Or download from: https://chromedriver.chromium.org/

### Permission Denied

```bash
chmod +x bf_essence_sp98.sh essence_tracker.py setup.sh
```

### Server Won't Start

Check logs:
```bash
tail -50 essence_tracker.log
```

Kill any process using port 9000:
```bash
lsof -ti:9000 | xargs kill -9
```

### Price Not Fetching Correctly

The scraper looks for prices in the range €1.5 - €2.5. If prices fall outside this range, update the regex pattern in `fetch_price_selenium()`.

## Project Structure

```
.
├── bf_essence_sp98.sh          # Control script (bash)
├── essence_tracker.py          # Main app (Python + Flask)
├── prices.json                 # Price database (JSON)
├── requirements.txt            # Python dependencies
├── setup.sh                    # Automated setup script
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
└── venv/                       # Virtual environment (auto-created)
```

## Development

The codebase is modular and easy to extend:

- **Add price alerts**: Modify `add_price()` to send notifications
- **Support multiple stations**: Extend database to handle many locations
- **API endpoints**: Add Flask routes for external access
- **Database upgrade**: Migrate from JSON to SQLite if needed
- **Deploy**: Run on Heroku, AWS, or your own server

## License

Open source - feel free to use and modify for personal use.

