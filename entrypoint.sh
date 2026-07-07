#!/bin/bash

# Start FastAPI backend in the background
echo "Starting FastAPI backend..."
PYTHONPATH=backend python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &

# Start Nginx in the foreground (since nginx.conf has daemon off, it will keep container running)
echo "Starting Nginx reverse proxy on port 7860..."
nginx -c /app/nginx.conf
