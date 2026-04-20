# Polymarket and yfinance API reference

Polymarket exposes three public REST APIs — **Gamma** for market discovery, **CLOB** for order book data and trading, and **Data** for user activity — all free, with no authentication required for read operations. The Gamma API is the primary entry point for finding markets, while the CLOB API provides real-time pricing and historical probability data. The yfinance library offers free Yahoo Finance data but faces increasingly aggressive rate limiting in 2025–2026. This report documents every endpoint, field, parameter, and integration pattern across all four systems.

---

## Gamma API: the market discovery layer

**Base URL**: `https://gamma-api.polymarket.com`  
**Authentication**: None required — fully public, read-only  
**Response format**: JSON arrays or objects

### Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/markets` | List markets with filtering and pagination |
| `GET` | `/markets/keyset` | Markets with cursor-based pagination |
| `GET` | `/markets/{id}` | Single market by numeric ID |
| `GET` | `/markets/slug/{slug}` | Single market by slug |
| `GET` | `/markets/{id}/tags` | Tags for a specific market |
| `GET` | `/events` | List events with filtering and pagination |
| `GET` | `/events/keyset` | Events with cursor-based pagination |
| `GET` | `/events/{id}` | Single event by numeric ID |
| `GET` | `/events/slug/{slug}` | Single event by slug |
| `GET` | `/events/{id}/tags` | Tags for a specific event |
| `GET` | `/tags` | All tags with pagination |
| `GET` | `/tags/{id}` | Tag by ID |
| `GET` | `/tags/slug/{slug}` | Tag by slug |
| `GET` | `/tags/{id}/related-tags/tags` | Related sub-tags |
| `GET` | `/public-search` | Full-text search across events, markets, profiles |
| `GET` | `/series` | Market series metadata |
| `GET` | `/profiles/{address}` | Public profile by wallet address |

### Query parameters for `/markets`

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Results per page |
| `offset` | integer | Offset-based pagination |
| `order` | string | Sort field: `volume_24hr`, `volume`, `liquidity`, `start_date`, `end_date`, `competitive`, `closed_time` |
| `ascending` | boolean | Sort direction (default: `false` for descending) |
| `id` | integer[] | Filter by market IDs |
| `slug` | string[] | Filter by slugs |
| `clob_token_ids` | string[] | Filter by CLOB token IDs |
| `condition_ids` | string[] | Filter by condition IDs |
| `tag_id` | integer | Filter by tag ID (**not** tag name) |
| `related_tags` | boolean | Include related sub-tags in filter |
| `active` | boolean | Filter active markets |
| `closed` | boolean | Filter closed markets |
| `liquidity_num_min` / `_max` | number | Liquidity range filter |
| `volume_num_min` / `_max` | number | Volume range filter |
| `start_date_min` / `_max` | datetime | Start date range |
| `end_date_min` / `_max` | datetime | End date range |

The `/events` endpoint accepts similar parameters plus `tag_slug` for filtering by tag slug string.

### Pagination

Two modes exist. **Offset-based**: use `limit` + `offset` on `/markets` and `/events`. **Cursor-based**: use `/markets/keyset` and `/events/keyset` with `after_cursor` parameter — the response includes a `next_cursor` field for the next page. Cursor pagination is more stable for large result sets.

### Rate limits

All enforced via Cloudflare throttling (requests are delayed, not dropped):

| Endpoint | Limit per 10 seconds |
|----------|---------------------|
| General (all endpoints) | 4,000 |
| `/events` | 500 |
| `/public-search` | 350 |
| `/markets` | 300 |
| `/tags` | 200 |

Exceeding limits returns HTTP 429. Wait 10+ seconds before retrying.

---

## Markets vs events: the data model hierarchy

**Events are parent containers. Markets are tradeable binary outcomes nested inside events.** This is the most important structural concept in Polymarket's API.

An event like "Presidential Election Winner 2024" (`id: 903193`) contains multiple markets — one for each candidate: "Will Donald Trump win?" (`id: 253591`), "Will Kamala Harris win?", and so on. Each market is a binary Yes/No question with its own `conditionId`, token IDs, and probability.

```
Event: "Presidential Election Winner 2024"
  ├── Market: "Will Donald Trump win?" → Yes: 54.5%, No: 45.5%
  ├── Market: "Will Kamala Harris win?" → Yes: 44.0%, No: 56.0%
  └── Market: "Will RFK Jr. win?" → Yes: 1.5%, No: 98.5%
```

