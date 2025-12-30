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

# --- GLOBAL CONFIGURATION ---
START_PORT = 8010
httpd = None

# These will be set automatically
BASE_DIR = ""
UPLOAD_DIR = ""
DOWNLOAD_DIR = ""
ACTUAL_PORT = START_PORT

# --- 1. SYSTEM HELPERS ---
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
    def log_message(self, format, *args):
        pass 

    def get_file_path(self, filename):
        """Helper: Searches for a file in shared folders."""
        fp = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(fp) and os.path.isfile(fp): return fp
        fp = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(fp) and os.path.isfile(fp): return fp
        return None

    def do_GET(self):
        """Handle GET requests"""
        
        # FIX FOR PYINSTALLER: Find where HTML/CSS/JS are hidden
        if getattr(sys, 'frozen', False):
            ASSET_DIR = sys._MEIPASS
        else:
            ASSET_DIR = os.path.dirname(os.path.abspath(__file__))

        # A. Serve Main Page
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200); self.send_header("Content-type", "text/html; charset=utf-8"); self.end_headers()
            with open(os.path.join(ASSET_DIR, "index.html"), "rb") as f: self.wfile.write(f.read())
            return

        # B. Serve Assets
        if self.path == '/styles.css':
            self.send_response(200); self.send_header("Content-type", "text/css"); self.end_headers()
            with open(os.path.join(ASSET_DIR, "styles.css"), "rb") as f: self.wfile.write(f.read())
            return
        if self.path == '/scripts.js':
            self.send_response(200); self.send_header("Content-type", "text/javascript"); self.end_headers()
            with open(os.path.join(ASSET_DIR, "scripts.js"), "rb") as f: self.wfile.write(f.read())
            return

        # C. Serve QR Code
        if self.path == '/qrcode.png':
            qr_path = os.path.join(BASE_DIR, "qrcode.png")
            if not os.path.exists(qr_path):
                qr_path = os.path.join(tempfile.gettempdir(), "pyshare_qrcode.png")
            
            if os.path.exists(qr_path):
                self.send_response(200); self.send_header("Content-type", "image/png"); self.end_headers()
                with open(qr_path, "rb") as f: self.wfile.write(f.read())
            return

        # D. API: Return File Lists
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

            response = {
                "pc": list_dir(DOWNLOAD_DIR),
                "mobile": list_dir(UPLOAD_DIR)
            }
            self.wfile.write(json.dumps(response).encode())
            return

        # E. View & Download
        if self.path.startswith('/view/') or self.path.startswith('/download/'):
            is_view = self.path.startswith('/view/')
            prefix = 6 if is_view else 10
            fn = urllib.parse.unquote(self.path[prefix:])
            fp = self.get_file_path(fn)
            
            if fp:
                self.send_response(200)
                ctype, _ = mimetypes.guess_type(fp)
                if ctype is None: ctype = 'application/octet-stream'
                self.send_header("Content-Type", ctype)
                if not is_view:
                    self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
            else:
                self.send_error(404, "File not found")
            return

        # F. Shutdown
        if self.path == '/shutdown':
            self.send_response(200); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
            def kill():
                if httpd: 
                    httpd.shutdown()
                    httpd.server_close()
                os._exit(0)
            threading.Thread(target=kill).start()
            return

        return super().do_GET()

    def do_POST(self):
        """Handle File Uploads"""
        try:
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
            
            if not os.path.exists(UPLOAD_DIR):
                os.makedirs(UPLOAD_DIR, exist_ok=True)

            out_path = os.path.join(UPLOAD_DIR, fn)
            remain = length - read_bytes
            
            with open(out_path, 'wb') as f:
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536))
                    if not chunk: break
                    f.write(chunk)
                    remain -= len(chunk)
            
            with open(out_path, 'rb+') as f:
                f.seek(0, 2); size = f.tell(); f.seek(max(0, size-300), 0); tail = f.read()
                loc = tail.find(b'--' + boundary)
                if loc != -1: f.truncate(max(0, size-300) + loc - 2)
            
            self.send_response(200); self.end_headers(); self.wfile.write(b"Upload Complete")
            print(f"✅ [RECEIVED] {fn}")
        except Exception as e:
            print(f"❌ [ERROR] Upload failed: {e}")

# --- 3. SERVER CONTROLLER ---
def start_server():
    global BASE_DIR, UPLOAD_DIR, DOWNLOAD_DIR, httpd, ACTUAL_PORT
    
    print("\n" + "="*40)
    print("🚀 Starting PyShare...")

    # 1. SETUP DESKTOP PATH
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        BASE_DIR = os.path.join(desktop, "PyShare_Files")
        
        SHARED_ROOT = os.path.join(BASE_DIR, "SharedFiles")
        UPLOAD_DIR = os.path.join(SHARED_ROOT, "From_Phone")
        DOWNLOAD_DIR = os.path.join(SHARED_ROOT, "From_PC")

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
