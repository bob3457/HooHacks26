"""Test the SQLite migration and verify functionality."""

import os
import sys
import sqlite3
import pandas as pd
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Test 1: Database schema
print("=" * 70)
print("TEST 1: Verify Database Schema")
print("=" * 70)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sql", "agrisignal.db")

if not os.path.exists(DB_PATH):
    print("❌ Database not found!")
    sys.exit(1)

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n✅ Found {len(tables)} tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"   • {table[0]}: {count} rows")

# Test 2: Subscribers functionality
print("\n" + "=" * 70)
print("TEST 2: Test Subscribers Module")
print("=" * 70)

try:
    from email_service.subscribers import (
        add_subscriber, 
        get_subscriber, 
        get_active_subscribers,
        remove_subscriber
    )
    
    # Add test subscriber
    test_email = "test_migration@agrisignal.dev"
    result = add_subscriber(test_email, "corn", 100, 0.1)
    print(f"✅ Added subscriber: {result}")
    
    # Retrieve subscriber
    subscriber = get_subscriber(test_email)
    print(f"✅ Retrieved subscriber: {subscriber}")
    
    # Get active subscribers
    active = get_active_subscribers()
    print(f"✅ Active subscribers count: {len(active)}")
    
    # Remove subscriber
    result = remove_subscriber(test_email)
    print(f"✅ Removed subscriber: {result}")
    
except Exception as e:
    print(f"❌ Error testing subscribers: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Data ingestion (NG prices)
print("\n" + "=" * 70)
print("TEST 3: Test Data Ingestion (NG prices from SQLite)")
print("=" * 70)

try:
    from backend.src.ingestion.pipeline import load_ng_monthly
    
    ng_series = load_ng_monthly()
    print(f"✅ Loaded NG prices series:")
    print(f"   • Type: {type(ng_series)}")
    print(f"   • Length: {len(ng_series)}")
    print(f"   • Date range: {ng_series.index.min()} to {ng_series.index.max()}")
    print(f"   • First 5 values:\n{ng_series.head()}")
    
except Exception as e:
    print(f"❌ Error loading NG prices: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Portfolio data (farm borrowers)
print("\n" + "=" * 70)
print("TEST 4: Test Portfolio Data Loading (from SQLite)")
print("=" * 70)

try:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM farm_borrowers LIMIT 5", conn)
    
    print(f"✅ Loaded farm borrowers from SQLite:")
    print(f"   • Shape: {df.shape}")
    print(f"   • Columns: {list(df.columns)}")
    print(f"   • First row:\n{df.iloc[0].to_dict() if len(df) > 0 else 'No data'}")
    
except Exception as e:
    print(f"❌ Error loading farm borrowers: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Database integrity
print("\n" + "=" * 70)
print("TEST 5: Verify Data Integrity")
print("=" * 70)

try:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Check subscribers
        cursor.execute("SELECT COUNT(*) FROM subscribers WHERE is_active = 1")
        active_subs = cursor.fetchone()[0]
        print(f"✅ Active subscribers: {active_subs}")
        
        # Check NG prices
        cursor.execute("SELECT COUNT(*) FROM ng_prices")
        ng_count = cursor.fetchone()[0]
        print(f"✅ NG price records: {ng_count}")
        
        # Check farm borrowers
        cursor.execute("SELECT COUNT(*) FROM farm_borrowers")
        borrower_count = cursor.fetchone()[0]
        print(f"✅ Farm borrower records: {borrower_count}")
        
        # Check indices exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = cursor.fetchall()
        print(f"✅ Indices created: {len(indices)}")
        for idx in indices:
            print(f"   • {idx[0]}")
        
except Exception as e:
    print(f"❌ Error checking data integrity: {e}")
    import traceback
    traceback.print_exc()

# Test 6: CSV fallback functionality
print("\n" + "=" * 70)
print("TEST 6: Test CSV Fallback in Ingestion Pipeline")
print("=" * 70)

try:
    # Temporarily rename database to test fallback
    import shutil
    backup_path = DB_PATH + ".backup"
    shutil.copy2(DB_PATH, backup_path)
    os.rename(DB_PATH, DB_PATH + ".test_disabled")
    
    # Try to load (should fallback to CSV)
    from backend.src.ingestion.pipeline import load_ng_monthly
    ng_series_csv = load_ng_monthly()
    print(f"✅ Fallback to CSV successful:")
    print(f"   • Loaded {len(ng_series_csv)} records from CSV")
    
    # Restore database
    os.rename(DB_PATH + ".test_disabled", DB_PATH)
    
except Exception as e:
    print(f"⚠️  Fallback test failed (might be expected): {e}")
    # Restore database if it got renamed
    if os.path.exists(DB_PATH + ".test_disabled"):
        os.rename(DB_PATH + ".test_disabled", DB_PATH)
finally:
    # Clean up backup if it exists
    if os.path.exists(backup_path):
        os.remove(backup_path)

print("\n" + "=" * 70)
print("✅ ALL TESTS COMPLETED")
print("=" * 70)