When you query `/events`, each event includes a nested `markets[]` array with full market objects. When you query `/markets`, each market includes an `events[]` array referencing its parent events. **The `/events` endpoint is strongly preferred for market discovery** because one call returns the full context — the overarching question, all possible outcomes, and categorization tags. Sorting events by `volume_24hr` surfaces trending topics efficiently.

---

## Complete market object schema

The Gamma API returns market objects with these fields (all confirmed from official documentation and SDK type definitions):

### Core identifiers

| Field | Type | Example |
|-------|------|---------|
| `id` | string | `"253591"` |
| `question` | string | `"Will Donald Trump win the 2024 US Presidential Election?"` |
| `conditionId` | string | `"0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917"` |
| `slug` | string | `"will-donald-trump-win-the-2024-us-presidential-election"` |
| `questionID` | string | `"0xe3b1bc389210504ebcb9cffe4b0ed06ccac50561e0f24abb6379984cec030f00"` |

### Outcomes and pricing — the critical fields

Three fields require special handling because they are returned as **JSON-stringified strings**, not native arrays:

| Field | Raw API Value | Parsed Value |
|-------|--------------|--------------|
| `outcomes` | `"[\"Yes\",\"No\"]"` | `["Yes", "No"]` |
| `outcomePrices` | `"[\"0.545\",\"0.455\"]"` | `["0.545", "0.455"]` |
| `clobTokenIds` | `"[\"21742633...\",\"48331043...\"]"` | `["21742633...", "48331043..."]` |

**You must call `json.loads()` on these fields.** The `outcomes` and `outcomePrices` arrays are parallel — index 0 of outcomes corresponds to index 0 of outcomePrices. Prices represent implied probabilities that sum to approximately **1.0**. The `clobTokenIds` array contains ERC-1155 token IDs (very large integers as strings, typically 70–78 digits) used by the CLOB API.

### Volume and liquidity

| Field | Type | Description |
|-------|------|-------------|
| `volume` / `volumeNum` | string / number | Total all-time volume |
| `volume24hr` | number | 24-hour trading volume |
| `volume1wk` / `volume1mo` / `volume1yr` | number | Rolling volume windows |
| `liquidity` / `liquidityNum` | string / number | Current total liquidity |
| `liquidityClob` | number | CLOB-specific liquidity |

### Price metrics

| Field | Type |
|-------|------|
| `lastTradePrice` | number |
| `bestBid` / `bestAsk` | number |
| `spread` | number |
| `oneDayPriceChange` / `oneHourPriceChange` / `oneWeekPriceChange` | number |

### Status flags

`active` (boolean), `closed` (boolean), `archived` (boolean), `new` (boolean), `featured` (boolean), `restricted` (boolean), `enableOrderBook` (boolean), `acceptingOrders` (boolean), `funded` (boolean), `ready` (boolean).

### Additional fields

Market objects also include `image`, `icon`, `description`, `resolutionSource`, `endDate`, `startDate` (ISO 8601), `category`, `marketType`, `formatType`, `fee`, `denominationToken`, `marketMakerAddress`, `createdAt`, `updatedAt`, `negRisk` (boolean for multi-outcome events), `orderPriceMinTickSize`, `makerBaseFee`, `takerBaseFee`, and nested `events[]`, `tags[]`, and `categories[]` arrays.

### Event object additions

Event objects include all the above grouping fields plus: `title`, `subtitle`, `ticker`, `negRiskMarketID`, `openInterest`, `series[]`, `subEvents[]`, `collections[]`, `showAllOutcomes`, `enableNegRisk`, `estimateValue`, and a nested `markets[]` array containing full market objects.

---

## CLOB API: order books and price history

**Base URL**: `https://clob.polymarket.com`  
**Authentication**: Public for reads; L2 wallet-based auth for trading

### Public endpoints (no authentication required)

| Endpoint | Parameters | Response |
|----------|-----------|----------|
| `GET /markets` | `next_cursor` (default `MA==`) | Paginated array of CLOB market objects |
| `GET /markets/{conditionId}` | — | Single CLOB market |
| `GET /book` | `token_id` (required) | Order book with `bids[]`, `asks[]` arrays |
| `GET /price` | `token_id`, `side` (`BUY`/`SELL`) | `{ price: string }` |
| `GET /midpoint` | `token_id` | `{ mid: string }` |
| `GET /spread` | `token_id` | `{ spread: string }` |
| `GET /prices-history` | `market` (token_id), `interval`, `fidelity`, `startTs`, `endTs` | `{ history: [{t, p}] }` |
| `GET /last-trade-price` | `token_id` | `{ price: string, side: string }` |
| `GET /market-trades-events` | `conditionID` | Array of trade events |
| `GET /tick-size` | `token_id` | Tick size string |
| `GET /time` | — | Unix timestamp (for clock sync) |

