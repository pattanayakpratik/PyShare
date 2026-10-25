/* ==========================================================================
   PyShare v4.8.0 - Universal Client & App Logic
   ========================================================================== */

let pcFiles = [];
let mobileFiles = [];
let lastClipboardTs = 0;
window.globalSSE = null;

(function init() {
    const urlTheme = new URLSearchParams(window.location.search).get('theme');
    const savedTheme = urlTheme || localStorage.getItem('pyshare_theme') || document.documentElement.getAttribute('data-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    if (urlTheme) {
        try { localStorage.setItem('pyshare_theme', urlTheme); } catch(e) {}
    }
    
    loadFiles();
    loadClipboard();
    setupDragDrop();
    initSSE();
    registerServiceWorker();
    
    if (window.location.protocol === 'https:') {
        const clientPill = document.querySelector('.client-status-pill span:last-child');
        if (clientPill) clientPill.innerText = 'Connected via Internet 🌐';
    }
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closePreview();
    });
})();

// Progressive Web App - Service Worker Registration
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js').catch(() => {});
        });
    }
}

// Server-Sent Events (SSE) Real-Time Push Engine
function initSSE() {
    if (!window.EventSource) return;
    if (window.globalSSE) return;

    try {
        const es = new EventSource('/api/events');
        window.globalSSE = es;
        let disconnectTimer = null;

        const clearDisconnect = () => {
            if (disconnectTimer) {
                clearTimeout(disconnectTimer);
                disconnectTimer = null;
            }
            const overlay = document.getElementById('disconnectOverlay');
            if (overlay) overlay.classList.remove('visible');
        };

        es.onopen = () => {
            clearDisconnect();
        };

        es.addEventListener('files', (e) => {
            clearDisconnect();
            try {
                const data = JSON.parse(e.data);
                pcFiles = data.host || data.pc || [];
                mobileFiles = data.client || data.mobile || [];
                renderPCFiles();
                renderMobileFiles();
            } catch (err) {}
        });

        es.addEventListener('clipboard', (e) => {
            clearDisconnect();
            try {
                const data = JSON.parse(e.data);
                if (data.timestamp > lastClipboardTs) {
                    renderClipboard(data.text);
                    lastClipboardTs = data.timestamp;
                }
            } catch (err) {}
        });

        es.onerror = () => {
            // EventSource handles automatic reconnection; show disconnect overlay if offline > 2.5s
            if (!disconnectTimer) {
                disconnectTimer = setTimeout(() => {
                    if (es.readyState !== EventSource.OPEN) {
                        const overlay = document.getElementById('disconnectOverlay');
                        if (overlay) overlay.classList.add('visible');
                    }
                }, 2500);
            }
        };

        // Notify other scripts (like host_scripts.js) that SSE is ready
        window.dispatchEvent(new CustomEvent('pyshare:sse_ready', { detail: es }));
    } catch (e) {}
}

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
    toast.className = 'toast-pill';
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 2600);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, (m) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
}

function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + units[i];
}

