/* ==========================================================================
   PyShare Host Scripts - Real-time Hub, PIN Sync & Activity Monitor
   ========================================================================== */

window.isHostSession = true;

// Set Host Address in Status Pill
const hostIpEl = document.getElementById('host-ip');
let realServerIp = '';
let realServerPort = '';
let isHostIpHidden = true;

function updateServerDisplay(ip, port) {
    if (ip && port) {
        realServerIp = ip;
        realServerPort = port;
        if (hostIpEl) {
            hostIpEl.innerText = isHostIpHidden ? `••••••••:${port}` : `${ip}:${port}`;
        }
    }
}

function toggleHostIpVisibility(event) {
    if (event) event.stopPropagation();
    isHostIpHidden = !isHostIpHidden;
    const iconEl = document.getElementById('hostIpEyeIcon');
    if (hostIpEl && realServerIp && realServerPort) {
        hostIpEl.innerText = isHostIpHidden ? `••••••••:${realServerPort}` : `${realServerIp}:${realServerPort}`;
    }
    if (iconEl) {
        iconEl.innerHTML = isHostIpHidden 
            ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>'
            : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    }
}
window.toggleHostIpVisibility = toggleHostIpVisibility;

// Fetch real physical Wi-Fi IP from server (ignores local loopback 127.0.0.1)
fetch('/api/info')
    .then(r => r.json())
    .then(data => {
        if (data && data.ip && data.port) {
            updateServerDisplay(data.ip, data.port);
        }
    })
    .catch(() => {});

// Fetch initial PIN and status immediately on load (without waiting for SSE tick)
fetch('/api/pin')
    .then(r => r.json())
    .then(data => {
        if (data) {
            const pinEl = document.getElementById('live-pin');
            const timerTextEl = document.getElementById('pin-timer-text');
            if (pinEl && data.pin) pinEl.innerText = data.pin;
            if (timerTextEl && data.ttl) timerTextEl.innerText = data.ttl + 's';
            if (data.ip && data.port) updateServerDisplay(data.ip, data.port);
        }
    })
    .catch(() => {});

function copyHostIp() {
    let addr = (realServerIp && realServerPort) ? `${realServerIp}:${realServerPort}` : (hostIpEl ? hostIpEl.innerText.trim() : '');
    if (!addr || addr.includes('•••') || addr === '...' || addr === 'Detecting...') {
        if (realServerIp && realServerPort) {
            addr = `${realServerIp}:${realServerPort}`;
        } else {
            return;
        }
    }
    const fullUrl = `http://${addr}/`;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(fullUrl).then(() => {
            showToast(`Server URL copied: ${fullUrl}`, 'copy');
        }).catch(() => {
            showToast(`Server URL: ${fullUrl}`, 'info');
        });
    } else {
        showToast(`Server URL: ${fullUrl}`, 'info');
    }
}
window.copyHostIp = copyHostIp;

// Host uploads land directly into Shared_Files
window.handleFilesCustom = function(files) {
    uploadManager.addFiles(files, '/?dest=host');
};

function handleFilesHost(files) {
    uploadManager.addFiles(files, '/?dest=host');
}

// Host Clipboard Direct Sync & Auto-Sync Switch
function toggleHostAutoClipboardSync(checked) {
    try {
        localStorage.setItem('pyshare_host_auto_clipboard', checked ? 'true' : 'false');
        showToast(checked ? 'OS Clipboard Auto-Sync enabled' : 'OS Clipboard Auto-Sync disabled', checked ? 'check' : 'info');
    } catch(e) {}
}
window.toggleHostAutoClipboardSync = toggleHostAutoClipboardSync;

(function initHostAutoClipboard() {
    const cb = document.getElementById('toggleHostAutoClipboard');
    if (cb) {
        const val = localStorage.getItem('pyshare_host_auto_clipboard');
        cb.checked = (val !== 'false'); // Default to true
    }
})();

async function syncPCClipboard() {
    try {
        const res = await fetch('/api/sync_clipboard');
        const data = await res.json();
        if (data.status === 'ok') {
            showToast('Host clipboard pushed to devices!', 'copy');
            if (typeof loadClipboard === 'function') loadClipboard();
        } else if (data.status === 'empty') {
            showToast('Host clipboard is empty', 'warning');
        } else {
            showToast('Could not sync host clipboard', 'error');
        }
    } catch (e) {
        showToast('Error syncing host clipboard', 'error');
    }
}

