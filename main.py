import os
import http.server
import socketserver
import socket
import pyqrcode
import urllib.parse
import shutil
import json
import mimetypes
import sys
import threading
import tempfile
import webbrowser
import platform
import subprocess
import time
import random
import string 

# --- GLOBAL CONFIGURATION ---
START_PORT = 8010
httpd = None
BASE_DIR = ""
UPLOAD_DIR = ""
DOWNLOAD_DIR = ""
ACTUAL_PORT = START_PORT

# Security & State
CURRENT_PIN = "0000"
SESSION = set()

# Global State for Notifications
state_lock = threading.Lock()
event_queue = []
upload_status = None

# --- 0. STATE MANAGEMENT HELPERS ---
# Event Queue Management
def add_event(msg):
    with state_lock:
        t = time.strftime("%H:%M:%S", time.localtime())
        event_queue.append({"time": t, "msg": msg})
        if len(event_queue) > 50:
            event_queue.pop(0)

# Upload Status Management
def set_upload_status(filename, current, total):
    global upload_status
    with state_lock:
        upload_status = {"filename": filename, "current": current, "total": total}

# Clear Upload Status
def clear_upload_status():
    global upload_status
    with state_lock:
        upload_status = None

# Pop Events Safely
def pop_events():
    with state_lock:
        return list(event_queue)

# Get Upload Status Safely
def get_upload_status_safe():
    with state_lock:
        return upload_status.copy() if upload_status else None
    
# Pin Manager
def pin_rotator():
    """
    Rotate Pin in every 30 seconds.
    """
    global CURRENT_PIN
    while True:
        new_pin = str(random.randint(1000, 9999))
        with state_lock:
            CURRENT_PIN = new_pin
        add_event(f"Pin Changed: {new_pin}")
        print(f"[Security] New Pin: {new_pin}")
        time.sleep(30)

def start_pin_rotator():
    threading.Thread(target=pin_rotator, daemon=True).start()
    
