#!/usr/bin/env python3
import os
import http.server
import socketserver

PORT = int(os.environ.get("PORT", 8791))
DIR = os.path.join(os.path.dirname(__file__), "relatorios")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)
    def log_message(self, *a):
        pass

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Servindo relatórios em http://localhost:{PORT}")
    httpd.serve_forever()
