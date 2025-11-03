# Every Now & Then - Autonomous Python Script Runner
# Multi-stage build for optimized container size

FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    openssh-client \
    cron \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"


# Create app directory
WORKDIR /app

# Copy project files
COPY install_uv_tools.sh /app/
COPY uv_tools.txt /app/
COPY crontab /app/crontab
COPY scripts /app/scripts/

# Make scripts executable
RUN chmod +x /app/install_uv_tools.sh

# Configure SSH for Git operations (if needed for private repos)
# Uncomment and add your SSH key during build if using private repositories:
# RUN mkdir -p /root/.ssh
# COPY id_rsa /root/.ssh/id_rsa
# RUN chmod 600 /root/.ssh/id_rsa && \
#     ssh-keyscan github.com >> /root/.ssh/known_hosts

# Install UV tools from Git repositories
# Comment this out if you don't have any tools in uv_tools.txt yet
RUN /app/install_uv_tools.sh

# Create log directory for cron
RUN mkdir -p /var/log && touch /var/log/cron.log

# Create data volume directory
RUN mkdir -p /data

# Install crontab from file
RUN crontab /app/crontab

# Create a startup script that runs cron and keeps container alive
RUN echo '#!/bin/bash\n\
    echo "Starting Every Now & Then Script Runner..."\n\
    echo "Environment variables loaded from .env"\n\
    echo ""\n\
    echo "Available scripts:"\n\
    ls -1 /app/scripts/ | grep -v "^\\."\n\
    echo ""\n\
    echo "Installed UV tools:"\n\
    uv tool list || echo "No UV tools installed"\n\
    echo ""\n\
    echo "Cron schedule:"\n\
    crontab -l\n\
    echo ""\n\
    echo "Starting cron service..."\n\
    cron\n\
    echo "Cron service started. Logs available at /var/log/cron.log"\n\
    echo ""\n\
    echo "Container is running. Press Ctrl+C to stop."\n\
    tail -f /var/log/cron.log' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose no ports (internal script runner)

# Define volume for data persistence
VOLUME ["/data"]

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
