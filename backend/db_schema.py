"""SQLite database schema and connection management."""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sql", "agrisignal.db")


@contextmanager
def get_db_connection():
    """Manage database connection lifecycle with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create schema if needed."""
    with get_db_connection() as conn:
        conn.executescript("""
            -- Subscribers table
            CREATE TABLE IF NOT EXISTS subscribers (
                email TEXT PRIMARY KEY,
                crop TEXT NOT NULL,
                acreage INTEGER NOT NULL,
                pre_purchased_pct REAL DEFAULT 0.0,
                subscribed_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            );

            -- Natural gas prices (monthly)
            CREATE TABLE IF NOT EXISTS ng_prices (
                date TEXT PRIMARY KEY,
                price REAL NOT NULL
            );

            -- Fertilizer prices (monthly)
            CREATE TABLE IF NOT EXISTS fertilizer_prices (
                date TEXT PRIMARY KEY,
                urea REAL,
                dap REAL
            );

            -- Storage data (monthly)
            CREATE TABLE IF NOT EXISTS ng_storage (
                date TEXT PRIMARY KEY,
                storage_mmcf REAL NOT NULL
            );

            -- Farm borrowers (synthetic data for ML)
            CREATE TABLE IF NOT EXISTS farm_borrowers (
                borrower_id TEXT PRIMARY KEY,
                crop_type TEXT NOT NULL,
                acreage REAL NOT NULL,
                irrigation_type TEXT,
                soil_type TEXT,
                season TEXT,
                loan_amount REAL,
                months_since_delinquency INTEGER,
                stress_probability REAL,
                requires_intervention INTEGER
            );

            -- Create indices for common queries
            CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(is_active);
            CREATE INDEX IF NOT EXISTS idx_ng_prices_date ON ng_prices(date);
            CREATE INDEX IF NOT EXISTS idx_fert_prices_date ON fertilizer_prices(date);
        """)
        conn.commit()
        print(f"✅ Database schema initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
