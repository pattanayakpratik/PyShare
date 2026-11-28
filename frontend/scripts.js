/* ==========================================================================
   PyShare - Universal Client & App Logic
   ========================================================================== */

let pcFiles = [];
let mobileFiles = [];
let lastClipboardTs = 0;
window.globalSSE = null;
// Declared up here (not next to initClientDevice) because init() below runs immediately and
// reads it: a `let` declared later in the file is in its temporal dead zone at that point.
let currentClientNickname = localStorage.getItem('pyshare_device_name') || 'My Device';

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
    initClientDevice();
    
    if (window.location.protocol === 'https:') {
        const clientPill = document.querySelector('.client-status-pill span:last-child');
        if (clientPill) clientPill.innerHTML = 'Connected via Internet <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>';
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
                if (!data) return;
                pcFiles = data.host || data.pc || [];
                mobileFiles = data.client || data.mobile || [];
                renderPCFiles();
                renderMobileFiles();
            } catch (err) {}
        });

        // The host renamed the PC: update "Connected to …" and the host's own name chip
        es.addEventListener('host_info', (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data && data.host_name && typeof setHostNameDisplays === 'function') setHostNameDisplays(data.host_name);
            } catch (err) {}
        });

        es.addEventListener('clipboard', (e) => {
            clearDisconnect();
            try {
                const data = JSON.parse(e.data);
                if (!data) return;
                if (data.new_message) {
                    handleIncomingChatMessage(data.new_message);
                }
                if (data.messages) {
                    renderClipboardChat(data.messages);
                } else if (data.text) {
                    renderClipboardChat([{ text: data.text, sender: "Clipboard", timestamp: data.timestamp }]);
                }
                lastClipboardTs = data.timestamp;
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

// Toast Notifications with Deduplication & Max Limit
let recentToastHistory = new Map();

function getToastSvg(icon) {
    if (!icon) return '';
    if (typeof icon === 'string' && icon.trim().startsWith('<svg')) {
        return icon;
    }
    const key = String(icon).trim().toLowerCase();
    switch (key) {
        case 'success':
        case 'check':
        case '\u2705':
        case '\u2713':
        case '\uD83C\uDF89':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><polyline points="20 6 9 17 4 12"/></svg>';
        case 'error':
        case 'danger':
        case 'cross':
        case '\u274C':
        case '\u26D4':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
        case 'warning':
        case 'alert':
        case '\u26A0\uFE0F':
        case '\u26A0':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
        case 'copy':
        case 'clipboard':
        case '\uD83D\uDCCB':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
        case 'chat':
        case 'message':
        case '\uD83D\uDCAC':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
        case 'trash':
        case 'delete':
        case '\uD83D\uDDD1\uFE0F':
        case '\uD83D\uDDD1':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
        case 'bell':
        case 'knock':
        case '\uD83D\uDD14':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>';
        case 'edit':
        case 'rename':
        case '\u270F\uFE0F':
        case '\u270F':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>';
        case 'lock':
        case 'revoked':
        case '\uD83D\uDD12':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
        case 'globe':
        case 'internet':
        case '\uD83C\uDF10':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>';
        case 'home':
        case 'local':
        case '\uD83C\uDFE0':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>';
        case 'save':
        case 'download':
        case '\uD83D\uDCBE':
        case '\uD83D\uDCE5':
        case '\uD83D\uDE80':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
        case 'key':
        case 'pin':
        case '\uD83D\uDD11':
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M21 2l-2 2m-1.5 1.5L14 9l-3-3-9 9v4h4l9-9 3.5 3.5 2-2"/></svg>';
        default:
            return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }
}

function showToast(message, icon = 'info') {
    if (!message) return;
    const now = Date.now();
    const lastSeen = recentToastHistory.get(message);
    if (lastSeen && (now - lastSeen) < 2500) {
        return; // Suppress duplicate notifications within 2.5s
    }
    recentToastHistory.set(message, now);
    if (recentToastHistory.size > 25) {
        recentToastHistory.forEach((ts, msg) => {
            if (now - ts > 10000) recentToastHistory.delete(msg);
        });
    }

    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Limit maximum visible toast pills to 3
    while (container.children.length >= 3) {
        container.removeChild(container.firstChild);
    }

    const toast = document.createElement('div');
    toast.className = 'toast-pill';
    const svgIcon = getToastSvg(icon);
    toast.innerHTML = `<span style="display:inline-flex; align-items:center;">${svgIcon}</span> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => {
            if (toast.parentNode === container) {
                container.removeChild(toast);
            }
        }, 300);
    }, 2600);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, (m) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
}

// Copy text from a click/tap. navigator.clipboard only exists on secure origins (https or
// localhost); phones open PyShare at http://192.168.x.x, where it is undefined, so fall back to
// the textarea + execCommand('copy') path, which works there during a user gesture.
// Resolves to true when the text was copied.
function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text).then(() => true, () => legacyCopyText(text));
    }
    return Promise.resolve(legacyCopyText(text));
}

function legacyCopyText(text) {
    const active = document.activeElement;
    try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');          // no on-screen keyboard on phones
        ta.style.cssText = 'position:fixed; top:-1000px; left:0; opacity:0;';
        document.body.appendChild(ta);
        ta.select();
        ta.setSelectionRange(0, text.length);
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        return ok;
    } catch (e) {
        return false;
    } finally {
        if (active && active.focus) { try { active.focus({ preventScroll: true }); } catch (e) {} }
    }
}
window.copyToClipboard = copyToClipboard;

// Embed any value as a JavaScript string argument inside an inline on*="..." attribute.
// escapeHtml() alone is NOT enough there: the browser decodes &#39; back to ' before the
// handler runs, so a crafted filename/nickname/message could break out and execute code.
// JSON.stringify produces a valid JS string literal; escapeHtml then protects the attribute.
// Usage: onclick="fn(${jsArg(value)})"  (no surrounding quotes)
function jsArg(value) {
    return escapeHtml(JSON.stringify(value == null ? '' : String(value)));
}

function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + units[i];
}

function formatEta(seconds) {
    if (!seconds || seconds <= 0 || !isFinite(seconds)) return '00:00';
    if (seconds >= 3600) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        return `${h}:${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
    }
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
}

async function extractFilesFromDataTransfer(dataTransfer) {
    if (!dataTransfer) return [];
    const items = dataTransfer.items;
    if (!items || !items.length) {
        return Array.from(dataTransfer.files || []);
    }

    const files = [];

    async function traverseDirectory(entry, path = "") {
        if (entry.isFile) {
            return new Promise((resolve) => {
                entry.file((file) => {
                    if (path) {
                        try {
                            Object.defineProperty(file, 'webkitRelativePath', {
                                value: path + file.name,
                                writable: false
                            });
                        } catch (e) {}
                    }
                    files.push(file);
                    resolve();
                }, () => resolve());
            });
        } else if (entry.isDirectory) {
            const dirReader = entry.createReader();
            const readBatch = () => {
                return new Promise((resolve) => {
                    dirReader.readEntries(async (entries) => {
                        if (!entries || !entries.length) {
                            resolve();
                        } else {
                            for (const child of entries) {
                                await traverseDirectory(child, path + entry.name + "/");
                            }
                            await readBatch();
                            resolve();
                        }
                    }, () => resolve());
                });
            };
            await readBatch();
        }
    }

    const promises = [];
    for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (typeof item.webkitGetAsEntry === 'function') {
            const entry = item.webkitGetAsEntry();
            if (entry) {
                promises.push(traverseDirectory(entry));
                continue;
            }
        }
        const file = item.getAsFile ? item.getAsFile() : null;
        if (file) files.push(file);
    }

    if (promises.length > 0) {
        await Promise.all(promises);
    }

    return files.length > 0 ? files : Array.from(dataTransfer.files || []);
}

function getSmartIcon(category, ext) {
    switch (category) {
        case 'image':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
        case 'video':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>';
        case 'audio':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>';
        case 'document':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>';
        case 'archive':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>';
        case 'code':
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>';
        default:
            return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>';
    }
}

// --- MULTI-FILE UPLOAD QUEUE WITH LIVE SPEED, ETA & CANCELLATION ---
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
        this.batchSummaryShown = false;
        clearTimeout(this.hideTimer);
        const speedEl = document.getElementById('queueSpeed');
        if (speedEl && this.activeUploads === 0) speedEl.innerText = 'Starting…';

        // Files added while others are still going join the same batch (one progress bar here and on the Host)
        const busy = this.queue.some(i => i.status === 'uploading' || i.status === 'pending');
        if (!busy || !this.batchId) {
            this.batchId = 'b' + Math.random().toString(36).slice(2, 12);
            this.speed = 0;
            this.speedTime = 0;
        }

        Array.from(files).forEach(file => {
            const item = {
                id: 'upl_' + Math.random().toString(36).substr(2, 9),
                file: file,
                url: uploadUrl,
                status: 'pending',
                batchId: this.batchId,
                loaded: 0,
                xhr: null
            };
            this.queue.push(item);
            this.renderQueueItem(item);
        });

        this.processNext();
    }

    renderQueueItem(item) {
        const list = document.getElementById('queueItemsList');
        if (!list) return;

        const displayName = item.file.webkitRelativePath || item.file.name;
        const el = document.createElement('div');
        el.id = item.id;
        el.style.cssText = "background:var(--input-bg); border:1px solid var(--border-color); border-radius:8px; padding:6px 10px; display:flex; flex-direction:column; gap:4px;";
        el.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px;">
                <span style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:65%;" title="${escapeHtml(displayName)}">${escapeHtml(displayName)}</span>
                <div style="display:flex; align-items:center; gap:6px;">
                    <span id="${item.id}_status" style="color:var(--text-sub); font-family:monospace; font-size:10px;">${formatSize(item.file.size)}</span>
                    <button id="${item.id}_cancel" class="icon-btn" onclick="uploadManager.cancelItem(${jsArg(item.id)})" style="width:18px; height:18px; padding:0; border:none; background:transparent; color:var(--text-muted); cursor:pointer; display:inline-flex; align-items:center; justify-content:center;" title="Cancel Upload" aria-label="Cancel">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                </div>
            </div>
            <div style="height:4px; background:rgba(255,255,255,0.1); border-radius:99px; overflow:hidden;">
                <div id="${item.id}_bar" style="height:100%; width:0%; background:var(--accent-blue); transition:width 0.15s ease;"></div>
            </div>
        `;
        list.appendChild(el);
    }

    cancelItem(id) {
        const item = this.queue.find(i => i.id === id);
        if (!item) return;

        if (item.status === 'uploading') {
            if (item.xhr) {
                try {
                    item.xhr.abort();
                } catch (e) {}
            }
            item.status = 'cancelled';
            this.activeUploads = Math.max(0, this.activeUploads - 1);
            const statusEl = document.getElementById(`${item.id}_status`);
            if (statusEl) statusEl.innerText = 'Cancelled';
            const cancelBtn = document.getElementById(`${item.id}_cancel`);
            if (cancelBtn) cancelBtn.style.display = 'none';
            const barEl = document.getElementById(`${item.id}_bar`);
            if (barEl) {
                barEl.style.width = '100%';
                barEl.style.background = 'var(--accent-red, #ef4444)';
            }
            showToast(`Cancelled: ${item.file.name}`, 'warning');
            this.processNext();
        } else if (item.status === 'pending') {
            item.status = 'cancelled';
            const statusEl = document.getElementById(`${item.id}_status`);
            if (statusEl) statusEl.innerText = 'Removed';
            const cancelBtn = document.getElementById(`${item.id}_cancel`);
            if (cancelBtn) cancelBtn.style.display = 'none';
            this.processNext();
        }
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
                this.updateOverall();
            } else if (this.queue.length > 0) {
                const overallBar = document.getElementById('queueOverallBar');
                if (overallBar) overallBar.style.width = '100%';
                const done = this.queue.filter(i => i.status === 'done').length;
                const failed = this.queue.filter(i => i.status === 'error').length;
                statusEl.innerText = failed ? `${done} sent, ${failed} failed` : 'All uploads complete!';
                const speedDoneEl = document.getElementById('queueSpeed');
                if (speedDoneEl) speedDoneEl.innerText = '';  // don't leave "calculating..." on a finished batch
                // One summary toast per batch (per-file "Saved" toasts used to pile up)
                if (!this.batchSummaryShown && done > 0) {
                    this.batchSummaryShown = true;
                    const plural = done === 1 ? 'file' : 'files';
                    showToast(window.isHostSession ? `Added ${done} ${plural} to Shared` : `Sent ${done} ${plural} to the host`, 'success');
                }
                clearTimeout(this.hideTimer);
                this.hideTimer = setTimeout(() => {
                    const drawer = document.getElementById('floatingQueue');
                    if (drawer) drawer.style.display = 'none';
                    const list = document.getElementById('queueItemsList');
                    if (list) list.innerHTML = '';
                    this.queue = [];
                }, 2500);
            }
        }
    }

    // The current batch as a whole: one percentage and one combined speed for the header and the
    // minimized bar. (Two files upload at once, and each used to write its own speed into the header.)
    updateOverall() {
        const items = this.queue.filter(i => i.batchId === this.batchId && i.status !== 'cancelled');
        const total = items.reduce((n, i) => n + i.file.size, 0);
        const sent = items.reduce((n, i) => n + (i.status === 'done' ? i.file.size : i.status === 'uploading' ? (i.loaded || 0) : 0), 0);
        const pct = total > 0 ? Math.min(100, Math.round((sent / total) * 100)) : 0;
        const remaining = items.filter(i => i.status === 'uploading' || i.status === 'pending').length;

        const now = Date.now();
        if (!this.speedTime || sent < this.speedBytes) {
            this.speedTime = now;
            this.speedBytes = sent;
        } else if (now - this.speedTime >= 400) {
            const cur = (sent - this.speedBytes) / ((now - this.speedTime) / 1000);
            this.speed = this.speed > 0 ? 0.7 * this.speed + 0.3 * cur : cur;
            this.speedTime = now;
            this.speedBytes = sent;
        }

        const bar = document.getElementById('queueOverallBar');
        if (bar) bar.style.width = pct + '%';
        if (!remaining) return;   // processNext writes the finished summary
        const speedEl = document.getElementById('queueSpeed');
        if (speedEl) speedEl.innerText = this.speed > 0 ? `${formatSize(this.speed)}/s` : 'Starting…';
        const statusEl = document.getElementById('queueOverallStatus');
        if (statusEl) statusEl.innerText = `Uploading ${remaining} file${remaining > 1 ? 's' : ''} • ${pct}%`;
    }

    // Tell the server what this batch holds, so the Host shows one bar for all of it
    batchInfo(batchId) {
        const items = this.queue.filter(i => i.batchId === batchId && i.status !== 'cancelled' && i.status !== 'error');
        return { files: items.length, bytes: items.reduce((n, i) => n + i.file.size, 0) };
    }

    uploadSingle(item) {
        this.activeUploads++;
        item.status = 'uploading';

        const statusEl = document.getElementById(`${item.id}_status`);
        const barEl = document.getElementById(`${item.id}_bar`);
        const cancelBtn = document.getElementById(`${item.id}_cancel`);

        const xhr = new XMLHttpRequest();
        item.xhr = xhr;

        let lastLoaded = 0;
        let lastTime = Date.now();
        let lastProgressTime = 0;
        let smoothedSpeed = 0;

        xhr.open('POST', item.url);
        xhr.setRequestHeader('X-File-Name', encodeURIComponent(item.file.name));
        if (item.file.webkitRelativePath) {
            xhr.setRequestHeader('X-Relative-Path', encodeURIComponent(item.file.webkitRelativePath));
        }
        xhr.setRequestHeader('Content-Type', 'application/octet-stream');
        const batch = this.batchInfo(item.batchId);
        xhr.setRequestHeader('X-Upload-Batch', item.batchId);
        xhr.setRequestHeader('X-Batch-Files', String(batch.files));
        xhr.setRequestHeader('X-Batch-Bytes', String(batch.bytes));

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable && item.status === 'uploading') {
                const now = Date.now();
                if (e.loaded < e.total && now - lastProgressTime < 100) return;
                lastProgressTime = now;
                const pct = Math.round((e.loaded / e.total) * 100);
                if (barEl) barEl.style.width = pct + '%';

                const timeDiff = (now - lastTime) / 1000;
                if (timeDiff >= 0.25) {
                    const curSpeed = (e.loaded - lastLoaded) / timeDiff;
                    smoothedSpeed = smoothedSpeed === 0 ? curSpeed : (0.7 * smoothedSpeed + 0.3 * curSpeed);
                    lastLoaded = e.loaded;
                    lastTime = now;
                }

                const remBytes = Math.max(0, e.total - e.loaded);
                const etaSec = smoothedSpeed > 0 ? Math.round(remBytes / smoothedSpeed) : 0;
                const speedText = smoothedSpeed > 0 ? `${formatSize(smoothedSpeed)}/s` : 'calculating...';
                const etaText = etaSec > 0 ? ` • ${formatEta(etaSec)} left` : '';

                if (statusEl) statusEl.innerText = `${pct}% • ${speedText}${etaText}`;
                item.loaded = e.loaded;
                this.updateOverall();
            }
        };

        xhr.onload = () => {
            if (item.status === 'cancelled') return;
            this.activeUploads = Math.max(0, this.activeUploads - 1);
            if (cancelBtn) cancelBtn.style.display = 'none';

            if (xhr.status === 200) {
                item.status = 'done';
                if (barEl) {
                    barEl.style.width = '100%';
                    barEl.style.background = 'var(--accent-green)';
                }
                if (statusEl) statusEl.innerText = 'Done';
                if (navigator.vibrate) navigator.vibrate(50);
            } else {
                item.status = 'error';
                if (statusEl) statusEl.innerText = 'Failed';
                if (navigator.vibrate) navigator.vibrate([80, 50, 80]);
                showToast(`Failed: ${item.file.name}`, 'error');
            }
            loadFiles();
            this.processNext();
        };

        xhr.onerror = () => {
            if (item.status === 'cancelled') return;
            this.activeUploads = Math.max(0, this.activeUploads - 1);
            if (cancelBtn) cancelBtn.style.display = 'none';
            item.status = 'error';
            if (statusEl) statusEl.innerText = 'Network Error';
            showToast(`Upload error: ${item.file.name}`, 'error');
            this.processNext();
        };

        xhr.onabort = () => {
            if (cancelBtn) cancelBtn.style.display = 'none';
        };

        xhr.send(item.file);
    }
}

const uploadManager = new UploadQueueManager();

function handleFiles(files) {
    uploadManager.addFiles(files, '/');
}

// Drop files anywhere on the page (not just the drop zone). A full-window overlay explains
// what will happen; dropping onto an open chat sends the files as chat attachments instead.
function setupDragDrop() {
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) return;

    let overlay = null;
    let dragDepth = 0;
    const isFileDrag = (e) => !!(e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files'));

    const showOverlay = () => {
        if (!overlay) {
            const host = window.isHostSession === true;
            overlay = document.createElement('div');
            overlay.className = 'page-drop-overlay';
            overlay.innerHTML = `<div class="page-drop-card">
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <strong>${host ? 'Drop to share' : 'Drop to send to the host'}</strong>
                <span>${host ? 'Connected devices will be able to download them' : 'Files are saved on the host computer'}</span>
            </div>`;
            document.body.appendChild(overlay);
        }
        overlay.classList.add('visible');
        dropZone.classList.add('dragover');
    };
    const hideOverlay = () => {
        dragDepth = 0;
        if (overlay) overlay.classList.remove('visible');
        dropZone.classList.remove('dragover');
    };

    window.addEventListener('dragenter', (e) => {
        if (!isFileDrag(e)) return;
        e.preventDefault();
        dragDepth++;
        showOverlay();
    }, false);
    window.addEventListener('dragover', (e) => e.preventDefault(), false);
    window.addEventListener('dragleave', (e) => {
        if (!isFileDrag(e)) return;
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0) hideOverlay();
    }, false);
    window.addEventListener('drop', async (e) => {
        e.preventDefault();
        hideOverlay();
        if (!isFileDrag(e)) return;
        const files = await extractFilesFromDataTransfer(e.dataTransfer);
        if (!files || !files.length) return;

        const chatOpen = (document.getElementById('clipboardModal')?.classList.contains('open'))
            || (document.getElementById('hubClipPane')?.classList.contains('active') && e.target.closest?.('#hubClipPane'));
        if (chatOpen) {
            files.forEach(f => uploadChatAttachment(f));
        } else if (window.handleFilesCustom) {
            window.handleFilesCustom(files);
        } else {
            handleFiles(files);
        }
    }, false);
}

// --- FILE FETCHING & RENDERING ---
async function loadFiles() {
    try {
        const res = await fetch('/api/files');
        if (res.status === 401) {
            window.location.reload();
            return;
        }
        if (!res.ok) return;
        const data = await res.json();
        pcFiles = data.host || data.pc || [];
        mobileFiles = data.client || data.mobile || [];

        renderPCFiles();
        renderMobileFiles();
    } catch (e) {}
}

function setCountBadge(id, count) {
    const el = document.getElementById(id);
    if (el) el.innerText = count;
}

function renderPCFiles() {
    const query = (document.getElementById('searchPC')?.value || '').toLowerCase();
    const filtered = pcFiles.filter(f => f.name.toLowerCase().includes(query));
    setCountBadge('sharedCount', pcFiles.length);
    const emptyMsg = query ? 'No shared files match your search'
        : (window.isHostSession ? 'Nothing shared yet. Drop files on the left to share them.' : 'The host hasn\'t shared any files yet');
    renderFileList(filtered, 'file-list', emptyMsg, 'shared');
}

function renderMobileFiles() {
    const query = (document.getElementById('searchMobile')?.value || '').toLowerCase();
    const filtered = mobileFiles.filter(f => f.name.toLowerCase().includes(query));
    setCountBadge('receivedCount', mobileFiles.length);
    renderFileList(filtered, 'mobile-list', query ? 'No received files match your search' : 'No files received yet. Files sent from phones land here.', 'received');
}

// "just now", "5 min ago", "3 h ago", "Yesterday", "12 Nov"
function formatRelativeTime(unixSeconds) {
    if (!unixSeconds) return '';
    const diff = Math.max(0, Date.now() / 1000 - unixSeconds);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
    if (diff < 172800) return 'Yesterday';
    return new Date(unixSeconds * 1000).toLocaleDateString([], { day: 'numeric', month: 'short' });
}

function renderFileList(files, elementId, emptyMsg, folderType) {
    const list = document.getElementById(elementId);
    if (!list) return;

    if (!files.length) {
        list.innerHTML = `<li class="empty-state">${escapeHtml(emptyMsg)}</li>`;
        return;
    }

    const isHost = window.isHostSession === true;

    list.innerHTML = files.map(f => {
        const icon = getSmartIcon(f.category, f.ext);
        const size = formatSize(f.size);
        const encName = encodeURIComponent(f.name);
        const previewCall = `openPreview(${jsArg(f.name)}, ${jsArg(f.category)}, ${Number(f.size) || 0})`;

        const age = formatRelativeTime(f.mtime);
        const catClass = /^[a-z]+$/.test(f.category || '') ? `cat-${f.category}` : '';

        return `
        <li class="file-row">
            <div class="file-icon ${catClass}">${icon}</div>
            <div class="file-details">
                <a href="javascript:void(0)" onclick="${previewCall}" class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</a>
                <div class="file-size">${size}${age ? `<span class="file-meta-sep">&bull;</span>${escapeHtml(age)}` : ''}</div>
            </div>
            <div class="file-actions">
                <button class="action-circle-btn" onclick="${previewCall}" title="Preview"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
                <a href="/download/${encName}" class="action-circle-btn" title="Download"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></a>
                ${isHost ? `<button class="action-circle-btn btn-del" onclick="deleteFile(${jsArg(f.name)}, ${jsArg(folderType)})" title="Delete"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>` : ''}
            </div>
        </li>`;
    }).join('');
}

// --- MEDIA PREVIEW LIGHTBOX MODAL ---
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
        body.innerHTML = `<img src="${fileUrl}" alt="${escapeHtml(filename)}">`;
        // Some formats (e.g. iPhone HEIC photos) can't be decoded by most browsers
        body.querySelector('img').addEventListener('error', () => {
            body.innerHTML = previewUnavailableHtml(filename, size,
                "This browser can't display this image format (common for iPhone HEIC photos). Download it to view.");
        }, { once: true });
    } else if (category === 'video') {
        body.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:12px; width:100%; align-items:center;">
                <video id="activeMediaElement" controls autoplay playsinline style="width:100%; max-height:60vh; border-radius:12px; background:#000;">
                    <source src="${fileUrl}">
                    Your browser does not support HTML5 video streaming.
                </video>
                <div style="display:flex; align-items:center; justify-content:space-between; width:100%; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--text-sub);">
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="background:var(--accent-blue-subtle, rgba(0,102,255,0.1)); color:var(--accent-blue, #0066ff); padding:2px 8px; border-radius:6px; font-weight:600; font-size:11px;">HTTP 206 Seekable Stream</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <button type="button" class="btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="adjustMediaSeek(-10)" title="Rewind 10s">-10s</button>
                        <button type="button" class="btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="adjustMediaSeek(10)" title="Forward 10s">+10s</button>
                        <select onchange="setMediaPlaybackRate(this.value)" class="search-input-box" style="padding:2px 6px; font-size:12px; width:auto; height:28px;">
                            <option value="0.75">0.75x</option>
                            <option value="1.0" selected>1.0x</option>
                            <option value="1.25">1.25x</option>
                            <option value="1.5">1.5x</option>
                            <option value="2.0">2.0x</option>
                        </select>
                    </div>
                </div>
            </div>`;
    } else if (category === 'audio') {
        body.innerHTML = `
            <div style="display:flex; flex-direction:column; align-items:center; gap:16px; padding:20px; width:100%; max-width:440px; margin:0 auto;">
                <div style="width:56px; height:56px; border-radius:50%; background:var(--accent-blue-subtle, rgba(0,102,255,0.1)); color:var(--accent-blue, #0066ff); display:flex; align-items:center; justify-content:center;">
                    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
                </div>
                <div style="font-weight:600; font-size:15px; text-align:center; word-break:break-word;">${escapeHtml(filename)}</div>
                <audio id="activeMediaElement" controls autoplay style="width:100%;">
                    <source src="${fileUrl}">
                </audio>
                <div style="display:flex; align-items:center; justify-content:space-between; width:100%; flex-wrap:wrap; gap:8px; font-size:12px; color:var(--text-sub);">
                    <span style="background:var(--accent-blue-subtle, rgba(0,102,255,0.1)); color:var(--accent-blue, #0066ff); padding:2px 8px; border-radius:6px; font-weight:600; font-size:11px;">HTTP 206 Audio Stream</span>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <button type="button" class="btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="adjustMediaSeek(-10)" title="Rewind 10s">-10s</button>
                        <button type="button" class="btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="adjustMediaSeek(10)" title="Forward 10s">+10s</button>
                        <select onchange="setMediaPlaybackRate(this.value)" class="search-input-box" style="padding:2px 6px; font-size:12px; width:auto; height:28px;">
                            <option value="0.75">0.75x</option>
                            <option value="1.0" selected>1.0x</option>
                            <option value="1.25">1.25x</option>
                            <option value="1.5">1.5x</option>
                            <option value="2.0">2.0x</option>
                        </select>
                    </div>
                </div>
            </div>`;
    } else if (category === 'code' || /\.(txt|log|md|csv)$/i.test(filename)) {
        const PREVIEW_LIMIT = 256 * 1024;  // never pull a multi-GB log into the page
        try {
            const res = await fetch(fileUrl, { headers: { Range: `bytes=0-${PREVIEW_LIMIT - 1}` } });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const bytes = new Uint8Array(await res.arrayBuffer());
            if (bytes.subarray(0, 8192).includes(0)) {
                body.innerHTML = previewUnavailableHtml(filename, size, "This looks like a binary file, so it can't be shown as text.");
                return;
            }
            const text = new TextDecoder('utf-8').decode(bytes);
            const truncated = size > bytes.length;
            body.innerHTML = `
                <div style="width:100%; display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:8px;">
                    <span class="preview-note" style="margin:0; flex:1; min-width:0;">${truncated ? `Showing the first ${formatSize(bytes.length)} of ${formatSize(size)}` : ''}</span>
                    <button class="btn-secondary" style="white-space:nowrap; flex-shrink:0;" onclick="copyPreviewText()"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy Text</button>
                </div>
                <pre id="previewTextContent"><code>${escapeHtml(text)}</code></pre>`;
        } catch (e) {
            body.innerHTML = previewUnavailableHtml(filename, size, 'Could not load the text preview.');
        }
    } else {
        body.innerHTML = previewUnavailableHtml(filename, size, '');
    }
}