function getSmartIcon(category, ext) {
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

// --- MULTI-FILE UPLOAD QUEUE ---
class UploadQueueManager {
    constructor() {
        this.queue = [];
        this.activeUploads = 0;
        this.maxConcurrent = 2;
    }

    addFiles(files, uploadUrl = '/') {
        if (!files || !files.length) return;
        
        const drawer = document.getElementById('floatingQueue');
        if (drawer) drawer.style.display = 'flex';

        Array.from(files).forEach(file => {
            const item = {
                id: 'upl_' + Math.random().toString(36).substr(2, 9),
                file: file,
                url: uploadUrl,
                status: 'pending'
            };
            this.queue.push(item);
            this.renderQueueItem(item);
        });

        this.processNext();
    }

    renderQueueItem(item) {
        const list = document.getElementById('queueItemsList');
        if (!list) return;

        const el = document.createElement('div');
        el.id = item.id;
        el.style.cssText = "background:var(--input-bg); border:1px solid var(--border-color); border-radius:8px; padding:6px 10px; display:flex; flex-direction:column; gap:4px;";
        el.innerHTML = `
            <div style="display:flex; justify-content:space-between; font-size:11px;">
                <span style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:70%;">${escapeHtml(item.file.name)}</span>
                <span id="${item.id}_status" style="color:var(--text-sub);">${formatSize(item.file.size)}</span>
            </div>
            <div style="height:4px; background:rgba(255,255,255,0.1); border-radius:99px; overflow:hidden;">
                <div id="${item.id}_bar" style="height:100%; width:0%; background:var(--accent-blue); transition:width 0.15s ease;"></div>
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

        const activeCount = this.queue.filter(i => i.status === 'uploading').length;
        const pendingCount = this.queue.filter(i => i.status === 'pending').length;
        const totalRemaining = activeCount + pendingCount;

        const statusEl = document.getElementById('queueOverallStatus');
        if (statusEl) {
            if (totalRemaining > 0) {
                statusEl.innerText = `Uploading ${totalRemaining} file${totalRemaining > 1 ? 's' : ''}...`;
            } else if (this.queue.length > 0) {
                statusEl.innerText = `✅ All uploads complete!`;
                setTimeout(() => {
                    const drawer = document.getElementById('floatingQueue');
                    if (drawer) drawer.style.display = 'none';
                    const list = document.getElementById('queueItemsList');
                    if (list) list.innerHTML = '';
                    this.queue = [];
                }, 2500);
            }
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
                    const speed = (e.loaded - lastLoaded) / timeDiff;
                    if (speedEl) speedEl.innerText = `${formatSize(speed)}/s`;
                    lastLoaded = e.loaded;
                    lastTime = now;
                }

                if (statusEl) statusEl.innerText = `${pct}% • ${formatSize(e.loaded)}`;
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
                if (statusEl) statusEl.innerText = '✅ Done';
                showToast(`Saved: ${item.file.name}`, '✅');
            } else {
                item.status = 'error';
                if (statusEl) statusEl.innerText = '❌ Failed';
                showToast(`Failed: ${item.file.name}`, '❌');
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

// --- FILE FETCHING & RENDERING ---
async function loadFiles() {
    try {
        const res = await fetch('/api/files');
        if (!res.ok) return;
        const data = await res.json();
        pcFiles = data.host || data.pc || [];
        mobileFiles = data.client || data.mobile || [];

        renderPCFiles();
        renderMobileFiles();
    } catch (e) {}
}

function renderPCFiles() {
    const query = (document.getElementById('searchPC')?.value || '').toLowerCase();
    const filtered = pcFiles.filter(f => f.name.toLowerCase().includes(query));
    renderFileList(filtered, 'file-list', 'No files in Shared folder', 'shared');
}

function renderMobileFiles() {
    const query = (document.getElementById('searchMobile')?.value || '').toLowerCase();
    const filtered = mobileFiles.filter(f => f.name.toLowerCase().includes(query));
    renderFileList(filtered, 'mobile-list', 'No uploads yet', 'received');
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
        const icon = getSmartIcon(f.category, f.ext);
        const size = formatSize(f.size);
        const encName = encodeURIComponent(f.name);
        
        return `
        <li class="file-row">
            <div class="file-icon">${icon}</div>
            <div class="file-details">
                <a href="javascript:void(0)" onclick="openPreviewEnc('${encName}', '${f.category}', ${f.size})" class="file-name" title="${escapeHtml(f.name)}">
                    ${escapeHtml(f.name)}
                </a>
                <div class="file-size">${size}</div>
            </div>
            <div class="file-actions">
                <button class="action-circle-btn" onclick="openPreviewEnc('${encName}', '${f.category}', ${f.size})" title="Preview">👁️</button>
                <a href="/download/${encName}" class="action-circle-btn" title="Download">⬇</a>
                ${isHost ? `<button class="action-circle-btn btn-del" onclick="deleteFileEnc('${encName}', '${folderType}')" title="Delete">🗑️</button>` : ''}
            </div>
        </li>`;
    }).join('');
}

// --- MEDIA PREVIEW LIGHTBOX MODAL ---
function openPreviewEnc(encName, category, size) {
    openPreview(decodeURIComponent(encName), category, size);
}

function deleteFileEnc(encName, folderType) {
    deleteFile(decodeURIComponent(encName), folderType);
}
async function openPreview(filename, category, size) {
    const modal = document.getElementById('previewModal');
    const title = document.getElementById('previewModalTitle');
    const body = document.getElementById('previewModalBody');
    const dlBtn = document.getElementById('previewDownloadBtn');
    if (!modal || !body) return;

    title.innerText = filename;
    dlBtn.href = `/download/${encodeURIComponent(filename)}`;
    body.innerHTML = '<div style="color:var(--text-sub);">Loading preview...</div>';
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
            body.innerHTML = `<p style="color:var(--text-sub);">Could not load text preview.</p>`;
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
    if (body) body.innerHTML = '';
}

function copyPreviewText() {
    const textEl = document.getElementById('previewTextContent');
    if (textEl) {
        navigator.clipboard.writeText(textEl.innerText).then(() => {
            showToast('Copied to clipboard!', '📋');
        });
    }
}

// --- SHARED CLIPBOARD ---
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
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80%; font-size:12px;">${escapeHtml(text)}</span>
            <button class="btn-secondary" onclick="copySharedClipboard()" style="padding:4px 10px; font-size:11px;">📋 Copy</button>
        `;
        display.dataset.raw = text;
    } else {
        display.innerHTML = `<span style="color:var(--text-sub); font-size:12px;">Clipboard is empty.</span>`;
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
            showToast('Shared with devices!', '🚀');
            loadClipboard();
        }
    } catch (e) {
        showToast('Failed to share text', '❌');
    }
}

// --- HOST ACTIONS ---
async function deleteFile(filename, folder) {
    if (!confirm(`Delete "${filename}"?`)) return;

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
    if (confirm("Stop PyShare server? All connections will be terminated.")) {
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
