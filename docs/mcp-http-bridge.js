#!/usr/bin/env node
/**
 * MCP HTTP Bridge - Converts HTTP-based MCP server to stdio for Claude Desktop
 * 
 * Usage:
 *   node mcp-http-bridge.js <mcp-url> [--header "Authorization: Bearer <token>"]
 * 
 * This script bridges HTTP-based MCP servers (like AgentxSuite MCP Fabric)
 * to stdio-based MCP protocol that Claude Desktop expects.
 * 
 * IMPORTANT: This is a STDIO-based MCP server.
 * - ONLY JSON-RPC messages are written to stdout
 * - All logging/errors go to stderr
 * - Following MCP specification: https://modelcontextprotocol.io/docs/develop/build-server
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

// Helper for logging to stderr only (never stdout!)
function log(message, ...args) {
  if (process.env.DEBUG) {
    process.stderr.write(`[mcp-bridge] ${message}\n`);
    if (args.length > 0) {
      process.stderr.write(JSON.stringify(args, null, 2) + '\n');
    }
  }
}

function error(message, ...args) {
  process.stderr.write(`[mcp-bridge ERROR] ${message}\n`);
  if (args.length > 0) {
    process.stderr.write(JSON.stringify(args, null, 2) + '\n');
  }
}

// Parse command line arguments
const args = process.argv.slice(2);
if (args.length < 1) {
  error('Usage: node mcp-http-bridge.js <mcp-url> [--header "Authorization: Bearer <token>"]');
  process.exit(1);
}

const mcpUrl = args[0];
let authHeader = null;

// Parse headers - handle both formats:
// Format 1: --header "Authorization: Bearer TOKEN"
// Format 2: --header Authorization: Bearer TOKEN (split by Claude)
for (let i = 1; i < args.length; i++) {
  if (args[i] === '--header') {
    // Collect all remaining args after --header as the header value
    const remainingArgs = args.slice(i + 1);
    
    // Check if next arg starts with "Authorization:"
    if (remainingArgs.length > 0) {
      // Join all remaining args to reconstruct the header
      // This handles: Authorization: Bearer TOKEN (3 separate args)
      const headerValue = remainingArgs.join(' ');
      
      if (headerValue.includes('Authorization:') || headerValue.includes('Bearer')) {
        // Normalize the header format
        authHeader = headerValue
          .replace(/^Authorization:\s*/, 'Authorization: ')
          .replace(/Bearer\s+/, 'Bearer ');
        
        // Ensure it starts with "Authorization: Bearer"
        if (!authHeader.startsWith('Authorization: Bearer ')) {
          // Try to fix common formats
          if (authHeader.startsWith('Bearer ')) {
            authHeader = 'Authorization: ' + authHeader;
          } else if (authHeader.startsWith('Authorization:Bearer')) {
            authHeader = 'Authorization: Bearer ' + authHeader.substring('Authorization:Bearer'.length).trim();
          }
        }
      }
    }
    break; // Stop after processing --header
  }
}

// Log startup info (only to stderr)
log('Starting MCP HTTP Bridge');
log('MCP URL:', mcpUrl);
log('Auth Header:', authHeader ? 'SET' : 'NOT SET');

// Parse URL
const url = new URL(mcpUrl);
const isHttps = url.protocol === 'https:';
const client = isHttps ? https : http;

// Base URL for MCP endpoints
const baseUrl = `${url.protocol}//${url.host}${url.pathname.replace(/\/$/, '')}`;

// MCP Protocol over stdio
// CRITICAL: Only JSON-RPC messages go to stdout!
process.stdin.setEncoding('utf8');

// Read JSON-RPC messages from stdin
let buffer = '';
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';
  
  for (const line of lines) {
    if (line.trim()) {
      try {
        const message = JSON.parse(line);
        log('Received message:', message.method || message.result || 'unknown');
        handleMessage(message);
      } catch (e) {
        error('Failed to parse message:', e.message);
        // Don't crash, just skip malformed messages
      }
    }
  }
});

process.stdin.on('end', () => {
  log('stdin closed, exiting');
  process.exit(0);
});

process.stdin.on('error', (err) => {
  error('stdin error:', err.message);
  process.exit(1);
});

