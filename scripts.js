/* ==========================================================================
   PyShare v4.0 - Universal Client & Core Frontend Logic
   ========================================================================== */

// --- 1. STATE & INITIALIZATION ---
let pcFiles = [];
let mobileFiles = [];
let currentCategoryPC = 'all';
let currentCategoryMobile = 'all';
let lastClipboardTs = 0;

(function init() {
    const savedTheme = localStorage.getItem('pyshare_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    // Initial fetch
    loadFiles();
    loadClipboard();
    setupDragDrop();
    
    // Global ESC key listener for modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closePreview();
    });
})();

// Theme Switcher
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const target = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', target);
    localStorage.setItem('pyshare_theme', target);
}

// Toast Notifications
function showToast(message, icon = 'ℹ️') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 2800);
}

// Helper: Escape HTML
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, (m) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
}

// Helper: Format Bytes to Human Readable
function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + units[i];
}

// Helper: Format Epoch to Readable Time
function formatTime(epoch) {
    if (!epoch) return '';
    const d = new Date(epoch * 1000);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Helper: Category-based Smart Icons
function getCategoryIcon(category, ext) {
    switch (category) {
        case 'image': return '🖼️';
        case 'video': return '🎬';
        case 'audio': return '🎵';
        case 'document': 
            if (ext === 'pdf') return '📕';
            if (['doc', 'docx'].includes(ext)) return '📘';
            if (['xls', 'xlsx', 'csv'].includes(ext)) return '📊';
            return '📄';
        case 'archive': return '📦';
        case 'code': return '💻';
        default: return '📁';
    }
}

// --- 2. MULTI-FILE UPLOAD QUEUE WITH TRANSFER SPEED ---
class UploadQueueManager {
    constructor() {
        this.queue = [];
        this.activeUploads = 0;
        this.maxConcurrent = 2;
    }

    addFiles(files, uploadUrl = '/') {
        if (!files || !files.length) return;
        
        const card = document.getElementById('uploadQueueCard');
        if (card) card.style.display = 'flex';

        Array.from(files).forEach(file => {
            const item = {
                id: 'upl_' + Math.random().toString(36).substr(2, 9),
                file: file,
                url: uploadUrl,
                status: 'pending',
                progress: 0
            };
            this.queue.push(item);
            this.renderQueueItem(item);
        });

        this.processNext();
    }

    renderQueueItem(item) {
        const list = document.getElementById('queueList');
        if (!list) return;

        const el = document.createElement('div');
        el.id = item.id;
        el.className = 'queue-item';
        el.innerHTML = `
            <div class="queue-item-meta">
                <span class="queue-item-name" title="${escapeHtml(item.file.name)}">${escapeHtml(item.file.name)}</span>
                <span id="${item.id}_status" style="color:var(--text-sub);">${formatSize(item.file.size)}</span>
            </div>
            <div class="queue-item-track">
                <div id="${item.id}_bar" class="queue-item-fill"></div>
            </div>
        `;
        list.appendChild(el);
    }

    processNext() {
        while (this.activeUploads < this.maxConcurrent) {
            const next = this.queue.find(i => i.status === 'pending');
            if (!next) break;
            this.uploadSingle(next);
        }

        // Hide queue card if all items are done
        const hasPendingOrActive = this.queue.some(i => i.status === 'pending' || i.status === 'uploading');
        if (!hasPendingOrActive && this.queue.length > 0) {
            setTimeout(() => {
                const card = document.getElementById('uploadQueueCard');
                if (card) card.style.display = 'none';
                const list = document.getElementById('queueList');
                if (list) list.innerHTML = '';
                this.queue = [];
            }, 3000);
        }
    }

    uploadSingle(item) {
        this.activeUploads++;
        item.status = 'uploading';

        const statusEl = document.getElementById(`${item.id}_status`);
        const barEl = document.getElementById(`${item.id}_bar`);
        const speedEl = document.getElementById('queueSpeed');

        const xhr = new XMLHttpRequest();
        let lastLoaded = 0;
        let lastTime = Date.now();

        xhr.open('POST', item.url);
        xhr.setRequestHeader('X-File-Name', encodeURIComponent(item.file.name));
        xhr.setRequestHeader('Content-Type', 'application/octet-stream');

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                if (barEl) barEl.style.width = pct + '%';

                const now = Date.now();
                const timeDiff = (now - lastTime) / 1000;
                if (timeDiff >= 0.5) {
                    const bytesDiff = e.loaded - lastLoaded;
                    const speed = bytesDiff / timeDiff; // bytes/sec
                    if (speedEl) speedEl.innerText = `${formatSize(speed)}/s`;
                    lastLoaded = e.loaded;
                    lastTime = now;
                }

                if (statusEl) statusEl.innerText = `${pct}% • ${formatSize(e.loaded)} / ${formatSize(e.total)}`;
            }
        };

        xhr.onload = () => {
            this.activeUploads--;
            if (xhr.status === 200) {
                item.status = 'done';
                if (barEl) {
                    barEl.style.width = '100%';
                    barEl.style.background = 'var(--accent-green)';
                }
                if (statusEl) statusEl.innerText = '✅ Complete';
                showToast(`Uploaded: ${item.file.name}`, '✅');
            } else {
                item.status = 'error';
                if (statusEl) statusEl.innerText = '❌ Failed';
                showToast(`Failed to upload: ${item.file.name}`, '❌');
            }
            loadFiles();
            this.processNext();
        };

        xhr.onerror = () => {
            this.activeUploads--;
            item.status = 'error';
            if (statusEl) statusEl.innerText = '❌ Network Error';
            showToast(`Upload error: ${item.file.name}`, '❌');
            this.processNext();
        };

        xhr.send(item.file);
    }
}

