import os
import http.server
import socketserver
import socket
import pyqrcode
import urllib.parse
import shutil
import sys

# --- CONFIGURATION ---
PORT = 8010
# Get the absolute path of the directory where this script resides
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define separate folders for organization
UPLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_Phone") # Files coming from devices
DOWNLOAD_DIR = os.path.join(BASE_DIR, "SharedFiles", "From_PC")   # Files hosted on PC

# Create directories if they don't exist
for folder in [UPLOAD_DIR, DOWNLOAD_DIR]:
    os.makedirs(folder, exist_ok=True)

def get_ip():
    """
    Finds the local IP address of the machine on the network.
    It attempts to connect to a non-existent public IP via UDP.
    This method is preferred over socket.gethostbyname() as it returns
    the actual interface IP used for internet/network traffic.
    """
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

class FinalFileHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom Request Handler inheriting from SimpleHTTPRequestHandler.
    We override do_GET and do_POST to handle custom routing and file uploads.
    """
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        """Handle GET requests (Viewing pages, downloading files, commands)"""
        try:
            # 1. Serve the Main Interface (index.html)
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                # Read external HTML file and send it
                with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
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

            # 3. Shutdown Command (stops the python script)
            if self.path == '/shutdown':
                self.send_response(200); self.end_headers()
                self.wfile.write(b"Server stopped.")
                print("\n[STOP] Server stopped."); os._exit(0)
                return

            # 4. Generate File List (Dynamic HTML generation)
            # This allows the user to browse files in the 'From_PC' folder
            if self.path == '/list/':
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                
                # Get files and sort alphabetically
                try: files = sorted(os.listdir(DOWNLOAD_DIR), key=str.lower)
                except: files = []
                
                file_rows = ""
                for f in files:
                    ext = f.lower().split('.')[-1]
                    # Calculate file size in KB
                    try: size = f"{os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) // 1024} KB"
                    except: size = "0 KB"
                    
                    # Assign icons based on file extension
                    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        # Generate a thumbnail preview using the /view/ route
                        icon = f'<img src="/view/{urllib.parse.quote(f)}" style="width:40px;height:40px;object-fit:cover;border-radius:4px;">'
                    elif ext in ['mp4', 'mkv', 'webm']: icon = "🎬"
                    elif ext in ['mp3', 'wav']: icon = "🎵"
                    elif ext == 'pdf': icon = "📕"
                    elif ext in ['docx', 'xlsx', 'pptx']: icon = "📝"
                    elif ext in ['py', 'js', 'html', 'css', 'json']: icon = "💻"
                    else: icon = "📄"

                    # Construct the HTML list item
                    file_rows += f"""
                    <li class="file-item" data-name="{f.lower()}">
                        <div style="display:flex;align-items:center;">
                            <div style="font-size:24px;margin-right:15px;width:40px;text-align:center;">{icon}</div>
                            <div style="flex-grow:1;overflow:hidden;">
                                <div class="fname" style="font-weight:bold;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{f}</div>
                                <small class="fsize">{size}</small>
                            </div>
                        </div>
                        <div class="actions">
                            <a href="/view/{f}" target="_blank" class="act-btn blue">View</a>
                            <a href="/download/{f}" class="act-btn green">Load</a>
                            <button onclick="deleteFile('{f}')" class="act-btn red">Del</button>
                        </div>
                    </li>"""
                
                # Render the file manager HTML page (Embedded here for simplicity)
                # Note: Contains internal CSS and JS for search/theme/delete
                html = f"""
                <html><head><meta name="viewport" content="width=device-width,initial-scale=1">
                <title>Files</title>
                <style>
                    :root {{ --bg: #f4f7f6; --text: #333; --card: #fff; --sub: #888; --border: #ddd; }}
                    [data-theme="dark"] {{ --bg: #121212; --text: #e0e0e0; --card: #1e1e1e; --sub: #bbb; --border: #333; }}
                    
                    body{{font-family:'Segoe UI',sans-serif; background:var(--bg); color:var(--text); padding:15px; max-width:600px; margin:auto; transition:0.3s;}} 
                    ul{{padding:0;list-style:none;}}
                    h2 {{text-align:center; position:relative;}}
                    .file-item {{background:var(--card); padding:12px; margin-bottom:10px; border-radius:10px; box-shadow:0 2px 5px rgba(0,0,0,0.1); border:1px solid var(--border);}}
                    .fname {{color:var(--text);}}
                    .fsize {{color:var(--sub);}}
                    .actions {{display:flex;gap:5px;margin-top:10px;}}
                    .act-btn {{flex:1;text-align:center;padding:8px;border-radius:5px;text-decoration:none;font-weight:bold;font-size:13px;border:none;cursor:pointer;color:white;}}
                    .blue {{background:#3498db;}} .green {{background:#27ae60;}} .red {{background:#e74c3c;}}
                    #search {{width:100%;padding:12px;background:var(--card); border:1px solid var(--border); color:var(--text); border-radius:8px; margin-bottom:20px; box-sizing:border-box; font-size:16px; outline:none;}}
                    
                    .toggle-btn {{ position:absolute; right:0; top:0; background:none; border:none; font-size:20px; cursor:pointer; }}
                    .back-btn {{display:block;text-align:center;margin-top:20px;color:#3498db;text-decoration:none;font-weight:bold;border:2px solid #3498db;padding:10px;border-radius:8px;}}
                </style>
                <script>
                    function deleteFile(n){{if(confirm('Delete '+n+'?'))fetch('/delete/'+encodeURIComponent(n)).then(()=>location.reload());}}
                    function doSearch() {{
                        let val = document.getElementById('search').value.toLowerCase();
                        document.querySelectorAll('.file-item').forEach(li => {{
                            li.style.display = li.getAttribute('data-name').includes(val) ? 'block' : 'none';
                        }});
                    }}
                    
                    // Theme Logic
                    function toggleTheme() {{
                        const current = document.documentElement.getAttribute('data-theme');
                        const target = current === 'dark' ? 'light' : 'dark';
                        document.documentElement.setAttribute('data-theme', target);
                        localStorage.setItem('theme', target);
                    }}
                    
                    // Init Theme
                    (function(){{
                        const saved = localStorage.getItem('theme');
                        const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                        if(saved) {{ document.documentElement.setAttribute('data-theme', saved); }}
                        else if(sysDark) {{ document.documentElement.setAttribute('data-theme', 'dark'); }}
                    }})();
                </script>
                </head><body>
                <h2>📂 Files <button class="toggle-btn" onclick="toggleTheme()">🌓</button></h2>
                <input type="text" id="search" placeholder="🔍 Search files..." onkeyup="doSearch()">
                <ul>{file_rows}</ul>
                <a href="/" class="back-btn">⬅ Back to Upload</a>
                </body></html>"""
                
                self.wfile.write(html.encode())
                return

            # 5. Serve Raw File Content (for browser viewing)
            if self.path.startswith('/view/'):
                fn = urllib.parse.unquote(self.path[6:]) # Decode URL (e.g. %20 -> space)
                fp = os.path.join(DOWNLOAD_DIR, fn)
                if os.path.exists(fp):
                    self.send_response(200)
                    # Guess MIME type
                    ext = fn.lower().split('.')[-1]
                    mimes = {'pdf':'application/pdf','mp4':'video/mp4','jpg':'image/jpeg','png':'image/png'}
                    self.send_header("Content-Type", mimes.get(ext, "application/octet-stream"))
                    self.send_header("Content-Length", str(os.path.getsize(fp)))
                    self.end_headers()
                    # Stream file to client
                    with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
                return

            # 6. Force Download File
            if self.path.startswith('/download/'):
                fn = urllib.parse.unquote(self.path[10:])
                fp = os.path.join(DOWNLOAD_DIR, fn)
                if os.path.exists(fp):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    # Content-Disposition forces the browser to show "Save As"
                    self.send_header("Content-Disposition", f'attachment; filename="{fn}"')
                    self.send_header("Content-Length", str(os.path.getsize(fp)))
                    self.end_headers()
                    with open(fp, 'rb') as f: shutil.copyfileobj(f, self.wfile)
                return

            # 7. Delete File
            if self.path.startswith('/delete/'):
                fn = urllib.parse.unquote(self.path[8:])
                fp = os.path.join(DOWNLOAD_DIR, fn)
                if os.path.exists(fp): os.remove(fp)
                self.send_response(200); self.end_headers()
                return

        except: pass
        return super().do_GET()

    def do_POST(self):
        """
        Handle File Uploads via POST.
        This manually parses the Multipart form data to save the file.
        """
        try:
            # Check content type for 'multipart/form-data'
            ctype = self.headers.get('Content-Type')
            if not ctype: return
            
            # Extract the boundary string (separator between form data parts)
            boundary = ctype.split("boundary=")[1].encode()
            length = int(self.headers.get('Content-Length'))
            
            # Read first line (should be boundary)
            line = self.rfile.readline()
            read = len(line)
            fn = "uploaded_file"
            
            # Parse headers to find the filename
            while line.strip():
                if 'filename=' in line.decode(errors='ignore'):
                    fn = line.decode(errors='ignore').split('filename=')[1].strip('"\r\n ')
                    fn = os.path.basename(urllib.parse.unquote(fn))
                line = self.rfile.readline()
                read += len(line)

            out = os.path.join(UPLOAD_DIR, fn)
            remain = length - read
            
            # Write raw data to file in chunks (to handle large files)
            with open(out, 'wb') as f:
                while remain > 0:
                    chunk = self.rfile.read(min(remain, 65536)) # 64KB chunks
                    if not chunk: break
                    f.write(chunk)
                    remain -= len(chunk)

            # Cleanup: The file now contains the end boundary (--) at the bottom.
            # We must remove it to ensure the file isn't corrupted.
            with open(out, 'rb+') as f:
                f.seek(0, 2); f_len = f.tell()
                # Check the last 300 bytes for the boundary string
                f.seek(max(0, f_len-300), 0)
                tail = f.read()
                loc = tail.find(b'--' + boundary)
                
                # Truncate file at the boundary location
                if loc != -1:
                    cut = max(0, f_len-300) + loc
                    if cut > 2: f.truncate(cut - 2) # Remove the CRLF before boundary
                    else: f.truncate(cut)

            # Send success response
            response_body = b"Upload Complete"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(response_body)
            print(f"[SUCCESS] Uploaded: {fn}")
        except Exception as e:
            print(f"[ERROR] {e}")

# --- STARTUP SEQUENCE ---
ip = get_ip()
url = f'http://{ip}:{PORT}'

# Create QR Code for easy mobile access
pyqrcode.create(url).png('qrcode.png', scale=6)

print(f"--- SERVER LIVE: {url} ---")
print(f"1. Connect via URL or Scan QR Code")
print(f"2. Uploads go to: {UPLOAD_DIR}")
print(f"3. Downloads served from: {DOWNLOAD_DIR}")

# Start the Threaded Server (Handling multiple requests simultaneously)
with socketserver.ThreadingTCPServer(("", PORT), FinalFileHandler) as httpd:
    httpd.allow_reuse_address = True
    httpd.serve_forever()