// Clear Chat & Clipboard Stream (Host Only)
async function clearChatStream() {
    if (typeof showPyShareConfirm === 'function') {
        showPyShareConfirm({
            title: "Clear Chat Stream",
            message: "Clear all messages in the quick chat stream for all connected devices?",
            confirmText: "Clear All",
            isDanger: true,
            onConfirm: async () => {
                try {
                    const res = await fetch('/api/chat/clear', { method: 'POST' });
                    if (res.ok) {
                        showToast('Chat history cleared', 'trash');
                        if (typeof loadClipboard === 'function') loadClipboard();
                    } else {
                        showToast('Failed to clear chat', 'error');
                    }
                } catch (e) {
                    showToast('Error clearing chat', 'error');
                }
            }
        });
    } else {
        if (!confirm("Clear all chat messages?")) return;
        try {
            const res = await fetch('/api/chat/clear', { method: 'POST' });
            if (res.ok) {
                showToast('Chat history cleared', 'trash');
                if (typeof loadClipboard === 'function') loadClipboard();
            }
        } catch(e) {}
    }
}
window.clearChatStream = clearChatStream;

// Toggle between Rotating PIN & Static PIN
async function togglePinMode() {
    const isCurrentlyStatic = document.getElementById('pin-timer-text')?.innerText.includes('Static');
    const newMode = isCurrentlyStatic ? 'rotating' : 'static';

    let customPin = '';
    if (newMode === 'static') {
        const input = prompt("Set a static 4-digit PIN for your personal/home network (leave blank for default 1234):", "");
        if (input === null) return; // User cancelled
        if (input && !/^\d{4}$/.test(input.trim())) {
            showToast("PIN must be exactly 4 numeric digits", "warning");
            return;
        }
        customPin = input.trim();
    }

    try {
        const res = await fetch('/api/pin/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: newMode, pin: customPin })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            const label = data.mode === 'static' ? `Static PIN set to ${data.pin}` : 'Switched to Auto-Rotating PIN';
            showToast(label, 'success');
            if (navigator.vibrate) navigator.vibrate(40);
            const qrImg = document.querySelector('.qr-code-img');
            if (qrImg) qrImg.src = '/qrcode.png?t=' + Date.now();
        }
    } catch (e) {
        showToast("Error updating PIN mode", "error");
    }
}

