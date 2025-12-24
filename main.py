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
# Directories for file storage
UPLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_Phone")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_PC")

# Ensure folders exist
for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
    os.makedirs(folder, exist_ok=True)

def get_ip():
    """Retrieves the local IP address for the server."""
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
    # Use HTTP 1.1 for more stable large file transfers
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        # 1. Serve the Main UI (index.html)
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            index_path = os.path.join(BASE_DIR, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    self.wfile.write(f.read())
            return

        # 2. Serve the generated QR Code
        if self.path == '/qrcode.png':
            if os.path.exists('qrcode.png'):
                self.send_response(200)
                self.send_header("Content-type", "image/png")
                self.end_headers()
                with open("qrcode.png", "rb") as f:
                    self.wfile.write(f.read())
            return

        # 3. Enhanced File List with Icons and File Size
        if self.path == '/list/':
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            files = os.listdir(DOWNLOAD_DIR)
            file_items = ""
            for f in files:
                ext = f.lower().split('.')[-1]
                size = os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) // 1024
                
                # Dynamic Visual Icons
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']: icon = "🖼️"
                elif ext in ['mp4', 'mkv', 'webm', 'mov']: icon = "🎬"
                elif ext in ['mp3', 'wav', 'm4a']: icon = "🎵"
                elif ext == 'pdf': icon = "📕"
                elif ext in ['docx', 'doc']: icon = "📝"
                elif ext in ['xlsx', 'xls']: icon = "📊"
                elif ext in ['pptx', 'ppt']: icon = "📽️"
                elif ext in ['py', 'js', 'html', 'css', 'txt', 'c', 'cpp', 'java', 'json']: icon = "💻"
                else: icon = "📄"

                file_items += f"""
                <li style="display: flex; align-items: center; background: white; padding: 12px; margin-bottom: 10px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    <div style="margin-right: 15px; font-size: 24px;">{icon}</div>
                    <div style="flex-grow: 1; overflow: hidden;">
                        <div style="font-weight: bold; white-space: nowrap; text-overflow: ellipsis; overflow: hidden;">{f}</div>
                        <div style="font-size: 11px; color: #888;">{size} KB</div>
                    </div>
                    <div style="display: flex; gap: 5px;">
                        <a href="/view/{f}" target="_blank" style="background: #3498db; color: white; padding: 6px 10px; border-radius: 5px; text-decoration: none; font-size: 12px; font-weight: bold;">Review</a>
                        <button onclick="deleteFile('{f}')" style="background: #e74c3c; color: white; border: none; padding: 6px 10px; border-radius: 5px; cursor: pointer; font-size: 12px; font-weight: bold;">Delete</button>
                    </div>
                </li>"""
            
            html = f"""<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
            <style>body{{font-family:'Segoe UI',sans-serif; background:#f0f2f5; padding:20px; color:#2c3e50;}} ul{{padding:0; list-style:none;}}</style>
            <script>function deleteFile(name){{if(confirm('Delete '+name+'?')){{fetch('/delete/'+encodeURIComponent(name)).then(()=>location.reload());}}}}</script>
            </head><body><h2 style="text-align:center;">📂 Universal Manager</h2><ul>{file_items if files else "<p style='text-align:center;'>No files in folder.</p>"}</ul>
            <a href="/" style="display:block; text-align:center; margin-top:20px; color:#3498db; text-decoration:none; font-weight:bold; padding:10px; border:2px solid #3498db; border-radius:8px;">⬅ Back to Upload</a>
            </body></html>"""
            self.wfile.write(html.encode())
            return

        # 4. Universal Review/Open Logic (Handles MKV, Code, Office, etc.)
        if self.path.startswith('/view/'):
            filename = urllib.parse.unquote(self.path[6:])
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(filepath):
                self.send_response(200)
                ext = filename.lower().split('.')[-1]
                
                # MIME Types for multimedia and documents
                mime_types = {
                    'mkv': 'video/x-matroska', 'mp4': 'video/mp4', 'webm': 'video/webm',
                    'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'm4a': 'audio/mp4',
                    'pdf': 'application/pdf',
                    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp',
                    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    'doc': 'application/msword'
                }
                # Code files served as text for browser viewing
                code_exts = ['txt', 'py', 'js', 'html', 'css', 'c', 'cpp', 'java', 'json', 'md', 'php']
                
                if ext in mime_types:
                    self.send_header("Content-Type", mime_types[ext])
                elif ext in code_exts:
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                else:
                    self.send_header("Content-Type", "application/octet-stream")
                
                self.end_headers()
                with open(filepath, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
                return

        # 5. File Deletion Logic
        if self.path.startswith('/delete/'):
            filename = urllib.parse.unquote(self.path[8:])
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            self.send_response(200)
            self.end_headers()
            return
            
        return super().do_GET()

    def do_POST(self):
        try:
            content_type = self.headers.get('Content-Type')
            boundary = content_type.split("boundary=")[1].encode()
            content_length = int(self.headers.get('Content-Length'))

            # Parse headers and get filename
            line = self.rfile.readline(); content_length -= len(line)
            line = self.rfile.readline(); content_length -= len(line)
            fn = line.decode().split('filename=')[1].strip('"\r\n ')
            fn = os.path.basename(urllib.parse.unquote(fn))
            
            line = self.rfile.readline(); content_length -= len(line)
            line = self.rfile.readline(); content_length -= len(line)

            # Stream save with 1MB chunks to handle large files and network resets
            out_path = os.path.join(UPLOAD_DIR, fn)
            with open(out_path, 'wb') as out_file:
                limit = content_length - len(boundary) - 6
                while limit > 0:
                    chunk = self.rfile.read(min(limit, 1024*1024))
                    if not chunk: break
                    out_file.write(chunk)
                    limit -= len(chunk)
                self.rfile.read() # Final cleanup of buffer

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            print(f"[SUCCESS] Uploaded: {fn}")
        except (ConnectionResetError, ConnectionAbortedError):
            print("[DISCONNECT] Client closed connection during upload.")
        except Exception as e:
            print(f"[ERROR] {e}")
            try: self.send_error(500)
            except: pass

# Start Server and Generate QR Code
ip = get_ip()
url = f'http://{ip}:{PORT}'
pyqrcode.create(url).png('qrcode.png', scale=6)

print(f"--- SERVER LIVE ---")
print(f"URL: {url}")
print(f"-------------------")

# Use Threading to allow multiple simultaneous connections
with socketserver.ThreadingTCPServer(("", PORT), FinalFileHandler) as httpd:
    httpd.allow_reuse_address = True
    httpd.serve_forever()