// Fallback card for files that can't be previewed inline
function previewUnavailableHtml(filename, size, reason) {
    const fileUrl = `/view/${encodeURIComponent(filename)}`;
    return `
        <div class="preview-unavailable">
            <div style="margin-bottom:12px;"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg></div>
            <h3 style="color:var(--text-main); word-break:break-word;">${escapeHtml(filename)}</h3>
            <p style="margin:8px 0 ${reason ? '8px' : '20px'} 0;">${formatSize(size)}</p>
            ${reason ? `<p style="margin:0 auto 20px auto; max-width:360px; font-size:13px; line-height:1.5;">${escapeHtml(reason)}</p>` : ''}
            <a href="${fileUrl}" target="_blank" rel="noopener" class="btn-secondary">Open in New Tab</a>
        </div>`;
}

function closePreview() {
    const modal = document.getElementById('previewModal');
    const body = document.getElementById('previewModalBody');
    const media = document.getElementById('activeMediaElement');
    if (media) {
        try {
            media.pause();
            media.src = '';
        } catch (e) {}
    }
    if (modal) modal.classList.remove('open');
    if (body) body.innerHTML = '';
}

function adjustMediaSeek(deltaSeconds) {
    const media = document.getElementById('activeMediaElement');
    if (media) {
        media.currentTime = Math.max(0, Math.min(media.duration || 999999, media.currentTime + deltaSeconds));
    }
}

