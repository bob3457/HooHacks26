#!/usr/bin/env python3
"""
Test script for the email service.

Run this to test the entire email workflow without sending real emails.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from email import subscribers, sender
from dotenv import load_dotenv
import os

load_dotenv()

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_subscriber_management():
    """Test adding and managing subscribers."""
    print_section("TEST 1: Subscriber Management")
    
    # Add a few test subscribers
    test_emails = [
        ("test1@example.com", "corn", 500, 0.0),
        ("test2@example.com", "wheat", 300, 0.2),
        ("test3@example.com", "soybeans", 200, 0.15),
    ]
    
    print("Adding test subscribers...")
    for email, crop, acreage, pre_pct in test_emails:
        result = subscribers.add_subscriber(email, crop, acreage, pre_pct)
        print(f"  ✓ {email}: {result['status']}")
    
    print("\nFetching active subscribers...")
    active = subscribers.get_active_subscribers()
    print(f"  Found {len(active)} active subscribers")
    for sub in active:
        print(f"    - {sub['email']:25} | {sub['crop']:10} | {sub['acreage']} acres")
    
    print("\nTesting unsubscribe...")
    result = subscribers.remove_subscriber("test2@example.com")
    print(f"  ✓ {result}")
    
    active = subscribers.get_active_subscribers()
    print(f"  Active subscribers now: {len(active)}")


def create_mock_forecast():
    """Create mock forecast data for testing."""
    return {
        "signal": "BUY_NOW",
        "confidence": 0.74,
        "rationale": "Natural gas has spiked 18% in the last 30 days. Historical data shows urea follows with a 4-8 week lag. With spring planting approaching, prices are likely to rise significantly.",
        "key_driver": "Henry Hub natural gas spot price is up $0.87 (+18%) over the past month. This typically triggers a 14-22% increase in urea prices within 4-8 weeks.",
        "ng_spot_current": 3.84,
        "ng_change_30d_pct": 0.18,
        "urea_current": 420.0,
        "urea_forecast_t2": 480.0,
        "pct_change_t2": 0.143,
    }


def create_mock_exposure():
    """Create mock exposure data for testing."""
    return {
        "crop": "corn",
        "acreage": 500,
        "exposed_acreage": 500.0,
        "current_cost_per_acre": 45.50,
        "forecast_cost_per_acre": 51.90,
        "cost_increase_per_acre": 6.40,
        "total_cost_increase": 3200.0,
        "p10_cost_increase": 1800.0,
        "p50_cost_increase": 3200.0,
        "p90_cost_increase": 4600.0,
        "prob_any_increase": 0.78,
        "pct_increase": 0.1407,
    }


def test_email_generation():
    """Test email HTML generation."""
    print_section("TEST 2: Email HTML Generation")
    
    subscriber = {
        "email": "farmer@example.com",
        "crop": "corn",
        "acreage": 500,
        "pre_purchased_pct": 0.0,
    }
    
    forecast = create_mock_forecast()
    exposure = create_mock_exposure()
    
    print("Generating email HTML...")
    html = sender.generate_digest_html(subscriber, forecast, exposure)
    
    print(f"✓ HTML generated ({len(html)} characters)")
    print("\n[First 500 characters of HTML preview]")
    print(html[:500] + "...\n")
    
    return subscriber, forecast, exposure, html


def test_email_send():
    """Test sending an email (in test mode)."""
    print_section("TEST 3: Email Send (Test Mode)")
    
    subscriber = {
        "email": "test1@example.com",
        "crop": "corn",
        "acreage": 500,
        "pre_purchased_pct": 0.0,
    }
    
    forecast = create_mock_forecast()
    exposure = create_mock_exposure()
    
    print(f"Sending test email to {subscriber['email']}...")
    print(f"(EMAIL_TEST_MODE={os.getenv('EMAIL_TEST_MODE', 'false')})\n")
    
    result = sender.send_weekly_digest(subscriber, forecast, exposure)
    print(f"\nResult: {result}")


def test_scheduler_status():
    """Show scheduler status."""
    print_section("TEST 4: Scheduler Status")
    
    from email.scheduler import scheduler
    
    if scheduler.running:
        print("✓ Scheduler is running")
        jobs = scheduler.get_jobs()
        print(f"  Active jobs: {len(jobs)}")
        for job in jobs:
            print(f"    - {job.name}: {job.trigger}")
    else:
        print("✓ Scheduler is not running (start via API startup)")
        print("  To start: uvicorn src.api.main:app --reload")


def save_test_email_to_file(html):
    """Save test email HTML to a file for manual inspection."""
    output_file = PROJECT_ROOT / "test_email_preview.html"
    with open(output_file, "w") as f:
        f.write(html)
    print(f"\n✓ Test email saved to: {output_file}")
    print(f"  Open in browser to preview the email design")


def main():
    """Run all tests."""
    print("\n")
    print("🌾 AgriSignal Email Service - Test Suite")
    print("=" * 70)
    
    try:
        test_subscriber_management()
        subscriber, forecast, exposure, html = test_email_generation()
        test_email_send()
        test_scheduler_status()
        save_test_email_to_file(html)
        
        print_section("✓ All Tests Passed!")
        print("\nNext steps:")
        print("  1. Start the API: uvicorn src.api.main:app --reload")
        print("  2. Test endpoints:")
        print("     - POST /email/subscribe")
        print("     - GET  /email/subscribers")
        print("     - POST /email/send-test-digest?email=test@example.com")
        print("     - POST /email/trigger-send-all")
        print("\n  3. Add email signup to dashboard (dashboard/app.py)")
        print("  4. Connect to real email provider when ready\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