const uploadManager = new UploadQueueManager();

function handleFiles(files) {
    uploadManager.addFiles(files, '/');
}

// Drag & Drop Setup
function setupDragDrop() {
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) return;

    window.addEventListener('dragover', (e) => e.preventDefault(), false);
    window.addEventListener('drop', (e) => e.preventDefault(), false);

    dropZone.addEventListener('dragenter', () => dropZone.classList.add('dragover'), false);
    dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'), false);
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'), false);

    dropZone.addEventListener('drop', (e) => {
        dropZone.classList.remove('dragover');
        if (e.dataTransfer && e.dataTransfer.files) {
            if (window.handleFilesCustom) {
                window.handleFilesCustom(e.dataTransfer.files);
            } else {
                handleFiles(e.dataTransfer.files);
            }
        }
    }, false);
}

// --- 3. FILE RETRIEVAL & FILTERING ---
async function loadFiles() {
    try {
        const res = await fetch('/api/files');
        if (!res.ok) return;
        const data = await res.json();
        pcFiles = data.pc || [];
        mobileFiles = data.mobile || [];

        renderPCFiles();
        renderMobileFiles();
    } catch (e) {
        console.error('Error fetching files:', e);
    }
}

function setFilterPC(category, el) {
    currentCategoryPC = category;
    if (el && el.parentElement) {
        el.parentElement.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
        el.classList.add('active');
    }
    renderPCFiles();
}

function setFilterMobile(category, el) {
    currentCategoryMobile = category;
    if (el && el.parentElement) {
        el.parentElement.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
        el.classList.add('active');
    }
    renderMobileFiles();
}

function renderPCFiles() {
    const query = (document.getElementById('searchPC')?.value || '').toLowerCase();
    const filtered = pcFiles.filter(f => {
        const matchesQuery = f.name.toLowerCase().includes(query);
        const matchesCategory = currentCategoryPC === 'all' || f.category === currentCategoryPC;
        return matchesQuery && matchesCategory;
    });
    renderFileList(filtered, 'file-list', 'No files in Shared folder', 'shared');
}

