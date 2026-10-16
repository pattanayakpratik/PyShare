from zeroconf import ServiceInfo, Zeroconf
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
import zipfile
import io
import datetime

# Protect against Windows cp1252 console UnicodeEncodeError
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# --- GLOBAL CONFIGURATION ---
START_PORT = 8010
httpd = None
BASE_DIR = ""
UPLOAD_DIR = ""    # Received from Phone (Mobile Uploads)
DOWNLOAD_DIR = ""  # Shared from PC (PC Shared Files)
ACTUAL_PORT = START_PORT
zc = None

# --- SECURITY & STATE ---
CURRENT_PIN = "0000"
PREVIOUS_PIN = ""  # 30-second grace window to prevent edge-case rejections
NEXT_CHANGE = 0    # Track timestamp when PIN rotates
SESSIONS = set()   # Stores authenticated client IPs
SHARED_TEXT = ""   # In-memory shared clipboard / quick link
TEXT_TIMESTAMP = 0 # Timestamp of last clipboard change
state_lock = threading.Lock()
events_queue = [] 
upload_status = {}

# Ensure MIME types are registered for streaming & previews
mimetypes.init()
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/webm", ".webm")
mimetypes.add_type("video/quicktime", ".mov")
mimetypes.add_type("audio/mpeg", ".mp3")
mimetypes.add_type("audio/ogg", ".ogg")
mimetypes.add_type("audio/wav", ".wav")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/svg+xml", ".svg")

# --- PIN MANAGER ---
def pin_rotator():
    """Rotates the 4-digit PIN every 30 seconds while retaining the previous PIN for a grace period."""
    global CURRENT_PIN, PREVIOUS_PIN, NEXT_CHANGE
    while True:
        new_pin = f"{random.randint(1000, 9999)}"
        with state_lock:
            PREVIOUS_PIN = CURRENT_PIN
            CURRENT_PIN = new_pin
            NEXT_CHANGE = time.time() + 30
        time.sleep(30)

def start_pin_rotator():
    t = threading.Thread(target=pin_rotator, daemon=True)
    t.start()

# --- STATE MANAGEMENT ---
def add_event(msg):
    with state_lock:
        t = time.strftime("%H:%M:%S")
        events_queue.append({"time": t, "msg": msg})
        if len(events_queue) > 60:
            events_queue.pop(0)

def set_upload_status(client_ip, filename, current, total):
    with state_lock:
        upload_status[client_ip] = {
            "filename": filename, 
            "current": current, 
            "total": total
        }

def clear_upload_status(client_ip=None):
    with state_lock:
        if client_ip:
            upload_status.pop(client_ip, None)
        else:
            upload_status.clear()

def pop_events():
    with state_lock:
        return list(events_queue)

# --- SYSTEM HELPERS ---
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def open_folder(path):
    try:
        if platform.system() == "Windows": 
            os.startfile(path)
        elif platform.system() == "Darwin": 
            subprocess.Popen(["open", path])
        else: 
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass

def get_category(ext):
    ext = ext.lower().lstrip('.')
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif']:
        return 'image'
    if ext in ['mp4', 'mkv', 'mov', 'webm', 'avi', 'wmv', 'm4v']:
        return 'video'
    if ext in ['mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a', 'wma']:
        return 'audio'
    if ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'csv']:
        return 'document'
    if ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz']:
        return 'archive'
    if ext in ['html', 'css', 'js', 'json', 'py', 'ts', 'jsx', 'tsx', 'cpp', 'c', 'java', 'go', 'rs', 'sh', 'md', 'xml', 'yaml', 'yml']:
        return 'code'
    return 'other'

def get_unique_filepath(directory, filename):
    """Avoid silent overwrite: append (1), (2), etc. if file already exists."""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base} ({counter}){ext}")
        counter += 1
    return candidate

def generate_qr(url):
    """Generates a dynamic QR Code pointing to the current server URL."""
    try:
        qr_path = os.path.join(BASE_DIR, "qrcode.png")
        qr = pyqrcode.create(url)
        qr.png(qr_path, scale=6)
        return qr_path
    except Exception as e:
        print(f"[!] QR generation failed: {e}")
        return None

