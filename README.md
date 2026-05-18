# TMASI CRM Application

Healthcare Operations CRM for managing WhatsApp Business communications, patient intake, patient files, doctors, clinics, bookings, and admin users.

## Features

- **WhatsApp Client** — Receive and reply to messages across 5 WhatsApp Business numbers
- **Patient Files** — Create and manage patient records linked to WhatsApp conversations
- **Appointments/Calendar** — Weekly calendar view with booking management
- **Doctors & Clinics** — Staff and facility management
- **Users** — Role-based access (super_admin, clinic_admin, agent, doctor)
- **Webhook Integration** — Full WhatsApp Cloud API webhook (receive/send text, images, documents)

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy
- **Database**: PostgreSQL (production) / SQLite (local dev)
- **Frontend**: Vanilla HTML/CSS/JS (server-served SPA)
- **Deployment**: Render

## Quick Start

### 1. Setup environment
```bash
cp .env.example .env
# Edit .env with your values
```

### 2. Install dependencies
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run locally
```bash
bash startup.sh
# Or directly:
uvicorn app.main:app --reload --port 8000
```

App available at: http://localhost:8000

Default login: **admin / admin123**

### 4. Run tests
```bash
pytest tests/ -v
```

### 5. Webhook test
```bash
python scripts/test_whatsapp_webhook.py --base-url http://localhost:8000
```

## WhatsApp Business Configuration

Preconfigured with 5 lines (set phone number IDs in `.env`):

| Line | Short Code | Default Phone |
|------|-----------|---------------|
| International Care | IC | +20 100 000 1001 |
| Bookings | BO | +20 100 000 1002 |
| Emergency Desk | ED | +20 100 000 1003 |
| Arabic Support | AS | +20 100 000 1004 |
| Follow-up Care | FC | +20 100 000 1005 |

### Webhook URL (set in Meta Developer Dashboard)
```
https://YOUR_RENDER_APP.onrender.com/api/whatsapp/webhook
```

### Verify Token
```
hcig_virtual_care_verify_token
```

## Deployment to Render

### 1. Create Render service
- Go to [render.com](https://render.com) → New Web Service
- Connect your GitHub repository
- Runtime: **Python**
- Build Command: `pip install -r requirements.txt`
- Start Command: `bash startup.sh`

### 2. Set environment variables in Render Dashboard

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | PostgreSQL connection string from Render DB |
| `BOOTSTRAP_ADMIN_USERNAME` | Your admin username |
| `BOOTSTRAP_ADMIN_PASSWORD` | Strong password |
| `SECRET_KEY` | Random 32+ char string |
| `WHATSAPP_ACCESS_TOKEN` | From Meta Developer Console |
| `WHATSAPP_VERIFY_TOKEN` | `hcig_virtual_care_verify_token` |
| `WHATSAPP_APP_SECRET` | From Meta Developer Console |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | Your WABA ID |
| `WHATSAPP_LINE_1_ID` | Phone Number ID from Meta |
| `WHATSAPP_LINE_1_LABEL` | International Care |
| `WHATSAPP_LINE_1_DISPLAY_PHONE` | +20 100 000 1001 |
| (repeat for lines 2–5) | |

### 3. Add PostgreSQL database
- Render Dashboard → New → PostgreSQL
- Copy the internal connection string to `DATABASE_URL`

### 4. Deploy and verify
```bash
git push origin main  # triggers auto-deploy

# Verify after deploy (wait ~3 min):
python scripts/verify_render_deploy.py --url https://YOUR_APP.onrender.com
```

## Full Deployment Workflow

```bash
# 1. Set env vars
cp .env.example .env && nano .env

# 2. Run local app
bash startup.sh

# 3. Run tests
pytest tests/ -v

# 4. Test webhooks
python scripts/test_whatsapp_webhook.py

# 5. Run UI test
python scripts/browser_ui_test.py

# 6. Commit and push
python scripts/deploy_github.py --message "feat: initial production deployment"

# 7. Wait for Render auto-deploy (~2-3 min), then verify
python scripts/verify_render_deploy.py --url https://YOUR_APP.onrender.com
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Current user |
| GET | `/api/whatsapp/lines` | WhatsApp lines |
| GET/POST | `/api/whatsapp/webhook` | WhatsApp webhook |
| GET | `/api/whatsapp/conversations` | List conversations |
| GET | `/api/whatsapp/conversations/{id}` | Get conversation with messages |
| POST | `/api/whatsapp/send` | Send text message |
| POST | `/api/whatsapp/send-media` | Send media file |
| GET/POST | `/api/patients` | Patient management |
| GET/POST | `/api/doctors` | Doctor management |
| GET/POST | `/api/clinics` | Clinic management |
| GET/POST | `/api/bookings` | Appointment management |
| GET/POST | `/api/users` | User management |
| GET | `/api/health` | Health check |
| GET | `/api/crm/whatsapp-lines` | Lines (no auth) |

## Security Notes

- Never commit `.env` to git
- Use strong passwords in production
- `SECRET_KEY` must be unique per deployment
- WhatsApp tokens are read from environment only
- Uploaded files in `uploads/` are excluded from git

## File Uploads

- Local development: stored in `./uploads/`
- Production: configure persistent disk in Render (1GB+ recommended) or use S3/Cloudflare R2

## Layout Architecture

```
app shell (sidebar + workspace)
  └── WhatsApp workspace (grid: rail | conv-list | chat+drawer)
        ├── WA Number Rail (68px) — 5 line buttons
        ├── Conversation List (280px) — scrollable
        └── Case Detail (1fr) — grid: chat-col | patient-drawer
              ├── Chat Column (grid: header | body | composer)
              │     ├── Chat Header (48px, fixed)
              │     ├── Chat Body (flex:1, overflow-y:auto)
              │     └── Composer (60px, fixed)
              └── Patient Drawer (300px, overflow-y:auto)
```

All containers use `min-height: 0` to prevent grid overflow. Horizontal scroll is reset on every navigation and conversation open event.
