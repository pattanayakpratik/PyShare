import os
import http.server
import socketserver
import socket
import pyqrcode
import urllib.parse
import shutil
import sys

PORT = 8010
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_Phone")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_PC")

for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
    os.makedirs(folder, exist_ok=True)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception: IP = '127.0.0.1'
    finally: s.close()
    return IP

class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        try:
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                    self.wfile.write(f.read())
                return

            if self.path == '/qrcode.png':
                if os.path.exists('qrcode.png'):
                    self.send_response(200)
                    self.send_header("Content-type", "image/png")
                    self.end_headers()
                    with open("qrcode.png", "rb") as f:
                        self.wfile.write(f.read())
                return

            if self.path == '/shutdown':
                self.send_response(200); self.end_headers()
                self.wfile.write(b"Server stopped.")
                print("\n[STOP] Server stopped."); os._exit(0)
                return

            if self.path == '/list/':
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                try: files = os.listdir(DOWNLOAD_DIR)
                except: files = []
                file_items = ""
                for f in files:
                    ext = f.lower().split('.')[-1]
                    try: size = f"{os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) // 1024} KB"
                    except: size = "0 KB"
                    
                    if ext in ['jpg', 'png', 'gif']: icon = "🖼️"
                    elif ext in ['mp4', 'mkv']: icon = "🎬"
                    elif ext == 'pdf': icon = "📕"
                    elif ext in ['docx', 'xlsx']: icon = "📝"
                    else: icon = "📄"

                    file_items += f"""<li style="background:white;padding:15px;margin-bottom:10px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                        <div style="display:flex;align-items:center;margin-bottom:10px;">
                            <span style="font-size:24px;margin-right:15px;">{icon}</span>
                            <div style="flex-grow:1;overflow:hidden;"><div style="font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{f}</div><small style="color:#888;">{size}</small></div>
                        </div>
                        <div style="display:flex;gap:10px;">
                            <a href="/view/{f}" target="_blank" style="flex:1;text-align:center;background:#3498db;color:white;padding:10px;border-radius:5px;text-decoration:none;font-weight:bold;font-size:14px;">Preview</a>
                            <a href="/download/{f}" style="flex:1;text-align:center;background:#27ae60;color:white;padding:10px;border-radius:5px;text-decoration:none;font-weight:bold;font-size:14px;">Download</a>
                            <button onclick="deleteFile('{f}')" style="flex:1;background:#e74c3c;color:white;border:none;padding:10px;border-radius:5px;font-weight:bold;font-size:14px;">Delete</button>
                        </div>
                    </li>"""
                
                self.wfile.write(f"""<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{{font-family:sans-serif;background:#f0f2f5;padding:15px;color:#333;}} ul{{padding:0;list-style:none;}}</style><script>function deleteFile(n){{if(confirm('Delete '+n+'?'))fetch('/delete/'+encodeURIComponent(n)).then(()=>location.reload());}}</script></head><body><h2 style="text-align:center;">📂 Files</h2><ul>{file_items}</ul><a href="/" style="display:block;text-align:center;margin-top:20px;border:2px solid #3498db;padding:10px;border-radius:8px;text-decoration:none;font-weight:bold;color:#3498db;">⬅ Back</a></body></html>""".encode())
                return

            if self.path.startswith('/view/'):
                fn = urllib.parse.unquote(self.path[6:])
                fp = os.path.join(DOWNLOAD_DIR, fn)
                if os.path.exists(fp):
                    self.send_response(200)
                    ext = fn.lower().split('.')[-1]
                    mimes = {'pdf':'application/pdf','mp4':'video/mp4','jpg':'image/jpeg','png':'image/png'}
                    self.send_header("Content-Type", mimes.get(ext, "application/octet-stream"))
                    self.send_header("Content-Length", str(os.path.getsize(fp)))
                    self.end_headers()
                    with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
                return

            if self.path.startswith('/download/'):
                fn = urllib.parse.unquote(self.path[10:])
                fp = os.path.join(DOWNLOAD_DIR, fn)
                if os.path.exists(fp):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                    self.send_header("Content-Length", str(os.path.getsize(fp)))
                    self.end_headers()
                    with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
                return

            if self.path.startswith('/delete/'):
                fn = urllib.parse.unquote(self.path[8:])
                fp = os.path.join(DOWNLOAD_DIR, fn)
                if os.path.exists(fp): os.remove(fp)
                self.send_response(200); self.end_headers()
                return

        except: pass
        return super().do_GET()

    def do_POST(self):
        try:
            ctype = self.headers.get('Content-Type')
            if not ctype: return
            boundary = ctype.split("boundary=")[1].encode()
            length = int(self.headers.get('Content-Length'))
            
            line = self.rfile.readline()
            read = len(line)
            fn = "uploaded_file"
            while line.strip():
                if 'filename=' in line.decode(errors='ignore'):
                    fn = line.decode(errors='ignore').split('filename=')[1].strip('"\r\n ')
                    fn = os.path.basename(urllib.parse.unquote(fn))
                line = self.rfile.readline()
                read += len(line)

            out = os.path.join(UPLOAD_DIR, fn)
            remain = length - read
            
            with open(out, 'wb') as f:
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536))
                    if not chunk: break
                    f.write(chunk)
                    remain -= len(chunk)

            with open(out, 'rb+') as f:
                f.seek(0, 2); f_len = f.tell()
                f.seek(max(0, f_len-300), 0)
                tail = f.read()
                loc = tail.find(b'--' + boundary)
                if loc != -1:
                    cut = max(0, f_len-300) + loc
                    if cut > 2: f.truncate(cut - 2)
                    else: f.truncate(cut)

            # --- THE FIX IS HERE ---
            response_body = b"Upload Complete"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            # We MUST tell the phone how long the response is so it stops waiting
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close") # Force close to ensure UI updates
            self.end_headers()
            self.wfile.write(response_body)
            # -----------------------
            
            print(f"[SUCCESS] Uploaded: {fn}")
        except Exception as e:
            print(f"[ERROR] {e}")

ip = get_ip()
url = f'http://{ip}:{PORT}'
pyqrcode.create(url).png('qrcode.png', scale=6)
print(f"--- SERVER LIVE: {url} ---")
with socketserver.ThreadingTCPServer(("", PORT), FinalFileHandler) as httpd:
    httpd.allow_reuse_address = True
    httpd.serve_forever()