def parse_range_header(range_header, file_size):
    """Parse HTTP Range header for 206 Partial Content video/audio streaming."""
    if not range_header or not range_header.startswith("bytes="):
        return None
    range_str = range_header[6:].strip()
    if "," in range_str:
        return None
    parts = range_str.split("-")
    if len(parts) != 2:
        return None
    start_str, end_str = parts[0].strip(), parts[1].strip()
    if not start_str and not end_str:
        return None
    try:
        if not start_str:
            length = int(end_str)
            if length > file_size:
                length = file_size
            start = file_size - length
            end = file_size - 1
        elif not end_str:
            start = int(start_str)
            end = file_size - 1
        else:
            start = int(start_str)
            end = int(end_str)
        if start < 0 or start > end or start >= file_size:
            return -1  # Unsatisfiable Range
        end = min(end, file_size - 1)
        return (start, end)
    except ValueError:
        return None

# --- REQUEST HANDLER ---
class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass  # Suppress default console logs

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, status=200, ctype="text/plain; charset=utf-8"):
        body = text.encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def get_file_path(self, filename):
        safe_download_dir = os.path.abspath(DOWNLOAD_DIR)
        safe_upload_dir = os.path.abspath(UPLOAD_DIR)
        dl_fp = os.path.abspath(os.path.join(safe_download_dir, filename))
        if dl_fp.startswith(safe_download_dir) and os.path.isfile(dl_fp): 
            return dl_fp
        up_fp = os.path.abspath(os.path.join(safe_upload_dir, filename))
        if up_fp.startswith(safe_upload_dir) and os.path.isfile(up_fp): 
            return up_fp
        return None

    def is_authenticated(self):
        """Check if client IP is in allowed sessions or is localhost/host."""
        ip = self.client_address[0]
        if ip in ("127.0.0.1", "localhost", get_ip()):
            return True
        return ip in SESSIONS

    def do_GET(self):
        if getattr(sys, 'frozen', False):
            ASSET_DIR = sys._MEIPASS
        else:
            ASSET_DIR = os.path.dirname(os.path.abspath(__file__))

        # 1. SERVE STATIC ASSETS (No Auth Required)
        if self.path.endswith('.css') or self.path.endswith('.js') or self.path.endswith('.ico') or self.path == '/login.html':
            clean_path = self.path.split('?')[0].lstrip('/')
            fp = os.path.join(ASSET_DIR, clean_path)
            if os.path.exists(fp):
                if clean_path.endswith('.css'): 
                    ctype = 'text/css; charset=utf-8'
                elif clean_path.endswith('.js'): 
                    ctype = 'application/javascript; charset=utf-8'
                elif clean_path.endswith('.ico'): 
                    ctype = 'image/x-icon'
                elif clean_path.endswith('.html'): 
                    ctype = 'text/html; charset=utf-8'
                else: 
                    ctype = 'application/octet-stream'
                
                with open(fp, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Asset not found")
            return

        # 2. SERVE QR CODE
        if self.path == '/qrcode.png' or self.path.startswith('/qrcode.png?'):
            qr_path = os.path.join(BASE_DIR, "qrcode.png")
            if not os.path.exists(qr_path):
                ip = get_ip()
                generate_qr(f"http://{ip}:{ACTUAL_PORT}")
            if os.path.exists(qr_path):
                with open(qr_path, "rb") as f:
                    content = f.read()
                self.send_response(200) 
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "QR Code not ready")
            return

        # 3. AUTHENTICATION ENFORCEMENT
        if not self.is_authenticated():
            if self.path.startswith('/api/'):
                self.send_error(401, "Unauthorized")
                return
            
            # Redirect to Login Page
            login_path = os.path.join(ASSET_DIR, "login.html")
            if os.path.exists(login_path):
                with open(login_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Login page missing")
            return

        # 4. AUTHENTICATED ROUTES
        
        # A. Serve Dashboard (Host or Client)
        if self.path == '/' or self.path.startswith('/?') or self.path == '/index.html':
            client_ip = self.client_address[0]
            host_ip = get_ip()
            is_host = (client_ip in ("127.0.0.1", "localhost", host_ip))
            
            page_file = "host.html" if is_host else "client.html"
            file_path = os.path.join(ASSET_DIR, page_file)

            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Dashboard template not found.")
            return

        # B. API: PIN (Host Only)
        if self.path == '/api/pin':
            if self.client_address[0] in ("127.0.0.1", "localhost", get_ip()):
                ttl = max(0, int(NEXT_CHANGE - time.time()))
                self.send_json({"pin": CURRENT_PIN, "ttl": ttl})
            else:
                self.send_error(403, "Forbidden")
            return

        # C. API: Files List
        if self.path == '/api/files':
            def list_dir(path):
                data = []
                try:
                    if os.path.exists(path):
                        files = sorted(os.listdir(path), key=str.lower)
                        for f in files:
                            fp = os.path.join(path, f)
                            if os.path.isfile(fp):
                                stat = os.stat(fp)
                                ext = os.path.splitext(f)[1]
                                data.append({
                                    "name": f,
                                    "size": stat.st_size,
                                    "mtime": int(stat.st_mtime),
                                    "category": get_category(ext),
                                    "ext": ext.lstrip('.').lower()
                                })
                except Exception: 
                    pass
                return data
            self.send_json({"pc": list_dir(DOWNLOAD_DIR), "mobile": list_dir(UPLOAD_DIR)})
            return

        # D. API: Updates / Poll
        if self.path == '/api/updates':
            with state_lock:
                active_uploads = list(upload_status.values()) if upload_status else None
                current_upload = active_uploads[0] if active_uploads else None
                data = {
                    "events": list(events_queue), 
                    "upload": current_upload,
                    "clipboard_ts": TEXT_TIMESTAMP
                }
            self.send_json(data)
            return

        # E. API: Shared Clipboard (GET)
        if self.path == '/api/text':
            with state_lock:
                data = {
                    "text": SHARED_TEXT,
                    "timestamp": TEXT_TIMESTAMP
                }
            self.send_json(data)
            return

        # F. API: Open Folder (Host Only)
        if self.path.startswith('/api/open'):
            if self.client_address[0] not in ("127.0.0.1", "localhost", get_ip()):
                self.send_error(403, "Forbidden")
                return
            
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            folder_type = params.get('folder', [''])[0]
            target_path = BASE_DIR
            if folder_type == 'received': 
                target_path = UPLOAD_DIR
            elif folder_type == 'shared': 
                target_path = DOWNLOAD_DIR
            open_folder(target_path)
            self.send_text("Opened")
            return

        # G. API: Download All as ZIP
        if self.path.startswith('/api/zip'):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            folder_type = params.get('folder', ['shared'])[0]
            target_dir = UPLOAD_DIR if folder_type == 'received' else DOWNLOAD_DIR
            
            if not os.path.exists(target_dir) or not os.listdir(target_dir):
                self.send_error(404, "No files found to archive")
                return

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(target_dir):
                    for file in files:
                        abs_p = os.path.join(root, file)
                        rel_p = os.path.relpath(abs_p, target_dir)
                        zf.write(abs_p, rel_p)
            
            zip_bytes = zip_buf.getvalue()
            zip_fn = f"PyShare_{folder_type.capitalize()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{zip_fn}"')
            self.send_header("Content-Length", str(len(zip_bytes)))
            self.end_headers()
            self.wfile.write(zip_bytes)
            return

        # H. File View & Download (With HTTP 206 Partial Content / Range Requests)
        if self.path.startswith('/view/') or self.path.startswith('/download/'):
            is_view = self.path.startswith('/view/')
            prefix = 6 if is_view else 10
            
            raw_path = self.path[prefix:].split('?')[0]
            raw_fn = urllib.parse.unquote(raw_path)
            fn = os.path.basename(raw_fn)
            
            fp = self.get_file_path(fn)
            if not fp or not os.path.isfile(fp):
                self.send_error(404, "File not found")
                return

            file_size = os.path.getsize(fp)
            ctype, _ = mimetypes.guess_type(fp)
            if ctype is None: 
                ctype = 'application/octet-stream'

            range_header = self.headers.get("Range")
            byte_range = parse_range_header(range_header, file_size)

            if byte_range == -1:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            if byte_range is not None:
                start, end = byte_range
                content_len = (end - start) + 1
                self.send_response(206, "Partial Content")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(content_len))
                self.send_header("Accept-Ranges", "bytes")
                if not is_view:
                    self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                self.end_headers()
                
                with open(fp, 'rb') as f:
                    f.seek(start)
                    remain = content_len
                    while remain > 0:
                        chunk = f.read(min(remain, 65536))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remain -= len(chunk)
            else:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(file_size))
                if not is_view:
                    self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                self.end_headers()
                with open(fp, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
            return

        # I. Server Shutdown
        if self.path == '/shutdown':
            if self.client_address[0] not in ("127.0.0.1", "localhost", get_ip()):
                self.send_error(403, "Forbidden")
                return
            self.send_text("Shutting down")
            def kill():
                global zc, httpd
                if zc:
                    try:
                        zc.unregister_all_services()
                        zc.close()
                    except Exception: pass
                if httpd:
                    try:
                        httpd.shutdown()
                        httpd.server_close()
                    except Exception: pass
                os._exit(0)
            threading.Thread(target=kill, daemon=True).start()
            return

        return super().do_GET()

    def do_POST(self):
        # 1. HANDLE LOGIN (Accept CURRENT_PIN or PREVIOUS_PIN for grace window)
        if self.path == '/login':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8', errors='ignore')
            params = urllib.parse.parse_qs(body)
            pin_input = params.get('pin', [''])[0].strip()
            
            with state_lock:
                valid_pins = {CURRENT_PIN, PREVIOUS_PIN}
            
            if pin_input in valid_pins and pin_input != "":
                SESSIONS.add(self.client_address[0])
                add_event(f"Device connected: {self.client_address[0]}")
                self.send_text("OK")
            else:
                self.send_text("Invalid PIN", status=401)
            return

        # 2. CHECK AUTH FOR PROTECTED ACTIONS
        if not self.is_authenticated():
            self.send_error(401, "Unauthorized")
            return

        # 3. HANDLE SHARED CLIPBOARD POST (/api/text)
        if self.path == '/api/text':
            global SHARED_TEXT, TEXT_TIMESTAMP
            length = int(self.headers.get('Content-Length', 0))
            if length > 1024 * 64:
                self.send_error(413, "Clipboard payload too large (Max 64KB)")
                return
            body = self.rfile.read(length).decode('utf-8', errors='ignore')
            try:
                data = json.loads(body)
                new_text = str(data.get("text", "")).strip()
            except Exception:
                new_text = body.strip()

            with state_lock:
                SHARED_TEXT = new_text
                TEXT_TIMESTAMP = int(time.time())

            snippet = (new_text[:35] + "...") if len(new_text) > 35 else new_text
            add_event(f"Clipboard updated: {snippet}")
            self.send_json({"status": "ok", "timestamp": TEXT_TIMESTAMP})
            return

        # 4. HANDLE FILE DELETION (/api/delete - Host Only)
        if self.path == '/api/delete':
            if self.client_address[0] not in ("127.0.0.1", "localhost", get_ip()):
                self.send_error(403, "Host Only")
                return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8', errors='ignore')
            try:
                data = json.loads(body)
                fn = os.path.basename(data.get('filename', ''))
                folder = data.get('folder', 'shared')
                target_dir = UPLOAD_DIR if folder == 'received' else DOWNLOAD_DIR
                target_fp = os.path.abspath(os.path.join(target_dir, fn))
                if target_fp.startswith(os.path.abspath(target_dir)) and os.path.isfile(target_fp):
                    os.remove(target_fp)
                    add_event(f"Deleted: {fn}")
                    self.send_json({"status": "ok", "deleted": fn})
                    return
                else:
                    self.send_error(404, "File not found")
                    return
            except Exception as e:
                self.send_error(500, str(e))
                return

        # 5. HANDLE FILE UPLOAD (Collision-safe + progress tracking)
        client_ip = self.client_address[0]
        try:
            is_host_upload = "dest=host" in self.path
            target_dir = DOWNLOAD_DIR if is_host_upload else UPLOAD_DIR

            encoded_fn = self.headers.get('X-File-Name')
            if not encoded_fn:
                self.send_error(400, "Missing X-File-Name header")
                return
                
            raw_fn = os.path.basename(urllib.parse.unquote(encoded_fn))
            length = int(self.headers.get('Content-Length', 0))
            
            os.makedirs(target_dir, exist_ok=True)

            # Prevent silent overwrite with automatic numbering: "file (1).ext"
            out_path = get_unique_filepath(target_dir, raw_fn)
            actual_fn = os.path.basename(out_path)
            
            remain = length
            total_size = length
            
            if not is_host_upload: 
                add_event(f"Receiving: {actual_fn}")
            
            with open(out_path, 'wb') as f:
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536))
                    if not chunk: 
                        break
                    f.write(chunk)
                    remain -= len(chunk)
                    if not is_host_upload: 
                        set_upload_status(client_ip, actual_fn, total_size - remain, total_size)
            
            clear_upload_status(client_ip)
            msg = f"Added to Shared: {actual_fn}" if is_host_upload else f"File received: {actual_fn}"
            add_event(msg)
            
            self.send_json({"status": "ok", "filename": actual_fn})
            
        except Exception as e:
            clear_upload_status(client_ip)
            self.send_error(500, str(e))