function setMediaPlaybackRate(rate) {
    const media = document.getElementById('activeMediaElement');
    if (media) {
        media.playbackRate = parseFloat(rate) || 1.0;
    }
}

function copyPreviewText() {
    const textEl = document.getElementById('previewTextContent');
    if (textEl) {
        copyToClipboard(textEl.innerText).then((ok) => {
            showToast(ok ? 'Copied to clipboard!' : 'Could not copy. Select the text and copy it manually.', ok ? 'copy' : 'error');
        });
    }
}

// --- SHARED CLIPBOARD & CHAT STREAM ---
let chatMessagesCache = [];
let unreadChatCount = 0;
window.isChatModalOpen = false;

function playChatChime() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(587.33, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.18);
    } catch(e) {}
}

function handleIncomingChatMessage(msg) {
    if (!msg) return;
    const isSelf = isOwnChatMessage(msg);
    if (!isSelf) {
        playChatChime();
        if (navigator.vibrate) navigator.vibrate([40, 30, 40]);
        
        // If chat modal or tab is not currently viewed, increment unread badge
        if (!window.isChatModalOpen) {
            unreadChatCount++;
            updateChatUnreadBadges();
        }

        // Auto-copy to the host PC's clipboard happens on the server (host setting). Never call the
        // clipboard API here: writing without a click triggers a browser permission prompt.
    }
}
window.handleIncomingChatMessage = handleIncomingChatMessage;