Batch variants exist: `POST /books`, `POST /prices`, `POST /midpoints`, `POST /spreads`, `POST /last-trades-prices`, `POST /prices-history/batch`.

### Order book response structure

```json
{
  "market": "0xdd22472e...",
  "asset_id": "21742633143...",
  "timestamp": "2024-01-15T12:00:00Z",
  "bids": [
    {"price": "0.54", "size": "1250.5"},
    {"price": "0.53", "size": "800.0"}
  ],
  "asks": [
    {"price": "0.55", "size": "950.0"},
    {"price": "0.56", "size": "500.0"}
  ],
  "min_order_size": "5",
  "tick_size": "0.01",
  "neg_risk": false,
  "hash": "..."
}
```

Each bid/ask level has `price` (string, 0–1 range) and `size` (string, USDC amount).

### Price history endpoint

The `/prices-history` endpoint is the primary tool for tracking probability changes over time. **The `market` parameter takes a token_id, not a condition_id.** The `interval` parameter accepts `1h`, `6h`, `1d`, `1w`, `max`. The `fidelity` parameter sets resolution in minutes (e.g., `60` = hourly data points). Response format:

```json
{
  "history": [
    {"t": 1713020400, "p": 0.545},
    {"t": 1713024000, "p": 0.552},
    {"t": 1713027600, "p": 0.548}
  ]
}
```

Each `t` is a Unix timestamp and `p` is the price (0.00–1.00), representing the implied probability. For resolved markets, fine granularity below 12 hours may return empty results.

### CLOB market object vs Gamma market object

The CLOB API returns a different market schema from Gamma. Key differences:

| Aspect | CLOB Market | Gamma Market |
|--------|-------------|--------------|
| Primary key | `condition_id` | `id` (numeric) |
| Token data | `tokens[]` array with `{token_id, outcome, price, winner}` | `clobTokenIds` (JSON-stringified string) |
| Slug field | `market_slug` | `slug` |
| Trading params | `minimum_tick_size`, `minimum_order_size`, `maker_base_fee`, `taker_base_fee` | Not included |
| Volume/liquidity | Not included | `volume`, `volume24hr`, `liquidity`, etc. |
| Event grouping | Flat (no event nesting) | Nested under events |

### Token IDs and condition IDs explained

The `condition_id` is a **0x-prefixed hex string** (66 characters, 32 bytes) that uniquely identifies a market across both APIs. Each market has exactly two **token IDs** — very large uint256 integers (70–78 digits, represented as strings) — one for the "Yes" outcome and one for "No." These are ERC-1155 asset IDs on Polygon. The Gamma API's `clobTokenIds` field maps directly to the CLOB API's `tokens[].token_id` values. Index 0 is always "Yes," index 1 is always "No."

### Authentication for trading

Trading requires L2 authentication using a triple-credential system: API key, secret, and passphrase. These are derived from a wallet private key via L1 authentication (EIP-712 signature). Headers: `POLY_ADDRESS`, `POLY_SIGNATURE`, `POLY_TIMESTAMP`, `POLY_API_KEY`, `POLY_PASSPHRASE`. All read endpoints are fully public.

### CLOB rate limits

| Endpoint | Limit per 10 seconds |
|----------|---------------------|
| General | 9,000 |
| `/book` | 1,500 |
| `/price` | 1,500 |
| Price History | 1,000 |
| `POST /books` (batch) | 500 |
| `POST /order` | 3,500 burst / 36,000 per 10min sustained |

---

## Geopolitical markets: slugs, tags, and discovery

### Tag-based filtering uses numeric IDs, not strings

A critical implementation detail: **the `tag=Politics` parameter does not work.** The Gamma API requires `tag_id` with numeric identifiers. Known tag IDs:

| Category | `tag_id` |
|----------|---------|
| Politics | 2 |
| Crypto | 21 |
| Finance | 120 |
| Culture | 596 |
| Tech | 1401 |
| Geopolitics | 100265 |
| Sports | 100639 |

Use `GET /tags` to discover all available tags. Sub-categories under Geopolitics include Iran, Ukraine, China, Middle East, India-Pakistan, South Korea, and more. Add `related_tags=true` to include sub-tag markets in results.

### Slug format and patterns

Slugs are **always lowercase, hyphen-separated, human-readable strings** using only `[a-z0-9-]`. They are unique across the platform. Two distinct patterns exist:

