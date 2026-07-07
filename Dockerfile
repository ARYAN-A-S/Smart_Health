FROM python:3.11-slim

# Install system dependencies including Nginx
RUN apt-get update && apt-get install -y \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Set environment variables
ENV PYTHONPATH=backend
ENV DATABASE_URL=sqlite:////app/backend/smart_health.db
ENV JWT_SECRET=supersecretjwtkeyforlocaldevelopmentonly12345

# Ensure entrypoint.sh has Unix line endings and is executable
RUN sed -i -e 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Create directory for SQLite and run setup permissions for Nginx cache/run directories
RUN mkdir -p /app/backend && chmod -R 777 /app/backend
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx && chmod -R 777 /var/cache/nginx /var/run /var/log/nginx /etc/nginx

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Run services via entrypoint
CMD ["/app/entrypoint.sh"]
