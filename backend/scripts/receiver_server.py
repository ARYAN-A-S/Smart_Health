import json
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8080
LOG_FILE = "activity_log.txt"

class WebhookReceiverHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard access logging to keep terminal clean for event outputs
        return

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
            event = payload.get("event", "UNKNOWN_EVENT")
            timestamp = payload.get("timestamp", datetime.datetime.utcnow().isoformat())
            data = payload.get("data", {})
            
            # Format time for display
            dt_str = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S UTC')
            
            # Print beautiful banner in the console
            print("\n" + "="*60)
            print(f"🔔 NEW ACTIVITY RECEIVED: {event.upper()}")
            print(f"⏰ Timestamp: {dt_str}")
            print("-"*60)
            print(json.dumps(data, indent=2))
            print("="*60 + "\n")
            
            # Write statefully to a local log file
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                log_entry = {
                    "event": event,
                    "timestamp": timestamp,
                    "data": data
                }
                f.write(json.dumps(log_entry) + "\n")
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "received"}).encode('utf-8'))
            
        except Exception as e:
            print(f"❌ Error parsing payload: {e}")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=WebhookReceiverHandler):
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    
    print("\n" + "*"*60)
    print(f"🚀 SMART HEALTH ACTIVITY RECEIVER SERVER RUNNING ON PORT {PORT}")
    print(f"📁 Logging stateful actions to: {LOG_FILE}")
    print(f"🔗 Configure your main server WEBHOOK_URL=http://localhost:{PORT}/ in .env")
    print("*"*60 + "\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping receiver server. Goodbye!")

if __name__ == "__main__":
    run()