function updateChatUnreadBadges() {
    const directBadge = document.getElementById('clientChatDirectBadge');
    const navBadge = document.getElementById('clientChatUnreadBadge');
    const hostBadge = document.getElementById('hostChatUnreadBadge');
    
    [directBadge, navBadge, hostBadge].forEach(el => {
        if (!el) return;
        if (unreadChatCount > 0) {
            el.innerText = unreadChatCount > 99 ? '99+' : unreadChatCount;
            el.style.display = 'inline-flex';
        } else {
            el.style.display = 'none';
        }
    });
}
window.updateChatUnreadBadges = updateChatUnreadBadges;

function clearChatUnread() {
    unreadChatCount = 0;
    updateChatUnreadBadges();
}
window.clearChatUnread = clearChatUnread;

async function uploadChatAttachment(file, fallbackName) {
    if (!file) return;
    const filename = file.name || fallbackName || `chat_attachment_${Date.now()}.png`;
    showToast(`Uploading ${filename}...`, 'info');
    try {
        const res = await fetch('/upload?dest=chat', {
            method: 'POST',
            headers: {
                'X-File-Name': encodeURIComponent(filename),
                'Content-Type': file.type || 'application/octet-stream'
            },
            body: file
        });
        if (res.ok) {
            showToast('Attachment shared in chat!', 'chat');
            loadClipboard();
        } else {
            showToast('Failed to upload attachment', 'error');
        }
    } catch(err) {
        showToast('Error uploading attachment', 'error');
    }
}
window.uploadChatAttachment = uploadChatAttachment;

