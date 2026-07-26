from db import execute_query

def top_bullish_tickers(limit=5):
    query = """
        SELECT d.ticker, COUNT(*) as buy_count, ROUND(AVG(s.confidence_score), 2) as avg_confidence
        FROM disclosures d
        JOIN trade_signals s ON d.disclosure_id = s.disclosure_id
        WHERE s.signal_type = 'BULLISH'
        GROUP BY d.ticker
        ORDER BY buy_count DESC, avg_confidence DESC
        LIMIT %s;
    """
    return execute_query(query, (limit,))

def top_active_politicians(limit=5):
    query = """
        SELECT p.name, p.chamber, COUNT(d.disclosure_id) as total_trades
        FROM politicians p
        JOIN disclosures d ON p.politician_id = d.politician_id
        GROUP BY p.name, p.chamber
        ORDER BY total_trades DESC
        LIMIT %s;
    """
    return execute_query(query, (limit,))

if __name__ == "__main__":
    print("=== TOP BULLISH TICKERS BY DISCLOSURE COUNT ===")
    for row in top_bullish_tickers():
        print(f"Ticker: {row['ticker']:<6} | Buy Disclosures: {row['buy_count']:<3} | Avg Confidence: {row['avg_confidence']}")
        
    print("\n=== MOST ACTIVE CONGRESSIONAL TRADERS ===")
    for row in top_active_politicians():
        print(f"Name: {row['name']:<25} | Chamber: {row['chamber']:<6} | Total Trades: {row['total_trades']}")
