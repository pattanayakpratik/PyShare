from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser
import os
import http.server
import socketserver
import socket
import pyqrcode
import urllib.parse
import urllib.request
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
import queue
import pyperclip
import re
import secrets
try:
    import ifaddr
except ImportError:
    ifaddr = None

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
UPLOAD_DIR = ""    # Received from Clients (Client Uploads)
DOWNLOAD_DIR = ""  # Shared by Host (Host Shared Files)
ACTUAL_PORT = START_PORT
zc = None

# --- PERSISTENT USER CONFIGURATION ---
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".pyshare_config.json")

def get_default_directories():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    base = os.path.join(desktop, "PyShare_Files")
    return {
        "shared_dir": os.path.join(base, "Shared_Files"),
        "received_dir": os.path.join(base, "Received_Files"),
        "client_download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "theme": "dark"
    }

def load_app_config():
    defaults = get_default_directories()
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    defaults.update(saved)
        except Exception:
            pass
    return defaults

def save_app_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[*] Could not save config: {e}")

def set_custom_shared_dir(path):
    global DOWNLOAD_DIR
    if path and os.path.isdir(path):
        DOWNLOAD_DIR = os.path.abspath(path)
        cfg = load_app_config()
        cfg["shared_dir"] = DOWNLOAD_DIR
        save_app_config(cfg)
        broadcast_sse("files", get_files_data())
        return True
    return False

def set_custom_received_dir(path):
    global UPLOAD_DIR
    if path and os.path.isdir(path):
        UPLOAD_DIR = os.path.abspath(path)
        cfg = load_app_config()
        cfg["received_dir"] = UPLOAD_DIR
        save_app_config(cfg)
        broadcast_sse("files", get_files_data())
        return True
    return False

def init_directories():
    global BASE_DIR, UPLOAD_DIR, DOWNLOAD_DIR
    cfg = load_app_config()
    defs = get_default_directories()
    DOWNLOAD_DIR = os.path.abspath(cfg.get("shared_dir", defs["shared_dir"]))
    UPLOAD_DIR = os.path.abspath(cfg.get("received_dir", defs["received_dir"]))
    BASE_DIR = os.path.dirname(DOWNLOAD_DIR)
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    except Exception:
        pass

init_directories()

# --- SECURITY & STATE ---
CURRENT_PIN = "0000"
PREVIOUS_PIN = ""  # 30-second grace window to prevent edge-case rejections
NEXT_CHANGE = 0    # Track timestamp when PIN rotates
SESSIONS = set()   # Stores authenticated client session tokens
SHARED_TEXT = ""   # In-memory shared clipboard / quick link
TEXT_TIMESTAMP = 0 # Timestamp of last clipboard change
state_lock = threading.Lock()
events_queue = [] 
upload_status = {}

# --- RATE LIMITING & CONCURRENCY CONTROLS ---
login_attempts = {}       # client_ip -> {"count": int, "lockout_until": float}
login_lock = threading.Lock()
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 30     # seconds lockout after repeated failures
zip_semaphore = threading.Semaphore(1)  # Maximum 1 active ZIP generation at a time

# --- SERVER-SENT EVENTS (SSE) REAL-TIME PUSH ENGINE ---
sse_subscribers = set()
sse_lock = threading.Lock()

def add_sse_subscriber(q):
    with sse_lock:
        sse_subscribers.add(q)

def remove_sse_subscriber(q):
    with sse_lock:
        sse_subscribers.discard(q)

def broadcast_sse(event_type, data):
    """Pushes a typed event packet down to all active SSE subscribers."""
    with sse_lock:
        dead = []
        for q in sse_subscribers:
            try:
                q.put_nowait((event_type, data))
            except queue.Full:
                dead.append(q)
        for q in dead:
            sse_subscribers.discard(q)

# --- CLOUDFLARE TUNNEL (PUBLIC INTERNET MODE) ---
TUNNEL_PROC = None
TUNNEL_URL = None
TUNNEL_STATUS = "idle"  # idle | downloading | starting | active | error
TUNNEL_LOCK = threading.Lock()

def get_cloudflared_path():
    """Locate or download cloudflared executable."""
    cf = shutil.which("cloudflared")
    if cf:
        return cf
    desktop_bin = os.path.join(os.path.expanduser("~"), "Desktop", "PyShare_Files", "bin", "cloudflared.exe")
    if os.path.exists(desktop_bin):
        return desktop_bin
    local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "cloudflared.exe")
    if os.path.exists(local_bin):
        return local_bin
    return desktop_bin

