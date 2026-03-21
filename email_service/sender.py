"""Generate and send weekly email digests."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
from pathlib import Path
import os
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

TEMPLATE_FILE = Path(__file__).parent / "templates" / "weekly_digest.html"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501")

# Test mode: log emails instead of sending
TEST_MODE = os.getenv("EMAIL_TEST_MODE", "false").lower() == "true"


def send_email(to_email: str, subject: str, html_content: str) -> Dict[str, str]:
    """Send email via SMTP."""
    if TEST_MODE or SENDER_EMAIL == "noreply@agrisignal.local":
        # Log to console in test mode
        print(f"\n{'='*60}")
        print(f"[TEST EMAIL]")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"{'='*60}\n")
        return {"status": "sent", "email": to_email, "mode": "test"}
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email

        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        return {"status": "sent", "email": to_email}
    except Exception as e:
        return {"status": "error", "email": to_email, "error": str(e)}


def generate_digest_html(subscriber: Dict[str, Any], forecast_data: Dict[str, Any], 
                        exposure_data: Dict[str, Any]) -> str:
    """Render Jinja2 template with subscriber + forecast data."""
    with open(TEMPLATE_FILE, "r") as f:
        template = Template(f.read())
    
    unsubscribe_token = subscriber['email']
    
    # Format cost increase
    total_cost = exposure_data.get('total_cost_increase', 0)
    if total_cost > 0:
        cost_summary = f"+${total_cost:.0f}"
    elif total_cost < 0:
        cost_summary = f"-${abs(total_cost):.0f}"
    else:
        cost_summary = "$0"
    
    return template.render(
        email=subscriber["email"],
        crop=subscriber["crop"],
        acreage=int(subscriber["acreage"]),
        pre_purchased_pct=int(subscriber.get("pre_purchased_pct", 0) * 100),
        signal=forecast_data.get("signal", "NEUTRAL"),
        confidence=int(forecast_data.get("confidence", 0.5) * 100),
        rationale=forecast_data.get("rationale", ""),
        key_driver=forecast_data.get("key_driver", ""),
        ng_spot=f"{forecast_data.get('ng_spot_current', 0):.2f}",
        ng_change_30d_pct=forecast_data.get("ng_change_30d_pct", 0),
        urea_current=f"{forecast_data.get('urea_current', 0):.0f}",
        urea_forecast_t2=f"{forecast_data.get('urea_forecast_t2', 0):.0f}",
        pct_change_t2=forecast_data.get("pct_change_t2", 0),
        cost_increase_summary=cost_summary,
        p10_cost_increase=exposure_data.get("p10_cost_increase", 0),
        p90_cost_increase=exposure_data.get("p90_cost_increase", 0),
        dashboard_url=DASHBOARD_URL,
        unsubscribe_url=f"{DASHBOARD_URL}/unsubscribe?email={unsubscribe_token}",
    )


def send_weekly_digest(subscriber: Dict[str, Any], forecast_data: Dict[str, Any], 
                       exposure_data: Dict[str, Any]) -> Dict[str, str]:
    """Generate and send weekly digest to one subscriber."""
    try:
        html_content = generate_digest_html(subscriber, forecast_data, exposure_data)
        subject = f"🌾 AgriSignal Weekly: {forecast_data.get('signal', 'NEUTRAL')}"
        return send_email(subscriber["email"], subject, html_content)
    except Exception as e:
        return {"status": "error", "email": subscriber.get("email", "unknown"), "error": str(e)}
