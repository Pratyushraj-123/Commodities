import http.server
import socketserver
import json
import webbrowser
import os
import threading
import time
import sys

# Import scraping logic from scrape.py
from scrape import run_scraper, load_stored_prices, JSON_FILE

PORT = 8000
LOG_FILE = "server.log"

# Redirect stdout and stderr to server.log for debugging
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open(LOG_FILE, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger()
sys.stderr = Logger()

print(f"\n--- Server started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        super().end_headers()

    def do_OPTIONS(self):
        # Support CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type, Accept')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/prices':
            try:
                prices = load_stored_prices()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(prices).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            
        elif self.path == '/api/refresh':
            try:
                # Trigger the scraper from scrape.py
                prices = run_scraper()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(prices).encode('utf-8'))
            except Exception as e:
                print(f"API /api/refresh failed: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            
        else:
            if self.path == '/' or self.path == '':
                self.path = '/index.html'
            super().do_GET()

def start_server():
    server_address = ('', PORT)
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(server_address, DashboardHandler) as httpd:
        print(f"Commodities dashboard server running at http://localhost:{PORT}")
        print("Keep this window open to auto-refresh prices in the browser.")
        
        # Run scraper once on startup in background thread to get initial prices
        threading.Thread(target=run_scraper, daemon=True).start()
        
        # Open browser in a separate thread
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")

if __name__ == "__main__":
    start_server()