# --- 1. SYSTEM HELPERS ---
# Get Local IP Address
def get_ip():
    """Finds the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# Open Folder in File Explorer
def open_folder(path):
    """Opens the destination folder in the system file explorer."""
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        else:  # Linux
            subprocess.Popen(["xdg-open", path])
    except:
        pass  # Ignore errors if we can't open the folder

# --- 2. REQUEST HANDLER ---
class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    # IMPROVEMENT: Silence the default spammy logs (GET /styles.css etc.)
    # by overriding log_message to do nothing
    def log_message(self, format, *args):
        pass 
    # END IMPROVEMENT
    def get_file_path(self, filename):
        """Helper: Searches for a file in shared folders."""
        fp = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(fp) and os.path.isfile(fp): 
            return fp
        fp = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(fp) and os.path.isfile(fp):
            return fp
        return None
    
    def is_authenticated(self):
        """Check if client IP is in allowed sessions."""
        ip = self.client_address[0]
        # Host (localhost) is always authenticated
        if ip == "127.0.0.1" or ip == get_ip():
            return True
        return ip in SESSION

    def do_GET(self):
        if getattr(sys, 'frozen', False):
            ASSET_DIR = sys._MEIPASS
        else:
            ASSET_DIR = os.path.dirname(os.path.abspath(__file__))

        # 1. SERVE ASSETS (No Auth Required)
        # We allow CSS, JS, Images, and the Login page to be loaded by anyone
        if self.path.endswith('.css') or self.path.endswith('.js') or self.path.endswith('.ico') or self.path == '/login.html':
            return super().do_GET() 

        # 2. CHECK AUTHENTICATION (For everything else)
        if not self.is_authenticated():
            # If requesting API data without auth, return 401
            if self.path.startswith('/api/'):
                self.send_error(401, "Unauthorized")
                return
            
            # Otherwise, redirect to Login Page
            login_path = os.path.join(ASSET_DIR, "login.html")
            if os.path.exists(login_path):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(login_path, "rb") as f: self.wfile.write(f.read())
            else:
                self.send_error(404, "Login page missing")
            return

        # 3. AUTHENTICATED ROUTES
        
        # A. Serve Dashboard
        if self.path == '/' or self.path == '/index.html':
            client_ip = self.client_address[0]
            host_ip = get_ip()
            is_host = (client_ip == "127.0.0.1") or (client_ip == host_ip)
            
            page_file = "host.html" if is_host else "client.html"
            file_path = os.path.join(ASSET_DIR, page_file)

            if os.path.exists(file_path):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(file_path, "rb") as f: self.wfile.write(f.read())
            else:
                self.send_error(404, "Dashboard not found.")
            return

        # B. Serve QR Code
        if self.path == '/qrcode.png':
            qr_path = os.path.join(BASE_DIR, "qrcode.png")
            if os.path.exists(qr_path):
                self.send_response(200); self.send_header("Content-type", "image/png"); self.end_headers()
                with open(qr_path, "rb") as f: self.wfile.write(f.read())
            return

        # C. API: PIN (Host Only)
        if self.path == '/api/pin':
            # Only Host can see the PIN via API
            if self.client_address[0] in ["127.0.0.1", get_ip()]:
                self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"pin": CURRENT_PIN}).encode())
            else:
                self.send_error(403)
            return

        # D. API: Files
        if self.path == '/api/files':
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            def list_dir(path):
                data = []
                try:
                    if os.path.exists(path):
                        files = sorted(os.listdir(path), key=str.lower)
                        for f in files:
                            fp = os.path.join(path, f)
                            if os.path.isfile(fp):
                                data.append({"name": f, "size": os.path.getsize(fp)})
                except: pass
                return data
            response = {"pc": list_dir(DOWNLOAD_DIR), "mobile": list_dir(UPLOAD_DIR)}
            self.wfile.write(json.dumps(response).encode())
            return

        # E. API: Updates
        if self.path == '/api/updates':
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            data = {"events": pop_events(), "upload": get_upload_status_safe()}
            self.wfile.write(json.dumps(data).encode())
            return

        # F. API: Open Folder
        if self.path.startswith('/api/open'):
            if self.client_address[0] not in ["127.0.0.1", get_ip()]:
                self.send_error(403); return
            
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            folder_type = params.get('folder', [''])[0]
            target_path = BASE_DIR
            if folder_type == 'received': target_path = UPLOAD_DIR
            elif folder_type == 'shared': target_path = DOWNLOAD_DIR
            open_folder(target_path)
            self.send_response(200); self.end_headers(); self.wfile.write(b"Opened")
            return

        # G. Downloads (Secured)
        if self.path.startswith('/view/') or self.path.startswith('/download/'):
            is_view = self.path.startswith('/view/')
            prefix = 6 if is_view else 10
            
            raw_fn = urllib.parse.unquote(self.path[prefix:])
            fn = os.path.basename(raw_fn) # Path Traversal Security Fix
            
            fp = self.get_file_path(fn)
            if fp:
                self.send_response(200)
                ctype, _ = mimetypes.guess_type(fp)
                if ctype is None: ctype = 'application/octet-stream'
                self.send_header("Content-Type", ctype)
                if not is_view: self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
            else: self.send_error(404)
            return

        # H. Shutdown
        if self.path == '/shutdown':
            self.send_response(200); self.end_headers()
            def kill():
                if httpd: httpd.shutdown(); httpd.server_close()
                os._exit(0)
            threading.Thread(target=kill).start()
            return

        return super().do_GET()

    def do_POST(self):
        # 1. HANDLE LOGIN
        if self.path == '/login':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode()
            params = urllib.parse.parse_qs(body)
            pin_input = params.get('pin', [''])[0]
            
            if pin_input == CURRENT_PIN:
                SESSION.add(self.client_address[0])
                add_event(f"Device authenticated: {self.client_address[0]}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Invalid PIN")
            return

        # 2. CHECK AUTH FOR UPLOADS
        if not self.is_authenticated():
            self.send_error(401, "Unauthorized")
            return

        # 3. HANDLE FILE UPLOAD
        try:
            is_host_upload = "dest=host" in self.path
            target_dir = DOWNLOAD_DIR if is_host_upload else UPLOAD_DIR
            
            ctype = self.headers.get('Content-Type')
            if not ctype: return
            boundary = ctype.split("boundary=")[1].encode()
            length = int(self.headers.get('Content-Length'))
            
            line = self.rfile.readline()
            read_bytes = len(line)
            fn = "uploaded_file"
            
            while line.strip():
                decoded = line.decode(errors='ignore')
                if 'filename=' in decoded:
                    fn = decoded.split('filename=')[1].strip('"\r\n ')
                    fn = os.path.basename(urllib.parse.unquote(fn))
                line = self.rfile.readline()
                read_bytes += len(line)
            
            if not os.path.exists(target_dir): os.makedirs(target_dir, exist_ok=True)

            out_path = os.path.join(target_dir, fn)
            remain = length - read_bytes
            total_size = remain
            
            if not is_host_upload: add_event(f"Receiving file: {fn}")
            
            with open(out_path, 'wb') as f:
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536))
                    if not chunk: break
                    f.write(chunk)
                    remain -= len(chunk)
                    if not is_host_upload: set_upload_status(fn, total_size - remain, total_size)
            
            with open(out_path, 'rb+') as f:
                f.seek(0, 2); size = f.tell(); f.seek(max(0, size-300), 0); tail = f.read()
                loc = tail.find(b'--' + boundary)
                if loc != -1: f.truncate(max(0, size-300) + loc - 2)
            
            clear_upload_status()
            msg = f"Added to Shared: {fn}" if is_host_upload else f"File received: {fn}"
            add_event(msg)
            self.send_response(200); self.end_headers(); self.wfile.write(b"Upload Complete")
        except Exception:
            clear_upload_status()


# --- 3. SERVER CONTROLLER ---
def start_server():
    global BASE_DIR, UPLOAD_DIR, DOWNLOAD_DIR, httpd, ACTUAL_PORT
    
    print("\n" + "="*40)
    print("🚀 Starting PyShare...")

    # 1. SETUP DESKTOP PATH
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        BASE_DIR = os.path.join(desktop, "PyShare_Files")
        
        # new flattened structure
        UPLOAD_DIR = os.path.join(BASE_DIR, "Received_Files")
        DOWNLOAD_DIR = os.path.join(BASE_DIR, "Shared_Files")

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        print(f"📂 Storage: {BASE_DIR}")
        
        # IMPROVEMENT: Auto-open the folder so user sees it
        open_folder(BASE_DIR)

    except Exception as e:
        print(f"❌ ERROR: Could not create folder on Desktop: {e}")
        return

    # 2. SMART PORT SELECTION
    socketserver.TCPServer.allow_reuse_address = True
    found_port = False
    
    # Try ports 8010, 8011, 8012... until one works
    for port in range(START_PORT, START_PORT + 10):
        try:
            server = socketserver.ThreadingTCPServer(("", port), FinalFileHandler)
            ACTUAL_PORT = port
            httpd = server
            found_port = True
            break
        except OSError:
            continue

    if not found_port:
        print("❌ Error: Could not find an open port between 8010-8020.")
        return

    # 3. GENERATE QR CODE
    start_pin_rotator()
    ip = get_ip()
    url = f'http://{ip}:{ACTUAL_PORT}'
    
    try:
        qr_path = os.path.join(BASE_DIR, 'qrcode.png')
        pyqrcode.create(url).png(qr_path, scale=6)
    except:
        try:
            temp_qr = os.path.join(tempfile.gettempdir(), "pyshare_qrcode.png")
            pyqrcode.create(url).png(temp_qr, scale=6)
        except:
            print("⚠️ Warning: QR Code generation failed.")

    print(f"⚡ SERVER LIVE: {url}")
    print("="*40 + "\n")

    # IMPROVEMENT: Open the browser automatically
    webbrowser.open(url)

    # 4. START SERVER
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("🛑 Server Stopped.")

if __name__ == "__main__":
    start_server()
