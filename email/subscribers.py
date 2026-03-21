"""Manage subscriber list in CSV."""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

SUBSCRIBERS_FILE = Path("data/subscribers.csv")


def init_subscribers_csv():
    """Create CSV if it doesn't exist."""
    if not SUBSCRIBERS_FILE.exists():
        SUBSCRIBERS_FILE.parent.mkdir(exist_ok=True)
        df = pd.DataFrame(columns=[
            "email", "crop", "acreage", "pre_purchased_pct", 
            "subscribed_at", "is_active"
        ])
        df.to_csv(SUBSCRIBERS_FILE, index=False)


def add_subscriber(email: str, crop: str, acreage: int, pre_purchased_pct: float = 0.0) -> Dict[str, str]:
    """Add or reactivate a subscriber."""
    df = pd.read_csv(SUBSCRIBERS_FILE)
    
    # Check if already subscribed (reactivate if unsubscribed)
    existing = df[df["email"] == email]
    if not existing.empty:
        df.loc[df["email"] == email, "is_active"] = True
        df.to_csv(SUBSCRIBERS_FILE, index=False)
        return {"status": "reactivated", "email": email}
    
    # Add new subscriber
    new_subscriber = pd.DataFrame([{
        "email": email,
        "crop": crop,
        "acreage": int(acreage),
        "pre_purchased_pct": float(pre_purchased_pct),
        "subscribed_at": datetime.now().isoformat(),
        "is_active": True
    }])
    df = pd.concat([df, new_subscriber], ignore_index=True)
    df.to_csv(SUBSCRIBERS_FILE, index=False)
    return {"status": "subscribed", "email": email}


def remove_subscriber(email: str) -> Dict[str, str]:
    """Soft delete — mark as inactive."""
    df = pd.read_csv(SUBSCRIBERS_FILE)
    
    if email not in df["email"].values:
        return {"status": "not_found", "email": email}
    
    df.loc[df["email"] == email, "is_active"] = False
    df.to_csv(SUBSCRIBERS_FILE, index=False)
    return {"status": "unsubscribed", "email": email}


def get_active_subscribers() -> List[Dict[str, Any]]:
    """Get all active subscribers for weekly send."""
    df = pd.read_csv(SUBSCRIBERS_FILE)
    active = df[df["is_active"] == True]
    return active.to_dict("records")


def get_subscriber(email: str) -> Dict[str, Any]:
    """Get a single subscriber by email."""
    df = pd.read_csv(SUBSCRIBERS_FILE)
    result = df[df["email"] == email]
    if result.empty:
        return None
    return result.iloc[0].to_dict()


# Initialize on import
init_subscribers_csv()
