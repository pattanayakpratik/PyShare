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
let lastDisplayedPin = null;
fetch('/api/pin')
    .then(r => r.json())
    .then(data => {
        if (data) {
            const pinEl = document.getElementById('live-pin');
            const timerTextEl = document.getElementById('pin-timer-text');
            if (data.pin) lastDisplayedPin = data.pin;
            if (pinEl && data.pin) pinEl.innerText = data.pin;
            if (timerTextEl) timerTextEl.innerText = (data.ttl < 0 || data.mode === 'static') ? 'Static' : (data.ttl + 's');
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
    copyToClipboard(fullUrl).then((ok) => {
        showToast(ok ? `Server URL copied: ${fullUrl}` : `Server URL: ${fullUrl}`, ok ? 'copy' : 'info');
    });
}
window.copyHostIp = copyHostIp;

// Host uploads land directly into Shared_Files
window.handleFilesCustom = function(files) {
    uploadManager.addFiles(files, '/?dest=host');
};

function handleFilesHost(files) {
    uploadManager.addFiles(files, '/?dest=host');
}

// Auto-copy incoming chat to this PC's clipboard. This is a server setting: the server writes the
// Windows clipboard itself, so the browser never calls the clipboard API without a click (which
// made Chromium/WebView2 show a "wants to see text and images copied to the clipboard" prompt).
async function toggleHostAutoClipboardSync(checked) {
    const cb = document.getElementById('toggleHostAutoClipboard');
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_clipboard: !!checked })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cb) cb.checked = !!data.auto_clipboard;
        showToast(data.auto_clipboard ? 'Incoming messages will be copied to this PC' : 'Auto-copy to this PC is off', data.auto_clipboard ? 'check' : 'info');
    } catch (e) {
        if (cb) cb.checked = !checked;  // revert: the setting didn't change
        showToast('Could not change the auto-copy setting', 'error');
    }
}
window.toggleHostAutoClipboardSync = toggleHostAutoClipboardSync;

