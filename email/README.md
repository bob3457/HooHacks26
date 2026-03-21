# AgriSignal Email Service

Weekly email digest delivery system for AgriSignal farmers.

## Architecture

```
email/
├── __init__.py
├── subscribers.py      # CSV-based subscriber management
├── sender.py          # Email generation & sending
├── scheduler.py       # Background scheduler (Monday 8 AM UTC)
└── templates/
    └── weekly_digest.html  # Jinja2 email template
```

## Features

- **CSV-based storage** — no database required
- **Test mode** — emails logged to console by default
- **Weekly scheduler** — automatic sends Monday 8 AM UTC
- **Personalizable** — each farmer sees their own cost estimates
- **Responsive design** — HTML email template

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Test the email service
```bash
python scripts/test_email_service.py
```

This will:
- Add test subscribers to `data/subscribers.csv`
- Generate sample email HTML
- Show what an email would look like in test mode
- Save preview to `test_email_preview.html`

### 3. Start the API (with scheduler)
```bash
uvicorn src.api.main:app --reload --port 8000
```

The scheduler will automatically start and run weekly sends.

## API Endpoints

### Subscribe
```bash
curl -X POST http://localhost:8000/email/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "email": "farmer@example.com",
    "crop": "corn",
    "acreage": 500,
    "pre_purchased_pct": 0.0
  }'
```

### Unsubscribe
```bash
curl -X POST http://localhost:8000/email/unsubscribe?email=farmer@example.com
```

### Get all subscribers
```bash
curl http://localhost:8000/email/subscribers
```

### Send test digest
```bash
curl -X POST http://localhost:8000/email/send-test-digest?email=farmer@example.com
```

### Trigger send to all subscribers
```bash
curl -X POST http://localhost:8000/email/trigger-send-all
```

## Configuration

Set in `.env`:

```
# Email settings
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
DASHBOARD_URL=http://localhost:8501
API_BASE_URL=http://localhost:8000

# Test mode (default: true)
# When true, emails are logged to console instead of sent
EMAIL_TEST_MODE=true
```

## How It Works

### Subscriber Flow
1. Farmer signs up via dashboard or API
2. Email + farm profile stored in `data/subscribers.csv`
3. Every Monday 8 AM UTC, scheduler wakes up
4. For each subscriber:
   - Fetches current forecast from `/forecast` endpoint
   - Computes farm-specific exposure via `/exposure` endpoint
   - Renders HTML template with personalized data
   - Sends email (or logs in test mode)

### Email Template
The template is in `email/templates/weekly_digest.html` and uses Jinja2 variables:
- `crop`, `acreage`, `pre_purchased_pct` — farm profile
- `signal`, `confidence`, `rationale` — forecast signal
- `urea_current`, `urea_forecast_t2` — prices
- `cost_increase_summary`, `p10/p90_cost_increase` — cost impact
- `dashboard_url` — link to full analysis

## Testing Without Real Emails

By default, `EMAIL_TEST_MODE=true` is set in `.env.example`. This means:

- Emails are printed to the console, not sent
- No SMTP credentials needed
- Perfect for development and hackathon

To test, run:
```bash
python scripts/test_email_service.py
```

## Switching to Real Email

When ready for production, you'll need:

### Option 1: Gmail (easiest for hackathon)
1. Enable "Less secure apps" or use "App Passwords"
2. Set in `.env`:
   ```
   SENDER_EMAIL=your-account@gmail.com
   SENDER_PASSWORD=your-app-password
   EMAIL_TEST_MODE=false
   ```

### Option 2: SendGrid
```python
# Modify sender.py to use sendgrid library
import sendgrid
from sendgrid.helpers.mail import Mail
```

### Option 3: AWS SES
```python
# Use boto3 to send via SES
import boto3
```

## Subscriber CSV Format

File: `data/subscribers.csv`

```
email,crop,acreage,pre_purchased_pct,subscribed_at,is_active
farmer1@example.com,corn,500,0.0,2024-03-21T12:34:56,True
farmer2@example.com,wheat,300,0.2,2024-03-21T12:35:10,True
```

## Scheduler Details

- **Trigger**: Cron job, Monday 8:00 AM UTC
- **Start**: Automatically when FastAPI app starts
- **Stop**: Gracefully on app shutdown
- **Manual trigger**: `POST /email/trigger-send-all` endpoint

## Logging

Enable debug logging by setting in your code:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check logs for:
- Scheduler startup/shutdown
- API call responses
- Email send status (success/error)

## Next Steps

1. **Add signup form to dashboard** — add email input to `dashboard/app.py` sidebar
2. **Test with real forecast data** — run `/email/send-test-digest?email=your@email.com` after API is running
3. **Monitor CSV** — check `data/subscribers.csv` for subscriber list
4. **Set real email** — when hackathon judging nears, configure a real SMTP provider
