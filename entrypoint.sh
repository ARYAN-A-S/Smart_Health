#!/bin/bash

# Start FastAPI backend in the background and redirect logs to /tmp/uvicorn.log
echo "Starting FastAPI backend..."
touch /tmp/uvicorn.log
PYTHONPATH=backend python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/uvicorn.log 2>&1 &

# Start Nginx in the foreground (since nginx.conf has daemon off, it will keep container running)
echo "Starting Nginx reverse proxy on port 7860..."
nginx -c /app/nginx.conf

