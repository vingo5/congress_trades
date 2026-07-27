import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from db import get_connection

HORIZONS = [30, 90, 180]  # Holding periods in calendar days

def setup_backtest_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS backtest_results (
            backtest_id SERIAL PRIMARY KEY,
            disclosure_id INT REFERENCES disclosures(disclosure_id) ON DELETE CASCADE,
            horizon_days INT NOT NULL,
            stock_return NUMERIC(8,4),
            spy_return NUMERIC(8,4),
            alpha NUMERIC(8,4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(disclosure_id, horizon_days)
        );
    """)

def fetch_price_data(tickers, start_date, end_date):
    """Fetches daily adjusted close prices for tickers + SPY from yfinance."""
    all_tickers = list(set(tickers + ['SPY']))
    print(f"Downloading historical price data for {len(all_tickers)} symbols...")
    try:
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False)['Close']
        return data
    except Exception as e:
        print(f"Error fetching yfinance data: {e}")
        return pd.DataFrame()

def run_backtest():
    conn = get_connection()
    cur = conn.cursor()
    setup_backtest_table(cur)
    conn.commit()

    # Query valid stock disclosures
    cur.execute("""
        SELECT d.disclosure_id, d.ticker, d.disclosure_date, d.transaction_type
        FROM disclosures d
        WHERE d.ticker NOT LIKE 'PTR_%'
          AND d.disclosure_date IS NOT NULL
          AND d.disclosure_date <= CURRENT_DATE - INTERVAL '30 days';
    """)
    records = cur.fetchall()
    if not records:
        print("No eligible disclosures found for backtesting.")
        return

    df = pd.DataFrame(records, columns=['disclosure_id', 'ticker', 'disclosure_date', 'type'])
    df['disclosure_date'] = pd.to_datetime(df['disclosure_date'])

    min_date = (df['disclosure_date'].min() - timedelta(days=5)).strftime('%Y-%m-%d')
    max_date = datetime.now().strftime('%Y-%m-%d')

    unique_tickers = df['ticker'].unique().tolist()
    prices = fetch_price_data(unique_tickers, min_date, max_date)

    if prices.empty:
        print("Failed to load price data. Exiting.")
        return

    inserted_count = 0

    for _, row in df.iterrows():
        disc_id = row['disclosure_id']
        ticker = row['ticker']
        disc_date = row['disclosure_date']
        is_buy = row['type'] == 'BUY'

        if ticker not in prices.columns or 'SPY' not in prices.columns:
            continue

        ticker_series = prices[ticker].dropna()
        spy_series = prices['SPY'].dropna()

        # Get exact or nearest trading day on/after disclosure_date
        valid_dates = ticker_series.index[ticker_series.index >= disc_date]
        if len(valid_dates) == 0:
            continue
        
        t0_date = valid_dates[0]
        p0_stock = ticker_series.loc[t0_date]
        p0_spy = spy_series.asof(t0_date)

        if pd.isna(p0_stock) or pd.isna(p0_spy) or p0_stock == 0 or p0_spy == 0:
            continue

        for h in HORIZONS:
            target_date = t0_date + timedelta(days=h)
            if target_date > ticker_series.index[-1]:
                continue  # Horizon extends beyond current date

            tn_date_stock = ticker_series.index.asof(target_date)
            tn_date_spy = spy_series.index.asof(target_date)

            pn_stock = ticker_series.loc[tn_date_stock]
            pn_spy = spy_series.loc[tn_date_spy]

            # Returns calculation
            stock_ret = (pn_stock - p0_stock) / p0_stock
            spy_ret = (pn_spy - p0_spy) / p0_spy

            # Invert sign for short/sell disclosures to reflect short trade performance
            if not is_buy:
                stock_ret = -stock_ret
                spy_ret = -spy_ret

            alpha = stock_ret - spy_ret

            cur.execute("""
                INSERT INTO backtest_results (disclosure_id, horizon_days, stock_return, spy_return, alpha)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (disclosure_id, horizon_days) DO UPDATE
                SET stock_return = EXCLUDED.stock_return,
                    spy_return = EXCLUDED.spy_return,
                    alpha = EXCLUDED.alpha;
            """, (disc_id, h, float(stock_ret), float(spy_ret), float(alpha)))
            inserted_count += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Backtest complete! Computed {inserted_count} performance metrics in PostgreSQL.")

if __name__ == "__main__":
    run_backtest()
