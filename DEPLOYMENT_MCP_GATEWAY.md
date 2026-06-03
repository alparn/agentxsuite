# MCP Gateway Deployment Guide

Complete guide to deploy the MCP Gateway service for AgentxSuite.

## 🎯 What You're Deploying

A server-side bridge that allows Claude Desktop users to connect **without installing a local bridge**.

```
User Flow:
Claude Desktop → mcp.agentxsuite.com (Gateway) → FastMCP Backend
```

## 📦 Prerequisites

- Server with Python 3.11+
- Domain for gateway (e.g., `mcp.agentxsuite.com`)
- SSL certificate
- Nginx or similar reverse proxy

## 🚀 Quick Start (Development)

```bash
# 1. Install dependencies
cd backend/mcp_gateway
pip install -r requirements.txt

# 2. Start gateway
python main.py

# Gateway runs on http://localhost:8091

# 3. Start FastMCP (in another terminal)
cd backend
make run-mcp-fabric

# FastMCP runs on http://localhost:8090
```

**Test it:**
```bash
curl http://localhost:8091/health
# Should return: {"status":"ok","service":"mcp-gateway"}
```

## 🏭 Production Deployment

### Option 1: Docker (Recommended)

```bash
# Build image
cd backend/mcp_gateway
docker build -t agentxsuite-mcp-gateway .

# Run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f mcp-gateway
```

### Option 2: Systemd Service

**1. Create systemd service:**

```bash
sudo nano /etc/systemd/system/mcp-gateway.service
```

**Paste:**
```ini
[Unit]
Description=AgentxSuite MCP Gateway
After=network.target mcp-fabric.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/agentxsuite/backend
Environment="PATH=/opt/agentxsuite/venv/bin"
Environment="FASTMCP_BACKEND_URL=http://localhost:8090"
ExecStart=/opt/agentxsuite/venv/bin/python mcp_gateway/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**2. Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-gateway
sudo systemctl start mcp-gateway
sudo systemctl status mcp-gateway
```

### Option 3: Supervisor

```bash
sudo nano /etc/supervisor/conf.d/mcp-gateway.conf
```

```ini
[program:mcp-gateway]
command=/opt/agentxsuite/venv/bin/python mcp_gateway/main.py
directory=/opt/agentxsuite/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/mcp-gateway.err.log
stdout_logfile=/var/log/mcp-gateway.out.log
environment=FASTMCP_BACKEND_URL="http://localhost:8090"
```

## 🔧 Nginx Configuration

### Basic Setup

```nginx
upstream mcp_gateway {
    server localhost:8091;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name mcp.agentxsuite.com;

    ssl_certificate /etc/letsencrypt/live/mcp.agentxsuite.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.agentxsuite.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # SSE endpoint - critical configuration!
    location /.well-known/mcp/sse {
        proxy_pass http://mcp_gateway;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Critical for SSE
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        chunked_transfer_encoding off;
    }

    # WebSocket endpoint
    location /.well-known/mcp/ws {
        proxy_pass http://mcp_gateway;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
    }

    # Other endpoints
    location / {
        proxy_pass http://mcp_gateway;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name mcp.agentxsuite.com;
    return 301 https://$server_name$request_uri;
}
```

**Apply config:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 🔐 SSL Certificate (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d mcp.agentxsuite.com

# Auto-renewal is configured automatically
```

## 📊 Monitoring

### Health Checks

```bash
# Basic health
curl https://mcp.agentxsuite.com/health

# SSE endpoint
curl -N -H "Authorization: Bearer TOKEN" \
  https://mcp.agentxsuite.com/.well-known/mcp/sse
```

### Logs

**Docker:**
```bash
docker-compose logs -f mcp-gateway
```

**Systemd:**
```bash
journalctl -u mcp-gateway -f
```

**Supervisor:**
```bash
tail -f /var/log/mcp-gateway.out.log
```

### Metrics

Add to your monitoring (Prometheus, Grafana):

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'mcp-gateway'
    static_configs:
      - targets: ['localhost:8091']
```

## 🧪 Testing

### Test SSE Connection

```bash
curl -N -H "Authorization: Bearer YOUR_TOKEN" \
  https://mcp.agentxsuite.com/.well-known/mcp/sse
```

Should stream events continuously.

### Test WebSocket

```bash
npm install -g wscat

wscat -c wss://mcp.agentxsuite.com/.well-known/mcp/ws \
  -H "Authorization: Bearer YOUR_TOKEN"

# Then send:
{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}
```

### Test from Claude Desktop

**Config:**
```json
{
  "mcpServers": {
    "agentxsuite": {
      "url": "https://mcp.agentxsuite.com/.well-known/mcp/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

**Restart Claude Desktop and test!**

## 🚨 Troubleshooting

### Gateway won't start

**Check port 8091:**
```bash
lsof -i :8091
# Kill if needed:
kill -9 $(lsof -t -i:8091)
```

**Check backend connection:**
```bash
curl http://localhost:8090/health
# Should work before gateway can
```

### SSE connection drops

**Check nginx timeout:**
```nginx
proxy_read_timeout 86400s;  # 24 hours
```

**Check system limits:**
```bash
ulimit -n  # Should be > 1024
```

### High memory usage

**Limit connections:**
```python
# In mcp_gateway/main.py
app = FastAPI(
    ...
    max_request_size=1024*1024,  # 1MB
)
```

## 📈 Scaling

### Load Balancing (Multiple Gateways)

```nginx
upstream mcp_gateway {
    least_conn;
    server gateway1:8091;
    server gateway2:8091;
    server gateway3:8091;
}
```

### Redis for Session State (Future)

```python
# For stateful connections
import redis
r = redis.Redis(host='localhost', port=6379)
```

## 🔒 Security Checklist

- [x] HTTPS enforced
- [x] Token validation on every request
- [x] Rate limiting configured
- [x] CORS properly configured
- [x] Logs don't contain tokens
- [x] Regular security updates
- [x] Firewall rules applied

## 📚 Additional Resources

- User Guide: `/docs/USER_GUIDE_MCP_GATEWAY.md`
- Gateway README: `/backend/mcp_gateway/README.md`
- FastMCP Docs: https://github.com/jlowin/fastmcp

## 🎉 Success Checklist

- [ ] Gateway health endpoint returns OK
- [ ] SSE endpoint streams events
- [ ] Claude Desktop can connect
- [ ] Tools are callable from Claude
- [ ] Logs show successful requests
- [ ] SSL certificate is valid
- [ ] Monitoring is set up

Congratulations! Your users can now use AgentxSuite **without any local bridge**! 🚀

