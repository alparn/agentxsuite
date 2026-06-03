# MCP Gateway Service

A server-side bridge that translates SSE/WebSocket connections from MCP clients (like Claude Desktop) to HTTP requests to the internal FastMCP server.

## Architecture

```
Claude Desktop → SSE/WebSocket → MCP Gateway → HTTP → FastMCP Server
   (User)         (Port 8091)      (This)      (Port 8090)
```

## Benefits

- ✅ **No local bridge needed** - Users don't install anything
- ✅ **Centralized** - All translation happens on your server
- ✅ **Secure** - Token validation on server-side
- ✅ **Scalable** - Can handle multiple concurrent connections

## How it Works

1. **Client connects** via SSE or WebSocket to `https://mcp.agentxsuite.com`
2. **Gateway receives** MCP protocol messages (JSON-RPC)
3. **Gateway translates** to HTTP calls to internal FastMCP server
4. **Gateway returns** responses back to client

## User Configuration

Users only need to configure Claude Desktop once:

```json
{
  "mcpServers": {
    "agentxsuite": {
      "url": "https://mcp.agentxsuite.com/.well-known/mcp/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

## Running

### Development

```bash
cd backend
python mcp_gateway/main.py
```

Service runs on http://localhost:8091

### Production

```bash
# With systemd
sudo systemctl start mcp-gateway

# With Docker
docker run -p 8091:8091 agentxsuite-mcp-gateway

# Behind Nginx
# Configure nginx to proxy https://mcp.agentxsuite.com to localhost:8091
```

## Endpoints

- `GET /.well-known/mcp` - Discovery endpoint
- `GET /.well-known/mcp/sse` - SSE transport endpoint
- `WS /.well-known/mcp/ws` - WebSocket transport endpoint
- `GET /health` - Health check

## Dependencies

```
fastapi
uvicorn[standard]
httpx
sse-starlette
```

## Configuration

Environment variables:

- `FASTMCP_BACKEND_URL` - Internal FastMCP server URL (default: http://localhost:8090)
- `PORT` - Gateway port (default: 8091)
- `LOG_LEVEL` - Logging level (default: info)

## Security

- All tokens are validated by the backend FastMCP server
- Gateway only proxies requests, doesn't store credentials
- HTTPS required in production
- CORS configured to allow only your domains

## Testing

```bash
# Test SSE endpoint
curl -N -H "Authorization: Bearer TOKEN" \
  http://localhost:8091/.well-known/mcp/sse

# Test WebSocket
wscat -c ws://localhost:8091/.well-known/mcp/ws \
  -H "Authorization: Bearer TOKEN"
```

## Deployment

### Nginx Configuration

```nginx
upstream mcp_gateway {
    server localhost:8091;
}

server {
    listen 443 ssl http2;
    server_name mcp.agentxsuite.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /.well-known/mcp/sse {
        proxy_pass http://mcp_gateway;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }

    location /.well-known/mcp/ws {
        proxy_pass http://mcp_gateway;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://mcp_gateway;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Systemd Service

```ini
[Unit]
Description=AgentxSuite MCP Gateway
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/agentxsuite/backend
Environment="PATH=/opt/agentxsuite/venv/bin"
ExecStart=/opt/agentxsuite/venv/bin/python mcp_gateway/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Monitoring

Gateway logs all requests with:
- Request ID
- Client IP
- Response time
- Error rates

Use these logs for monitoring and debugging.

