import re
import io
import requests
import pdfplumber
from db import get_connection

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Stop words to filter out non-ticker uppercase strings in PDFs
STOP_WORDS = {
    "STOCK", "CS", "RSU", "NYSE", "NASDAQ", "LLC", "LP", "INC", "CORP", "CLASS", 
    "OPTION", "CALL", "PUT", "BOND", "PDF", "PTR", "FD", "ST", "SP", "DC", "JT", 
    "F", "P", "S", "ID", "SUB", "L", "R", "E", "W", "A", "B", "C", "D"
}

def extract_tickers_from_pdf_bytes(pdf_bytes):
    """
    Parses a House PTR PDF file to extract official stock ticker symbols.
    Strictly searches for uppercase tickers enclosed in parentheses: e.g., (NVDA), (AAPL).
    """
    valid_tickers = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                # Strict match: 1-5 uppercase letters enclosed in parentheses
                matches = re.findall(r'\(([A-Z]{1,5})\)', text)
                for candidate in matches:
                    if candidate not in STOP_WORDS:
                        valid_tickers.append(candidate)
                        
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        
    return list(set(valid_tickers))

def process_pending_house_pdfs(batch_size=100):
    conn = get_connection()
    cur = conn.cursor()
    
    # Query records with unresolved DocID placeholders
    cur.execute("""
        SELECT disclosure_id, ticker, transaction_date 
        FROM disclosures 
        WHERE ticker LIKE %s 
        LIMIT %s;
    """, ('PTR_%', batch_size))
    
    pending_records = cur.fetchall()
    print(f"Found {len(pending_records)} pending House PDF records to scrape...")
    
    updated_count = 0
    resolved_tickers = []

    for disc_id, ptr_ticker, tx_date in pending_records:
        doc_id = ptr_ticker.replace("PTR_", "")
        year = str(tx_date)[:4] if tx_date else "2026"
        pdf_url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
        
        try:
            res = requests.get(pdf_url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                tickers = extract_tickers_from_pdf_bytes(res.content)
                if tickers:
                    primary_ticker = tickers[0]
                    cur.execute("""
                        UPDATE disclosures 
                        SET ticker = %s 
                        WHERE disclosure_id = %s;
                    """, (primary_ticker, disc_id))
                    updated_count += 1
                    resolved_tickers.append((doc_id, primary_ticker))
                    print(f"DocID {doc_id} -> Resolved Ticker: {primary_ticker}")
                else:
                    # Remove entry if PDF represents non-stock asset (e.g. municipal bonds/cash)
                    cur.execute("DELETE FROM disclosures WHERE disclosure_id = %s;", (disc_id,))
            else:
                cur.execute("DELETE FROM disclosures WHERE disclosure_id = %s;", (disc_id,))
        except Exception as e:
            print(f"Skipping DocID {doc_id}: {e}")
            continue

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nSuccessfully processed {len(pending_records)} filings! Updated {updated_count} valid stock tickers in PostgreSQL.")

if __name__ == "__main__":
    process_pending_house_pdfs(batch_size=100)
