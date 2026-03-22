"""Migrate CSV data to SQLite."""

import os
import sys
import pandas as pd
import sqlite3
from pathlib import Path

# Add parent dir to path so we can import db_schema
sys.path.insert(0, os.path.dirname(__file__))

from db_schema import get_db_connection, init_db

ROOT = os.path.join(os.path.dirname(__file__), "..")
CSV_SUBSCRIBERS = os.path.join(ROOT, "data", "csv", "subscribers.csv")
CSV_FARM_BORROWERS = os.path.join(ROOT, "data", "csv", "agriculture-and-farming-dataset", "synthetic_farm_borrowers.csv")
CSV_NG_MONTHLY = os.path.join(ROOT, "data", "csv", "natural-gas-prices", "monthly.csv")


def migrate_all():
    """Run all migrations."""
    print("🔄 Starting SQLite migration...\n")
    
    # 1. Initialize schema
    print("1️⃣ Initializing database schema...")
    init_db()
    
    # 2. Migrate subscribers
    if os.path.exists(CSV_SUBSCRIBERS):
        print(f"\n2️⃣ Migrating subscribers from {CSV_SUBSCRIBERS}...")
        migrate_subscribers()
    else:
        print(f"\n⚠️  Subscribers CSV not found: {CSV_SUBSCRIBERS}")
    
    # 3. Migrate farm borrowers
    if os.path.exists(CSV_FARM_BORROWERS):
        print(f"\n3️⃣ Migrating farm borrowers from {CSV_FARM_BORROWERS}...")
        migrate_farm_borrowers()
    else:
        print(f"\n⚠️  Farm borrowers CSV not found: {CSV_FARM_BORROWERS}")
    
    # 4. Migrate NG prices
    if os.path.exists(CSV_NG_MONTHLY):
        print(f"\n4️⃣ Migrating natural gas prices from {CSV_NG_MONTHLY}...")
        migrate_ng_prices()
    else:
        print(f"\n⚠️  NG prices CSV not found: {CSV_NG_MONTHLY}")
    
    print("\n✅ Migration complete!")


def migrate_subscribers():
    """Load subscribers CSV into SQLite."""
    try:
        df = pd.read_csv(CSV_SUBSCRIBERS)
        print(f"   • Read {len(df)} rows from CSV")
        
        # Ensure is_active is integer (0/1)
        if "is_active" in df.columns:
            df["is_active"] = df["is_active"].astype(int)
        
        with get_db_connection() as conn:
            df.to_sql("subscribers", conn, if_exists="replace", index=False)
            conn.commit()
        
        print(f"   ✅ Inserted {len(df)} subscribers into SQLite")
    except Exception as e:
        print(f"   ❌ Error: {e}")


def migrate_farm_borrowers():
    """Load farm borrowers CSV into SQLite."""
    try:
        df = pd.read_csv(CSV_FARM_BORROWERS)
        print(f"   • Read {len(df)} rows from CSV")
        
        # Rename columns to match schema and lowercase
        col_map = {
            "Borrower_ID": "borrower_id",
            "Crop_Type": "crop_type",
            "Acreage": "acreage",
            "Irrigation_Type": "irrigation_type",
            "Soil_Type": "soil_type",
            "Season": "season",
            "Loan_Amount": "loan_amount",
            "Months_Since_Delinquency": "months_since_delinquency",
            "Stress_Probability": "stress_probability",
            "Requires_Intervention": "requires_intervention"
        }
        df = df.rename(columns=col_map)
        
        with get_db_connection() as conn:
            df.to_sql("farm_borrowers", conn, if_exists="replace", index=False)
            conn.commit()
        
        print(f"   ✅ Inserted {len(df)} farm borrowers into SQLite")
    except Exception as e:
        print(f"   ❌ Error: {e}")


def migrate_ng_prices():
    """Load natural gas prices CSV into SQLite."""
    try:
        df = pd.read_csv(CSV_NG_MONTHLY)
        print(f"   • Read {len(df)} rows from CSV")
        
        # Normalize column names
        df.columns = ["date", "price"]
        df["date"] = df["date"].astype(str)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        
        with get_db_connection() as conn:
            df.to_sql("ng_prices", conn, if_exists="replace", index=False)
            conn.commit()
        
        print(f"   ✅ Inserted {len(df)} NG price records into SQLite")
    except Exception as e:
        print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    migrate_all()