// Setup Host SSE Real-time Listeners
function setupHostSSE(es) {
    if (!es) return;

    // 0. Live Server Info (Physical IP push)
    es.addEventListener('server_info', (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data && data.ip && data.port) {
                updateServerDisplay(data.ip, data.port);
            }
        } catch (err) {}
    });

    // 1. Live PIN & Grace Period Countdown (Pushed every second from server)
    es.addEventListener('pin', (e) => {
        try {
            const data = JSON.parse(e.data);
            const pinEl = document.getElementById('live-pin');
            const timerTextEl = document.getElementById('pin-timer-text');
            const timerBarEl = document.getElementById('pin-timer-bar');

            if (data.ip && data.port) {
                updateServerDisplay(data.ip, data.port);
            }

            if (pinEl) pinEl.innerText = data.pin;
            if (timerTextEl) {
                if (data.ttl < 0 || data.mode === 'static') {
                    timerTextEl.innerText = 'Static';
                    timerTextEl.title = 'Static PIN (Does not expire). Click to toggle.';
                } else {
                    timerTextEl.innerText = data.ttl + 's';
                    timerTextEl.title = 'Rotating PIN (Expires in ' + data.ttl + 's). Click to toggle.';
                }
            }
            
            if (timerBarEl) {
                if (data.ttl < 0 || data.mode === 'static') {
                    timerBarEl.style.width = '100%';
                    timerBarEl.style.background = 'var(--accent-cyan)';
                } else {
                    const pct = (data.ttl / 30) * 100;
                    timerBarEl.style.width = pct + '%';
                    if (data.ttl < 5) {
                        timerBarEl.style.background = 'var(--accent-red)';
                    } else {
                        timerBarEl.style.background = 'var(--accent-blue)';
                    }
                }
            }
        } catch (err) {}
    });

    // 2. Real-time Activity Log (Pushed instantly on events)
    es.addEventListener('log', (e) => {
        try {
            const entryData = JSON.parse(e.data);
            const logBox = document.getElementById('hubLogPane');
            if (logBox) {
                const entry = document.createElement('div');
                entry.className = 'log-entry-row';
                entry.innerHTML = `<span class="log-timestamp">${escapeHtml(entryData.time)}</span><span class="log-message">${escapeHtml(entryData.msg)}</span>`;
                logBox.prepend(entry);
            }
        } catch (err) {}
    });

    // 3. Incoming Mobile Upload Monitor (High-frequency throttled push with Speed & ETA)
    let lastRxLoaded = 0;
    let lastRxTime = Date.now();
    let rxSmoothedSpeed = 0;
    let currentRxFile = '';

    es.addEventListener('upload', (e) => {
        try {
            const upload = JSON.parse(e.data);
            const rxBox = document.getElementById('rx-container');
            const rxBar = document.getElementById('rx-bar');
            const rxName = document.getElementById('rx-filename');
            const rxStats = document.getElementById('rx-stats');
            const rxEta = document.getElementById('rx-eta');

            if (rxBox && rxBar && rxName) {
                if (upload) {
                    rxBox.style.display = 'block';
                    rxName.innerText = upload.filename;

                    if (currentRxFile !== upload.filename) {
                        currentRxFile = upload.filename;
                        lastRxLoaded = upload.current;
                        lastRxTime = Date.now();
                        rxSmoothedSpeed = 0;
                    }

                    const pct = Math.round((upload.current / upload.total) * 100);
                    rxBar.style.width = pct + "%";

                    const now = Date.now();
                    const timeDiff = (now - lastRxTime) / 1000;
                    if (timeDiff >= 0.25) {
                        const curSpeed = (upload.current - lastRxLoaded) / timeDiff;
                        rxSmoothedSpeed = rxSmoothedSpeed === 0 ? curSpeed : (0.7 * rxSmoothedSpeed + 0.3 * curSpeed);
                        lastRxLoaded = upload.current;
                        lastRxTime = now;
                    }

                    const remBytes = Math.max(0, upload.total - upload.current);
                    const etaSec = rxSmoothedSpeed > 0 ? Math.round(remBytes / rxSmoothedSpeed) : 0;
                    const speedStr = rxSmoothedSpeed > 0 ? `${formatSize(rxSmoothedSpeed)}/s` : 'calculating...';
                    const etaStr = etaSec > 0 ? `${formatEta(etaSec)} left` : '';

                    if (rxStats) rxStats.innerText = `${pct}% • ${speedStr}`;
                    if (rxEta) rxEta.innerText = etaStr;
                } else {
                    rxBox.style.display = 'none';
                    currentRxFile = '';
                    rxSmoothedSpeed = 0;
                }
            }
        } catch (err) {}
    });

    // 4. Public Internet Tunnel Listener
    es.addEventListener('tunnel', (e) => {
        try {
            const data = JSON.parse(e.data);
            updateTunnelUI(data);
        } catch (err) {}
    });

    // 5. Active Connected Peers Real-time Inspector
    es.addEventListener('peers', (e) => {
        try {
            const peers = JSON.parse(e.data);
            renderPeers(peers);
        } catch (err) {}
    });

    // 6. Incoming Device Join Requests (Knock Approval)
    es.addEventListener('join_request', (e) => {
        try {
            const req = JSON.parse(e.data);
            if (req && req.id) {
                displayHostJoinRequest(req);
            }
        } catch (err) {}
    });
}

// --- Host Join Request Handling ---
let activeHostJoinRequest = null;
let hostJoinReqCountdownTimer = null;

function displayHostJoinRequest(req) {
    activeHostJoinRequest = req;
    const modal = document.getElementById('hostJoinRequestModal');
    const nameEl = document.getElementById('joinReqDeviceName');
    const infoEl = document.getElementById('joinReqDeviceInfo');
    const timerEl = document.getElementById('joinReqTimer');
    if (!modal) return;

    if (nameEl) nameEl.innerText = req.nickname || 'Unknown Device';
    if (infoEl) infoEl.innerText = `${req.browser || 'Browser'} on ${req.device || 'Device'} • IP: ${req.ip || 'Unknown'}`;

    modal.style.display = 'flex';
    showToast(`Device wants to join: ${req.nickname}`, 'bell');
    if (navigator.vibrate) navigator.vibrate([80, 50, 80]);

    let secondsLeft = req.expires_in || 60;
    if (timerEl) timerEl.innerText = `Auto-expires in ${secondsLeft}s`;

    if (hostJoinReqCountdownTimer) clearInterval(hostJoinReqCountdownTimer);
    hostJoinReqCountdownTimer = setInterval(() => {
        secondsLeft--;
        if (timerEl) timerEl.innerText = `Auto-expires in ${secondsLeft}s`;
        if (secondsLeft <= 0) {
            clearInterval(hostJoinReqCountdownTimer);
            hideHostJoinRequestModal();
        }
    }, 1000);
}

