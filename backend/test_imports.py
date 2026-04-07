import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from config import ASSETS, DATA_DIR, INTRADAY_WINDOW_MINUTES
from pipeline.features import (
    analyse_sentiment_dynamics,
    build_preopen_panel,
    check_lead_lag,
    collapse_to_windows,
)
from pipeline.orderbook import Orderbook

print("✅ all imports OK")
print(f"   assets configured: {[asset[0].upper() for asset in ASSETS]}")
print(f"   intraday window:   {INTRADAY_WINDOW_MINUTES} minutes")
print(f"   data directory:    {DATA_DIR}")