def download_cloudflared(dest_path):
    """Download standalone cloudflared binary if missing."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    temp_path = dest_path + ".tmp"
    try:
        urllib.request.urlretrieve(url, temp_path)
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.replace(temp_path, dest_path)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise

def tunnel_worker():
    global TUNNEL_PROC, TUNNEL_URL, TUNNEL_STATUS
    try:
        bin_path = get_cloudflared_path()
        if not os.path.exists(bin_path):
            with TUNNEL_LOCK:
                TUNNEL_STATUS = "downloading"
            broadcast_sse("tunnel", {"status": "downloading", "url": None})
            download_cloudflared(bin_path)

        with TUNNEL_LOCK:
            TUNNEL_STATUS = "starting"
        broadcast_sse("tunnel", {"status": "starting", "url": None})

        creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        cmd = [bin_path, "tunnel", "--url", f"http://127.0.0.1:{ACTUAL_PORT}"]
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creationflags
        )
        
        with TUNNEL_LOCK:
            TUNNEL_PROC = proc

        found_url = None
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if m:
                found_url = m.group(0)
                with TUNNEL_LOCK:
                    TUNNEL_URL = found_url
                    TUNNEL_STATUS = "active"
                generate_qr(TUNNEL_URL)
                broadcast_sse("tunnel", {"status": "active", "url": TUNNEL_URL})
                add_event(f"Public Internet Mode Active: {TUNNEL_URL}")
                break

        if not found_url:
            with TUNNEL_LOCK:
                if TUNNEL_STATUS != "idle":
                    TUNNEL_STATUS = "error"
                    broadcast_sse("tunnel", {"status": "error", "url": None})
                    add_event("Failed to establish Internet Tunnel")
            return

        # Keep monitoring process
        proc.wait()

    except Exception as e:
        with TUNNEL_LOCK:
            if TUNNEL_STATUS != "idle":
                TUNNEL_STATUS = "error"
                broadcast_sse("tunnel", {"status": "error", "url": None})
                add_event(f"Tunnel Error: {e}")
    finally:
        with TUNNEL_LOCK:
            if TUNNEL_STATUS not in ("idle", "error"):
                TUNNEL_STATUS = "idle"
                TUNNEL_URL = None
                TUNNEL_PROC = None
                generate_qr()
                broadcast_sse("tunnel", {"status": "idle", "url": None})

def start_tunnel():
    global TUNNEL_STATUS
    with TUNNEL_LOCK:
        if TUNNEL_STATUS in ("starting", "active"):
            return
        TUNNEL_STATUS = "starting"
    t = threading.Thread(target=tunnel_worker, daemon=True)
    t.start()

def stop_tunnel():
    global TUNNEL_PROC, TUNNEL_URL, TUNNEL_STATUS
    with TUNNEL_LOCK:
        TUNNEL_STATUS = "idle"
        TUNNEL_URL = None
        if TUNNEL_PROC:
            try:
                TUNNEL_PROC.terminate()
                TUNNEL_PROC.wait(timeout=2)
            except Exception:
                try:
                    TUNNEL_PROC.kill()
                except Exception:
                    pass
            TUNNEL_PROC = None
    generate_qr()
    broadcast_sse("tunnel", {"status": "idle", "url": None})
    add_event("Reverted to Local Wi-Fi Mode")

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
mimetypes.add_type("application/manifest+json", ".json")

# --- PIN MANAGER WITH REAL-TIME TICKER ---
def pin_rotator():
    """Rotates the 4-digit PIN every 30 seconds and broadcasts countdown every second to SSE clients."""
    global CURRENT_PIN, PREVIOUS_PIN, NEXT_CHANGE
    while True:
        now = time.time()
        with state_lock:
            if now >= NEXT_CHANGE:
                PREVIOUS_PIN = CURRENT_PIN
                CURRENT_PIN = f"{random.randint(1000, 9999)}"
                NEXT_CHANGE = now + 30
            ttl = max(0, int(NEXT_CHANGE - now))
            pin_data = {"pin": CURRENT_PIN, "ttl": ttl}
        broadcast_sse("pin", pin_data)
        time.sleep(1)

def start_pin_rotator():
    t = threading.Thread(target=pin_rotator, daemon=True)
    t.start()

# --- STATE MANAGEMENT ---
def add_event(msg):
    with state_lock:
        t = time.strftime("%H:%M:%S")
        ev = {"time": t, "msg": msg}
        events_queue.append(ev)
        if len(events_queue) > 60:
            events_queue.pop(0)
    broadcast_sse("log", ev)

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
_cached_ip = None
_cached_ip_time = 0

def get_ip():
    """Detect the physical Wi-Fi / LAN IP, ignoring virtual / bridge adapters (WSL, Docker, VirtualBox)."""
    global _cached_ip, _cached_ip_time
    now = time.time()
    if _cached_ip and (now - _cached_ip_time < 10):
        return _cached_ip
    try:
        global ifaddr
        if ifaddr is None:
            import ifaddr
        adapters = ifaddr.get_adapters()
        virtual_keywords = ['virtual', 'vethernet', 'wsl', 'docker', 'vmware', 'vbox', 'pseudo', 'loopback', 'teredo']
        
        candidates = []
        for adapter in adapters:
            name_lower = adapter.name.lower()
            nice_lower = getattr(adapter, 'nice_name', '').lower()
            if any(vk in name_lower or vk in nice_lower for vk in virtual_keywords):
                continue
            for ip_info in adapter.ips:
                if isinstance(ip_info.ip, str):
                    ip = ip_info.ip
                    if ip.startswith('127.') or ip.startswith('169.254.'):
                        continue
                    if ip.startswith('192.168.'):
                        candidates.append((1, ip))
                    elif ip.startswith('10.'):
                        candidates.append((2, ip))
                    elif ip.startswith('172.'):
                        parts = ip.split('.')
                        if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
                            candidates.append((3, ip))
        
        if candidates:
            candidates.sort(key=lambda x: x[0])
            _cached_ip = candidates[0][1]
            _cached_ip_time = now
            return _cached_ip
    except Exception:
        pass

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    _cached_ip = ip
    _cached_ip_time = now
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

# Pre-compressed file formats where re-compression wastes CPU with zero size gain
PRECOMPRESSED_EXTS = {
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.avif',
    # Video
    '.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.wmv', '.m4v', '.3gp',
    # Audio
    '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.wma', '.opus',
    # Archives & Packages
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.zst', '.apk', '.dmg', '.iso',
    # Compressed Documents
    '.pdf', '.docx', '.xlsx', '.pptx'
}

def get_unique_filepath(directory, filename):
    """Avoid silent overwrite: append (1), (2), etc. if file already exists."""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base} ({counter}){ext}")
        counter += 1
    return candidate

def get_qr_path():
    """Returns the dynamic QR code image path, creating parent directory or falling back to temp dir."""
    target_dir = BASE_DIR if (BASE_DIR and os.path.isdir(BASE_DIR)) else tempfile.gettempdir()
    if BASE_DIR and not os.path.exists(BASE_DIR):
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
            target_dir = BASE_DIR
        except Exception:
            target_dir = tempfile.gettempdir()
    return os.path.join(target_dir, "qrcode.png")

def generate_qr(url=None):
    """Generates a dynamic QR Code pointing to the current server URL or tunnel URL."""
    try:
        if url is None:
            if TUNNEL_URL:
                url = TUNNEL_URL
            else:
                ip = get_ip()
                url = f"http://{ip}:{ACTUAL_PORT}"
        qr_path = get_qr_path()

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

def list_dir(path):
    data = []
    try:
        if os.path.exists(path):
            files = sorted(os.listdir(path), key=str.lower)
            for f in files:
                if f.endswith('.part') or f.endswith('.tmp'):
                    continue
                fp = os.path.join(path, f)
                if os.path.isfile(fp):
                    stat = os.stat(fp)
                    ext = os.path.splitext(f)[1]
                    data.append({
                        "name": f,
                        "size": stat.st_size,
                        "mtime": int(stat.st_mtime),
                        "category": get_category(ext),
                        "ext": ext.lstrip('.').lower(),
                        "path": fp
                    })
    except Exception: 
        pass
    return data

# --- QUICK SHARE STAGED FILES REGISTRY ---
# Zero-copy sharing: files stream directly from their original disk paths
STAGED_FILES = {}  # filename -> dict(name, path, size, mtime, category, ext)
STAGED_LOCK = threading.RLock()

def stage_file(filepath):
    """Register a specific file to share without duplicating it on disk."""
    if not filepath or not os.path.isfile(filepath):
        return False
    abs_path = os.path.abspath(filepath)
    fn = os.path.basename(abs_path)
    try:
        stat = os.stat(abs_path)
        ext = os.path.splitext(fn)[1]
        with STAGED_LOCK:
            STAGED_FILES[fn] = {
                "name": fn,
                "path": abs_path,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "category": get_category(ext),
                "ext": ext.lstrip('.').lower()
            }
        broadcast_sse("files", get_files_data())
        return True
    except Exception as e:
        print(f"[*] Could not stage file {filepath}: {e}")
        return False

def stage_files(filepaths):
    """Register multiple files or directories recursively."""
    added = 0
    with STAGED_LOCK:
        for p in filepaths:
            if not p:
                continue
            abs_p = os.path.abspath(p)
            if os.path.isfile(abs_p):
                fn = os.path.basename(abs_p)
                try:
                    stat = os.stat(abs_p)
                    ext = os.path.splitext(fn)[1]
                    STAGED_FILES[fn] = {
                        "name": fn,
                        "path": abs_p,
                        "size": stat.st_size,
                        "mtime": int(stat.st_mtime),
                        "category": get_category(ext),
                        "ext": ext.lstrip('.').lower()
                    }
                    added += 1
                except Exception:
                    pass
            elif os.path.isdir(abs_p):
                for root, _, files in os.walk(abs_p):
                    for f in files:
                        if f.endswith('.part') or f.endswith('.tmp'):
                            continue
                        fp = os.path.join(root, f)
                        try:
                            stat = os.stat(fp)
                            ext = os.path.splitext(f)[1]
                            STAGED_FILES[f] = {
                                "name": f,
                                "path": fp,
                                "size": stat.st_size,
                                "mtime": int(stat.st_mtime),
                                "category": get_category(ext),
                                "ext": ext.lstrip('.').lower()
                            }
                            added += 1
                        except Exception:
                            pass
    if added > 0:
        broadcast_sse("files", get_files_data())
    return added

def unstage_file(filename):
    """Remove a file from the shared list (does NOT delete original file from disk)."""
    with STAGED_LOCK:
        removed = STAGED_FILES.pop(filename, None)
    if removed:
        broadcast_sse("files", get_files_data())
        return True
    return False

def clear_staged_files():
    """Unstage all shared files."""
    with STAGED_LOCK:
        STAGED_FILES.clear()
    broadcast_sse("files", get_files_data())

def get_staged_files():
    """Return list of valid staged file dictionaries."""
    with STAGED_LOCK:
        valid = []
        for fn, item in list(STAGED_FILES.items()):
            if os.path.isfile(item["path"]):
                valid.append(item)
            else:
                STAGED_FILES.pop(fn, None)
        return list(valid)

def get_files_data():
    host_files = get_staged_files()
    client_files = list_dir(UPLOAD_DIR)
    return {
        "host": host_files,
        "client": client_files,
        "pc": host_files,
        "mobile": client_files
    }

# --- REQUEST HANDLER ---
def get_asset_dir():
    """Returns the directory containing static web templates and assets."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        web_sub = os.path.join(base, "web")
        if os.path.isdir(web_sub):
            return web_sub
        return base
    here = os.path.dirname(os.path.abspath(__file__))
    sibling_web = os.path.abspath(os.path.join(here, "..", "web"))
    if os.path.isdir(sibling_web):
        return sibling_web
    child_web = os.path.abspath(os.path.join(here, "web"))
    if os.path.isdir(child_web):
        return child_web
    return here


