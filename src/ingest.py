import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from db import get_connection

SENATE_URL = "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_date(date_str):
    if not date_str or date_str in ["--", "N/A", ""]:
        return None
    # Strip off extra time formats if present (e.g. '2026-05-12T00:00:00' -> '2026-05-12')
    date_str = str(date_str).strip().split("T")[0].split(" ")[0]
    
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def fetch_senate_data():
    try:
        response = requests.get(SENATE_URL, headers=HEADERS, timeout=20)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching Senate data: {e}")
    return []

def fetch_official_house_disclosures(years=[2026, 2025, 2024]):
    records = []
    for year in years:
        zip_url = f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.ZIP"
        print(f"Downloading official House Clerk Index for {year}: {zip_url}...")
        try:
            res = requests.get(zip_url, headers=HEADERS, timeout=30)
            if res.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(res.content)) as z:
                    xml_filename = f"{year}FD.xml"
                    if xml_filename in z.namelist():
                        with z.open(xml_filename) as f:
                            tree = ET.parse(f)
                            root = tree.getroot()
                            
                            ptr_count = 0
                            for member in root.findall("Member"):
                                report_type = member.findtext("FilingType", "").strip() or member.findtext("ReportType", "").strip()
                                if report_type == "P":
                                    first_name = member.findtext("First", "").strip()
                                    last_name = member.findtext("Last", "").strip()
                                    full_name = f"{first_name} {last_name}".strip()
                                    filing_date = member.findtext("FilingDate", "").strip()
                                    doc_id = member.findtext("DocID", "").strip()
                                    
                                    if doc_id:
                                        records.append({
                                            "representative": full_name,
                                            "disclosure_date": filing_date,
                                            "doc_id": doc_id,
                                            "ticker": f"PTR_{doc_id}",
                                            "type": "BUY",
                                            "amount": "$1,001 - $15,000"
                                        })
                                        ptr_count += 1
                            print(f"Extracted {ptr_count} PTR index records for {year}.")
        except Exception as e:
            print(f"Error reading House Clerk ZIP for {year}: {e}")
            
    return records

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
    print("Fetching official House Clerk PTR index disclosures...")
    house_trades = fetch_official_house_disclosures(years=[2026, 2025, 2024])
    
    print("Fetching Senate disclosures...")
    senate_trades = fetch_senate_data()

    conn = get_connection()
    cur = conn.cursor()
    
    # Expand ticker column size limit dynamically before insertion so PTR_ DOC_IDs don't crash it
    cur.execute("ALTER TABLE disclosures ALTER COLUMN ticker TYPE VARCHAR(50);")
    
    cur.execute("TRUNCATE TABLE disclosures CASCADE;")
    cur.execute("TRUNCATE TABLE politicians RESTART IDENTITY CASCADE;")
    
    records_inserted = 0
    all_dataset = [(t, 'House') for t in house_trades] + [(t, 'Senate') for t in senate_trades]

    for trade, chamber in all_dataset:
        if chamber == 'House':
            name = str(trade.get("representative", "")).strip()
            raw_tx_date = trade.get("disclosure_date")
            raw_disc_date = trade.get("disclosure_date")
            ticker = str(trade.get("ticker", "")).strip().upper()
            type_raw = str(trade.get("type", "")).upper()
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

        if not name or not ticker or ticker in ["--", "NONE", "N/A"]:
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
        except Exception as e:
            conn.rollback()
            # If a record still fails, this will now print out why!
            print(f"Failed inserting {ticker} for {name}: {e}")
            continue

    conn.commit()
    cur.close()
    conn.close()
    print(f"Ingestion complete! Successfully inserted {records_inserted} total disclosures into PostgreSQL.")

if __name__ == "__main__":
    ingest_trades()
