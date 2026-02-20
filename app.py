
import os
import threading
import sys
import webview
import uvicorn
from server import app as fast_app

# Set window details
WIDTH = 1200
HEIGHT = 850
TITLE = "JARVIS AI - Desktop Assistant"

def start_server():
    """Runs the FastAPI server in a background thread."""
    # Ensure uvicorn logs don't clutter console too much
    config = uvicorn.Config(fast_app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    server.run()

if __name__ == '__main__':
    # 1. Start Server Thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # 2. Launch Webview
    # Use 'edge' or 'cef' for better rendering if available
    # debug=True allows right-click inspect element
    webview.create_window(TITLE, "http://127.0.0.1:8000", width=WIDTH, height=HEIGHT, background_color='#212121')
    
    # 3. Start App
    webview.start(debug=True)
    
    # 4. Force Kill on Window Close
    print("Uygulama Kapatılıyor...")
    os._exit(0)
