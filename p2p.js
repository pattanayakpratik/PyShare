/* ==========================================================================
   PyShare v4.7.0 - WebRTC Peer-to-Peer Transfer Engine
   Direct Device-to-Device • Zero App Install • Works across any browser
   ========================================================================== */

const CHUNK_SIZE = 32 * 1024; // 32KB chunk slice for smooth WebRTC backpressure
let peer = null;
let activeConnections = [];
let currentPin = "";
let isHost = false;

let sharedFilesList = [];
let receivedFilesList = [];
let activeTransfers = {}; // fileId -> state
let lastSpeedCheck = Date.now();
let lastSpeedLoaded = 0;

// Theme Initialization
(function initTheme() {
    const urlTheme = new URLSearchParams(window.location.search).get('theme');
    const savedTheme = urlTheme || localStorage.getItem('pyshare_theme') || document.documentElement.getAttribute('data-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    if (urlTheme) {
        try { localStorage.setItem('pyshare_theme', urlTheme); } catch(e) {}
    }
})();

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
    }, 2800);
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

function getCategory(ext) {
    ext = (ext || '').toLowerCase().lstrip ? ext.toLowerCase().lstrip('.') : (ext || '').toLowerCase().replace(/^\./, '');
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif'].includes(ext)) return 'image';
    if (['mp4', 'mkv', 'mov', 'webm', 'avi', 'wmv', 'm4v'].includes(ext)) return 'video';
    if (['mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a', 'wma'].includes(ext)) return 'audio';
    if (['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'csv'].includes(ext)) return 'document';
    if (['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'].includes(ext)) return 'archive';
    if (['html', 'css', 'js', 'json', 'py', 'ts', 'jsx', 'tsx', 'cpp', 'c', 'java', 'go', 'rs', 'sh', 'md'].includes(ext)) return 'code';
    return 'other';
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

// --- PEERJS WEBRTC P2P MANAGER ---
const PEER_CONFIG = {
    debug: 1,
    config: {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' },
            { urls: 'stun:global.stun.twilio.com:3478' }
        ]
    }
};

// Start as Mobile Host
function startHostMode() {
    isHost = true;
    currentPin = Math.floor(1000 + Math.random() * 9000).toString();
    const peerId = 'pyshare-v4-' + currentPin;

    document.getElementById('screenLanding').style.display = 'none';
    document.getElementById('screenHost').style.display = 'flex';
    document.getElementById('hostPinDisplay').innerText = currentPin;
    generateHostQR(currentPin);
    updateConnectionStatus('Ready! Waiting for device to scan...', 'blue');

    try {
        peer = new Peer(peerId, PEER_CONFIG);

        peer.on('open', (id) => {
            updateConnectionStatus('Ready! Waiting for device to scan...', 'blue');
            generateHostQR(currentPin);
            showToast(`Room PIN created: ${currentPin}`, '🔑');
        });

        peer.on('connection', (conn) => {
            setupConnectionHandlers(conn);
        });

        peer.on('error', (err) => {
            if (err.type === 'unavailable-id') {
                // Pin collision, retry with new pin
                startHostMode();
            } else {
                showToast(`P2P notice: ${err.type}`, '⚠️');
            }
        });
    } catch (e) {
        showToast('WebRTC initialization failed', '❌');
    }
}

// Generate QR Code on Screen
function generateHostQR(pin) {
    const qrContainer = document.getElementById('qrcodeContainer');
    if (!qrContainer) return;
    qrContainer.innerHTML = '';

    const shareUrl = window.location.origin + window.location.pathname + '?room=' + pin;
    
    // Check if QRCode library loaded
    if (window.QRCode) {
        new QRCode(qrContainer, {
            text: shareUrl,
            width: 170,
            height: 170,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.M
        });
    } else {
        qrContainer.innerHTML = `<a href="${shareUrl}" target="_blank" style="font-size:12px;color:var(--accent-blue);word-break:break-all;">${shareUrl}</a>`;
    }

    const linkEl = document.getElementById('hostShareLink');
    if (linkEl) {
        linkEl.innerText = shareUrl;
        linkEl.dataset.url = shareUrl;
    }
}

// Copy Share Link
function copyShareLink() {
    const linkEl = document.getElementById('hostShareLink');
    const url = linkEl ? linkEl.dataset.url : (window.location.origin + window.location.pathname + '?room=' + currentPin);
    if (navigator.clipboard && url) {
        navigator.clipboard.writeText(url).then(() => {
            showToast('Share link copied to clipboard!', '📋');
        });
    }
}

// Start as Mobile Client (Join Mode)
function startJoinMode(roomPin = null) {
    isHost = false;
    document.getElementById('screenLanding').style.display = 'none';

    if (roomPin && roomPin.length === 4) {
        connectToHost(roomPin);
    } else {
        document.getElementById('screenKeypad').style.display = 'flex';
    }
}

// Connect to Host Peer via PIN
function connectToHost(pin) {
    document.getElementById('screenKeypad').style.display = 'none';
    document.getElementById('screenClient').style.display = 'flex';
    updateClientStatus('Connecting to peer...', 'yellow');

    const targetPeerId = 'pyshare-v4-' + pin;
    
    try {
        peer = new Peer(PEER_CONFIG);

        peer.on('open', () => {
            const conn = peer.connect(targetPeerId, {
                reliable: true
            });
            setupConnectionHandlers(conn);
        });

        peer.on('error', (err) => {
            updateClientStatus('Connection failed. Check PIN.', 'red');
            showToast(`Connection failed: ${err.type}`, '❌');
        });
    } catch (e) {
        showToast('WebRTC connection error', '❌');
    }
}

// Setup DataChannel Event Handlers
function setupConnectionHandlers(conn) {
    conn.on('open', () => {
        activeConnections.push(conn);
        
        if (isHost) {
            updateConnectionStatus('Connected to Client Peer! ⚡', 'green');
            document.getElementById('hostConnectedBadge').style.display = 'flex';
            showToast('Peer connected! Ready to transfer.', '✅');
            
            // Sync current shared files list with newly connected client
            syncSharedFilesToPeer(conn);
        } else {
            updateClientStatus('Connected to Host! ⚡', 'green');
            showToast('Connected! Ready to transfer.', '✅');
        }
    });

    conn.on('data', (data) => {
        handleIncomingData(data, conn);
    });

    conn.on('close', () => {
        activeConnections = activeConnections.filter(c => c !== conn);
        if (isHost) {
            if (activeConnections.length === 0) {
                updateConnectionStatus('Ready! Waiting for device to scan...', 'blue');
                document.getElementById('hostConnectedBadge').style.display = 'none';
            }
            showToast('Peer disconnected', '⚠️');
        } else {
            updateClientStatus('Disconnected from Host', 'red');
            showToast('Disconnected from Host', '⚠️');
        }
    });

    conn.on('error', (err) => {
        showToast(`P2P Transfer Notice: ${err}`, '⚠️');
    });
}

function updateConnectionStatus(text, color) {
    const el = document.getElementById('hostStatusPill');
    if (el) {
        el.innerHTML = `<span class="status-dot" style="background:${color === 'green' ? 'var(--accent-green)' : color === 'yellow' ? 'var(--accent-yellow, #eab308)' : 'var(--accent-blue)'}"></span> <span>${escapeHtml(text)}</span>`;
    }
}

function updateClientStatus(text, color) {
    const el = document.getElementById('clientStatusPill');
    if (el) {
        el.innerHTML = `<span class="status-dot" style="background:${color === 'green' ? 'var(--accent-green)' : color === 'yellow' ? 'var(--accent-yellow, #eab308)' : 'var(--accent-red)'}"></span> <span>${escapeHtml(text)}</span>`;
    }
}

// --- FILE STREAMING & RECEIVING ENGINE ---
function handleIncomingData(msg, conn) {
    if (!msg || !msg.type) return;

    // 1. File Metadata Arrival
    if (msg.type === 'file_start') {
        activeTransfers[msg.id] = {
            meta: msg,
            chunks: [],
            receivedBytes: 0,
            startTime: Date.now()
        };
        showFloatingQueue();
        renderQueueItem(msg.id, msg.name, msg.size, 'download');
    }

    // 2. Binary File Chunk
    else if (msg.type === 'file_chunk') {
        const transfer = activeTransfers[msg.id];
        if (!transfer) return;

        transfer.chunks.push(msg.chunk);
        transfer.receivedBytes += msg.chunk.byteLength;

        updateQueueProgress(msg.id, transfer.receivedBytes, transfer.meta.size);
    }

    // 3. File Transfer Complete
    else if (msg.type === 'file_end') {
        const transfer = activeTransfers[msg.id];
        if (!transfer) return;

        const blob = new Blob(transfer.chunks, { type: transfer.meta.mime });
        const objectUrl = URL.createObjectURL(blob);

        const fileRecord = {
            id: transfer.meta.id,
            name: transfer.meta.name,
            size: transfer.meta.size,
            category: transfer.meta.category,
            ext: transfer.meta.ext,
            url: objectUrl,
            blob: blob
        };

        receivedFilesList.push(fileRecord);
        delete activeTransfers[msg.id];

        markQueueDone(msg.id);
        renderReceivedFilesUI();
        showToast(`Saved: ${fileRecord.name}`, '📥');
    }

    // 4. File Catalog Sync (From Host to Client)
    else if (msg.type === 'files_catalog') {
        renderPeerCatalog(msg.files);
    }

    // 5. Request File Download (Client asks Host for a specific shared file)
    else if (msg.type === 'request_file') {
        const target = sharedFilesList.find(f => f.id === msg.id);
        if (target && target.file) {
            streamFileToConnection(target.file, conn);
        }
    }

    // 6. Universal Shared Clipboard
    else if (msg.type === 'clipboard') {
        renderClipboardText(msg.text);
        showToast('Clipboard updated by peer!', '📋');
    }
}

// Send Files to All Active Peers
function sendFiles(files) {
    if (!files || !files.length) return;
    if (activeConnections.length === 0) {
        showToast('No peer connected yet. Scan QR code to connect!', '⚠️');
        return;
    }

    showFloatingQueue();

    Array.from(files).forEach(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        const category = getCategory(ext);
        const fileId = 'f_' + Math.random().toString(36).substr(2, 9);

        // Store in local shared files if host
        if (isHost) {
            sharedFilesList.push({
                id: fileId,
                name: file.name,
                size: file.size,
                category: category,
                ext: ext,
                file: file
            });
            renderHostSharedFilesUI();
        }

        renderQueueItem(fileId, file.name, file.size, 'upload');

        // Stream file to all connected peers
        activeConnections.forEach(conn => {
            streamFileToConnection(file, conn, fileId);
        });
    });
}

// Stream File using FileReader and Backpressure Control
function streamFileToConnection(file, conn, existingId = null) {
    const fileId = existingId || ('f_' + Math.random().toString(36).substr(2, 9));
    const ext = file.name.split('.').pop().toLowerCase();
    const category = getCategory(ext);

    // 1. Send Header
    conn.send({
        type: 'file_start',
        id: fileId,
        name: file.name,
        size: file.size,
        category: category,
        ext: ext,
        mime: file.type || 'application/octet-stream'
    });

    let offset = 0;
    const reader = new FileReader();

    function readNextSlice() {
        const slice = file.slice(offset, offset + CHUNK_SIZE);
        reader.readAsArrayBuffer(slice);
    }

    reader.onload = (e) => {
        const buffer = e.target.result;
        try {
            conn.send({
                type: 'file_chunk',
                id: fileId,
                chunk: buffer
            });
            offset += buffer.byteLength;

            updateQueueProgress(fileId, offset, file.size);

            if (offset < file.size) {
                // Backpressure Check: wait if buffer exceeds 1MB
                if (conn.dataChannel && conn.dataChannel.bufferedAmount > 1024 * 1024) {
                    conn.dataChannel.onbufferedamountlow = () => {
                        conn.dataChannel.onbufferedamountlow = null;
                        readNextSlice();
                    };
                } else {
                    readNextSlice();
                }
            } else {
                conn.send({
                    type: 'file_end',
                    id: fileId
                });
                markQueueDone(fileId);
                showToast(`Sent: ${file.name}`, '✅');
            }
        } catch (err) {
            showToast('Transfer interrupted', '❌');
        }
    };

    readNextSlice();
}

function syncSharedFilesToPeer(conn) {
    const catalog = sharedFilesList.map(f => ({
        id: f.id,
        name: f.name,
        size: f.size,
        category: f.category,
        ext: f.ext
    }));
    conn.send({
        type: 'files_catalog',
        files: catalog
    });
}

function requestFileFromHost(fileId) {
    if (activeConnections.length > 0) {
        showToast('Requesting file download...', '⏳');
        activeConnections[0].send({
            type: 'request_file',
            id: fileId
        });
    }
}

// --- FLOATING QUEUE & PROGRESS UI ---
function showFloatingQueue() {
    const drawer = document.getElementById('floatingQueue');
    if (drawer) drawer.style.display = 'flex';
}

function renderQueueItem(id, filename, totalSize, direction) {
    lastSpeedLoaded = 0;
    lastSpeedCheck = Date.now();
    const list = document.getElementById('queueItemsList');
    if (!list) return;

    const el = document.createElement('div');
    el.id = 'q_' + id;
    el.style.cssText = "background:var(--input-bg); border:1px solid var(--border-color); border-radius:10px; padding:8px 12px; display:flex; flex-direction:column; gap:6px;";
    el.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px;">
            <span style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:65%;" title="${escapeHtml(filename)}">${direction === 'upload' ? '📤' : '📥'} ${escapeHtml(filename)}</span>
            <span id="q_status_${id}" style="color:var(--accent-cyan); font-family:monospace; font-size:11px;">0% • ${formatSize(totalSize)}</span>
        </div>
        <div style="height:6px; background:rgba(255,255,255,0.08); border-radius:99px; overflow:hidden;">
            <div id="q_bar_${id}" style="height:100%; width:0%; background:linear-gradient(90deg, var(--accent-blue), var(--accent-cyan)); transition:width 0.15s ease; border-radius:99px;"></div>
        </div>
    `;
    list.appendChild(el);
}

function updateQueueProgress(id, current, total) {
    const bar = document.getElementById('q_bar_' + id);
    const status = document.getElementById('q_status_' + id);
    const speedEl = document.getElementById('queueSpeed');

    const pct = Math.min(100, Math.round((current / total) * 100));
    if (bar) bar.style.width = pct + '%';
    if (status) status.innerText = `${pct}% • ${formatSize(current)}`;

    // Speed calculation
    const now = Date.now();
    const timeDiff = (now - lastSpeedCheck) / 1000;
    if (timeDiff >= 0.5 && speedEl) {
        if (current < lastSpeedLoaded) {
            lastSpeedLoaded = 0;
        }
        const bytesDiff = current - lastSpeedLoaded;
        const speed = bytesDiff / timeDiff;
        speedEl.innerText = `${formatSize(Math.max(0, speed))}/s`;
        lastSpeedCheck = now;
        lastSpeedLoaded = current;
    }
}

function markQueueDone(id) {
    const bar = document.getElementById('q_bar_' + id);
    const status = document.getElementById('q_status_' + id);
    if (bar) {
        bar.style.width = '100%';
        bar.style.background = 'var(--accent-green)';
    }
    if (status) status.innerText = '✅ Complete';

    // Reset speed calculation for subsequent transfers
    lastSpeedLoaded = 0;
    lastSpeedCheck = Date.now();
    const speedEl = document.getElementById('queueSpeed');
    if (speedEl) speedEl.innerText = '0 B/s';

    setTimeout(() => {
        const item = document.getElementById('q_' + id);
        if (item) item.remove();
        const list = document.getElementById('queueItemsList');
        if (list && list.children.length === 0) {
            const drawer = document.getElementById('floatingQueue');
            if (drawer) drawer.style.display = 'none';
        }
    }, 2500);
}

// --- FILE LIST RENDERING ---
function renderHostSharedFilesUI() {
    const list = document.getElementById('hostSharedFileList');
    if (!list) return;

    if (sharedFilesList.length === 0) {
        list.innerHTML = `<li class="empty-state">No files shared yet</li>`;
        return;
    }

    list.innerHTML = sharedFilesList.map(f => `
        <li class="file-row">
            <div class="file-icon">${getSmartIcon(f.category, f.ext)}</div>
            <div class="file-details">
                <span class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
                <div class="file-size">${formatSize(f.size)}</div>
            </div>
        </li>
    `).join('');
}

function renderReceivedFilesUI() {
    const listHost = document.getElementById('receivedFileList');
    const listClient = document.getElementById('receivedFileListClient');
    const targets = [listHost, listClient].filter(Boolean);

    targets.forEach(list => {
        if (receivedFilesList.length === 0) {
            list.innerHTML = `<li class="empty-state">No files received yet</li>`;
            return;
        }

        list.innerHTML = receivedFilesList.map(f => `
            <li class="file-row">
                <div class="file-icon">${getSmartIcon(f.category, f.ext)}</div>
                <div class="file-details">
                    <a href="javascript:void(0)" onclick="openPreviewBlob('${escapeHtml(f.name)}', '${f.category}', '${f.url}', ${f.size})" class="file-name" title="${escapeHtml(f.name)}">
                        ${escapeHtml(f.name)}
                    </a>
                    <div class="file-size">${formatSize(f.size)}</div>
                </div>
                <div class="file-actions">
                    <button class="action-circle-btn" onclick="openPreviewBlob('${escapeHtml(f.name)}', '${f.category}', '${f.url}', ${f.size})" title="Preview">👁️</button>
                    <a href="${f.url}" download="${escapeHtml(f.name)}" class="action-circle-btn" title="Download">⬇</a>
                </div>
            </li>
        `).join('');
    });
}

function renderPeerCatalog(files) {
    const list = document.getElementById('peerCatalogList');
    if (!list) return;

    if (!files || files.length === 0) {
        list.innerHTML = `<li class="empty-state">Host has not added files yet</li>`;
        return;
    }

    list.innerHTML = files.map(f => `
        <li class="file-row">
            <div class="file-icon">${getSmartIcon(f.category, f.ext)}</div>
            <div class="file-details">
                <span class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
                <div class="file-size">${formatSize(f.size)}</div>
            </div>
            <div class="file-actions">
                <button class="btn-primary" onclick="requestFileFromHost('${f.id}')" style="padding:4px 10px; font-size:11px; border-radius:8px;">⬇ Download</button>
            </div>
        </li>
    `).join('');
}

// --- LIGHTBOX PREVIEW MODAL ---
function openPreviewBlob(filename, category, url, size) {
    const modal = document.getElementById('previewModal');
    const title = document.getElementById('previewModalTitle');
    const body = document.getElementById('previewModalBody');
    const dlBtn = document.getElementById('previewDownloadBtn');
    if (!modal || !body) return;

    title.innerText = filename;
    dlBtn.href = url;
    dlBtn.download = filename;
    body.innerHTML = '';
    modal.classList.add('open');

    if (category === 'image') {
        body.innerHTML = `<img src="${url}" alt="${escapeHtml(filename)}" style="max-width:100%; max-height:65vh; border-radius:12px; object-fit:contain;">`;
    } else if (category === 'video') {
        body.innerHTML = `
            <video controls autoplay playsinline style="max-width:100%; max-height:60vh; border-radius:12px;">
                <source src="${url}">
                Your browser does not support HTML5 video streaming.
            </video>`;
    } else if (category === 'audio') {
        body.innerHTML = `
            <div style="display:flex; flex-direction:column; align-items:center; gap:16px; padding:20px;">
                <div style="font-size:48px;">🎵</div>
                <div style="font-weight:600; font-size:15px;">${escapeHtml(filename)}</div>
                <audio controls autoplay style="width:100%; max-width:400px;">
                    <source src="${url}">
                </audio>
            </div>`;
    } else {
        body.innerHTML = `
            <div style="text-align:center; padding:30px;">
                <div style="font-size:48px; margin-bottom:12px;">📄</div>
                <h3>${escapeHtml(filename)}</h3>
                <p style="color:var(--text-sub); margin:8px 0 20px 0;">${formatSize(size)}</p>
                <a href="${url}" download="${escapeHtml(filename)}" class="btn-primary" style="display:inline-block; padding:10px 20px;">Download File</a>
            </div>`;
    }
}

function closePreview() {
    const modal = document.getElementById('previewModal');
    const body = document.getElementById('previewModalBody');
    if (modal) modal.classList.remove('open');
    if (body) body.innerHTML = '';
}

// --- SHARED CLIPBOARD ---
function renderClipboardText(text) {
    const display = document.getElementById('clipboardCurrent');
    if (!display) return;
    if (text && text.trim().length > 0) {
        display.innerHTML = `
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80%; font-size:12px;">${escapeHtml(text)}</span>
            <button class="btn-secondary" onclick="copyClipboardText('${escapeHtml(text)}')" style="padding:4px 10px; font-size:11px;">📋 Copy</button>
        `;
    } else {
        display.innerHTML = `<span style="color:var(--text-sub); font-size:12px;">Clipboard is empty.</span>`;
    }
}

function copyClipboardText(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copied to clipboard!', '📋');
        });
    }
}

function sendClipboardP2P() {
    const input = document.getElementById('clipboardInput');
    if (!input || !input.value.trim()) return;

    const text = input.value.trim();
    renderClipboardText(text);

    if (activeConnections.length > 0) {
        activeConnections.forEach(conn => {
            conn.send({
                type: 'clipboard',
                text: text
            });
        });
        input.value = '';
        showToast('Shared with peer!', '🚀');
    } else {
        showToast('No peer connected to receive text', '⚠️');
    }
}

// Keypad Input Controller for Joining
let keypadPin = "";
function keypadAdd(digit) {
    if (keypadPin.length < 4) {
        keypadPin += digit;
        updateKeypadDisplay();
        if (keypadPin.length === 4) {
            setTimeout(() => {
                connectToHost(keypadPin);
            }, 250);
        }
    }
}

function keypadBack() {
    keypadPin = keypadPin.slice(0, -1);
    updateKeypadDisplay();
}

function keypadClear() {
    keypadPin = "";
    updateKeypadDisplay();
}

function updateKeypadDisplay() {
    const el = document.getElementById('keypadPinDisplay');
    if (el) {
        el.innerText = keypadPin.padEnd(4, '•');
    }
}

// Keyboard Input Support for PC / Laptop Web Users
window.addEventListener('keydown', (e) => {
    const keypad = document.getElementById('screenKeypad');
    if (keypad && keypad.style.display !== 'none' && keypad.style.display !== '') {
        if (e.key >= '0' && e.key <= '9') {
            keypadAdd(e.key);
        } else if (e.key === 'Backspace') {
            keypadBack();
        } else if (e.key === 'Escape' || e.key.toLowerCase() === 'c') {
            keypadClear();
        }
    }
});

// Drag & Drop Support for Desktop Web Browsers
function setupDragAndDrop() {
    window.addEventListener('dragover', (e) => e.preventDefault(), false);
    window.addEventListener('drop', (e) => e.preventDefault(), false);

    const zones = [document.getElementById('hostDropZone'), document.getElementById('clientDropZone')];
    zones.forEach((zone) => {
        if (!zone) return;
        zone.addEventListener('dragenter', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        }, false);
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        }, false);
        zone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
        }, false);
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                sendFiles(e.dataTransfer.files);
            }
        }, false);
    });
}

// Auto-check URL for ?room=XXXX or ?mode=host on page load & setup drag/drop
window.addEventListener('DOMContentLoaded', () => {
    setupDragAndDrop();
    const params = new URLSearchParams(window.location.search);
    const roomParam = params.get('room');
    if (roomParam && roomParam.length === 4) {
        startJoinMode(roomParam);
    } else if (params.get('mode') === 'host') {
        startHostMode();
    }
});
