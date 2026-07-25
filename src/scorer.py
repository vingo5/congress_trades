from datetime import datetime
from db import get_connection

def parse_amount(amount_str):
    """Estimate numeric USD value from congressional bracket string."""
    if not amount_str:
        return 10000
    if "1,001" in amount_str or "1000" in amount_str:
        return 8000
    elif "15,001" in amount_str:
        return 32500
    elif "50,001" in amount_str:
        return 75000
    elif "100,001" in amount_str:
        return 175000
    elif "250,001" in amount_str:
        return 375000
    elif "500,001" in amount_str:
        return 750000
    elif "1,000,001" in amount_str:
        return 3000000
    elif "5,000,001" in amount_str:
        return 15000000
    return 15000

def compute_signal(tx_type, tx_date, disc_date, amount_range):
    """Calculate confidence score (0-100) and signal direction based on trade lag & volume."""
    lag_days = (disc_date - tx_date).days if disc_date and tx_date else 30
    lag_days = max(0, lag_days)
    
    # Base score decays as reporting lag increases (decay factor)
    recency_factor = max(0.2, 1.0 - (lag_days / 45.0))
    
    usd_val = parse_amount(amount_range)
    # Scale score logarithmically with dollar range
    val_weight = min(1.0, usd_val / 500000.0)
    
    base_score = (50 * recency_factor) + (50 * val_weight)
    confidence = round(min(100.0, max(1.0, base_score)), 2)
    
    if tx_type == "BUY":
        signal_type = "BULLISH"
    elif tx_type == "SELL":
        signal_type = "BEARISH"
    else:
        signal_type = "NEUTRAL"
        
    return confidence, signal_type

def generate_signals():
    conn = get_connection()
    cur = conn.cursor()
    
    # Fetch all disclosures without a generated signal
    cur.execute("""
        SELECT d.disclosure_id, d.transaction_type, d.transaction_date, d.disclosure_date, d.amount_range
        FROM disclosures d
        LEFT JOIN trade_signals s ON d.disclosure_id = s.disclosure_id
        WHERE s.signal_id IS NULL;
    """)
    unscored = cur.fetchall()
    
    print(f"Generating signals for {len(unscored)} unscored disclosures...")
    
    inserted = 0
    for row in unscored:
        disc_id, tx_type, tx_date, disc_date, amount_range = row
        confidence, signal_type = compute_signal(tx_type, tx_date, disc_date, amount_range)
        
        cur.execute(
            """
            INSERT INTO trade_signals (disclosure_id, confidence_score, signal_type)
            VALUES (%s, %s, %s);
            """,
            (disc_id, confidence, signal_type)
        )
        inserted += 1
        
    conn.commit()
    cur.close()
    conn.close()
    print(f"Scoring complete! Inserted {inserted} trade signals into PostgreSQL.")

if __name__ == "__main__":
    generate_signals()
