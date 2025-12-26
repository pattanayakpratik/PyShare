// --- 1. INITIALIZATION ---
(function () {
    // Load saved theme (default to dark)
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);

    // Load file lists
    loadFiles();
    // Enable Drag & Drop
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

// --- 2. DRAG & DROP LOGIC ---
function setupDragDrop() {
    const dropZone = document.getElementById('dropZone');

    // Prevent default browser behavior (opening file)
    window.addEventListener("dragover", e => e.preventDefault(), false);
    window.addEventListener("drop", e => e.preventDefault(), false);

    // Visual Cues
    dropZone.addEventListener('dragenter', () => dropZone.classList.add('dragover'), false);
    dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'), false);
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'), false);

    // Handle Drop
    dropZone.addEventListener('drop', (e) => {
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    }, false);
}

// --- FILE LISTS & SEARCH ---
let pcFiles = [];
let mobileFiles = [];

async function loadFiles() {
    try {
        const res = await fetch('/api/files');
        const data = await res.json();

        pcFiles = data.pc || [];
        mobileFiles = data.mobile || [];

        renderList(pcFiles, 'file-list', 'No files on PC');
        renderList(mobileFiles, 'mobile-list', 'No uploads from phone yet');

    } catch (e) { console.error(e); }
}

function renderList(files, elementId, emptyMsg) {
    const list = document.getElementById(elementId);
    if (!list) return;

    if (files.length === 0) {
        list.innerHTML = `<li style="text-align:center;padding:15px;color:var(--text-sub);font-size:13px;">${emptyMsg}</li>`;
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

// --- NEW: SEPARATE FILTER FUNCTIONS ---

function filterPC() {
    const query = document.getElementById('searchPC').value.toLowerCase();
    const filtered = pcFiles.filter(f => f.name.toLowerCase().includes(query));
    renderList(filtered, 'file-list', 'No matches on PC');
}

function filterMobile() {
    const query = document.getElementById('searchMobile').value.toLowerCase();
    const filtered = mobileFiles.filter(f => f.name.toLowerCase().includes(query));
    renderList(filtered, 'mobile-list', 'No matches in Mobile Uploads');
}
// Helper: Smart Icons
function getSmartIcon(name) {
    const ext = name.split('.').pop().toLowerCase();
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return '🖼️';
    if (['mp4', 'mkv', 'mov', 'webm'].includes(ext)) return '🎬';
    if (['mp3', 'wav', 'aac'].includes(ext)) return '🎵';
    if (['zip', 'rar', '7z', 'tar'].includes(ext)) return '📦';
    if (['pdf', 'doc', 'docx', 'txt'].includes(ext)) return '📄';
    return '📁';
}

// Helper: Readable Size
function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + ['B', 'KB', 'MB', 'GB'][i];
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
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
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
        status.innerText = "✅ Done!";
        loadFiles(); // Refresh lists
        setTimeout(() => { container.style.display = 'none'; bar.style.width = '0%'; }, 2000);
    };
    xhr.open("POST", "/");
    xhr.send(formData);
}

// --- 5. DISCONNECT ---
function disconnectServer() {
    if (confirm("Stop the server?")) {
        fetch('/shutdown').finally(() => {
            document.body.innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;color:#e74c3c;text-align:center;font-family:sans-serif;">
                <div style="font-size:60px;">🛑</div><h1>Disconnected</h1><p>You can close this tab.</p>
            </div>`;
        });
    }
}