function setupChatPasteListener() {
    document.addEventListener('paste', async (e) => {
        const chatInput = document.getElementById('clipboardInput');
        const modal = document.getElementById('clipboardModal');
        const hubPane = document.getElementById('hubClipPane');
        
        // Only handle paste if user is typing in chat input or chat is currently visible
        const isInputFocused = document.activeElement === chatInput;
        const isChatVisible = (modal && modal.classList.contains('open')) || (hubPane && hubPane.classList.contains('active'));
        if (!isInputFocused && !isChatVisible) return;

        const clipboardData = e.clipboardData || window.clipboardData;
        if (!clipboardData || !clipboardData.items) return;

        for (let i = 0; i < clipboardData.items.length; i++) {
            const item = clipboardData.items[i];
            if (item.type.indexOf('image') !== -1) {
                const blob = item.getAsFile();
                if (blob) {
                    e.preventDefault();
                    uploadChatAttachment(blob, `screenshot_${Date.now()}.png`);
                    return;
                }
            }
        }
    });
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupChatPasteListener);
} else {
    setupChatPasteListener();
}

function formatChatText(text) {
    if (!text) return '';
    const escaped = escapeHtml(text);
    return escaped.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer" class="chat-link">$1</a>');
}

const CHAT_COPY_SVG = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const CHAT_CHECK_SVG = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';

