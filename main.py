import os
import http.server
import socketserver
import socket
import pyqrcode
import urllib.parse
import shutil
import json
import mimetypes  # Used for the preview feature
import sys

# --- CONFIGURATION ---
PORT = 8010
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_Phone")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_PC")

# Create directories
for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
    os.makedirs(folder, exist_ok=True)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # 1. Main Page
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        # 2. Assets (QR, CSS, JS)
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

        # 3. JSON API (File List)
        if self.path == '/api/files':
            self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers()
            try:
                files = sorted(os.listdir(DOWNLOAD_DIR), key=str.lower)
                file_data = []
                for f in files:
                    fp = os.path.join(DOWNLOAD_DIR, f)
                    if os.path.isfile(fp): # Only list actual files
                        size = os.path.getsize(fp)
                        file_data.append({"name": f, "size": size})
                self.wfile.write(json.dumps(file_data).encode())
            except: self.wfile.write(b"[]")
            return

        # 4. VIEW / PREVIEW (Fixed)
        if self.path.startswith('/view/'):
            fn = urllib.parse.unquote(self.path[6:])
            fp = os.path.join(DOWNLOAD_DIR, fn)
            # Check if exists AND is a file (Prevents crash on folders)
            if os.path.exists(fp) and os.path.isfile(fp):
                self.send_response(200)
                ctype, _ = mimetypes.guess_type(fp)
                if ctype is None: ctype = 'application/octet-stream'
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
            return

        # 5. DOWNLOAD
        if self.path.startswith('/download/'):
            fn = urllib.parse.unquote(self.path[10:])
            fp = os.path.join(DOWNLOAD_DIR, fn)
            if os.path.exists(fp) and os.path.isfile(fp):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.end_headers()
                with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
            return

        # 6. SHUTDOWN
        if self.path == '/shutdown':
            # 1. Send Success Response to Browser
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            # 2. Print Message to Terminal
            print("\n" + "="*40)
            print("🛑 SERVER DISCONNECTED BY USER")
            print("="*40 + "\n")
            
            # 3. Kill Server (Flush stdout first to ensure message appears)
            sys.stdout.flush()
            
            # We use a thread to kill it so the response can finish sending
            def kill_me():
                import time
                time.sleep(0.5) # Give browser time to receive "200 OK"
                os._exit(0)
                
            import threading
            threading.Thread(target=kill_me).start()
            return

        return super().do_GET()

    def do_POST(self):
        # HANDLE UPLOADS
        try:
            ctype = self.headers.get('Content-Type')
            if not ctype: return
            boundary = ctype.split("boundary=")[1].encode()
            length = int(self.headers.get('Content-Length'))
            
            line = self.rfile.readline()
            read = len(line)
            fn = "uploaded_file"
            
            # Parse filename
            while line.strip():
                if 'filename=' in line.decode(errors='ignore'):
                    fn = line.decode(errors='ignore').split('filename=')[1].strip('"\r\n ')
                    fn = os.path.basename(urllib.parse.unquote(fn))
                line = self.rfile.readline()
                read += len(line)

            out = os.path.join(UPLOAD_DIR, fn)
            remain = length - read
            
            # Save File
            with open(out, 'wb') as f:
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536))
                    if not chunk: break
                    f.write(chunk)
                    remain -= len(chunk)

            # Cleanup boundary
            with open(out, 'rb+') as f:
                f.seek(0, 2); f_len = f.tell()
                f.seek(max(0, f_len-300), 0); tail = f.read()
                loc = tail.find(b'--' + boundary)
                if loc != -1: f.truncate(max(0, f_len-300) + loc - 2)
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Upload Complete")
            
            # --- TERMINAL LOGGING ---
            print(f"✅ [RECEIVED] File added: {fn}")
            
        except Exception as e:
            print(f"❌ [ERROR] Upload failed: {e}")

# --- STARTUP ---
ip = get_ip()
url = f'http://{ip}:{PORT}'
pyqrcode.create(url).png('qrcode.png', scale=6)

print(f"\n⚡ SERVER LIVE: {url}")
print(f"📂 Storage: {UPLOAD_DIR}")
print(f"📱 Scan QR or open URL to connect.\n")

with socketserver.ThreadingTCPServer(("", PORT), FinalFileHandler) as httpd:
    httpd.allow_reuse_address = True
    httpd.serve_forever()