(async function initHostAutoClipboard() {
    const cb = document.getElementById('toggleHostAutoClipboard');
    if (!cb) return;
    cb.checked = true;  // server default
    try {
        const res = await fetch('/api/settings');
        if (res.ok) cb.checked = !!(await res.json()).auto_clipboard;
    } catch (e) {}
    try { localStorage.removeItem('pyshare_host_auto_clipboard'); } catch (e) {}  // old browser-side flag
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
        const input = (typeof showPySharePrompt === 'function')
            ? await showPySharePrompt({
                title: 'Use a fixed PIN',
                message: 'Pick a 4-digit PIN that stays the same, handy on your own home network. Leave it empty to use 1234.',
                defaultValue: '',
                placeholder: '4 digits, e.g. 2580',
                confirmText: 'Use this PIN',
                maxLength: 4,
                inputMode: 'numeric'
            })
            : prompt("Set a static 4-digit PIN for your personal/home network (leave blank for default 1234):", "");
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
            if (qrImg) qrImg.src = '/api/qr?t=' + Date.now();
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
            if (data.pin && data.pin !== lastDisplayedPin) {
                lastDisplayedPin = data.pin;
                const qrImg = document.querySelector('.qr-code-img');
                if (qrImg) qrImg.src = '/api/qr?t=' + Date.now();
            }
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
            addActivityEntry(JSON.parse(e.data));
        } catch (err) {}
    });

    // 3. Incoming uploads: one combined status for everything phones are sending
    es.addEventListener('upload', (e) => {
        try {
            renderReceiveStatus(JSON.parse(e.data));
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

    // 7. A knock ended elsewhere: the guest cancelled or left the page, it timed out, or another Host window answered
    es.addEventListener('join_request_closed', (e) => {
        try {
            const d = JSON.parse(e.data);
            if (!d || !d.id) return;
            const name = d.nickname || 'The device';
            const message = d.reason === 'cancelled' ? `${name} cancelled the join request`
                : d.reason === 'expired' ? `Join request from ${name} expired`
                : '';
            closeHostJoinRequest(d.id, message);
        } catch (err) {}
    });
}

// --- RECEIVE PROGRESS ---
// The server sends one snapshot covering every file in flight (phones upload 2 at a time):
// {active, filename, done, files, received, total}. One bar, one speed, one ETA, so nothing flips
// between files. active == 0 means the batch finished; null means nothing is being received.
let rxLastBytes = 0;
let rxLastTime = 0;
let rxSpeed = 0;
let rxLastFilename = '';
let rxDoneTimer = null;

function renderReceiveStatus(u) {
    const box = document.getElementById('rx-container');
    const bar = document.getElementById('rx-bar');
    const label = document.getElementById('rx-label-text');
    const name = document.getElementById('rx-filename');
    const stats = document.getElementById('rx-stats');
    const eta = document.getElementById('rx-eta');
    if (!box || !bar) return;
    clearTimeout(rxDoneTimer);

    const reset = () => {
        box.style.display = 'none';
        box.classList.remove('rx-done');
        rxSpeed = 0;
        rxLastTime = 0;
    };
    if (!u) {
        reset();
        return;
    }

    if (u.active > 0) {
        const pct = u.total > 0 ? Math.min(100, Math.round((u.received / u.total) * 100)) : 0;
        const now = Date.now();
        if (!rxLastTime || u.received < rxLastBytes) {
            // New batch, or a failed file's bytes dropped out of the total: restart the speed sample
            rxLastBytes = u.received;
            rxLastTime = now;
        } else if (now - rxLastTime >= 400) {
            const cur = (u.received - rxLastBytes) / ((now - rxLastTime) / 1000);
            rxSpeed = rxSpeed > 0 ? 0.7 * rxSpeed + 0.3 * cur : cur;
            rxLastBytes = u.received;
            rxLastTime = now;
        }
        rxLastFilename = u.filename || rxLastFilename;

        box.style.display = 'block';
        box.classList.remove('rx-done');
        bar.style.width = pct + '%';
        if (label) label.innerText = u.files > 1 ? `Receiving ${u.done}/${u.files}` : 'Receiving';
        if (name) {
            name.innerText = u.filename;
            name.title = u.filename;
        }
        const speedStr = rxSpeed > 0 ? `${formatSize(rxSpeed)}/s` : 'starting…';
        const etaSec = rxSpeed > 0 ? Math.round(Math.max(0, u.total - u.received) / rxSpeed) : 0;
        if (stats) stats.innerText = `${pct}% • ${speedStr}`;
        if (eta) eta.innerText = etaSec > 0 ? `${formatEta(etaSec)} left` : '';
        return;
    }

    // Nothing in flight. The phone's next queued file usually starts within a moment, so wait before
    // calling it done, otherwise the bar would blink off and on between files. Counts update right away.
    if (u.total > 0) bar.style.width = Math.min(100, Math.round((u.received / u.total) * 100)) + '%';
    if (label && u.files > 1) label.innerText = `Receiving ${u.done}/${u.files}`;
    rxDoneTimer = setTimeout(() => {
        if (u.done === 0) {
            reset();   // everything was cancelled or failed
            return;
        }
        box.style.display = 'block';
        box.classList.add('rx-done');
        bar.style.width = '100%';
        if (label) label.innerText = 'Received';
        if (name) name.innerText = u.done === 1 ? rxLastFilename : `${u.done} files`;
        if (stats) stats.innerText = `Done • ${formatSize(u.received)}`;
        if (eta) eta.innerText = '';
        rxDoneTimer = setTimeout(reset, 3500);
    }, 1200);
}

// --- ACTIVITY LOG (history on open + live entries, newest first) ---
const MAX_ACTIVITY_ROWS = 60;
const seenActivity = new Set();  // time|msg keys, so history + live SSE never double-render

function addActivityEntry(entry) {
    const logBox = document.getElementById('hubLogPane');
    if (!logBox || !entry || !entry.msg) return;
    const key = `${entry.time}|${entry.msg}`;
    if (seenActivity.has(key)) return;
    seenActivity.add(key);

    document.getElementById('hubLogEmpty')?.remove();
    const row = document.createElement('div');
    row.className = 'log-entry-row';
    row.innerHTML = `<span class="log-timestamp">${escapeHtml(entry.time)}</span><span class="log-message" title="${escapeHtml(entry.msg)}">${escapeHtml(entry.msg)}</span>`;
    logBox.prepend(row);
    while (logBox.children.length > MAX_ACTIVITY_ROWS) {
        logBox.removeChild(logBox.lastChild);
    }
}

async function loadActivityHistory() {
    try {
        const res = await fetch('/api/updates');
        if (!res.ok) return;
        const data = await res.json();
        (data.events || []).forEach(addActivityEntry);  // oldest first => newest ends on top
    } catch (e) {}
}

// --- Host Join Request Handling ---
// One knock is on screen at a time; any others wait on the server and appear when it closes.
let activeHostJoinRequest = null;
let hostJoinReqCountdownTimer = null;
const closedJoinRequestIds = new Set();     // answered, cancelled or expired: never show again
const announcedJoinRequestIds = new Set();  // knocks waiting behind the current one, already toasted

function displayHostJoinRequest(req) {
    if (!req || !req.id || closedJoinRequestIds.has(req.id)) return;
    const modal = document.getElementById('hostJoinRequestModal');
    if (!modal) return;
    if (activeHostJoinRequest && activeHostJoinRequest.id !== req.id) {
        if (!announcedJoinRequestIds.has(req.id)) {
            announcedJoinRequestIds.add(req.id);
            showToast(`${req.nickname || 'Another device'} is also waiting to join`, 'bell');
        }
        return;
    }
    const isNew = !activeHostJoinRequest;
    activeHostJoinRequest = { ...req, shownAt: isNew ? Date.now() : activeHostJoinRequest.shownAt };

    const nameEl = document.getElementById('joinReqDeviceName');
    const infoEl = document.getElementById('joinReqDeviceInfo');
    const timerEl = document.getElementById('joinReqTimer');
    if (nameEl) nameEl.innerText = req.nickname || 'Unknown Device';
    if (infoEl) infoEl.innerText = `${req.browser || 'Browser'} on ${req.device || 'Device'} • IP: ${req.ip || 'Unknown'}`;

    modal.style.display = 'flex';
    if (isNew) {
        showToast(`Device wants to join: ${req.nickname}`, 'bell');
        if (navigator.vibrate) navigator.vibrate([80, 50, 80]);
    }

    let secondsLeft = req.expires_in || 60;
    if (timerEl) timerEl.innerText = `Auto-expires in ${secondsLeft}s`;

    if (hostJoinReqCountdownTimer) clearInterval(hostJoinReqCountdownTimer);
    hostJoinReqCountdownTimer = setInterval(() => {
        secondsLeft--;
        if (timerEl) timerEl.innerText = `Auto-expires in ${Math.max(0, secondsLeft)}s`;
        if (secondsLeft <= 0) closeHostJoinRequest(req.id);
    }, 1000);
}

// The knock is over: the guest cancelled or left, it expired, or it was answered (here or in another
// Host window). Close it if it's on screen, then show the next device waiting, if any.
function closeHostJoinRequest(id, message) {
    closedJoinRequestIds.add(id);
    if (!activeHostJoinRequest || activeHostJoinRequest.id !== id) return;
    hideHostJoinRequestModal();
    if (message) showToast(message, 'info');
    checkPendingJoinRequests();
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
    const req = activeHostJoinRequest;
    if (!req || !req.id) {
        hideHostJoinRequestModal();
        return;
    }
    closedJoinRequestIds.add(req.id);
    hideHostJoinRequestModal();

    try {
        const res = await fetch('/api/join/respond', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: req.id, action: action })
        });
        if (!res.ok) {
            // The guest cancelled (or it expired) in the moment before the click
            showToast(`${req.nickname || 'That device'} is no longer waiting to join`, 'warning');
        } else if (action === 'accept') {
            showToast(`Allowed ${req.nickname} to connect`, 'success');
            fetchPeers();
        } else {
            showToast(`Declined request from ${req.nickname}`, 'error');
        }
    } catch (e) {
        showToast('Error responding to join request', 'error');
    }
    checkPendingJoinRequests();
}
window.respondHostJoinRequest = respondHostJoinRequest;

