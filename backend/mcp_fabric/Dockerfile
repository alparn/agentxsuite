# MCP Fabric Dockerfile - FastAPI Service
# Build-Kontext: ./backend (daher relative Pfade)
FROM python:3.13-slim

# Runtime dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 mcpfabric && \
    mkdir -p /app && \
    chown -R mcpfabric:mcpfabric /app

WORKDIR /app

# Copy requirements and install
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements/base.txt

# Copy entire backend (für Django Setup und MCP Fabric)
COPY --chown=mcpfabric:mcpfabric . /app/

# Switch to non-root user
USER mcpfabric

# Expose port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health').read()" || exit 1

# Run uvicorn (mcp_fabric ist Teil des Backend-Pakets)
CMD ["uvicorn", "mcp_fabric.main:app", "--host", "0.0.0.0", "--port", "8090"]

