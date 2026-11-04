/* ==========================================================================
   PyShare Host Scripts - Real-time Hub, PIN Sync & Activity Monitor
   ========================================================================== */

window.isHostSession = true;

// Set Host Address in Status Pill
const hostIpEl = document.getElementById('host-ip');

function updateServerDisplay(ip, port) {
    if (hostIpEl && ip && port) {
        hostIpEl.innerText = `${ip}:${port}`;
    }
}

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
    if (!hostIpEl) return;
    const addr = hostIpEl.innerText.trim();
    if (!addr || addr === '...' || addr === 'Detecting...') return;
    const fullUrl = `http://${addr}/`;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(fullUrl).then(() => {
            showToast(`Server URL copied: ${fullUrl}`, '📋');
        }).catch(() => {
            showToast(`Server URL: ${fullUrl}`, '📋');
        });
    } else {
        showToast(`Server URL: ${fullUrl}`, '📋');
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

// Host Clipboard Direct Sync
async function syncPCClipboard() {
    try {
        const res = await fetch('/api/sync_clipboard');
        const data = await res.json();
        if (data.status === 'ok') {
            showToast('Host clipboard pushed to devices!', '📋');
        } else if (data.status === 'empty') {
            showToast('Host clipboard is empty', '⚠️');
        } else {
            showToast('Could not sync host clipboard', '❌');
        }
    } catch (e) {
        showToast('Error syncing host clipboard', '❌');
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
            if (timerTextEl) timerTextEl.innerText = data.ttl + 's';
            
            if (timerBarEl) {
                const pct = (data.ttl / 30) * 100;
                timerBarEl.style.width = pct + '%';
                if (data.ttl < 5) {
                    timerBarEl.style.background = 'var(--accent-red)';
                } else {
                    timerBarEl.style.background = 'var(--accent-blue)';
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
            showToast('Internet Mode Active! Works on mobile data.', '🌐');
        } else if (data.status === 'idle') {
            showToast('Reverted to Local Wi-Fi Mode', '🏠');
        }
    } catch (e) {
        showToast('Error toggling Internet Mode', '❌');
        if (btnEl) btnEl.disabled = false;
    }
}

function copyTunnelUrl() {
    if (currentTunnelUrl) {
        navigator.clipboard.writeText(currentTunnelUrl).then(() => {
            showToast('Copied Public URL to clipboard!', '📋');
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
        const res = await fetch('/api/updates');
        if (!res.ok) return;
        const data = await res.json();

        // Sync clipboard if updated remotely
        if (data.clipboard_ts && data.clipboard_ts > lastClipboardTs) {
            loadClipboard();
        }
    } catch (e) {}
}, 15000);

