/* ==========================================================================
   PyShare Host Scripts - Real-time Hub, PIN Sync & Activity Monitor
   ========================================================================== */

window.isHostSession = true;

// Set Host Address in Status Pill
const hostIpEl = document.getElementById('host-ip');
if (hostIpEl) {
    hostIpEl.innerText = window.location.host;
}

// Host uploads land directly into Shared_Files
window.handleFilesCustom = function(files) {
    uploadManager.addFiles(files, '/?dest=host');
};

function handleFilesHost(files) {
    uploadManager.addFiles(files, '/?dest=host');
}

// Windows OS Clipboard Direct Sync
async function syncPCClipboard() {
    try {
        const res = await fetch('/api/sync_clipboard');
        const data = await res.json();
        if (data.status === 'ok') {
            showToast('PC Clipboard pushed to devices!', '💻');
        } else if (data.status === 'empty') {
            showToast('PC clipboard is empty', '⚠️');
        } else {
            showToast('Could not sync PC clipboard', '❌');
        }
    } catch (e) {
        showToast('Error syncing PC clipboard', '❌');
    }
}

// Setup Host SSE Real-time Listeners
function setupHostSSE(es) {
    if (!es) return;

    // 1. Live PIN & Grace Period Countdown (Pushed every second from server)
    es.addEventListener('pin', (e) => {
        try {
            const data = JSON.parse(e.data);
            const pinEl = document.getElementById('live-pin');
            const timerTextEl = document.getElementById('pin-timer-text');
            const timerBarEl = document.getElementById('pin-timer-bar');

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

    // 3. Incoming Mobile Upload Monitor (High-frequency throttled push)
    es.addEventListener('upload', (e) => {
        try {
            const upload = JSON.parse(e.data);
            const rxBox = document.getElementById('rx-container');
            const rxBar = document.getElementById('rx-bar');
            const rxName = document.getElementById('rx-filename');
            if (rxBox && rxBar && rxName) {
                if (upload) {
                    rxBox.style.display = 'block';
                    rxName.innerText = upload.filename;
                    const pct = Math.round((upload.current / upload.total) * 100);
                    rxBar.style.width = pct + "%";
                } else {
                    rxBox.style.display = 'none';
                }
            }
        } catch (err) {}
    });
}

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