function hideHostJoinRequestModal() {
    const modal = document.getElementById('hostJoinRequestModal');
    if (modal) modal.style.display = 'none';
    if (hostJoinReqCountdownTimer) {
        clearInterval(hostJoinReqCountdownTimer);
        hostJoinReqCountdownTimer = null;
    }
    activeHostJoinRequest = null;
}

async function respondHostJoinRequest(action) {
    if (!activeHostJoinRequest || !activeHostJoinRequest.id) {
        hideHostJoinRequestModal();
        return;
    }
    const reqId = activeHostJoinRequest.id;
    const reqNickname = activeHostJoinRequest.nickname;
    hideHostJoinRequestModal();

    try {
        const res = await fetch('/api/join/respond', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: reqId, action: action })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            if (action === 'accept') {
                showToast(`Allowed ${reqNickname} to connect`, 'success');
                fetchPeers();
            } else {
                showToast(`Declined request from ${reqNickname}`, 'error');
            }
        }
    } catch (e) {
        showToast('Error responding to join request', 'error');
    }
}
window.respondHostJoinRequest = respondHostJoinRequest;

// Check for any currently pending join requests on Host load
async function checkPendingJoinRequests() {
    try {
        const res = await fetch('/api/join/pending');
        if (res.ok) {
            const data = await res.json();
            if (data && data.requests && data.requests.length > 0) {
                displayHostJoinRequest(data.requests[0]);
            }
        }
    } catch (e) {}
}

// --- ACTIVE CONNECTED PEERS INSPECTOR ---
let currentPeers = [];
let peersIpMasked = true;
let revealedPeerIps = new Set();

