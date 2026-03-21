"""Background scheduler for weekly email digests."""

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging
import httpx
import os

from . import subscribers, sender

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def send_all_weekly_digests():
    """Run every Monday at 8 AM — send digest to all active subscribers."""
    active_subs = subscribers.get_active_subscribers()
    logger.info(f"[{datetime.now()}] Sending weekly digests to {len(active_subs)} subscribers...")
    
    if not active_subs:
        logger.info("No active subscribers.")
        return
    
    for sub in active_subs:
        try:
            # Call your existing API endpoints to get forecast & exposure
            with httpx.Client(timeout=10.0) as client:
                # Get current forecast
                forecast_resp = client.get(f"{API_BASE_URL}/forecast")
                forecast_resp.raise_for_status()
                forecast_data = forecast_resp.json()
                
                # Compute exposure for this subscriber's farm
                exposure_resp = client.post(
                    f"{API_BASE_URL}/exposure",
                    json={
                        "crop": sub["crop"],
                        "acreage": int(sub["acreage"]),
                        "pre_purchased_pct": float(sub.get("pre_purchased_pct", 0))
                    }
                )
                exposure_resp.raise_for_status()
                exposure_data = exposure_resp.json()
            
            # Send email
            result = sender.send_weekly_digest(sub, forecast_data, exposure_data)
            logger.info(f"Email to {sub['email']}: {result.get('status', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to send digest to {sub.get('email', 'unknown')}: {e}")


def start_scheduler():
    """Start the background scheduler."""
    if not scheduler.running:
        # Every Monday at 8 AM UTC
        scheduler.add_job(
            send_all_weekly_digests,
            trigger="cron",
            day_of_week="mon",
            hour=8,
            minute=0,
            id="weekly_digest"
        )
        scheduler.start()
        logger.info("Email scheduler started (runs Monday 8:00 AM UTC)")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Email scheduler stopped")


def trigger_manual_send():
    """Manually trigger send for testing."""
    logger.info("Manual trigger: sending digests now...")
    send_all_weekly_digests()