function copyChatMessage(btn, text) {
    if (!text) return;
    copyToClipboard(text).then((ok) => {
        if (!ok) {
            showToast('Could not copy. Long-press the message to copy it.', 'error');
            return;
        }
        showToast('Copied to clipboard!', 'copy');
        if (btn) {
            btn.innerHTML = CHAT_CHECK_SVG;
            btn.classList.add('copied');
            setTimeout(() => { btn.innerHTML = CHAT_COPY_SVG; btn.classList.remove('copied'); }, 1500);
        }
    });
}
window.copyChatMessage = copyChatMessage;

// Was this chat message sent by this device? Host: messages flagged is_host. Client: match on the
// session id the server reports (/api/info peer_id), falling back to nickname for older servers.
let currentPeerId = '';
function isOwnChatMessage(msg) {
    if (!msg) return false;
    if (window.isHostSession) return !!msg.is_host;
    if (currentPeerId && msg.sender_id) return msg.sender_id === currentPeerId;
    const myNickname = currentClientNickname || localStorage.getItem('pyshare_device_name') || '';
    return Boolean(myNickname && msg.sender === myNickname);
}

function renderClipboardChat(messages) {
    chatMessagesCache = Array.isArray(messages) ? messages : [];
    
    // 1. Update count pill if present
    const countEl = document.getElementById('chatMessageCount');
    if (countEl) {
        countEl.innerText = `${chatMessagesCache.length}/30`;
    }

    // 2. Render in chat list (#clipboardChatList)
    const listEl = document.getElementById('clipboardChatList');
    if (listEl) {
        if (chatMessagesCache.length === 0) {
            listEl.innerHTML = `<div class="hub-empty">No messages yet. Send text, a link, or paste a screenshot.</div>`;
        } else {
            let html = '';
            chatMessagesCache.forEach(msg => {
                const isSelf = isOwnChatMessage(msg);
                const roleClass = isSelf ? 'self' : (msg.is_host ? 'host' : 'peer');
                const timeText = msg.time_str || (msg.timestamp ? new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '');
                const senderLabel = isSelf ? 'You' : (msg.sender || 'Device');

                let attachmentHtml = '';
                if (msg.attachment) {
                    if (msg.attachment.is_image) {
                        attachmentHtml = `<div class="chat-attachment-img-box"><img src="${escapeHtml(msg.attachment.preview_url || msg.attachment.url)}" alt="${escapeHtml(msg.attachment.name)}" onclick="window.open(${jsArg(msg.attachment.url)}, '_blank')"></div>`;
                    } else {
                        attachmentHtml = `<a href="${escapeHtml(msg.attachment.url)}" download="${escapeHtml(msg.attachment.name)}" class="chat-file-card">`
                            + `<span style="color:var(--accent-cyan); display:inline-flex;">${getToastSvg('save')}</span>`
                            + `<span style="flex:1; min-width:0;"><span style="display:block; font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(msg.attachment.name)}</span>`
                            + `<span style="display:block; font-size:10px; color:var(--text-sub);">${formatSize(msg.attachment.size || 0)}</span></span></a>`;
                    }
                }

                // Keep bubble markup free of template whitespace: .chat-text uses white-space: pre-wrap
                const bubble = `<div class="chat-bubble">${msg.text ? `<div class="chat-text">${formatChatText(msg.text)}</div>` : ''}${attachmentHtml}</div>`;
                const copyBtn = msg.text
                    ? `<button type="button" class="chat-copy-btn" onclick="copyChatMessage(this, ${jsArg(msg.text)})" title="Copy text" aria-label="Copy message">${CHAT_COPY_SVG}</button>`
                    : '';

                html += `
                    <div class="chat-msg-row ${roleClass}">
                        <div class="chat-msg-header"><span class="chat-sender-name">${escapeHtml(senderLabel)}</span><span class="chat-msg-time">${escapeHtml(timeText)}</span></div>
                        <div class="chat-msg-body">${bubble}${copyBtn}</div>
                    </div>`;
            });
            listEl.innerHTML = html;
            listEl.scrollTop = listEl.scrollHeight;
        }
    }

    // 3. Fallback for legacy single-item display if still present
    const legacyDisplay = document.getElementById('clipboardCurrent');
    if (legacyDisplay) {
        const latest = chatMessagesCache.length > 0 ? chatMessagesCache[chatMessagesCache.length - 1].text : '';
        renderClipboard(latest);
    }
}
window.renderClipboardChat = renderClipboardChat;

