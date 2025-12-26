// --- 1. THEME & INIT ---
(function () {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    loadFiles();
    setupDragDrop();
})();

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const target = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', target);
    localStorage.setItem('theme', target);
}

function toggleQR() {
    const overlay = document.getElementById('qrOverlay');
    overlay.style.display = (overlay.style.display === 'flex') ? 'none' : 'flex';
}

// --- 2. DRAG & DROP LOGIC (FIXED) ---
function setupDragDrop() {
    const dropZone = document.getElementById('dropZone');

    // 1. Prevent browser from opening the file
    window.addEventListener("dragover", function (e) {
        e = e || event;
        e.preventDefault();
    }, false);
    window.addEventListener("drop", function (e) {
        e = e || event;
        e.preventDefault();
    }, false);

    // 2. Visual Cues (Add class when dragging OVER the box)
    dropZone.addEventListener('dragenter', () => dropZone.classList.add('dragover'), false);
    dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'), false);

    // 3. Remove class when leaving
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'), false);
    dropZone.addEventListener('drop', (e) => {
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    }, false);
}

// --- 3. FILE LIST & SEARCH ---
let allFiles = [];

async function loadFiles() {
    try {
        const res = await fetch('/api/files');
        allFiles = await res.json();
        renderFiles(allFiles);
    } catch (e) {
        document.getElementById('file-list').innerHTML = '<li style="text-align:center;padding:20px;color:#e74c3c">Failed to load files</li>';
    }
}

function renderFiles(files) {
    const list = document.getElementById('file-list');
    if (files.length === 0) {
        list.innerHTML = '<li style="text-align:center;padding:20px;color:#888">No files found</li>';
        return;
    }

    list.innerHTML = files.map(f => {
        const icon = getSmartIcon(f.name);
        const size = formatSize(f.size);
        return `
        <li class="file-item">
            <div class="f-icon">${icon}</div>
            <div class="f-info">
                <a href="/view/${encodeURIComponent(f.name)}" target="_blank" class="f-name-link">${f.name}</a>
                <div class="f-size">${size}</div>
            </div>
            <a href="/download/${encodeURIComponent(f.name)}" class="dl-btn" title="Download">⬇</a>
        </li>`;
    }).join('');
}

function getSmartIcon(name) {
    const ext = name.split('.').pop().toLowerCase();
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return '🖼️';
    if (['mp4', 'mkv', 'mov', 'webm'].includes(ext)) return '🎬';
    if (['mp3', 'wav', 'aac'].includes(ext)) return '🎵';
    if (['zip', 'rar', '7z', 'tar'].includes(ext)) return '📦';
    if (['pdf', 'doc', 'docx', 'txt'].includes(ext)) return '📄';
    if (['py', 'js', 'html', 'css', 'c'].includes(ext)) return '💻';
    return '📁';
}

function filterFiles() {
    const query = document.getElementById('searchBox').value.toLowerCase();
    const filtered = allFiles.filter(f => f.name.toLowerCase().includes(query));
    renderFiles(filtered);
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// --- 4. UPLOAD LOGIC ---
function handleFiles(files) {
    if (!files.length) return;
    Array.from(files).forEach(file => uploadFile(file));
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    const bar = document.getElementById('progress-bar');
    const container = document.getElementById('progress-container');
    const status = document.getElementById('status');
    const pct = document.getElementById('percent-text');

    container.style.display = 'block';
    status.innerText = `Uploading: ${file.name}...`;

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            bar.style.width = percent + "%";
            pct.innerText = Math.round(percent) + "%";
        }
    };

    xhr.onload = () => {
        status.innerText = "✅ Upload Complete!";
        loadFiles();
        setTimeout(() => {
            container.style.display = 'none';
            bar.style.width = '0%';
        }, 2000);
    };

    xhr.open("POST", "/");
    xhr.send(formData);
}

// --- 5. DISCONNECT LOGIC (FIXED) ---
function disconnectServer() {
    if (confirm("Are you sure you want to stop the server?")) {
        // 1. Send the request FIRST
        fetch('/shutdown')
            .then(() => {
                // 2. Show the "Disconnected" screen ONLY after we tried sending
                showDisconnectScreen();
            })
            .catch(() => {
                // Even if it fails (e.g., server died fast), still show the screen
                showDisconnectScreen();
            });
    }
}

function showDisconnectScreen() {
    document.body.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; text-align:center; font-family:'Segoe UI', sans-serif; color: #e74c3c;">
            <div style="font-size:60px; margin-bottom:20px;">🛑</div>
            <h1 style="margin:0;">Server Disconnected</h1>
            <p style="color:#888; margin-top:10px;">You can close this tab.</p>
        </div>
    `;
}