function togglePeersIpMask() {
    peersIpMasked = !peersIpMasked;
    const label = document.getElementById('peersPrivacyLabel');
    const icon = document.getElementById('peersPrivacyIcon');
    if (label) label.innerText = peersIpMasked ? 'IPs Hidden' : 'IPs Visible';
    if (icon) {
        icon.innerHTML = peersIpMasked 
            ? '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>'
            : '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    }
    renderPeers(currentPeers);
}
window.togglePeersIpMask = togglePeersIpMask;

function togglePeerIp(id) {
    if (revealedPeerIps.has(id)) {
        revealedPeerIps.delete(id);
    } else {
        revealedPeerIps.add(id);
    }
    renderPeers(currentPeers);
}
window.togglePeerIp = togglePeerIp;

async function renamePeer(id, currentName) {
    let newName;
    if (typeof showPySharePrompt === 'function') {
        newName = await showPySharePrompt({
            title: 'Rename Device',
            message: 'Assign a friendly nickname for this device:',
            defaultValue: currentName,
            placeholder: "e.g. Alex's iPhone, Work Laptop",
            confirmText: 'Save Nickname'
        });
    } else {
        newName = prompt('Enter a nickname for this device:', currentName);
    }
    if (!newName || newName.trim() === '' || newName.trim() === currentName) return;
    try {
        const res = await fetch('/api/device/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, nickname: newName.trim() })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            showToast(`Device renamed: ${data.nickname}`, 'rename');
            fetchPeers();
        } else {
            showToast('Could not rename device', 'error');
        }
    } catch (e) {
        showToast('Network error renaming device', 'error');
    }
}
window.renamePeer = renamePeer;

function getDeviceIcon(iconType) {
    if (iconType === 'smartphone') {
        return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>`;
    }
    if (iconType === 'tablet') {
        return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>`;
    }
    return `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="2" y1="20" x2="22" y2="20"/></svg>`;
}

function formatTimeAgo(ts) {
    if (!ts) return '';
    const diff = Math.max(0, Math.floor(Date.now() / 1000 - ts));
    if (diff < 15) return 'Active now';
    if (diff < 60) return `${diff}s ago`;
    const mins = Math.floor(diff / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ago`;
}

function renderPeers(peers) {
    if (!Array.isArray(peers)) return;
    currentPeers = peers;
    const badge = document.getElementById('peerCount');
    if (badge) badge.innerText = peers.length;

    const list = document.getElementById('peersList');
    const emptyState = document.getElementById('peersEmptyState');
    if (!list) return;

    if (peers.length === 0) {
        list.innerHTML = '';
        if (emptyState) emptyState.style.display = 'block';
        return;
    }

    if (emptyState) emptyState.style.display = 'none';

    list.innerHTML = peers.map(p => {
        const isRecent = p.active;
        const iconSvg = getDeviceIcon(p.icon);
        const timeAgo = formatTimeAgo(p.last_seen);
        const pId = escapeHtml(p.id);
        const pIp = escapeHtml(p.ip);
        const pNickname = escapeHtml(p.nickname || p.device || 'Device');
        const pDevice = escapeHtml(p.device);
        const pBrowser = escapeHtml(p.browser);

        const isIpVisible = !peersIpMasked || revealedPeerIps.has(p.id);
        const ipBadgeHtml = isIpVisible 
            ? `<span class="peer-ip-badge" onclick="togglePeerIp('${pId}')" title="Click to hide IP">${pIp}</span>`
            : `<span class="peer-ip-badge private" onclick="togglePeerIp('${pId}')" title="Click to reveal IP"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle; margin-right:4px;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>IP Hidden</span>`;

        return `
            <div class="peer-card" id="peer-${pId}">
                <div class="peer-info">
                    <div class="peer-icon-box">
                        ${iconSvg}
                        <span class="peer-status-dot ${isRecent ? 'active' : 'idle'}" title="${isRecent ? 'Active now' : 'Idle'}"></span>
                    </div>
                    <div class="peer-details">
                        <div class="peer-title">
                            <span class="peer-nickname">${pNickname}</span>
                            <button type="button" class="peer-rename-btn" onclick="renamePeer('${pId}', '${pNickname}')" title="Rename this device">
                                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                            </button>
                            <span style="font-weight:400; font-size:11px; color:var(--text-sub); margin-left:2px;">(${pBrowser})</span>
                        </div>
                        <div class="peer-meta">
                            ${ipBadgeHtml}
                            <span>• ${timeAgo}</span>
                        </div>
                    </div>
                </div>
                <button class="btn-peer-revoke" onclick="disconnectPeer('${pId}', '${pIp}')" title="Revoke device session">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Revoke
                </button>
            </div>
        `;
    }).join('');
}

async function fetchPeers() {
    try {
        const res = await fetch('/api/peers');
        if (res.ok) {
            const data = await res.json();
            if (data && data.peers) {
                renderPeers(data.peers);
            }
        }
    } catch (e) {}
}

async function disconnectPeer(id, ip) {
    if (!confirm(`Revoke access for this device (${ip})?`)) return;
    try {
        const res = await fetch('/api/peers/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, ip })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            showToast('Device access revoked', 'lock');
            currentPeers = currentPeers.filter(p => p.id !== id);
            renderPeers(currentPeers);
        } else {
            showToast('Failed to revoke device', 'error');
        }
    } catch (e) {
        showToast('Network error revoking device', 'error');
    }
}

// --- CLOUDFLARE PUBLIC INTERNET TUNNEL CONTROLLER ---
let currentTunnelUrl = null;

function updateTunnelUI(data) {
    const titleEl = document.getElementById('tunnel-mode-text');
    const iconEl = document.getElementById('tunnel-mode-icon');
    const subEl = document.getElementById('tunnel-mode-sub');
    const btnEl = document.getElementById('btnToggleTunnel');
    const btnTextEl = document.getElementById('btnTunnelText');
    const badgeEl = document.getElementById('tunnel-url-badge');
    const urlTextEl = document.getElementById('tunnel-url-text');
    const qrImg = document.querySelector('.qr-code-img');

    if (!titleEl || !btnEl) return;

    if (data.status === 'starting' || data.status === 'downloading') {
        iconEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/></svg>';
        titleEl.innerText = data.status === 'downloading' ? 'Downloading Engine...' : 'Starting Tunnel...';
        subEl.innerText = 'Securing public HTTPS route...';
        btnEl.disabled = true;
        btnTextEl.innerText = 'Connecting...';
    } else if (data.status === 'active' && data.url) {
        currentTunnelUrl = data.url;
        iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>';
        titleEl.innerText = 'Public Internet Mode';
        titleEl.style.color = 'var(--accent-green)';
        subEl.innerText = 'Accessible via 4G/5G mobile data worldwide';
        btnEl.disabled = false;
        btnEl.style.borderColor = 'rgba(239, 68, 68, 0.4)';
        btnEl.style.color = 'var(--accent-red)';
        btnTextEl.innerText = 'Switch to Local';
        if (badgeEl && urlTextEl) {
            badgeEl.style.display = 'inline-block';
            urlTextEl.innerText = data.url;
        }
        if (qrImg) {
            qrImg.src = '/qrcode.png?t=' + Date.now();
        }
    } else {
        currentTunnelUrl = null;
        iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>';
        titleEl.innerText = 'Local Wi-Fi Mode';
        titleEl.style.color = 'inherit';
        subEl.innerText = 'Works on same Wi-Fi / Hotspot';
        btnEl.disabled = false;
        btnEl.style.borderColor = 'var(--border-color)';
        btnEl.style.color = 'var(--text-main)';
        btnTextEl.innerText = 'Enable Internet';
        if (badgeEl) {
            badgeEl.style.display = 'none';
        }
        if (qrImg) {
            qrImg.src = '/qrcode.png?t=' + Date.now();
        }
    }
}

async function toggleTunnel() {
    const btnEl = document.getElementById('btnToggleTunnel');
    const btnTextEl = document.getElementById('btnTunnelText');
    if (btnEl) btnEl.disabled = true;
    if (btnTextEl) btnTextEl.innerText = 'Updating...';

    try {
        const res = await fetch('/api/tunnel/toggle', { method: 'POST' });
        const data = await res.json();
        updateTunnelUI(data);
        if (data.status === 'active') {
            showToast('Internet Mode Active! Works on mobile data.', 'globe');
        } else if (data.status === 'idle') {
            showToast('Reverted to Local Wi-Fi Mode', 'home');
        }
    } catch (e) {
        showToast('Error toggling Internet Mode', 'error');
        if (btnEl) btnEl.disabled = false;
    }
}

function copyTunnelUrl() {
    if (currentTunnelUrl) {
        navigator.clipboard.writeText(currentTunnelUrl).then(() => {
            showToast('Copied Public URL to clipboard!', 'copy');
        });
    }
}

// Initial Tunnel Status Check
(async function initTunnelStatus() {
    try {
        const res = await fetch('/api/tunnel');
        if (res.ok) {
            const data = await res.json();
            updateTunnelUI(data);
        }
    } catch (e) {}
})();

// Check for peer PyShare rooms on local subnet
async function checkLanRoomsHost() {
    try {
        const res = await fetch('/api/lan/rooms');
        if (!res.ok) return;
        const data = await res.json();
        const rooms = data.rooms || [];
        const container = document.getElementById('lanHostsNotification');
        if (container) {
            if (rooms.length > 0) {
                container.style.display = 'flex';
                const textEl = document.getElementById('lanHostsText');
                if (textEl) {
                    textEl.innerText = `${rooms.length} other PyShare instance${rooms.length > 1 ? 's' : ''} active on LAN`;
                }
            } else {
                container.style.display = 'none';
            }
        }
    } catch (e) {}
}

// Initial Connected Peers & Pending Join Requests Check
fetchPeers();
checkPendingJoinRequests();
checkLanRoomsHost();

// Bind to SSE when ready or immediately if already active
if (window.globalSSE) {
    setupHostSSE(window.globalSSE);
} else {
    window.addEventListener('pyshare:sse_ready', (e) => {
        setupHostSSE(e.detail);
    });
}

// Gentle Fallback Heartbeat (Every 15s instead of 1s aggressive polling)
setInterval(async () => {
    try {
        fetchPeers();
        checkPendingJoinRequests();
        checkLanRoomsHost();
        const res = await fetch('/api/updates');
        if (!res.ok) return;
        const data = await res.json();

        // Sync clipboard if updated remotely
        if (data.clipboard_ts && data.clipboard_ts > lastClipboardTs) {
            loadClipboard();
        }
    } catch (e) {}
}, 15000);