**Event slugs** are clean and descriptive, sometimes with a single numeric suffix for disambiguation:
- `us-china-tariff-agreement-before-90-day-deadline`
- `will-china-invade-taiwan-by-march-31-2026`
- `netanyahu-out-before-2027`
- `where-will-trump-and-putin-meet-next-584`

**Market slugs** (individual outcomes within events) often append longer numeric disambiguation codes:
- `netanyahu-out-before-2027-684-719-226`
- `us-forces-enter-iran-by-december-31-573-642-385-371-179-425-262`
- `will-crude-oil-cl-hit-high-100-by-end-of-march-658-396-769-971`

**Up/down financial market slugs** use a deterministic format: `{asset}-updown-{interval}-{unix_timestamp}`. Examples: `btc-updown-5m-1775241600`, `eth-updown-15m-1768502700`. The timestamp represents the window boundary, calculated by rounding the current time down to the interval boundary.

### How to find geopolitical markets programmatically

Four methods exist, in order of reliability:

1. **Tag filtering** (best for category browsing): `GET /events?tag_id=100265&related_tags=true&active=true&closed=false&order=volume_24hr&ascending=false&limit=100`

2. **Full-text search** (best for specific topics): `GET /public-search?query=US-China+tariffs&limit=20` — returns matching events, tags, and profiles ranked by relevance

3. **Event grouping** (for exploring related markets): Fetch an event by slug to get all child markets — `GET /events/slug/us-x-iran-ceasefire-by` returns the event with all its deadline-variant markets

4. **Related tags browsing**: `GET /tags/100265/related-tags/tags` discovers sub-categories like Iran, Ukraine, China, each with their own `tag_id`

### Mapping a topic to active markets: step by step

```python
import requests, json

# 1. Search for relevant events
results = requests.get("https://gamma-api.polymarket.com/public-search",
    params={"query": "US-China tariffs", "limit": 20}).json()

# 2. Also try tag-based discovery
events = requests.get("https://gamma-api.polymarket.com/events",
    params={"tag_id": 100265, "related_tags": "true",
            "active": "true", "closed": "false",
            "order": "volume_24hr", "ascending": "false",
            "limit": 100}).json()

# 3. Extract tradeable markets with keyword filtering
for event in events:
    for market in event.get("markets", []):
        question = market.get("question", "").lower()
        if any(kw in question for kw in ["tariff", "china", "trade"]):
            tokens = json.loads(market["clobTokenIds"])
            prices = json.loads(market["outcomePrices"])
            print(f"{market['question']}: Yes={prices[0]}, token={tokens[0]}")

# 4. Get price history for a specific token
history = requests.get("https://clob.polymarket.com/prices-history",
    params={"market": tokens[0], "interval": "1d", "fidelity": 60}).json()
```

Polymarket currently hosts approximately **540 active geopolitical markets** with over $464M in total trading volume, covering topics from Iran regime change to US-China tariff rates.

---

## yfinance: capabilities and critical limitations

### `Ticker.history()` parameters

```python
history(period=None, interval='1d', start=None, end=None, prepost=False,
        actions=True, auto_adjust=True, back_adjust=False, repair=False,
        keepna=False, rounding=False, timeout=10, raise_errors=False)
```

Valid `period` values: `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`. Valid `interval` values: `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `5d`, `1wk`, `1mo`, `3mo`. Returns a pandas DataFrame with columns `Open`, `High`, `Low`, `Close`, `Volume`, `Dividends`, `Stock Splits`. Timestamps are **timezone-aware**, localized to the exchange's timezone (e.g., `America/New_York` for NYSE, `UTC` for crypto).

**Intraday data constraints are strict**: 1-minute data is only available for the **last 7 days**. All intraday intervals (< 1d) are limited to the **last 60 days**. Requesting data beyond these windows returns an empty DataFrame with no error.

### `fast_info` vs `info`

`Ticker.fast_info` (introduced in v0.2.6) provides a dict-like interface with keys including `lastPrice`, `previousClose`, `open`, `dayHigh`, `dayLow`, `volume`, `marketCap`, `fiftyDayAverage`, `twoHundredDayAverage`, `fiftyTwoWeekHigh`, `fiftyTwoWeekLow`, `currency`, `exchange`, `timezone`. It uses historical price data rather than the expensive `quoteSummary` API, making it lighter weight. However, as of recent versions, **the speed advantage over `.info` has diminished** after `.info` was optimized.

`Ticker.info` returns a comprehensive dict from Yahoo's `quoteSummary` endpoint with 100+ fields including `sector`, `industry`, `longBusinessSummary`, `fullTimeEmployees`, `trailingPE`, `forwardPE`, `marketCap`, `currentPrice`, and financial ratios. It is the most expensive single request yfinance makes. Not all tickers return the same keys — **ETFs, stocks, and crypto each have different available fields**, and `currentPrice` may be missing for ETFs (use `fast_info['lastPrice']` as fallback).

### `yf.download()` for multiple tickers

```python
data = yf.download(["AAPL", "MSFT", "GOOG"], period="1mo",
                    group_by="column", threads=True, auto_adjust=True)
