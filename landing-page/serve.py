#!/usr/bin/env python3
"""
Simple HTTP server for testing the AgentxSuite landing page locally.
Usage: python3 serve.py [port]
Default port: 8000
"""

import http.server
import socketserver
import sys
import os

# Change to the landing-page directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def do_GET(self):
        # Custom MIME types
        if self.path.endswith('.css'):
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open(self.path.lstrip('/'), 'rb') as f:
                self.wfile.write(f.read())
            return
        elif self.path.endswith('.js'):
            self.send_response(200)
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            with open(self.path.lstrip('/'), 'rb') as f:
                self.wfile.write(f.read())
            return
        
        return super().do_GET()

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║         AgentxSuite Landing Page Local Server            ║
╚═══════════════════════════════════════════════════════════╝

✓ Server running at: http://localhost:{PORT}

📄 Pages:
  • Home (EN):        http://localhost:{PORT}/
  • Home (DE):        http://localhost:{PORT}/de/
  • Blog (EN):        http://localhost:{PORT}/blog/
  • Blog (DE):        http://localhost:{PORT}/de/blog/

⚠️  Remember to replace placeholder variables in HTML:
  • ${{SITE_URL}}
  • ${{GITHUB_REPO_URL}}
  • ${{CONTACT_EMAIL}}
  • ${{LICENSE_NAME}}

Press Ctrl+C to stop the server
""")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")
        sys.exit(0)





