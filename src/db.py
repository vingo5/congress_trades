import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "congress_trades")
DB_USER = os.getenv("DB_USER", "vincentngo")
DB_PASS = os.getenv("DB_PASS", "")

def get_connection():
    """Establish and return a connection to PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def execute_query(query, params=None):
    """Execute a query and return results as dictionaries for SELECT queries."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            conn.commit()

if __name__ == "__main__":
    # Sanity check connection
    try:
        result = execute_query("SELECT 1 AS test;")
        print("Database connection test successful:", result)
    except Exception as e:
        print("Database connection failed:", e)