class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass  # Suppress default console logs

    def send_security_headers(self):
        """Append defense-in-depth HTTP security headers."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, status=200, ctype="text/plain; charset=utf-8"):
        body = text.encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def get_file_path(self, filename):
        if not filename or filename.endswith('.part') or filename.endswith('.tmp'):
            return None

        # 1. Check Staged Files (Quick Share: Zero-RAM copy, stream direct from original path)
        with STAGED_LOCK:
            if filename in STAGED_FILES:
                fp = STAGED_FILES[filename]["path"]
                if os.path.isfile(fp):
                    return fp

        # 2. Check Shared Directory
        safe_download_dir = os.path.abspath(DOWNLOAD_DIR)
        dl_fp = os.path.abspath(os.path.join(safe_download_dir, filename))
        if os.path.commonpath([safe_download_dir, dl_fp]) == safe_download_dir and os.path.isfile(dl_fp): 
            return dl_fp

        # 3. Check Received Directory
        safe_upload_dir = os.path.abspath(UPLOAD_DIR)
        up_fp = os.path.abspath(os.path.join(safe_upload_dir, filename))
        if os.path.commonpath([safe_upload_dir, up_fp]) == safe_upload_dir and os.path.isfile(up_fp): 
            return up_fp

        return None

    def get_session_token(self):
        cookie_str = self.headers.get("Cookie", "")
        for item in cookie_str.split(";"):
            item = item.strip()
            if item.startswith("pyshare_session="):
                return item.split("pyshare_session=")[1].strip()
        return None

    def get_client_ip(self):
        # Only trust reverse-proxy headers if the incoming socket connection is from local loopback
        if self.client_address[0] in ("127.0.0.1", "localhost", "::1"):
            cf_ip = self.headers.get("CF-Connecting-IP")
            if cf_ip:
                return cf_ip.strip()
            x_forwarded = self.headers.get("X-Forwarded-For")
            if x_forwarded:
                return x_forwarded.split(",")[0].strip()
        return self.client_address[0]

    def is_authenticated(self):
        """Check if client is authenticated via session token cookie or direct host access."""
        if self.is_host_client():
            return True
        token = self.get_session_token()
        if token:
            with state_lock:
                return token in SESSIONS
        return False

    def is_host_client(self):
        # Incoming requests through Cloudflare tunnel or reverse proxy are external clients, not the host
        if self.headers.get("CF-Connecting-IP") or self.headers.get("CF-Ray") or self.headers.get("X-Forwarded-For") or self.headers.get("X-Forwarded-Proto"):
            return False

        # Verify remote address is local loopback or local host IP
        if self.client_address[0] not in ("127.0.0.1", "localhost", "::1", get_ip()):
            return False

        # Allow top-level browser page navigation (GET /) so the Host is never locked out of host.html
        is_top_nav = (self.command == "GET" and self.path in ("/", "/index.html") and self.headers.get("Sec-Fetch-Mode") == "navigate")
        if not is_top_nav:
            sec_fetch = self.headers.get("Sec-Fetch-Site")
            if sec_fetch == "cross-site":
                return False
            allowed_hosts = ("127.0.0.1", "localhost", "::1", get_ip(), socket.gethostname().lower(), f"{socket.gethostname().lower()}.local")
            for hdr in ("Origin", "Referer"):
                val = self.headers.get(hdr)
                if val:
                    try:
                        host = urllib.parse.urlparse(val).hostname
                        if not host or host.lower() not in allowed_hosts:
                            return False
                    except Exception:
                        return False
        return True

    def do_GET(self):
        global SHARED_TEXT, TEXT_TIMESTAMP
        ASSET_DIR = get_asset_dir()

        # 1. SERVE QR CODE (Must precede static assets)
        if self.path == '/qrcode.png' or self.path.startswith('/qrcode.png?'):
            qr_path = get_qr_path()

            if not os.path.exists(qr_path):
                generate_qr()
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

        # 2. SERVE P2P SUITE & USER GUIDE (No Auth Required)
        if self.path in ('/p2p', '/p2p/', '/p2p.html', '/index.html') or self.path.startswith(('/p2p?', '/p2p.html?', '/index.html?')):
            fp = os.path.join(ASSET_DIR, "index.html")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(content)
                return

        if self.path in ('/guide', '/guide/', '/guide.html') or self.path.startswith('/guide?') or self.path.startswith('/guide.html?'):
            fp = os.path.join(ASSET_DIR, "guide.html")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(content)
                return

        asset_exts = ('.css', '.js', '.ico', '.png', '.jpg', '.jpeg', '.svg', '.webp', '.json')
        raw_clean = urllib.parse.unquote(self.path.split('?')[0]).lstrip('/')
        # Strictly reject directory traversal sequences
        if '..' in raw_clean or '\\' in raw_clean:
            self.send_error(400, "Bad Request")
            return

        if not raw_clean.startswith(('view/', 'download/', 'api/')):
            if any(raw_clean.endswith(ext) for ext in asset_exts) or raw_clean in ('login.html', 'manifest.json', 'sw.js', 'index.html', 'guide.html'):
                safe_asset_dir = os.path.abspath(ASSET_DIR)
                fp = os.path.abspath(os.path.join(safe_asset_dir, raw_clean))
                # Validate the target file resides strictly within ASSET_DIR
                if os.path.commonpath([safe_asset_dir, fp]) == safe_asset_dir and os.path.isfile(fp):
                    if raw_clean.endswith('.css'): 
                        ctype = 'text/css; charset=utf-8'
                    elif raw_clean.endswith('.js') or raw_clean == 'sw.js': 
                        ctype = 'application/javascript; charset=utf-8'
                    elif raw_clean.endswith('.json') or raw_clean == 'manifest.json': 
                        ctype = 'application/manifest+json; charset=utf-8'
                    elif raw_clean.endswith('.ico'): 
                        ctype = 'image/x-icon'
                    elif raw_clean.endswith('.png'): 
                        ctype = 'image/png'
                    elif raw_clean.endswith(('.jpg', '.jpeg')): 
                        ctype = 'image/jpeg'
                    elif raw_clean.endswith('.svg'): 
                        ctype = 'image/svg+xml'
                    elif raw_clean.endswith('.webp'): 
                        ctype = 'image/webp'
                    elif raw_clean.endswith('.html'): 
                        ctype = 'text/html; charset=utf-8'
                    else: 
                        ctype = 'application/octet-stream'
                    
                    with open(fp, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_security_headers()
                    self.end_headers()
                    self.wfile.write(content)
                    return
                elif raw_clean in ('login.html', 'manifest.json', 'sw.js', 'index.html', 'guide.html'):
                    self.send_error(404, "Asset not found")
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
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Login page missing")
            return

        # 4. AUTHENTICATED ROUTES
        
        # A. Serve Dashboard (Host or Client)
        if self.path == '/' or self.path.startswith('/?'):
            is_host = self.is_host_client()
            page_file = "host.html" if is_host else "client.html"
            file_path = os.path.join(ASSET_DIR, page_file)

            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Dashboard template not found.")
            return

        # B. API: Server-Sent Events (SSE) Stream
        if self.path == '/api/events':
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            q = queue.Queue(maxsize=50)
            add_sse_subscriber(q)

            # Send initial state snapshot immediately
            try:
                # 1. File list snapshot
                files_json = json.dumps(get_files_data())
                self.wfile.write(f"event: files\ndata: {files_json}\n\n".encode('utf-8'))
                
                # 2. Clipboard snapshot
                with state_lock:
                    clip_json = json.dumps({"text": SHARED_TEXT, "timestamp": TEXT_TIMESTAMP})
                self.wfile.write(f"event: clipboard\ndata: {clip_json}\n\n".encode('utf-8'))
                
                # 3. PIN snapshot (Host only)
                if self.is_host_client():
                    with state_lock:
                        ttl = max(0, int(NEXT_CHANGE - time.time()))
                        pin_json = json.dumps({"pin": CURRENT_PIN, "ttl": ttl})
                    self.wfile.write(f"event: pin\ndata: {pin_json}\n\n".encode('utf-8'))

                # 4. Tunnel snapshot (Host only)
                if self.is_host_client():
                    with TUNNEL_LOCK:
                        tun_json = json.dumps({"status": TUNNEL_STATUS, "url": TUNNEL_URL})
                    self.wfile.write(f"event: tunnel\ndata: {tun_json}\n\n".encode('utf-8'))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, Exception):
                remove_sse_subscriber(q)
                return

            try:
                while True:
                    try:
                        event_type, event_data = q.get(timeout=10)
                        msg = f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n".encode('utf-8')
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, Exception):
                pass
            finally:
                remove_sse_subscriber(q)
            return

        # C. API: Direct Windows Clipboard Sync (Host Only)
        if self.path == '/api/sync_clipboard':
            if not self.is_host_client():
                self.send_error(403, "Host Only")
                return
            try:
                clip_val = pyperclip.paste().strip()
                if clip_val:
                    with state_lock:
                        SHARED_TEXT = clip_val
                        TEXT_TIMESTAMP = int(time.time())
                    snippet = (clip_val[:35] + "...") if len(clip_val) > 35 else clip_val
                    add_event(f"Synced Host Clipboard: {snippet}")
                    broadcast_sse("clipboard", {"text": SHARED_TEXT, "timestamp": TEXT_TIMESTAMP})
                    self.send_json({"status": "ok", "text": SHARED_TEXT, "timestamp": TEXT_TIMESTAMP})
                else:
                    self.send_json({"status": "empty", "message": "Host clipboard is empty"})
            except Exception as e:
                self.send_error(500, str(e))
            return

        # D. API: Tunnel Status (Host Only)
        if self.path == '/api/tunnel':
            if not self.is_host_client():
                self.send_error(403, "Host Only")
                return
            with TUNNEL_LOCK:
                self.send_json({"status": TUNNEL_STATUS, "url": TUNNEL_URL})
            return

        # D. API: PIN (Host Only)
        if self.path == '/api/pin':
            if self.is_host_client():
                ttl = max(0, int(NEXT_CHANGE - time.time()))
                self.send_json({"pin": CURRENT_PIN, "ttl": ttl})
            else:
                self.send_error(403, "Forbidden")
            return

        # E. API: Files List
        if self.path == '/api/files':
            self.send_json(get_files_data())
            return

        # F. API: Updates / Poll (Fallback)
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

        # G. API: Shared Clipboard (GET)
        if self.path in ('/api/text', '/api/clipboard'):
            with state_lock:
                data = {
                    "text": SHARED_TEXT,
                    "timestamp": TEXT_TIMESTAMP
                }
            self.send_json(data)
            return

        # H. API: Open Folder (Host Only)
        if self.path.startswith('/api/open'):
            if not self.is_host_client():
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

        # I. API: Download All as ZIP (Zero-RAM Disk-Backed Stream with DoS Protection)
        if self.path.startswith('/api/zip') or self.path.startswith('/download-all'):
            acquired = zip_semaphore.acquire(blocking=False)
            if not acquired:
                self.send_error(429, "An archive is already being generated. Please wait.")
                return

            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            folder_type = params.get('folder', ['shared'])[0]
            
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_zip_path = temp_zip.name
            temp_zip.close()

            try:
                files_to_pack = []  # (abs_path, arcname)
                if folder_type == 'received':
                    target_dir = UPLOAD_DIR
                    if os.path.exists(target_dir):
                        for root, _, files in os.walk(target_dir):
                            for file in files:
                                if file.endswith('.part') or file.endswith('.tmp'):
                                    continue
                                abs_p = os.path.join(root, file)
                                rel_p = os.path.relpath(abs_p, target_dir)
                                files_to_pack.append((abs_p, rel_p))
                else:
                    # Shared files: prefer STAGED_FILES if any
                    with STAGED_LOCK:
                        if STAGED_FILES:
                            for fn, item in STAGED_FILES.items():
                                if os.path.isfile(item["path"]):
                                    files_to_pack.append((item["path"], fn))
                    if not files_to_pack and os.path.exists(DOWNLOAD_DIR):
                        for root, _, files in os.walk(DOWNLOAD_DIR):
                            for file in files:
                                if file.endswith('.part') or file.endswith('.tmp'):
                                    continue
                                abs_p = os.path.join(root, file)
                                rel_p = os.path.relpath(abs_p, DOWNLOAD_DIR)
                                files_to_pack.append((abs_p, rel_p))

                if not files_to_pack:
                    zip_semaphore.release()
                    self.send_error(404, "No files found to archive")
                    return

                with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for abs_p, arcname in files_to_pack:
                        _, ext = os.path.splitext(arcname)
                        comp_mode = zipfile.ZIP_STORED if ext.lower() in PRECOMPRESSED_EXTS else zipfile.ZIP_DEFLATED
                        zf.write(abs_p, arcname, compress_type=comp_mode)

                zip_size = os.path.getsize(temp_zip_path)
                zip_fn = f"PyShare_{folder_type.capitalize()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{zip_fn}"')
                self.send_header("Content-Length", str(zip_size))
                self.send_security_headers()
                self.end_headers()

                with open(temp_zip_path, 'rb') as f:
                    while True:
                        chunk = f.read(262144)  # 256KB chunks
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                self.send_error(500, f"Error creating ZIP: {e}")
            finally:
                zip_semaphore.release()
                if os.path.exists(temp_zip_path):
                    try:
                        os.unlink(temp_zip_path)
                    except Exception:
                        pass
            return

        # J. File View & Download (With HTTP 206 Partial Content / Range Requests)
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

            # Defense-in-depth: Sandbox active HTML/SVG file views to eliminate Stored XSS
            is_active_scriptable = fn.lower().endswith(('.html', '.htm', '.svg', '.xml', '.xhtml'))

            range_header = self.headers.get("Range")
            byte_range = parse_range_header(range_header, file_size)

            if byte_range == -1:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.send_security_headers()
                self.end_headers()
                return

            try:
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
                    elif is_active_scriptable:
                        self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox")
                    self.send_security_headers()
                    self.end_headers()
                    
                    with open(fp, 'rb') as f:
                        f.seek(start)
                        remain = content_len
                        while remain > 0:
                            chunk = f.read(min(remain, 262144))
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
                    elif is_active_scriptable:
                        self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox")
                    self.send_security_headers()
                    self.end_headers()
                    with open(fp, 'rb') as f:
                        while True:
                            chunk = f.read(262144)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # K. Server Shutdown
        if self.path == '/shutdown':
            if not self.is_host_client():
                self.send_error(403, "Forbidden")
                return
            self.send_text("Shutting down")
            def kill():
                global zc, httpd
                stop_tunnel()
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

        # Fallback for unhandled routes: Return 404 rather than serving directory contents
        self.send_error(404, "Endpoint not found")
        return

    def do_POST(self):
        # 1. HANDLE LOGIN (Accept CURRENT_PIN or PREVIOUS_PIN for grace window with Rate Limiting)
        if self.path == '/login':
            client_ip = self.get_client_ip()
            now = time.time()
            
            with login_lock:
                attempt_info = login_attempts.get(client_ip, {"count": 0, "lockout_until": 0})
                if attempt_info["lockout_until"] > now:
                    remaining = int(attempt_info["lockout_until"] - now)
                    self.send_text(f"Too many failed attempts. Locked out for {remaining}s", status=429)
                    return
                elif attempt_info["lockout_until"] != 0 and attempt_info["lockout_until"] <= now:
                    # Lockout expired, reset counter
                    attempt_info = {"count": 0, "lockout_until": 0}
                    login_attempts[client_ip] = attempt_info

            length = int(self.headers.get('Content-Length', 0))
            if length > 1024:
                self.send_error(400, "Bad Request")
                return
            body = self.rfile.read(length).decode('utf-8', errors='ignore')
            params = urllib.parse.parse_qs(body)
            pin_input = params.get('pin', [''])[0].strip()
            
            with state_lock:
                valid_pins = {CURRENT_PIN, PREVIOUS_PIN}
            
            if pin_input in valid_pins and pin_input != "":
                with login_lock:
                    login_attempts.pop(client_ip, None)

                token = secrets.token_hex(16)
                with state_lock:
                    SESSIONS.add(token)
                add_event(f"Device connected: {client_ip}")

                body_bytes = b"OK"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                cookie_flags = "Path=/; Max-Age=86400; SameSite=Lax; HttpOnly"
                if self.headers.get("CF-Ray") or self.headers.get("X-Forwarded-Proto") == "https":
                    cookie_flags += "; Secure"
                self.send_header("Set-Cookie", f"pyshare_session={token}; {cookie_flags}")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(body_bytes)
            else:
                with login_lock:
                    attempt_info["count"] += 1
                    if attempt_info["count"] >= MAX_FAILED_ATTEMPTS:
                        attempt_info["lockout_until"] = now + LOCKOUT_DURATION
                        login_attempts[client_ip] = attempt_info
                        self.send_text(f"Too many failed attempts. Locked out for {LOCKOUT_DURATION}s", status=429)
                    else:
                        login_attempts[client_ip] = attempt_info
                        remaining_tries = MAX_FAILED_ATTEMPTS - attempt_info["count"]
                        self.send_text(f"Invalid PIN ({remaining_tries} tries left)", status=401)
            return

        # 2. CHECK AUTH FOR PROTECTED ACTIONS
        if not self.is_authenticated():
            self.send_error(401, "Unauthorized")
            return

        # 3. HANDLE CLOUDFLARE TUNNEL TOGGLE (/api/tunnel/toggle - Host Only)
        if self.path == '/api/tunnel/toggle':
            if not self.is_host_client():
                self.send_error(403, "Host Only")
                return
            with TUNNEL_LOCK:
                is_active = (TUNNEL_STATUS == "active" or TUNNEL_STATUS == "starting")
            if is_active:
                stop_tunnel()
            else:
                start_tunnel()
            with TUNNEL_LOCK:
                self.send_json({"status": TUNNEL_STATUS, "url": TUNNEL_URL})
            return

        # 3. HANDLE SHARED CLIPBOARD POST (/api/text)
        if self.path in ('/api/text', '/api/clipboard'):
            global SHARED_TEXT, TEXT_TIMESTAMP
            length = int(self.headers.get('Content-Length', 0))
            if length > 1024 * 64:
                self.send_error(413, "Clipboard payload too large (Max 64KB)")
                return
            body = self.rfile.read(length).decode('utf-8', errors='ignore')
            try:
                data = json.loads(body)
                new_text = str(data.get("text", data.get("clipboard", ""))).strip()
            except Exception:
                new_text = body.strip()

            with state_lock:
                SHARED_TEXT = new_text
                TEXT_TIMESTAMP = int(time.time())

            # Direct sync to Windows OS clipboard
            try:
                pyperclip.copy(new_text)
            except Exception:
                pass

            snippet = (new_text[:35] + "...") if len(new_text) > 35 else new_text
            add_event(f"Clipboard updated: {snippet}")
            broadcast_sse("clipboard", {"text": SHARED_TEXT, "timestamp": TEXT_TIMESTAMP})
            self.send_json({"status": "ok", "timestamp": TEXT_TIMESTAMP})
            return

        # 4. HANDLE FILE DELETION (/api/delete - Host Only)
        if self.path == '/api/delete':
            if not self.is_host_client():
                self.send_error(403, "Host Only")
                return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8', errors='ignore')
            try:
                data = json.loads(body)
                fn = os.path.basename(data.get('filename', ''))
                folder = data.get('folder', 'shared')
                if folder == 'shared' and fn in STAGED_FILES:
                    staged_info = STAGED_FILES.get(fn, {})
                    staged_path = staged_info.get("path", "")
                    unstage_file(fn)
                    if staged_path and os.path.isfile(staged_path) and os.path.commonpath([os.path.abspath(DOWNLOAD_DIR), os.path.abspath(staged_path)]) == os.path.abspath(DOWNLOAD_DIR):
                        try:
                            os.remove(staged_path)
                        except Exception:
                            pass
                    add_event(f"Unshared: {fn}")
                    broadcast_sse("files", get_files_data())
                    self.send_json({"status": "ok", "deleted": fn})
                    return

                target_dir = UPLOAD_DIR if folder == 'received' else DOWNLOAD_DIR
                target_fp = os.path.abspath(os.path.join(target_dir, fn))
                safe_target_dir = os.path.abspath(target_dir)
                if os.path.commonpath([safe_target_dir, target_fp]) == safe_target_dir and os.path.isfile(target_fp):
                    os.remove(target_fp)
                    add_event(f"Deleted: {fn}")
                    broadcast_sse("files", get_files_data())
                    self.send_json({"status": "ok", "deleted": fn})
                    return
                else:
                    self.send_error(404, "File not found")
                    return
            except Exception as e:
                self.send_error(500, str(e))
                return

        # 5. HANDLE FILE UPLOAD (High-speed 256KB buffer + throttled progress lock)
        client_ip = self.get_client_ip()
        try:
            is_host_upload = ("dest=host" in self.path) and self.is_host_client()
            target_dir = DOWNLOAD_DIR if is_host_upload else UPLOAD_DIR

            encoded_fn = self.headers.get('X-File-Name')
            if not encoded_fn:
                self.send_error(400, "Missing X-File-Name header")
                return
                
            raw_fn = os.path.basename(urllib.parse.unquote(encoded_fn)).strip()
            # Sanitize control characters and Windows forbidden characters (< > : " / \ | ? * and ASCII 0x00-0x1f)
            raw_fn = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', raw_fn).strip(' .')
            # Sanitize filename: prevent empty names or reserved Windows device names
            reserved_names = {'con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'}
            base_check = raw_fn.split('.')[0].lower()
            if not raw_fn or raw_fn in ('.', '..') or base_check in reserved_names:
                raw_fn = f"upload_{int(time.time())}.bin"
            length = int(self.headers.get('Content-Length', 0))
            
            os.makedirs(target_dir, exist_ok=True)

            out_path = get_unique_filepath(target_dir, raw_fn)
            actual_fn = os.path.basename(out_path)
            part_path = out_path + ".part"
            
            remain = length
            total_size = length
            
            if not is_host_upload: 
                add_event(f"Receiving: {actual_fn}")
            
            last_status_time = 0
            try:
                with open(part_path, 'wb') as f:
                    while remain > 0:
                        chunk = self.rfile.read(min(remain, 262144))  # 256KB chunk
                        if not chunk: 
                            break
                        f.write(chunk)
                        remain -= len(chunk)
                        
                        if not is_host_upload:
                            now = time.time()
                            # Throttle lock & SSE broadcast to max 10 times per second
                            if now - last_status_time >= 0.1 or remain == 0:
                                last_status_time = now
                                set_upload_status(client_ip, actual_fn, total_size - remain, total_size)
                                broadcast_sse("upload", {
                                    "filename": actual_fn,
                                    "current": total_size - remain,
                                    "total": total_size
                                })
                if remain == 0:
                    # Atomic commit: Rename completed .part file to final path
                    if os.path.exists(out_path):
                        os.remove(out_path)
                    os.rename(part_path, out_path)
                    if is_host_upload:
                        stage_file(out_path)
                else:
                    if os.path.exists(part_path):
                        os.remove(part_path)
                    raise IOError("Transfer interrupted before complete upload")
            except Exception as e:
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass
                raise e
            
            clear_upload_status(client_ip)
            broadcast_sse("upload", None)
            
            msg = f"Added to Shared: {actual_fn}" if is_host_upload else f"File received: {actual_fn}"
            add_event(msg)
            
            # Broadcast updated file lists immediately across all connected devices
            broadcast_sse("files", get_files_data())
            
            self.send_json({"status": "ok", "filename": actual_fn})
            
        except Exception as e:
            clear_upload_status(client_ip)
            broadcast_sse("upload", None)
            self.send_error(500, str(e))

# --- SERVER CONTROLLER ---
# --- DESKTOP APPLICATION LAUNCHER ---
def launch_desktop_app(url):
    """
    PyShare Server Core Runner.
    Native Desktop GUI runs via app_gui.py without spawning any browser windows.
    """
    print(f"[*] PyShare server active at: {url}")
    print("[*] Press Ctrl+C to terminate.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def start_server():
    global BASE_DIR, UPLOAD_DIR, DOWNLOAD_DIR, httpd, ACTUAL_PORT, zc
    
    print("\n" + "="*45)
    print("[*] Starting PyShare...")

    try:
        cfg = load_app_config()
        defaults = get_default_directories()
        DOWNLOAD_DIR = os.path.abspath(cfg.get("shared_dir", defaults["shared_dir"]))
        UPLOAD_DIR = os.path.abspath(cfg.get("received_dir", defaults["received_dir"]))
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        BASE_DIR = os.path.dirname(DOWNLOAD_DIR)
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

    # Start PIN Rotation & 1-second countdown ticker
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
    
    # Run HTTP server on background daemon thread
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    host_app_url = f"http://127.0.0.1:{ACTUAL_PORT}/"
    try:
        launch_desktop_app(host_app_url)
    except KeyboardInterrupt: 
        print("\n[-] Shutting down server...")
    finally:
        stop_tunnel()
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
        print("[-] PyShare Stopped.")

if __name__ == "__main__":
    if "--no-gui" in sys.argv:
        start_server()
    else:
        try:
            import app_gui
            app_gui.start_native_app()
        except Exception as e:
            print(f"[*] Native GUI notice: {e}, falling back to server mode.")
            start_server()