function renderMobileFiles() {
    const query = (document.getElementById('searchMobile')?.value || '').toLowerCase();
    const filtered = mobileFiles.filter(f => {
        const matchesQuery = f.name.toLowerCase().includes(query);
        const matchesCategory = currentCategoryMobile === 'all' || f.category === currentCategoryMobile;
        return matchesQuery && matchesCategory;
    });
    renderFileList(filtered, 'mobile-list', 'No files received yet', 'received');
}

function renderFileList(files, elementId, emptyMsg, folderType) {
    const list = document.getElementById(elementId);
    if (!list) return;

    if (!files.length) {
        list.innerHTML = `<li class="empty-state">${emptyMsg}</li>`;
        return;
    }

    const isHost = window.isHostSession === true;

    list.innerHTML = files.map(f => {
        const icon = getCategoryIcon(f.category, f.ext);
        const size = formatSize(f.size);
        const time = formatTime(f.mtime);
        const encName = encodeURIComponent(f.name);
        
        return `
        <li class="file-item">
            <div class="f-icon">${icon}</div>
            <div class="f-info">
                <a href="javascript:void(0)" onclick="openPreview('${escapeHtml(f.name)}', '${f.category}', ${f.size})" class="f-name" title="${escapeHtml(f.name)}">
                    ${escapeHtml(f.name)}
                </a>
                <div class="f-meta">
                    <span>${size}</span>
                    ${time ? `<span>• ${time}</span>` : ''}
                </div>
            </div>
            <div class="f-actions">
                <button class="f-btn" onclick="openPreview('${escapeHtml(f.name)}', '${f.category}', ${f.size})" title="Preview">👁️</button>
                <a href="/download/${encName}" class="f-btn" title="Download">⬇️</a>
                ${isHost ? `<button class="f-btn btn-delete" onclick="deleteFile('${escapeHtml(f.name)}', '${folderType}')" title="Delete File">🗑️</button>` : ''}
            </div>
        </li>`;
    }).join('');
}

// --- 4. MEDIA PREVIEW LIGHTBOX MODAL ---
async function openPreview(filename, category, size) {
    const modal = document.getElementById('previewModal');
    const title = document.getElementById('previewModalTitle');
    const body = document.getElementById('previewModalBody');
    const dlBtn = document.getElementById('previewDownloadBtn');
    if (!modal || !body) return;

    title.innerText = filename;
    dlBtn.href = `/download/${encodeURIComponent(filename)}`;
    body.innerHTML = '<div style="color:var(--text-sub)">Loading preview...</div>';
    modal.classList.add('open');

    const fileUrl = `/view/${encodeURIComponent(filename)}`;

    if (category === 'image') {
        body.innerHTML = `<img src="${fileUrl}" alt="${escapeHtml(filename)}" loading="lazy">`;
    } else if (category === 'video') {
        body.innerHTML = `
            <video controls autoplay playsinline style="max-width:100%; max-height:60vh; border-radius:12px;">
                <source src="${fileUrl}">
                Your browser does not support HTML5 video streaming.
            </video>`;
    } else if (category === 'audio') {
        body.innerHTML = `
            <div style="display:flex; flex-direction:column; align-items:center; gap:16px; padding:20px;">
                <div style="font-size:48px;">🎵</div>
                <div style="font-weight:600; font-size:15px;">${escapeHtml(filename)}</div>
                <audio controls autoplay style="width:100%; max-width:400px;">
                    <source src="${fileUrl}">
                </audio>
            </div>`;
    } else if (category === 'code' || filename.endsWith('.txt') || filename.endsWith('.log') || filename.endsWith('.md')) {
        try {
            const res = await fetch(fileUrl);
            const text = await res.text();
            body.innerHTML = `
                <div style="width:100%; display:flex; justify-content:flex-end; margin-bottom:8px;">
                    <button class="btn-secondary" onclick="copyPreviewText()">📋 Copy Text</button>
                </div>
                <pre id="previewTextContent"><code>${escapeHtml(text)}</code></pre>`;
        } catch (e) {
            body.innerHTML = `<p style="color:var(--text-sub)">Could not load text preview.</p>`;
        }
    } else {
        body.innerHTML = `
            <div style="text-align:center; padding:30px;">
                <div style="font-size:48px; margin-bottom:12px;">📄</div>
                <h3>${escapeHtml(filename)}</h3>
                <p style="color:var(--text-sub); margin:8px 0 20px 0;">${formatSize(size)}</p>
                <div style="display:flex; gap:10px; justify-content:center;">
                    <a href="${fileUrl}" target="_blank" class="btn-secondary">Open in New Tab</a>
                    <a href="/download/${encodeURIComponent(filename)}" class="btn-primary">Download File</a>
                </div>
            </div>`;
    }
}