function handleMessage(message) {
  // CRITICAL: Check if this is a notification (no id) or a request (has id)
  // Notifications must NOT receive a response per JSON-RPC spec!
  const isNotification = message.id === undefined || message.id === null;
  
  // Handle notifications (no response should be sent)
  if (isNotification) {
    log(`Received notification: ${message.method}`);
    // Notifications like "notifications/initialized" don't require a response
    // Just log and return
    return;
  }
  
  if (message.method === 'initialize') {
    // Use the protocol version from the client request or default to 2024-11-05
    const clientProtocolVersion = message.params?.protocolVersion || '2024-11-05';
    sendResponse(message.id, {
      protocolVersion: clientProtocolVersion,
      capabilities: {
        tools: {},
      },
      serverInfo: {
        name: 'agentxsuite-mcp-bridge',
        version: '1.0.0',
      },
    });
  } else if (message.method === 'tools/list') {
    httpRequest('GET', `${baseUrl}/tools`, (err, data) => {
      if (err) {
        sendError(message.id, -32603, 'Internal error', err.message);
        return;
      }
      
      try {
        const tools = Array.isArray(data) ? data : (data.tools || []);
        
        // Normalize tool names to match MCP spec: ^[a-zA-Z0-9_-]{1,64}$
        // Replace spaces and invalid chars with underscores
        const normalizedTools = tools.map(tool => {
          const originalName = tool.name;
          const normalizedName = originalName
            .replace(/[^a-zA-Z0-9_-]/g, '_')  // Replace invalid chars with _
            .replace(/_+/g, '_')               // Collapse multiple underscores
            .replace(/^_|_$/g, '')             // Remove leading/trailing underscores
            .substring(0, 64);                 // Limit to 64 chars
          
          if (originalName !== normalizedName) {
            log(`Normalized tool name: "${originalName}" -> "${normalizedName}"`);
          }
          
          return {
            ...tool,
            name: normalizedName,
            // Store original name in description for reference
            description: tool.description || `Tool: ${originalName}`,
          };
        });
        
        sendResponse(message.id, { tools: normalizedTools });
      } catch (e) {
        sendError(message.id, -32603, 'Internal error', e.message);
      }
    });
  } else if (message.method === 'tools/call') {
    const { name, arguments: args } = message.params;
    
    httpRequest('POST', `${baseUrl}/run`, {
      name: name,
      arguments: args || {},
    }, (err, data) => {
      if (err) {
        sendError(message.id, -32603, 'Internal error', err.message);
        return;
      }
      
      try {
        // Convert MCP Fabric response to MCP protocol format
        if (data.isError) {
          sendResponse(message.id, {
            content: data.content || [{ type: 'text', text: data.error || 'Tool execution failed' }],
            isError: true,
          });
        } else {
          sendResponse(message.id, {
            content: data.content || [{ type: 'text', text: JSON.stringify(data) }],
            isError: false,
          });
        }
      } catch (e) {
        sendError(message.id, -32603, 'Internal error', e.message);
      }
    });
  } else if (message.method === 'resources/list') {
    sendResponse(message.id, { resources: [] });
  } else if (message.method === 'prompts/list') {
    httpRequest('GET', `${baseUrl}/prompts`, (err, data) => {
      if (err) {
        sendResponse(message.id, { prompts: [] });
        return;
      }
      
      try {
        const prompts = Array.isArray(data) ? data : (data.prompts || []);
        sendResponse(message.id, { prompts });
      } catch (e) {
        sendResponse(message.id, { prompts: [] });
      }
    });
  } else {
    sendError(message.id, -32601, 'Method not found', `Unknown method: ${message.method}`);
  }
}

function httpRequest(method, url, body, callback) {
  if (typeof body === 'function') {
    callback = body;
    body = null;
  }
  
  const urlObj = new URL(url);
  const options = {
    hostname: urlObj.hostname,
    port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
    path: urlObj.pathname + urlObj.search,
    method: method,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  };
  
  if (authHeader) {
    const [key, value] = authHeader.split(': ');
    options.headers[key] = value;
  }
  
  if (body) {
    options.headers['Content-Length'] = JSON.stringify(body).length;
  }
  
  const req = client.request(options, (res) => {
    let data = '';
    
    res.on('data', (chunk) => {
      data += chunk;
    });
    
    res.on('end', () => {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        try {
          const json = JSON.parse(data);
          callback(null, json);
        } catch (e) {
          callback(new Error(`Invalid JSON response: ${e.message}`));
        }
      } else {
        callback(new Error(`HTTP ${res.statusCode}: ${data}`));
      }
    });
  });
  
  req.on('error', (err) => {
    callback(err);
  });
  
  if (body) {
    req.write(JSON.stringify(body));
  }
  
  req.end();
}

function sendResponse(id, result) {
  const response = {
    jsonrpc: '2.0',
    id: id,
    result: result,
  };
  // CRITICAL: This is the ONLY place we write to stdout!
  // Each response must be on its own line (newline-delimited JSON)
  const jsonString = JSON.stringify(response);
  process.stdout.write(jsonString + '\n');
  log('Sent response:', response.result?.tools ? `${response.result.tools.length} tools` : 'response');
}

function sendError(id, code, message, data) {
  const response = {
    jsonrpc: '2.0',
    id: id,
    error: {
      code: code,
      message: message,
      data: data,
    },
  };
  const jsonString = JSON.stringify(response);
  process.stdout.write(jsonString + '\n');
  error('Sent error response:', code, message);
}

