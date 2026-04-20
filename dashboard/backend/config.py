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
    ("pltr", "new york"),
    ("coin", "new york"),
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
    "pltr": "PLTR",
    "coin": "COIN",
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

# ── Unified asset universe (heatmap + frontend) ──────────────────────────

ASSET_UNIVERSE = [
    # US Equities
    {"ticker": "NVDA",   "label": "Nvidia",       "category": "US Equities", "yf_symbol": "NVDA"},
    {"ticker": "GOOGL",  "label": "Alphabet",      "category": "US Equities", "yf_symbol": "GOOGL"},
    {"ticker": "AMZN",   "label": "Amazon",        "category": "US Equities", "yf_symbol": "AMZN"},
    {"ticker": "AAPL",   "label": "Apple",         "category": "US Equities", "yf_symbol": "AAPL"},
    {"ticker": "MSFT",   "label": "Microsoft",     "category": "US Equities", "yf_symbol": "MSFT"},
    {"ticker": "TSLA",   "label": "Tesla",         "category": "US Equities", "yf_symbol": "TSLA"},
    {"ticker": "NFLX",   "label": "Netflix",       "category": "US Equities", "yf_symbol": "NFLX"},
    {"ticker": "META",   "label": "Meta",          "category": "US Equities", "yf_symbol": "META"},
    {"ticker": "PLTR",   "label": "Palantir",      "category": "US Equities", "yf_symbol": "PLTR"},
    {"ticker": "COIN",   "label": "Coinbase",      "category": "US Equities", "yf_symbol": "COIN"},
    # Indices
    {"ticker": "SPX",    "label": "S&P 500",       "category": "Indices",     "yf_symbol": "^GSPC"},
    {"ticker": "NDX",    "label": "Nasdaq 100",    "category": "Indices",     "yf_symbol": "^NDX"},
    {"ticker": "RUT",    "label": "Russell 2000",  "category": "Indices",     "yf_symbol": "^RUT"},
    {"ticker": "QQQ",    "label": "QQQ",           "category": "Indices",     "yf_symbol": "QQQ"},
    {"ticker": "DJIA",   "label": "Dow Jones",     "category": "Indices",     "yf_symbol": "^DJI"},
    {"ticker": "DAX",    "label": "DAX",           "category": "Indices",     "yf_symbol": "^GDAXI"},
    # Crypto
    {"ticker": "BTC",    "label": "Bitcoin",       "category": "Crypto",      "yf_symbol": "BTC-USD"},
    {"ticker": "ETH",    "label": "Ethereum",      "category": "Crypto",      "yf_symbol": "ETH-USD"},
    {"ticker": "SOL",    "label": "Solana",        "category": "Crypto",      "yf_symbol": "SOL-USD"},
    # Commodities
    {"ticker": "XAUUSD", "label": "Gold",          "category": "Commodities", "yf_symbol": "stooq:xauusd"},
    {"ticker": "WTI",    "label": "WTI",           "category": "Commodities", "yf_symbol": "CL=F"},
    {"ticker": "XAGUSD", "label": "Silver",        "category": "Commodities", "yf_symbol": "stooq:xagusd"},
]

EQUITY_TICKERS = [
    a["ticker"] for a in ASSET_UNIVERSE if a["category"] == "US Equities"
]

CATEGORY_ORDER = ["US Equities", "Indices", "Crypto", "Commodities"]

POLYMARKET_RIGHT_PANEL = {
    "Indices": [
        ("S&P 500",      "SPX"),
        ("Nasdaq 100",   "NDX"),
        ("Russell 2000", "RUT"),
        ("QQQ",          "QQQ"),
        ("Dow Jones",    "DJIA"),
        ("DAX",          "DAX"),
    ],
    "Crypto": [
        ("Bitcoin",  "bitcoin"),
        ("Ethereum", "ethereum"),
        ("Solana",   "solana"),
    ],
    "Commodities": [
        ("Gold",   "XAUUSD"),
        ("WTI",    "WTI"),
        ("Silver", "XAGUSD"),
    ],
}

POLYMARKET_YF_SYMBOL_MAP = {
    ("Indices",     "SPX"):      "^GSPC",
    ("Indices",     "NDX"):      "^NDX",
    ("Indices",     "RUT"):      "^RUT",
    ("Indices",     "QQQ"):      "QQQ",
    ("Indices",     "DJIA"):     "^DJI",
    ("Indices",     "DAX"):      "^GDAXI",
    ("Crypto",      "BITCOIN"):  "BTC-USD",
    ("Crypto",      "ETHEREUM"): "ETH-USD",
    ("Crypto",      "SOLANA"):   "SOL-USD",
    ("Commodities", "XAUUSD"):   "stooq:xauusd",
    ("Commodities", "WTI"):      "CL=F",
    ("Commodities", "XAGUSD"):   "stooq:xagusd",
}
