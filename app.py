import streamlit as st
import pandas as pd
import plotly.express as px
from src.db import get_connection

st.set_page_config(page_title="Congressional Trade Tracker", layout="wide")

st.title("🏛️ Congressional Trade Tracker & Quantitative Signals")
st.markdown("Real-time monitoring and quantitative scoring of U.S. House & Senate financial disclosures.")

@st.cache_data(ttl=300)
def load_analytics_data():
    conn = get_connection()
    
    # Leaderboard by Ticker
    df_tickers = pd.read_sql("""
        SELECT 
            d.ticker,
            COUNT(*) as total_disclosures,
            SUM(CASE WHEN d.transaction_type = 'BUY' THEN 1 ELSE 0 END) as buy_count,
            SUM(CASE WHEN d.transaction_type = 'SELL' THEN 1 ELSE 0 END) as sell_count,
            ROUND(AVG(s.confidence_score)::numeric, 2) as avg_confidence
        FROM disclosures d
        LEFT JOIN trade_signals s ON d.disclosure_id = s.disclosure_id
        WHERE d.ticker NOT LIKE 'PTR_%'
        GROUP BY d.ticker
        HAVING COUNT(*) > 1
        ORDER BY buy_count DESC
        LIMIT 20;
    """, conn)

    # Leaderboard by Politician
    df_politicians = pd.read_sql("""
        SELECT 
            p.name,
            p.chamber,
            COUNT(d.disclosure_id) as total_trades,
            SUM(CASE WHEN d.transaction_type = 'BUY' THEN 1 ELSE 0 END) as buy_trades,
            SUM(CASE WHEN d.transaction_type = 'SELL' THEN 1 ELSE 0 END) as sell_trades
        FROM politicians p
        JOIN disclosures d ON p.politician_id = d.politician_id
        WHERE d.ticker NOT LIKE 'PTR_%'
        GROUP BY p.name, p.chamber
        ORDER BY total_trades DESC
        LIMIT 15;
    """, conn)
    
    conn.close()
    return df_tickers, df_politicians

df_tickers, df_politicians = load_analytics_data()

# Summary Metrics Row
col1, col2, col3 = st.columns(3)
col1.metric("Top Bullish Ticker", df_tickers.iloc[0]['ticker'] if not df_tickers.empty else "N/A")
col2.metric("Most Active Politician", df_politicians.iloc[0]['name'] if not df_politicians.empty else "N/A")
col3.metric("Tracked Unique Stocks", len(df_tickers))

st.markdown("---")

# Visual Layout
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🔥 Top Most Traded Stocks")
    fig_tickers = px.bar(
        df_tickers, 
        x="ticker", 
        y=["buy_count", "sell_count"], 
        title="Buy vs Sell Disclosures by Ticker",
        barmode="group",
        labels={"value": "Disclosure Count", "ticker": "Stock Symbol"}
    )
    st.plotly_chart(fig_tickers, use_container_width=True)

with col_right:
    st.subheader("👨‍💼 Most Active Congressional Traders")
    fig_politicians = px.bar(
        df_politicians, 
        x="total_trades", 
        y="name", 
        color="chamber",
        orientation="h",
        title="Total Filings by Representative / Senator",
        labels={"total_trades": "Total Disclosures", "name": "Politician"}
    )
    st.plotly_chart(fig_politicians, use_container_width=True)

st.subheader("📋 Raw Stock Signal Breakdown")
st.dataframe(df_tickers, use_container_width=True)
