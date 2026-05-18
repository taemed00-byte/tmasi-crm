#!/usr/bin/env bash
set -e

echo "=== TMASI CRM Startup ==="
echo "Python: $(python --version)"
echo "DATABASE_URL type: ${DATABASE_URL%%:*}"

# Create uploads directory
mkdir -p uploads

# Run database initialization and migrations
python -c "
from app.database import engine, Base
from app import models  # import all models so they register
Base.metadata.create_all(bind=engine)
print('Database tables created/verified')
"

# Bootstrap admin user and WhatsApp lines
python -c "
from app.startup import run_startup
run_startup()
print('Startup initialization complete')
"

echo "Starting TMASI CRM on port \${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
