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

# --- 1. CONFIGURATION ---
PORT = 8010
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define separate folders for organization
# "From_Phone": Where files uploaded via the web interface go
# "From_PC": Where you put files on your computer to share
UPLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_Phone")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_PC")

# Create directories if they don't exist
for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
    os.makedirs(folder, exist_ok=True)

# --- 2. NETWORK HELPER ---
def get_ip():
    """Finds the local IP address of the machine on the Wi-Fi network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually connect, just calculates the route
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1' # Fallback to localhost
    finally:
        s.close()
    return IP

# --- 3. REQUEST HANDLER ---
class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    
    def get_file_path(self, filename):
        """Helper: Searches for a file in both 'From_PC' and 'From_Phone' folders."""
        # Check PC Folder first
        fp = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(fp) and os.path.isfile(fp): return fp
        # Check Mobile Uploads Folder next
        fp = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(fp) and os.path.isfile(fp): return fp
        return None

    def do_GET(self):
        """Handle GET requests (Serving pages, API data, and downloads)"""
        
        # A. Serve Main Page
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        # B. Serve Static Assets (CSS, JS, QR Image)
        if self.path == '/qrcode.png':
            if os.path.exists('qrcode.png'):
                self.send_response(200); self.send_header("Content-type", "image/png"); self.end_headers()
                with open("qrcode.png", "rb") as f: self.wfile.write(f.read())
            return
        if self.path == '/styles.css':
            self.send_response(200); self.send_header("Content-type", "text/css"); self.end_headers()
            with open(os.path.join(BASE_DIR, "styles.css"), "rb") as f: self.wfile.write(f.read())
            return
        if self.path == '/scripts.js':
            self.send_response(200); self.send_header("Content-type", "text/javascript"); self.end_headers()
            with open(os.path.join(BASE_DIR, "scripts.js"), "rb") as f: self.wfile.write(f.read())
            return

        # C. API: Return File Lists (JSON)
        # Used by the frontend to populate "Files on PC" and "Received from Phone"
        if self.path == '/api/files':
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            
            def list_dir(path):
                data = []
                try:
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

        # D. View/Preview File (In Browser)
        if self.path.startswith('/view/'):
            fn = urllib.parse.unquote(self.path[6:])
            fp = self.get_file_path(fn)
            
            if fp:
                self.send_response(200)
                # Guess MIME type (e.g. image/jpeg, application/pdf)
                ctype, _ = mimetypes.guess_type(fp)
                if ctype is None: ctype = 'application/octet-stream'
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
            else:
                self.send_error(404, "File not found")
            return

        # E. Force Download File
        if self.path.startswith('/download/'):
            fn = urllib.parse.unquote(self.path[10:])
            fp = self.get_file_path(fn)
            
            if fp:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
            else:
                self.send_error(404, "File not found")
            return

        # F. Shutdown Server
        if self.path == '/shutdown':
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            print("\n" + "="*40); print("🛑 SERVER DISCONNECTED BY USER"); print("="*40 + "\n")
            sys.stdout.flush()
            # Kill server in a separate thread to allow response to finish
            def kill_me():
                import time; time.sleep(0.5); os._exit(0)
            threading.Thread(target=kill_me).start()
            return

        return super().do_GET()

    def do_POST(self):
        """Handle File Uploads via Drag & Drop"""
        try:
            ctype = self.headers.get('Content-Type')
            if not ctype: return
            boundary = ctype.split("boundary=")[1].encode()
            length = int(self.headers.get('Content-Length'))
            line = self.rfile.readline(); read = len(line); fn = "uploaded_file"
            
            # Parse filename
            while line.strip():
                if 'filename=' in line.decode(errors='ignore'):
                    fn = line.decode(errors='ignore').split('filename=')[1].strip('"\r\n ')
                    fn = os.path.basename(urllib.parse.unquote(fn))
                line = self.rfile.readline(); read += len(line)
            
            out = os.path.join(UPLOAD_DIR, fn)
            remain = length - read
            
            # Write file chunks
            with open(out, 'wb') as f:
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536))
                    if not chunk: break
                    f.write(chunk)
                    remain -= len(chunk)
            
            # Clean up trailing boundary bytes
            with open(out, 'rb+') as f:
                f.seek(0, 2); f_len = f.tell(); f.seek(max(0, f_len-300), 0); tail = f.read()
                loc = tail.find(b'--' + boundary)
                if loc != -1: f.truncate(max(0, f_len-300) + loc - 2)
            
            self.send_response(200); self.end_headers(); self.wfile.write(b"Upload Complete")
            print(f"✅ [RECEIVED] File added: {fn}")
        except Exception as e:
            print(f"❌ [ERROR] Upload failed: {e}")

# --- 4. STARTUP ---
ip = get_ip()
url = f'http://{ip}:{PORT}'
# Generate QR code
pyqrcode.create(url).png('qrcode.png', scale=6)

print(f"\n⚡ SERVER LIVE: {url}")
print(f"📂 Mobile Uploads: {UPLOAD_DIR}")
print(f"📂 PC Files: {DOWNLOAD_DIR}")
print(f"📱 Scan QR to connect.\n")

with socketserver.ThreadingTCPServer(("", PORT), FinalFileHandler) as httpd:
    httpd.allow_reuse_address = True; httpd.serve_forever()