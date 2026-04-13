# DEPRECATED — import from pipeline instead.
# This compatibility shim exists so backend-local imports do not depend on the
# root-level prototype shim.

from pipeline import *  # noqa: F401, F403
from pipeline import (  # explicit re-export for IDEs
    build_up_down_slug,
    fetch_token_market_details,
    get_effective_crypto_market_date,
    get_effective_nyse_market_date,
    get_effective_nyse_trading_date,
    get_market_probabilities_by_slug,
    get_probabilities_for_tickers,
    get_up_probability,
)
