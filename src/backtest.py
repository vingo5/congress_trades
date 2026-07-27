import yfinance as yf
from datetime import timedelta, datetime
from db import execute_query

def fetch_top_signals(limit=20):
    query = """
        SELECT d.ticker, d.transaction_date, s.signal_type, s.confidence_score
        FROM disclosures d
        JOIN trade_signals s ON d.disclosure_id = s.disclosure_id
        WHERE d.transaction_date >= '2023-01-01'
        ORDER BY s.confidence_score DESC
        LIMIT %s;
    """
    return execute_query(query, (limit,))

def run_backtest():
    signals = fetch_top_signals(limit=20)
    print(f"Evaluating backtest performance for {len(signals)} high-confidence signals...\n")
    
    results = []
    
    for row in signals:
        ticker = row['ticker']
        tx_date = row['transaction_date']
        signal_type = row['signal_type']
        score = row['confidence_score']
        
        start_dt = datetime.strptime(str(tx_date), "%Y-%m-%d") if isinstance(tx_date, str) else tx_date
        end_dt = start_dt + timedelta(days=60)
        
        try:
            df = yf.download(ticker, start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), progress=False)
            if not df.empty and len(df) >= 2:
                entry_price = float(df['Close'].iloc[0])
                exit_price = float(df['Close'].iloc[-1])
                pct_change = round(((exit_price - entry_price) / entry_price) * 100, 2)
                
                results.append({
                    "ticker": ticker,
                    "date": start_dt.strftime("%Y-%m-%d"),
                    "signal": signal_type,
                    "score": score,
                    "return_60d": pct_change
                })
        except Exception as e:
            continue

    print(f"{'TICKER':<8} | {'DATE':<10} | {'SIGNAL':<8} | {'SCORE':<6} | {'60-DAY RETURN'}")
    print("-" * 55)
    for r in results:
        print(f"{r['ticker']:<8} | {r['date']:<10} | {r['signal']:<8} | {r['score']:<6} | {r['return_60d']}%")

if __name__ == "__main__":
    run_backtest()
