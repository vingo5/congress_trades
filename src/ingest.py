import json
import os
import requests
import re
from db import get_connection

SENATE_URL = "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json"
HOUSE_LOCAL_PATH = "data/house.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_date(date_str):
    if not date_str or date_str in ["--", "N/A"]:
        return None
    date_str = str(date_str).strip()
    match_iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", date_str)
    if match_iso:
        y, m, d = match_iso.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    match_us = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", date_str)
    if match_us:
        m, d, y = match_us.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return None

def fetch_senate_data():
    try:
        response = requests.get(SENATE_URL, headers=HEADERS, timeout=20)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching Senate data: {e}")
    return []

def fetch_house_data():
    if os.path.exists(HOUSE_LOCAL_PATH):
        with open(HOUSE_LOCAL_PATH, "r") as f:
            return json.load(f)
    return []

def upsert_politician(cur, name, chamber="House"):
    cur.execute(
        """
        INSERT INTO politicians (name, chamber)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING;
        """,
        (name, chamber)
    )
    cur.execute("SELECT politician_id FROM politicians WHERE name = %s LIMIT 1;", (name,))
    row = cur.fetchone()
    return row[0] if row else None

def ingest_trades():
    print("Fetching House disclosures from local dataset...")
    house_trades = fetch_house_data()
    print(f"Loaded {len(house_trades)} House records.")

    print("Fetching Senate disclosures from live public endpoint...")
    senate_trades = fetch_senate_data()
    print(f"Fetched {len(senate_trades)} Senate records.")

    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("TRUNCATE TABLE disclosures CASCADE;")
    cur.execute("TRUNCATE TABLE politicians RESTART IDENTITY CASCADE;")
    
    records_inserted = 0
    all_dataset = [(t, 'House') for t in house_trades] + [(t, 'Senate') for t in senate_trades]

    for trade, chamber in all_dataset:
        if chamber == 'House':
            name = str(trade.get("representative", "")).strip()
            raw_tx_date = trade.get("transaction_date")
            raw_disc_date = trade.get("disclosure_date")
        else:
            name = str(trade.get("senator", "")).strip()
            raw_tx_date = trade.get("transaction_date")
            raw_disc_date = trade.get("disclosure_date") or raw_tx_date

        ticker = str(trade.get("ticker", "")).strip().upper()
        type_raw = str(trade.get("type", "")).upper()

        if "PURCHASE" in type_raw or "BUY" in type_raw:
            tx_type = "BUY"
        elif "SALE" in type_raw or "SELL" in type_raw:
            tx_type = "SELL"
        else:
            tx_type = None

        tx_date = parse_date(raw_tx_date)
        disc_date = parse_date(raw_disc_date) or tx_date
        amount_range = trade.get("amount")

        if not name or not ticker or ticker in ["--", "NONE", "N/A"] or len(ticker) > 10:
            continue
        if not tx_date or not tx_type:
            continue

        try:
            politician_id = upsert_politician(cur, name, chamber)
            cur.execute(
                """
                INSERT INTO disclosures (politician_id, ticker, transaction_date, disclosure_date, transaction_type, amount_range)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (politician_id, ticker, tx_date, disc_date, tx_type, amount_range)
            )
            records_inserted += 1
        except Exception:
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()
    print(f"Ingestion complete! Successfully inserted {records_inserted} disclosures into PostgreSQL.")

if __name__ == "__main__":
    ingest_trades()
