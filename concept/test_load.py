import traceback
from backend.heatmap.dashboard import load_market_bundle
try:
    df, _, _ = load_market_bundle()
    print("SUCCESS, df size:", len(df))
    print(df.head())
except Exception as e:
    traceback.print_exc()