function closePreview() {
    const modal = document.getElementById('previewModal');
    const body = document.getElementById('previewModalBody');
    if (modal) modal.classList.remove('open');
    if (body) body.innerHTML = ''; // Stop audio/video playback
}

function copyPreviewText() {
    const textEl = document.getElementById('previewTextContent');
    if (textEl) {
        navigator.clipboard.writeText(textEl.innerText).then(() => {
            showToast('Text copied to clipboard!', '📋');
        });
    }
}

// --- 5. SHARED CLIPBOARD / INSTANT TEXT SYNC ---
async function loadClipboard() {
    try {
        const res = await fetch('/api/text');
        if (res.ok) {
            const data = await res.json();
            renderClipboard(data.text);
            lastClipboardTs = data.timestamp;
        }
    } catch (e) {}
}

function renderClipboard(text) {
    const display = document.getElementById('clipboardCurrent');
    if (!display) return;
    if (text && text.trim().length > 0) {
        display.innerHTML = `
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:85%;">${escapeHtml(text)}</span>
            <button class="btn-secondary" onclick="copySharedClipboard()" title="Copy to clipboard">📋 Copy</button>
        `;
        display.dataset.raw = text;
    } else {
        display.innerHTML = `<span style="color:var(--text-sub); font-size:12px;">Clipboard is empty. Send text or links below.</span>`;
        display.dataset.raw = '';
    }
}

function copySharedClipboard() {
    const display = document.getElementById('clipboardCurrent');
    const raw = display?.dataset?.raw;
    if (raw) {
        navigator.clipboard.writeText(raw).then(() => {
            showToast('Copied to system clipboard!', '📋');
        });
    }
}

async function sendClipboard() {
    const input = document.getElementById('clipboardInput');
    if (!input || !input.value.trim()) return;

    const text = input.value.trim();
    try {
        const res = await fetch('/api/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        if (res.ok) {
            input.value = '';
            showToast('Shared with connected devices!', '🚀');
            loadClipboard();
        }
    } catch (e) {
        showToast('Failed to share text', '❌');
    }
}

// --- 6. HOST ACTIONS (Delete & Disconnect) ---
async function deleteFile(filename, folder) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;

    try {
        const res = await fetch('/api/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename, folder: folder })
        });
        if (res.ok) {
            showToast(`Deleted ${filename}`, '🗑️');
            loadFiles();
        } else {
            showToast('Failed to delete file', '❌');
        }
    } catch (e) {
        showToast('Error deleting file', '❌');
    }
}

function disconnectServer() {
    if (confirm("Stop the PyShare server? All connections will be terminated.")) {
        fetch('/shutdown').finally(() => {
            document.body.innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;color:#ef4444;text-align:center;font-family:sans-serif;padding:20px;">
                <div style="font-size:64px;margin-bottom:16px;">🛑</div>
                <h2>PyShare Server Stopped</h2>
                <p style="color:#94a3b8;margin-top:8px;">You can now safely close this window.</p>
            </div>`;
        });
    }
}