async function loadClipboard() {
    try {
        const res = await fetch('/api/text');
        if (res.status === 401) {
            window.location.reload();
            return;
        }
        if (res.ok) {
            const data = await res.json();
            if (data.messages) {
                renderClipboardChat(data.messages);
            } else if (data.text) {
                renderClipboardChat([{ text: data.text, sender: "Clipboard", timestamp: data.timestamp }]);
            }
            lastClipboardTs = data.timestamp || 0;
        }
    } catch (e) {}
}

function renderClipboard(text) {
    const display = document.getElementById('clipboardCurrent');
    if (!display) return;
    if (text && text.trim().length > 0) {
        display.innerHTML = `
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80%; font-size:12px;">${escapeHtml(text)}</span>
            <button class="btn-secondary" onclick="copySharedClipboard()" style="padding:4px 10px; font-size:11px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy</button>
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
        copyToClipboard(raw).then((ok) => {
            showToast(ok ? 'Copied to system clipboard!' : 'Could not copy to the clipboard', ok ? 'copy' : 'error');
        });
    }
}

let chatSendInFlight = false;

async function sendClipboard() {
    const input = document.getElementById('clipboardInput');
    if (!input) return;
    const text = input.value.trim();
    if (!text || chatSendInFlight) return;

    chatSendInFlight = true;
    const sendBtn = document.querySelector('.btn-send');
    if (sendBtn) sendBtn.disabled = true;
    try {
        const res = await fetch('/api/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });
        if (res.ok) {
            input.value = '';
            // The server returns the updated conversation: render it straight away
            const data = await res.json().catch(() => null);
            if (data && Array.isArray(data.messages)) {
                renderClipboardChat(data.messages);
                if (data.timestamp) lastClipboardTs = data.timestamp;
            } else {
                loadClipboard();
            }
        } else if (res.status === 401) {
            showToast('Your session ended. Reconnecting...', 'error');
            setTimeout(() => window.location.reload(), 1500);
        } else if (res.status === 413) {
            showToast('That message is too long (max 64 KB)', 'warning');
        } else {
            showToast(`Message not sent (server error ${res.status})`, 'error');
        }
    } catch (e) {
        showToast('Message not sent. Check your Wi-Fi connection.', 'error');
    } finally {
        chatSendInFlight = false;
        if (sendBtn) sendBtn.disabled = false;
    }
}

// Phones: when the keyboard opens, keep the newest messages in view above it
document.addEventListener('focusin', (e) => {
    if (e.target && e.target.id === 'clipboardInput') {
        setTimeout(() => {
            const list = document.getElementById('clipboardChatList');
            if (list) list.scrollTop = list.scrollHeight;
        }, 300);
    }
});

// --- HOST ACTIONS ---
function deleteFile(filename, folder) {
    const isShared = folder === 'shared';
    showPyShareConfirm({
        title: isShared ? 'Remove from Shared?' : 'Delete this file?',
        message: isShared
            ? `"${filename}" will no longer be available to connected devices.`
            : `"${filename}" will be permanently deleted from the Received folder on this PC.`,
        confirmText: isShared ? 'Remove' : 'Delete',
        isDanger: true,
        onConfirm: async () => {
            try {
                const res = await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: filename, folder: folder })
                });
                if (res.ok) {
                    showToast(isShared ? `Removed ${filename} from Shared` : `Deleted ${filename}`, 'trash');
                    loadFiles();
                } else {
                    showToast('Failed to delete file', 'error');
                }
            } catch (e) {
                showToast('Error deleting file', 'error');
            }
        }
    });
}

function disconnectServer() {
    showPyShareConfirm({
        title: "PyShare",
        message: "Stop PyShare server? All connections will be terminated.",
        confirmText: "Stop Server",
        isDanger: true,
        onConfirm: () => {
            fetch('/shutdown').finally(() => {
                document.body.innerHTML = `
                <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;color:#ef4444;text-align:center;font-family:sans-serif;padding:20px;">
                    <div style="margin-bottom:16px;"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><rect x="9" y="9" width="6" height="6"/></svg></div>
                    <h2>PyShare Server Stopped</h2>
                    <p style="color:#94a3b8;margin-top:8px;">You can now safely close this window.</p>
                </div>`;
            });
        }
    });
}

// --- Client Device Nickname Management (currentClientNickname is declared at the top) ---
async function initClientDevice() {
    const nameEl = document.getElementById('clientDeviceNameText');
    if (nameEl && currentClientNickname) {
        nameEl.innerText = currentClientNickname;
    }

    try {
        const res = await fetch('/api/info');
        if (res.ok) {
            const data = await res.json();
            if (data && data.nickname) {
                currentClientNickname = data.nickname;
                if (nameEl) nameEl.innerText = data.nickname;
                try { localStorage.setItem('pyshare_device_name', data.nickname); } catch(e) {}
            }
            if (data && data.peer_id) currentPeerId = data.peer_id;
            if (data && data.host_name && typeof setHostNameDisplays === 'function') setHostNameDisplays(data.host_name);
            // Chat may have rendered before we knew who we are: re-render so own messages align right
            if (chatMessagesCache.length) renderClipboardChat(chatMessagesCache);
        }
    } catch (e) {}
}

async function promptRenameDevice() {
    let newName;
    if (typeof showPySharePrompt === 'function') {
        newName = await showPySharePrompt({
            title: 'Rename This Device',
            message: 'Choose a nickname so the host easily recognizes your device:',
            defaultValue: currentClientNickname,
            placeholder: "e.g. Alex's iPhone, Work Laptop",
            confirmText: 'Save Nickname'
        });
    } else {
        newName = prompt('Enter a nickname for this device:', currentClientNickname);
    }

    if (!newName || newName.trim() === '' || newName.trim() === currentClientNickname) return;
    newName = newName.trim();

    try {
        const res = await fetch('/api/device/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nickname: newName })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            currentClientNickname = data.nickname || newName;
            const nameEl = document.getElementById('clientDeviceNameText');
            if (nameEl) nameEl.innerText = currentClientNickname;
            try { localStorage.setItem('pyshare_device_name', currentClientNickname); } catch(e) {}
            showToast(`Device renamed: ${currentClientNickname}`, 'rename');
        } else {
            showToast('Failed to rename device', 'error');
        }
    } catch (e) {
        showToast('Error updating nickname', 'error');
    }
}
window.promptRenameDevice = promptRenameDevice;