```

Returns a DataFrame with **MultiIndex columns** by default: `(Price, Ticker)` pairs. Access with `data['Close']['AAPL']` or use `group_by='ticker'` for `data['AAPL']['Close']`. Uses multithreading for faster downloads. **Not thread-safe** for concurrent calls — uses a shared global dictionary internally.

### Rate limiting has become severe

Yahoo Finance rate limiting is **significantly more aggressive** in 2025–2026. There are no documented official limits since yfinance uses unofficial APIs. Users report **429 errors with as few as 20 requests per session**. Shared hosting (Streamlit Cloud, PythonAnywhere, Colab) is especially affected because many users share IP addresses. Errors manifest as `YFRateLimitError`, misleading `YFTzMissingError('possibly delisted')`, or `JSONDecodeError` on empty responses.

Best practices: use `yf.download()` instead of individual `Ticker` calls (batches requests), add `time.sleep(5)` between requests, download in chunks of ~80 tickers with 10-second delays, use `requests_cache.CachedSession` for repeat queries.

### Common failure modes

**Delisted tickers** return empty DataFrames with a warning — no exception is raised by default. **Weekend/holiday gaps** are normal — daily data simply has no entries. **Crypto tickers** (`BTC-USD`) trade 24/7 with UTC timestamps, while equity tickers reflect market hours. The `prepost=True` parameter includes pre-market and after-hours data but only works with intraday intervals. **Empty DataFrames** are the most common failure mode, caused by rate limiting, expired intraday windows, or Yahoo API changes.

### Breaking changes across versions

- **v0.2.51** (Jan 2025): `yf.download()` now always returns **MultiIndex columns even for single tickers** and columns are alphabetically ordered (CHLOV, not OHLCV). Fix: use `multi_level_index=False`.
- **v0.2.51+**: `auto_adjust` default changed to `True` in `yf.download()`. The separate `Adj Close` column no longer exists — `Close` IS the adjusted close.
- **v0.2.54** (Feb 2025): Critical fix for a Yahoo API backend change that broke all downloads globally.
- **v0.2.60+**: Custom `requests.Session` objects may be rejected; yfinance now requires `curl_cffi` sessions internally.
- **v1.0** (Jan 2026): No breaking changes from 0.2.66, but deprecated the old config method in favor of `yf.config`.

---

## How `build_up_down_slug()` compares to real Polymarket slugs

The typical `build_up_down_slug()` function generates slugs in the format **`{asset}-updown-{interval}-{unix_timestamp}`**, where the timestamp is a window boundary calculated by rounding the current Unix time down to the interval:

```python
now = int(time.time())
window_ts = now - (now % 300)  # 5-minute boundary
slug = f"btc-updown-5m-{window_ts}"  # e.g., "btc-updown-5m-1775241600"
```

This format is **correct but only applies to recurring financial up/down markets**. Geopolitical market slugs are completely different — they are **ad hoc, human-readable descriptions** like `will-china-invade-taiwan-by-march-31-2026` or `us-tariff-rate-on-china-on-august-15`. There is no algorithmic way to construct geopolitical slugs; they must be discovered via the `/public-search` endpoint or tag-based filtering. The `build_up_down_slug()` pattern works because Polymarket creates up/down markets on a fixed schedule aligned to Unix epoch boundaries, making the slugs deterministic and predictable.

## Conclusion

The Gamma and CLOB APIs form a complementary pair: **Gamma for discovery, CLOB for execution and pricing.** The workflow is always Gamma → parse `clobTokenIds` → CLOB for order books and price history. Three non-obvious pitfalls stand out: tag filtering requires numeric `tag_id` values (not string names), the `outcomePrices` field is a JSON string that must be parsed, and the CLOB `/prices-history` endpoint takes `token_id` (not `condition_id`) as its `market` parameter. For yfinance integration, the biggest risk is Yahoo's rate limiting — the library remains functional but fragile, requiring defensive coding with retries, caching, and batch downloads. The `multi_level_index=False` parameter on `yf.download()` is essential for backward compatibility with code written before v0.2.51.