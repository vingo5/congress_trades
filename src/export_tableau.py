import pandas as pd
from db import get_connection

def export_for_tableau():
    conn = get_connection()
    
    query = """
        SELECT 
            d.disclosure_id,
            p.name AS politician_name,
            p.chamber,
            d.ticker,
            d.transaction_type,
            d.transaction_date,
            d.disclosure_date,
            d.reporting_lag_days,
            d.amount_range,
            COALESCE(s.confidence_score, 50.0) AS signal_confidence,
            b.horizon_days,
            b.stock_return,
            b.spy_return,
            b.alpha
        FROM disclosures d
        JOIN politicians p ON d.politician_id = p.politician_id
        LEFT JOIN trade_signals s ON d.disclosure_id = s.disclosure_id
        LEFT JOIN backtest_results b ON d.disclosure_id = b.disclosure_id
        WHERE d.ticker NOT LIKE 'PTR_%'
        ORDER BY d.disclosure_date DESC;
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    df['horizon_days'] = df['horizon_days'].fillna(0).astype(int)
    df['reporting_lag_days'] = df['reporting_lag_days'].fillna(0).astype(int)
    
    # Export to a completely fresh filename to bypass file locking/caching issues
    output_path = "tableau_congress_trades_v2.csv"
    df.to_csv(output_path, index=False)
    print(f"SUCCESS: Exported {len(df)} records to fresh file: {output_path}!")

if __name__ == "__main__":
    export_for_tableau()