// Show the oldest waiting knock: on load, after each one closes, and every 15s as a fallback
// that also catches a cancel whose live event was missed (e.g. the event stream reconnecting).
async function checkPendingJoinRequests() {
    const startedAt = Date.now();
    try {
        const res = await fetch('/api/join/pending');
        if (!res.ok) return;
        const data = await res.json();
        const requests = (data && Array.isArray(data.requests)) ? data.requests : [];
        const active = activeHostJoinRequest;
        // Only trust this snapshot about a dialog that was already open when it was taken
        if (active && active.shownAt < startedAt && !requests.some(r => r && r.id === active.id)) {
            closeHostJoinRequest(active.id, `${active.nickname || 'The device'} is no longer waiting to join`);
            return;
        }
        const next = requests.find(r => r && r.id && !closedJoinRequestIds.has(r.id) && r.expires_in > 1);
        if (next) displayHostJoinRequest(next);
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

        // Inline handlers get jsArg() values: nicknames come from client devices and must not
        // be able to break out of the JS string (escapeHtml's &#39; is decoded before JS runs).
        const idArg = jsArg(p.id);
        const isIpVisible = !peersIpMasked || revealedPeerIps.has(p.id);
        const ipBadgeHtml = isIpVisible
            ? `<span class="peer-ip-badge" onclick="togglePeerIp(${idArg})" title="Click to hide IP">${pIp}</span>`
            : `<span class="peer-ip-badge private" onclick="togglePeerIp(${idArg})" title="Click to reveal IP"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle; margin-right:4px;"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>IP Hidden</span>`;

        return `
            <div class="peer-card" id="peer-${pId}">
                <div class="peer-info">
                    <div class="peer-icon-box">
                        ${iconSvg}
                        <span class="peer-status-dot ${isRecent ? 'active' : 'idle'}" title="${isRecent ? 'Active now' : 'Idle'}"></span>
                    </div>
                    <div class="peer-details">
                        <div class="peer-title">
                            <span class="peer-nickname" title="${pNickname}">${pNickname}</span>
                            <button type="button" class="peer-rename-btn" onclick="renamePeer(${idArg}, ${jsArg(p.nickname || p.device || 'Device')})" title="Rename this device" aria-label="Rename device">
                                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                            </button>
                        </div>
                        <div class="peer-meta">
                            <span>${pBrowser}</span>
                            ${ipBadgeHtml}
                            <span>${timeAgo}</span>
                        </div>
                    </div>
                </div>
                <button class="btn-icon btn-icon-danger btn-peer-revoke" onclick="disconnectPeer(${idArg}, ${jsArg(p.ip)})" title="Revoke access (disconnect this device)" aria-label="Revoke device access">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><line x1="5.6" y1="5.6" x2="18.4" y2="18.4"></line></svg>
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
    const displayTarget = (!peersIpMasked || revealedPeerIps.has(id)) ? ip : id;
    const confirmed = (typeof showPyShareConfirm === 'function')
        ? await showPyShareConfirm({
            title: 'Revoke Device Access',
            message: `Disconnect device (${displayTarget}) and revoke its active session?`,
            confirmText: 'Revoke Access',
            isDanger: true
        })
        : confirm(`Revoke access for this device (${displayTarget})?`);
    if (!confirmed) return;
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
        titleEl.innerText = 'Internet Mode';
        titleEl.style.color = 'var(--accent-green)';
        subEl.innerText = 'Public HTTPS link';
        btnEl.disabled = false;
        btnEl.style.borderColor = 'rgba(239, 68, 68, 0.4)';
        btnEl.style.color = 'var(--accent-red)';
        btnTextEl.innerText = 'Turn off';
        btnEl.title = 'Stop the public link and go back to local Wi-Fi only';
        if (badgeEl && urlTextEl) {
            badgeEl.style.display = 'inline-block';
            urlTextEl.innerText = data.url;
        }
        if (qrImg) {
            qrImg.src = '/api/qr?t=' + Date.now();
        }
    } else {
        currentTunnelUrl = null;
        iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>';
        titleEl.innerText = 'Local Wi-Fi';
        titleEl.style.color = 'inherit';
        subEl.innerText = 'Same network only';
        btnEl.disabled = false;
        btnEl.style.borderColor = 'var(--border-color)';
        btnEl.style.color = 'var(--text-main)';
        btnTextEl.innerText = 'Go online';
        btnEl.title = 'Share over 4G/5G mobile data or a different Wi-Fi';
        if (badgeEl) {
            badgeEl.style.display = 'none';
        }
        if (qrImg) {
            qrImg.src = '/api/qr?t=' + Date.now();
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
        copyToClipboard(currentTunnelUrl).then((ok) => {
            showToast(ok ? 'Copied Public URL to clipboard!' : 'Could not copy the link', ok ? 'copy' : 'error');
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

// Initial Activity History, Connected Peers & Pending Join Requests Check
loadActivityHistory();
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

