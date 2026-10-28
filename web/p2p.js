/* ==========================================================================
   PyShare v4.9.0 - WebRTC Peer-to-Peer Transfer Engine
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
let activeFileStreams = {}; // fileId -> FileSystemWritableFileStream
let peerCatalogFiles = [];
let pendingFileRequests = new Set(); // fileId Set to prevent duplicate requests
let lastSpeedCheck = Date.now();
let lastSpeedLoaded = 0;
let recentToastHistory = new Map(); // msg -> timestamp for deduplication

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

// Toast Notifications with Deduplication & Max Limit
function showToast(message, icon = 'ℹ️') {
    if (!message) return;
    const now = Date.now();
    const lastSeen = recentToastHistory.get(message);
    // Suppress exact duplicate toast within 2.5 seconds
    if (lastSeen && (now - lastSeen) < 2500) {
        return;
    }
    recentToastHistory.set(message, now);

    // Prune old history entries
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
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
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
    ext = (ext || '').toLowerCase().replace(/^\./, '');
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
        if (conn._sendQueue) conn._sendQueue = [];
        conn._isSending = false;
        conn._currentSendingId = null;

        if (isHost) {
            if (activeConnections.length === 0) {
                updateConnectionStatus('Ready! Waiting for device to scan...', 'blue');
                document.getElementById('hostConnectedBadge').style.display = 'none';
            }
            showToast('Peer disconnected', '⚠️');
        } else {
            updateClientStatus('Disconnected from Host', 'red');
            showToast('Disconnected from Host', '⚠️');
            pendingFileRequests.clear();
        }
    });

    conn.on('error', (err) => {
        console.warn('P2P connection error:', err);
        showToast(`P2P Transfer Notice: ${err?.message || err}`, '⚠️');
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
async function handleIncomingData(msg, conn) {
    if (!msg || !msg.type) return;

    // 1. File Metadata Arrival
    if (msg.type === 'file_start') {
        // Prevent duplicate file_start resetting an active transfer
        if (activeTransfers[msg.id]) {
            console.warn('Ignoring duplicate file_start for', msg.id);
            return;
        }

        activeTransfers[msg.id] = {
            meta: msg,
            chunks: [],
            receivedBytes: 0,
            startTime: Date.now()
        };
        pendingFileRequests.delete(msg.id);
        showFloatingQueue();
        renderQueueItem(msg.id, msg.name, msg.size, 'download');
        updateCatalogButtonState(msg.id, 'downloading', 0);

        if (msg.size > 500 * 1024 * 1024) {
            const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
            if (isMobile) {
                showToast(`Receiving large file (${formatSize(msg.size)}). Keep browser tab active.`, 'ℹ️');
            }
        }
    }

    // 2. Binary File Chunk
    else if (msg.type === 'file_chunk') {
        const transfer = activeTransfers[msg.id];
        if (!transfer) return;

        const stream = activeFileStreams[msg.id];
        if (stream) {
            transfer.writeQueue = (transfer.writeQueue || Promise.resolve()).then(() => 
                stream.write(msg.chunk)
            ).catch(() => {
                delete activeFileStreams[msg.id];
                transfer.chunks.push(msg.chunk);
            });
        } else {
            transfer.chunks.push(msg.chunk);
        }

        transfer.receivedBytes += msg.chunk.byteLength;
        updateQueueProgress(msg.id, transfer.receivedBytes, transfer.meta.size);
        const pct = Math.min(100, Math.round((transfer.receivedBytes / (transfer.meta.size || 1)) * 100));
        updateCatalogButtonState(msg.id, 'downloading', pct);
    }

    // 3. File Transfer Complete
    else if (msg.type === 'file_end') {
        const transfer = activeTransfers[msg.id];
        if (!transfer) return;

        pendingFileRequests.delete(msg.id);

        const stream = activeFileStreams[msg.id];
        if (stream) {
            try {
                if (transfer.writeQueue) await transfer.writeQueue;
                await stream.close();
            } catch (e) {}
            delete activeFileStreams[msg.id];
            delete activeTransfers[msg.id];
            markQueueDone(msg.id);
            updateCatalogButtonState(msg.id, 'downloaded');
            showToast(`Saved to disk: ${transfer.meta.name}`, '💾');
            return;
        }

        try {
            const blob = new Blob(transfer.chunks, { type: transfer.meta.mime });
            transfer.chunks = []; // Clear array of ArrayBuffers to release RAM immediately
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

            // Deduplicate record in receivedFilesList
            const existingIdx = receivedFilesList.findIndex(f => f.id === fileRecord.id);
            if (existingIdx >= 0) {
                receivedFilesList[existingIdx] = fileRecord;
            } else {
                receivedFilesList.push(fileRecord);
            }

            delete activeTransfers[msg.id];

            markQueueDone(msg.id);
            renderReceivedFilesUI();
            updateCatalogButtonState(msg.id, 'downloaded');

            // Trigger standard browser download prompt directly to user device
            try {
                const a = document.createElement('a');
                a.href = objectUrl;
                a.download = fileRecord.name;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            } catch (e) {
                console.warn('Browser auto-download trigger notice:', e);
            }

            showToast(`Saved: ${fileRecord.name}`, '📥');
        } catch (err) {
            delete activeTransfers[msg.id];
            updateCatalogButtonState(msg.id, 'idle');
            showToast('Memory limit reached. For large multi-GB transfers, use PyShare Desktop App.', '⚠️');
        }
    }

    // 4. File Catalog Sync (From Host to Client)
    else if (msg.type === 'files_catalog') {
        const newCount = (msg.files || []).length;
        const oldCount = peerCatalogFiles.length;
        if (newCount > oldCount && oldCount > 0) {
            showToast(`Host shared ${newCount - oldCount} new file${newCount - oldCount > 1 ? 's' : ''}`, '📂');
        }
        renderPeerCatalog(msg.files);
    }

    // 5. Request File Download (Client asks Host for a specific shared file)
    else if (msg.type === 'request_file') {
        const target = sharedFilesList.find(f => f.id === msg.id);
        if (target && target.file) {
            queueFileSend(target.file, conn, target.id);
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

    // Allow Host to stage files in "Shared by You" even before a peer connects
    if (activeConnections.length === 0 && !isHost) {
        showToast('No peer connected yet. Scan QR code to connect!', '⚠️');
        return;
    }

    const hasLargeFile = Array.from(files).some(f => f.size > 500 * 1024 * 1024);
    if (hasLargeFile) {
        showToast('Large file (>500MB) queued. For multi-GB files, PyShare Desktop App provides unlimited offline transfer with zero browser RAM limits.', '💡');
    }

    Array.from(files).forEach(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        const category = getCategory(ext);
        const fileId = 'f_' + Math.random().toString(36).substr(2, 9);

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

            // Sync updated catalog to all connected peers
            if (activeConnections.length > 0) {
                activeConnections.forEach(conn => {
                    syncSharedFilesToPeer(conn);
                });
            }
        } else {
            // Client drops files: directly send to connected Host
            if (activeConnections.length > 0) {
                activeConnections.forEach(conn => {
                    queueFileSend(file, conn, fileId);
                });
            }
        }
    });

    if (isHost) {
        if (activeConnections.length === 0) {
            showToast('Files staged! They will sync as soon as a peer connects.', '✅');
        } else {
            showToast(`Shared ${files.length} file${files.length > 1 ? 's' : ''} with peer!`, '✅');
        }
    }
}

// Wait for RTCDataChannel buffer to drain below threshold
function waitForBufferDrain(dc, maxBuffered = 512 * 1024) {
    if (!dc || dc.bufferedAmount <= maxBuffered) {
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        let timer = null;
        const handler = () => {
            if (!dc || dc.bufferedAmount <= maxBuffered) {
                cleanup();
                resolve();
            }
        };
        const cleanup = () => {
            if (timer) clearTimeout(timer);
            try {
                dc.removeEventListener('bufferedamountlow', handler);
            } catch (e) {}
        };
        try {
            dc.addEventListener('bufferedamountlow', handler);
        } catch (e) {
            resolve();
            return;
        }
        // Safety fallback timer to prevent infinite hang if event is dropped by browser
        timer = setTimeout(() => {
            cleanup();
            resolve();
        }, 350);
    });
}

// Sequential Outgoing Transfer Queue per Peer Connection
function queueFileSend(file, conn, fileId) {
    if (!conn) return;
    if (!conn._sendQueue) {
        conn._sendQueue = [];
    }
    // Prevent duplicate enqueue if already sending or in queue
    if (conn._currentSendingId === fileId || conn._sendQueue.some(item => item.fileId === fileId)) {
        return;
    }
    conn._sendQueue.push({ file, fileId });
    processSendQueue(conn);
}

async function processSendQueue(conn) {
    if (!conn || conn._isSending || !conn._sendQueue || conn._sendQueue.length === 0) {
        return;
    }
    conn._isSending = true;
    const { file, fileId } = conn._sendQueue.shift();
    conn._currentSendingId = fileId;

    try {
        await streamFileToConnectionAsync(file, conn, fileId);
    } catch (err) {
        console.error('P2P send error:', err);
        showToast(`Transfer interrupted: ${file.name}`, '❌');
    } finally {
        conn._currentSendingId = null;
        conn._isSending = false;
        // Process next queued file sequentially
        processSendQueue(conn);
    }
}

// Stream File using Modern ArrayBuffer Slices and Backpressure Control
async function streamFileToConnectionAsync(file, conn, fileId) {
    const ext = file.name.split('.').pop().toLowerCase();
    const category = getCategory(ext);

    if (!conn.open) return;

    // 1. Send File Header Metadata
    conn.send({
        type: 'file_start',
        id: fileId,
        name: file.name,
        size: file.size,
        category: category,
        ext: ext,
        mime: file.type || 'application/octet-stream'
    });

    showFloatingQueue();
    renderQueueItem(fileId, file.name, file.size, 'upload');

    let offset = 0;
    const totalSize = file.size;

    // Handle 0-byte empty file edge case
    if (totalSize === 0) {
        conn.send({ type: 'file_end', id: fileId });
        markQueueDone(fileId);
        showToast(`Sent: ${file.name}`, '✅');
        return;
    }

    // 2. Stream Binary Chunks with Backpressure Control
    while (offset < totalSize) {
        if (!conn.open) {
            throw new Error('Connection closed during transfer');
        }

        // Backpressure Check: wait if RTCDataChannel buffer exceeds 1MB
        if (conn.dataChannel && conn.dataChannel.bufferedAmount > 1024 * 1024) {
            await waitForBufferDrain(conn.dataChannel, 512 * 1024);
        }

        const slice = file.slice(offset, offset + CHUNK_SIZE);
        const buffer = await slice.arrayBuffer();

        conn.send({
            type: 'file_chunk',
            id: fileId,
            chunk: buffer
        });

        offset += buffer.byteLength;
        updateQueueProgress(fileId, offset, totalSize);
    }

    // 3. Send File Completion Signal
    conn.send({
        type: 'file_end',
        id: fileId
    });
    markQueueDone(fileId);
    showToast(`Sent: ${file.name}`, '✅');
}

// Backward-compatible alias
function streamFileToConnection(file, conn, existingId = null) {
    const fileId = existingId || ('f_' + Math.random().toString(36).substr(2, 9));
    queueFileSend(file, conn, fileId);
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

async function requestFileFromHost(fileId) {
    if (activeConnections.length === 0) {
        showToast('No active peer connection', '⚠️');
        return;
    }

    // Check 1: Already downloaded? Save immediately from memory without network transfer
    const existing = receivedFilesList.find(f => f.id === fileId);
    if (existing && existing.url) {
        showToast(`Downloading ${existing.name}...`, '💾');
        const a = document.createElement('a');
        a.href = existing.url;
        a.download = existing.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        return;
    }

    // Check 2: Already currently downloading or requested?
    if (activeTransfers[fileId]) {
        showToast('File is currently downloading!', '⏳');
        return;
    }
    if (pendingFileRequests.has(fileId)) {
        return; // Ignore duplicate clicks
    }

    const target = peerCatalogFiles.find(f => f.id === fileId);
    if (!target) return;

    pendingFileRequests.add(fileId);
    updateCatalogButtonState(fileId, 'pending');

    // Stream large files directly to disk using File System Access API if supported
    if (window.showSaveFilePicker && target.size > 50 * 1024 * 1024) {
        try {
            const handle = await window.showSaveFilePicker({
                suggestedName: target.name
            });
            const writable = await handle.createWritable();
            activeFileStreams[fileId] = writable;
            showToast(`Streaming ${target.name} directly to disk...`, '💾');
        } catch (e) {
            if (e.name === 'AbortError') {
                pendingFileRequests.delete(fileId);
                updateCatalogButtonState(fileId, 'idle');
                return; // User intentionally cancelled save picker
            }
            console.warn('File System Access API fallback:', e);
        }
    } else if (target.size > 500 * 1024 * 1024) {
        showToast('Large file (>500MB). Keep browser tab active until complete.', 'ℹ️');
    }

    showToast(`Requesting ${target.name}...`, '⏳');
    activeConnections[0].send({
        type: 'request_file',
        id: fileId
    });

    // Timeout safety: if host doesn't respond within 10s, restore button state
    setTimeout(() => {
        if (pendingFileRequests.has(fileId) && !activeTransfers[fileId]) {
            pendingFileRequests.delete(fileId);
            updateCatalogButtonState(fileId, 'idle');
        }
    }, 10000);
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

    // Reuse existing queue DOM element if present to avoid duplicate elements
    let el = document.getElementById('q_' + id);
    if (!el) {
        el = document.createElement('div');
        el.id = 'q_' + id;
        el.style.cssText = "background:var(--input-bg); border:1px solid var(--border-color); border-radius:10px; padding:8px 12px; display:flex; flex-direction:column; gap:6px;";
        list.appendChild(el);
    }
    el.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px;">
            <span style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:65%;" title="${escapeHtml(filename)}">${direction === 'upload' ? '📤' : '📥'} ${escapeHtml(filename)}</span>
            <span id="q_status_${id}" style="color:var(--accent-cyan); font-family:monospace; font-size:11px;">0% • ${formatSize(totalSize)}</span>
        </div>
        <div style="height:6px; background:rgba(255,255,255,0.08); border-radius:99px; overflow:hidden;">
            <div id="q_bar_${id}" style="height:100%; width:0%; background:linear-gradient(90deg, var(--accent-blue), var(--accent-cyan)); transition:width 0.15s ease; border-radius:99px;"></div>
        </div>
    `;
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
                    <a href="javascript:void(0)" onclick="openPreviewBlobById('${encodeURIComponent(f.id)}')" class="file-name" title="${escapeHtml(f.name)}">
                        ${escapeHtml(f.name)}
                    </a>
                    <div class="file-size">${formatSize(f.size)}</div>
                </div>
                <div class="file-actions">
                    <button class="action-circle-btn" onclick="openPreviewBlobById('${encodeURIComponent(f.id)}')" title="Preview">👁️</button>
                    <a href="${f.url}" download="${escapeHtml(f.name)}" class="action-circle-btn" title="Download">⬇</a>
                </div>
            </li>
        `).join('');
    });
}

function renderPeerCatalog(files) {
    peerCatalogFiles = files || [];
    const list = document.getElementById('peerCatalogList');
    if (!list) return;

    if (!files || files.length === 0) {
        list.innerHTML = `<li class="empty-state">Host has not added files yet</li>`;
        return;
    }

    list.innerHTML = files.map(f => {
        const isDownloaded = receivedFilesList.some(rf => rf.id === f.id);
        const isTransferring = !!activeTransfers[f.id];
        const isPending = pendingFileRequests.has(f.id);

        let btnContent = '⬇ Download';
        let btnClass = 'btn-primary';
        let btnDisabled = '';
        let btnStyle = 'padding:4px 10px; font-size:11px; border-radius:8px;';

        if (isDownloaded) {
            btnContent = '✅ Downloaded';
            btnClass = 'btn-secondary';
            btnStyle += ' color:var(--accent-green); border-color:var(--accent-green);';
        } else if (isTransferring) {
            const tr = activeTransfers[f.id];
            const pct = tr ? Math.min(100, Math.round((tr.receivedBytes / (tr.meta?.size || 1)) * 100)) : 0;
            btnContent = `⏳ ${pct}%`;
            btnClass = 'btn-secondary';
            btnDisabled = 'disabled';
            btnStyle += ' opacity:0.7; cursor:not-allowed;';
        } else if (isPending) {
            btnContent = '⏳ Requesting...';
            btnClass = 'btn-secondary';
            btnDisabled = 'disabled';
            btnStyle += ' opacity:0.7; cursor:not-allowed;';
        }

        return `
            <li class="file-row">
                <div class="file-icon">${getSmartIcon(f.category, f.ext)}</div>
                <div class="file-details">
                    <span class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
                    <div class="file-size">${formatSize(f.size)}</div>
                </div>
                <div class="file-actions">
                    <button id="btn_dl_${f.id}" class="${btnClass}" ${btnDisabled} onclick="requestFileFromHost('${f.id}')" style="${btnStyle}">${btnContent}</button>
                </div>
            </li>
        `;
    }).join('');
}

// Update catalog download button state in real time
function updateCatalogButtonState(fileId, state, pct = 0) {
    const btn = document.getElementById('btn_dl_' + fileId);
    if (!btn) return;

    if (state === 'pending') {
        btn.disabled = true;
        btn.className = 'btn-secondary';
        btn.style.opacity = '0.7';
        btn.style.cursor = 'not-allowed';
        btn.innerHTML = '⏳ Requesting...';
    } else if (state === 'downloading') {
        btn.disabled = true;
        btn.className = 'btn-secondary';
        btn.style.opacity = '0.7';
        btn.style.cursor = 'not-allowed';
        btn.innerHTML = `⏳ ${pct}%`;
    } else if (state === 'downloaded') {
        btn.disabled = false;
        btn.className = 'btn-secondary';
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
        btn.style.color = 'var(--accent-green)';
        btn.style.borderColor = 'var(--accent-green)';
        btn.innerHTML = '✅ Downloaded';
    } else {
        btn.disabled = false;
        btn.className = 'btn-primary';
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
        btn.style.color = '';
        btn.style.borderColor = '';
        btn.innerHTML = '⬇ Download';
    }
}

// --- LIGHTBOX PREVIEW MODAL ---
function openPreviewBlobById(fileId) {
    const id = decodeURIComponent(fileId);
    const f = receivedFilesList.find(item => item.id === id);
    if (f) {
        openPreviewBlob(f.name, f.category, f.url, f.size);
    }
}

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
let currentClipboardText = "";

function renderClipboardText(text) {
    currentClipboardText = text || "";
    const display = document.getElementById('clipboardCurrent');
    if (!display) return;
    if (text && text.trim().length > 0) {
        display.innerHTML = `
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80%; font-size:12px;">${escapeHtml(text)}</span>
            <button class="btn-secondary" onclick="copyClipboardText()" style="padding:4px 10px; font-size:11px;">📋 Copy</button>
        `;
    } else {
        display.innerHTML = `<span style="color:var(--text-sub); font-size:12px;">Clipboard is empty.</span>`;
    }
}

function copyClipboardText(text) {
    const textToCopy = (typeof text === 'string' && text) ? text : currentClipboardText;
    if (!textToCopy) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).then(() => {
            showToast('Copied to clipboard!', '📋');
        }).catch(() => {
            legacyCopy(textToCopy);
        });
    } else {
        legacyCopy(textToCopy);
    }
}

function legacyCopy(val) {
    try {
        const ta = document.createElement('textarea');
        ta.value = val;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Copied to clipboard!', '📋');
    } catch(e) {
        showToast('Could not copy to clipboard', '❌');
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
