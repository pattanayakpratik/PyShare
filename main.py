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
# Files uploaded from phone go here
UPLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_Phone")
# Files you want to download to phone go here
DOWNLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_PC")

# Ensure folders exist
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
        # 1. Serve the Main UI
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            index_path = os.path.join(BASE_DIR, "index.html")
            with open(index_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # 2. Serve the QR Code Image
        if self.path == '/qrcode.png':
            if os.path.exists('qrcode.png'):
                self.send_response(200)
                self.send_header("Content-type", "image/png")
                self.end_headers()
                with open("qrcode.png", "rb") as f:
                    self.wfile.write(f.read())
            return

        # 3. Custom File Listing with Delete Button
        if self.path == '/list/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            files = os.listdir(DOWNLOAD_DIR)
            file_items = ""
            for f in files:
                file_items += f"""
                <li style="display: flex; justify-content: space-between; align-items: center; background: white; padding: 12px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    <a href="/download/{f}" style="color: #2c3e50; text-decoration: none; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%;">{f}</a>
                    <button onclick="deleteFile('{f}')" style="background: #e74c3c; color: white; border: none; padding: 6px 12px; border-radius: 5px; cursor: pointer; font-size: 12px; font-weight: bold;">Delete</button>
                </li>"""
            
            html = f"""
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f7f6; padding: 20px; color: #2c3e50; }}
                    h2 {{ text-align: center; color: #34495e; }}
                    ul {{ padding: 0; list-style: none; }}
                    .back-btn {{ display: block; text-align: center; margin-top: 20px; color: #3498db; text-decoration: none; font-weight: bold; padding: 10px; border: 2px solid #3498db; border-radius: 8px; }}
                </style>
                <script>
                    function deleteFile(name) {{
                        if(confirm('Are you sure you want to delete ' + name + '?')) {{
                            fetch('/delete/' + encodeURIComponent(name))
                            .then(response => {{
                                if(response.ok) location.reload();
                                else alert('Delete failed');
                            }});
                        }}
                    }}
                </script>
            </head>
            <body>
                <h2>📂 Available Files</h2>
                <ul>{file_items if files else "<p style='text-align:center;'>Your 'From_PC' folder is empty.</p>"}</ul>
                <a href="/" class="back-btn">⬅ Back to Upload</a>
            </body></html>"""
            self.wfile.write(html.encode())
            return

        # 4. Handle File Deletion
        if self.path.startswith('/delete/'):
            filename = urllib.parse.unquote(self.path[8:])
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"[DELETED] {filename}")
                    self.send_response(200)
                else:
                    self.send_response(404)
            except Exception as e:
                print(f"[ERROR DELETING] {e}")
                self.send_response(500)
            self.end_headers()
            return

        # 5. Handle Downloads
        if self.path.startswith('/download/'):
            filename = urllib.parse.unquote(self.path[10:])
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(filepath):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(os.path.getsize(filepath)))
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

            # Read multipart headers
            line = self.rfile.readline(); content_length -= len(line)
            line = self.rfile.readline(); content_length -= len(line)
            fn = line.decode().split('filename=')[1].strip('"\r\n ')
            fn = os.path.basename(urllib.parse.unquote(fn))
            
            line = self.rfile.readline(); content_length -= len(line)
            line = self.rfile.readline(); content_length -= len(line)

            out_path = os.path.join(UPLOAD_DIR, fn)
            with open(out_path, 'wb') as out_file:
                limit = content_length - len(boundary) - 6
                while limit > 0:
                    chunk = self.rfile.read(min(limit, 64*1024))
                    if not chunk: break
                    out_file.write(chunk)
                    limit -= len(chunk)
                self.rfile.read() # Clean remaining boundary

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            print(f"[SUCCESS] Uploaded: {fn}")
        except Exception as e:
            print(f"[ERROR UPLOADING] {e}")
            self.send_error(500)

# Start Server
ip = get_ip()
url = f"http://{ip}:{PORT}"
qr = pyqrcode.create(url)
qr.png('qrcode.png', scale=6)

print(f"--- SERVER STARTED ---")
print(f"Local IP: {ip}")
print(f"URL:      {url}")
print(f"-----------------------")

with socketserver.ThreadingTCPServer(("", PORT), FinalFileHandler) as httpd:
    httpd.allow_reuse_address = True
    httpd.serve_forever()