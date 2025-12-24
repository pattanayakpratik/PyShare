import os
import http.server
import socketserver
import socket
import pyqrcode
import urllib.parse
import shutil
from PIL import Image

PORT = 8010
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_Phone")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_PC")

# Ensure folders exist
for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
    os.makedirs(folder, exist_ok=True)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a non-existent external IP to find the local network interface
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception: 
        IP = '127.0.0.1'
    finally: 
        s.close()
    return IP

class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # 1. Serve the Main UI
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            index_path = os.path.join(BASE_DIR, "index.html")
            with open(index_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # 2. Serve the QR Code Image for the UI
        if self.path == '/qrcode.png':
            if os.path.exists('qrcode.png'):
                self.send_response(200)
                self.send_header("Content-type", "image/png")
                self.end_headers()
                with open("qrcode.png", "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "QR Code not found")
            return

        # 3. Custom File Listing (Browse Files)
        if self.path == '/list/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            files = os.listdir(DOWNLOAD_DIR)
            file_links = "".join([f'<li><a href="/download/{f}">{f}</a></li>' for f in files])
            
            html = f"""
            <html>
            <head><meta name="viewport" content="width=device-width, initial-scale=1">
            <style>body{{font-family:sans-serif; padding:20px; background:#f4f7f6;}} a{{color:#3498db; text-decoration:none; font-weight:bold;}} li{{margin-bottom:10px; padding:10px; background:white; border-radius:5px; list-style:none; shadow: 0 2px 5px rgba(0,0,0,0.1);}}</style>
            </head>
            <body>
                <h2>📂 Available Files</h2>
                <ul>{file_links if files else "<li>No files available</li>"}</ul>
                <br><a href="/">⬅ Back to Upload</a>
            </body></html>
            """
            self.wfile.write(html.encode())
            return

        # 4. Handle specific file downloads
        if self.path.startswith('/download/'):
            filename = urllib.parse.unquote(self.path[10:])
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
                return
        
        return super().do_GET()

    def do_POST(self):
        try:
            content_type = self.headers.get('Content-Type')
            boundary = content_type.split("boundary=")[1].encode()
            content_length = int(self.headers.get('Content-Length'))

            # Parse file headers from stream
            line = self.rfile.readline(); content_length -= len(line)
            line = self.rfile.readline(); content_length -= len(line)
            fn = line.decode().split('filename=')[1].strip('"\r\n ')
            fn = os.path.basename(urllib.parse.unquote(fn))
            
            line = self.rfile.readline(); content_length -= len(line)
            line = self.rfile.readline(); content_length -= len(line)

            # Save the file
            out_path = os.path.join(UPLOAD_DIR, fn)
            with open(out_path, 'wb') as out_file:
                limit = content_length - len(boundary) - 6
                while limit > 0:
                    chunk = self.rfile.read(min(limit, 64*1024))
                    if not chunk: break
                    out_file.write(chunk)
                    limit -= len(chunk)
                self.rfile.read()

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            print(f"[SUCCESS] Uploaded: {fn}")
        except Exception as e:
            print(f"[ERROR] {e}")
            self.send_error(500)

# Generate QR and Start Server
ip = get_ip()
url = f'http://{ip}:{PORT}'
qr = pyqrcode.create(url)
qr.png('qrcode.png', scale=6)
print(f"Server LIVE: {url}")

with socketserver.ThreadingTCPServer(("", PORT), FinalFileHandler) as httpd:
    httpd.allow_reuse_address = True
    httpd.serve_forever()