# --- SERVER CONTROLLER ---
def start_server():
    global BASE_DIR, UPLOAD_DIR, DOWNLOAD_DIR, httpd, ACTUAL_PORT, zc
    
    print("\n" + "="*45)
    print("[*] Starting PyShare...")

    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        BASE_DIR = os.path.join(desktop, "PyShare_Files")
        UPLOAD_DIR = os.path.join(BASE_DIR, "Received_Files")
        DOWNLOAD_DIR = os.path.join(BASE_DIR, "Shared_Files")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    except Exception as e:
        print(f"[!] Storage Directory Initialization Error: {e}")
        return

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(START_PORT, START_PORT + 10):
        try:
            server = socketserver.ThreadingTCPServer(("", port), FinalFileHandler)
            ACTUAL_PORT = port
            httpd = server
            break
        except OSError: 
            continue

    if not httpd: 
        print("[!] Could not bind to any available port.")
        return

    # Start PIN Rotation
    start_pin_rotator()

    ip = get_ip()
    url = f'http://{ip}:{ACTUAL_PORT}'
    
    # Generate Dynamic QR code on startup
    generate_qr(url)

    # mDNS Service Broadcast
    try:
        zc = Zeroconf()
        desc = {'app': 'PyShare', 'device': socket.gethostname(), 'url': url}
        info = ServiceInfo(
            "_pyshare._tcp.local.",
            f"{socket.gethostname()}._pyshare._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=ACTUAL_PORT,
            properties=desc,
            server=f"{socket.gethostname()}.local."
        )
        zc.register_service(info)
        print(f"[+] mDNS Service Active: _pyshare._tcp.local.")
    except Exception as e:
        print(f"[*] mDNS Broadcast Notice: {e}")

    print(f"[+] PyShare Server Live at: {url}")
    print(f"[+] Local Storage: {BASE_DIR}")
    print("="*45 + "\n")
    
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt: 
        print("\n[-] Shutting down server...")
    finally:
        if zc:
            try:
                zc.unregister_all_services()
                zc.close()
            except Exception: pass
        if httpd:
            try:
                httpd.server_close()
            except Exception: pass
        print("[-] PyShare Stopped.")

if __name__ == "__main__":
    start_server()