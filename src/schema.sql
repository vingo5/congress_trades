CREATE TABLE IF NOT EXISTS politicians (
    politician_id SERIAL PRIMARY KEY,
    name VARCHAR(250) NOT NULL,
    chamber VARCHAR(10) CHECK (chamber IN ('House', 'Senate')),
    party VARCHAR(50),
    state VARCHAR(2)
);

CREATE TABLE IF NOT EXISTS disclosures (
    disclosure_id SERIAL PRIMARY KEY,
    politician_id INT REFERENCES politicians(politician_id),
    ticker VARCHAR(10) NOT NULL,
    transaction_date DATE NOT NULL,
    disclosure_date DATE NOT NULL,
    transaction_type VARCHAR(10) CHECK (transaction_type IN ('BUY', 'SELL')),
    amount_range VARCHAR(50),
    estimated_value_usd NUMERIC(12, 2)
);

CREATE TABLE IF NOT EXISTS trade_signals (
    signal_id SERIAL PRIMARY KEY,
    disclosure_id INT REFERENCES disclosures(disclosure_id),
    confidence_score NUMERIC(5, 2),
    signal_type VARCHAR(10) CHECK (signal_type IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
