"""API routes for email service."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr
import httpx
import os
from typing import Optional
import logging

from email import subscribers, sender

router = APIRouter(prefix="/email", tags=["email"])
logger = logging.getLogger(__name__)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


class SubscribeRequest(BaseModel):
    """Request model for email subscription."""
    email: EmailStr
    crop: str
    acreage: int
    pre_purchased_pct: float = 0.0


class UnsubscribeRequest(BaseModel):
    """Request model for unsubscribe."""
    email: EmailStr


@router.post("/subscribe")
def subscribe(req: SubscribeRequest):
    """Subscribe to weekly email updates."""
    try:
        result = subscribers.add_subscriber(
            email=req.email,
            crop=req.crop,
            acreage=req.acreage,
            pre_purchased_pct=req.pre_purchased_pct
        )
        return result
    except Exception as e:
        logger.error(f"Subscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
def unsubscribe(email: EmailStr = Query(...)):
    """Unsubscribe from emails."""
    try:
        result = subscribers.remove_subscriber(email)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail="Subscriber not found")
        return result
    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-test-digest")
def send_test_digest(email: EmailStr = Query(...)):
    """Manually trigger a test email for debugging."""
    try:
        # Try to get subscriber profile, or use defaults
        sub = subscribers.get_subscriber(email)
        if not sub:
            # Use defaults for testing
            sub = {
                "email": email,
                "crop": "corn",
                "acreage": 500,
                "pre_purchased_pct": 0.0
            }
        
        # Fetch current forecast from API
        with httpx.Client(timeout=10.0) as client:
            forecast_resp = client.get(f"{API_BASE_URL}/forecast")
            forecast_resp.raise_for_status()
            forecast_data = forecast_resp.json()
            
            # Compute exposure
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
        
        # Send test email
        result = sender.send_weekly_digest(sub, forecast_data, exposure_data)
        logger.info(f"Test email sent to {email}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Test email error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-send-all")
def trigger_send_all():
    """Manually trigger send to all subscribers (for testing)."""
    try:
        from email.scheduler import trigger_manual_send
        trigger_manual_send()
        return {"status": "triggered", "message": "Check logs for results"}
    except Exception as e:
        logger.error(f"Trigger send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscribers")
def get_subscribers_list():
    """Get list of all subscribers (for admin/testing)."""
    try:
        active = subscribers.get_active_subscribers()
        return {"count": len(active), "subscribers": active}
    except Exception as e:
        logger.error(f"Get subscribers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
