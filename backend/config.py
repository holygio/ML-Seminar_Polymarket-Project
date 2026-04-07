from pathlib import Path

# Project root paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Assets to track
ASSETS = [
    ("nflx", "new york"),
    ("tsla", "new york"),
    ("aapl", "new york"),
    ("nvda", "new york"),
    ("googl", "new york"),
    ("meta", "new york"),
    ("msft", "new york"),
    ("amzn", "new york"),
]

# Ticker map: slug -> Yahoo Finance ticker
TICKER_MAP = {
    "nflx": "NFLX",
    "tsla": "TSLA",
    "aapl": "AAPL",
    "nvda": "NVDA",
    "googl": "GOOGL",
    "meta": "META",
    "msft": "MSFT",
    "amzn": "AMZN",
}

# Pipeline parameters
DAYS_BACK = 60
INTRADAY_WINDOW_MINUTES = 5
MAX_WORKERS = 10
START_DAY_FROM_NOW = 0

# Signal parameters
LIQUIDITY_THRESHOLD = 500
FIREWALL_HOUR_NY = 9
FIREWALL_MINUTE_NY = 30
RISK_FREE_ANN = 0.04

# Signal quality scoring weights
SQ_VOLUME_HIGH = 500
SQ_VOLUME_MED = 100
SQ_SPREAD_TIGHT = 0.01
SQ_SPREAD_MED = 0.03

# Heatmap parameters
HEATMAP_MIN_MOVE = 0.005

# APIs
GAMMA_API = "https://gamma-api.polymarket.com/events/slug"
GOLDSKY_URL = "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw/subgraphs/orderbook-subgraph/0.0.1/gn"

TIMEZONE_MAP = {
    "new york": "America/New_York",
    "london": "Europe/London",
    "tokyo": "Asia/Tokyo",
    "europe": "Europe/Berlin",
}
