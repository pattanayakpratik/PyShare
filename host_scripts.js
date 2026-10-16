/* ==========================================================================
   PyShare Host Scripts - Real-time Hub, PIN Sync & Activity Monitor
   ========================================================================== */

window.isHostSession = true;

// Set Host Address
const hostIpEl = document.getElementById('host-ip');
if (hostIpEl) {
    hostIpEl.innerText = window.location.host;
}

// Override file handler so Host uploads land directly into Shared_Files
window.handleFilesCustom = function(files) {
    uploadManager.addFiles(files, '/?dest=host');
};

function handleFilesHost(files) {
    uploadManager.addFiles(files, '/?dest=host');
}

// Live Polling Loop for Events, RX Progress & Clipboard
let lastEventJson = "";
setInterval(async () => {
    try {
        const res = await fetch('/api/updates');
        if (!res.ok) return;
        const data = await res.json();

        // 1. Update Real-time Activity Log
        const logBox = document.getElementById('notif-log');
        if (data.events && logBox) {
            const currentEventJson = JSON.stringify(data.events);
            if (currentEventJson !== lastEventJson) {
                logBox.innerHTML = "";
                data.events.forEach(e => {
                    const entry = document.createElement('div');
                    entry.className = 'log-entry';
                    entry.innerHTML = `<span class="log-time">${escapeHtml(e.time)}</span><span class="log-msg">${escapeHtml(e.msg)}</span>`;
                    logBox.prepend(entry);
                });
                lastEventJson = currentEventJson;
                loadFiles(); // Refresh file listing when new events occur
            }
        }

        // 2. Update Incoming Mobile Upload Monitor
        const rxBox = document.getElementById('rx-container');
        const rxBar = document.getElementById('rx-bar');
        const rxName = document.getElementById('rx-filename');
        if (rxBox && rxBar && rxName) {
            if (data.upload) {
                rxBox.style.display = 'block';
                rxName.innerText = data.upload.filename;
                const pct = Math.round((data.upload.current / data.upload.total) * 100);
                rxBar.style.width = pct + "%";
            } else {
                rxBox.style.display = 'none';
            }
        }

        // 3. Sync Clipboard if updated remotely
        if (data.clipboard_ts && data.clipboard_ts > lastClipboardTs) {
            loadClipboard();
        }

    } catch (e) {
        // Silently catch network dropouts during shutdown
    }
}, 1000);

// Live Polling Loop for PIN & Grace Period Countdown
setInterval(async () => {
    try {
        const res = await fetch('/api/pin');
        if (!res.ok) return;
        const data = await res.json();

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
    } catch (e) {}
}, 1000);