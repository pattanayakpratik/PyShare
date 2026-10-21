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

    // 4. Public Internet Tunnel Listener
    es.addEventListener('tunnel', (e) => {
        try {
            const data = JSON.parse(e.data);
            updateTunnelUI(data);
        } catch (err) {}
    });

    // 5. Real-time Feedback Notification Listener
    es.addEventListener('feedback', (e) => {
        try {
            const item = JSON.parse(e.data);
            prependFeedbackCard(item);
            incrementFeedbackBadge();
            const catIcons = { bug: '🐛', feature: '💡', question: '❓', general: '⭐' };
            const icon = catIcons[item.category] || '💬';
            if (typeof showToast === 'function') {
                showToast(`New feedback: ${icon} [${item.category.toUpperCase()}] ${item.message.slice(0, 30)}`, '💬');
            }
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
        iconEl.innerText = '⏳';
        titleEl.innerText = data.status === 'downloading' ? 'Downloading Engine...' : 'Starting Tunnel...';
        subEl.innerText = 'Securing public HTTPS route...';
        btnEl.disabled = true;
        btnTextEl.innerText = 'Connecting...';
    } else if (data.status === 'active' && data.url) {
        currentTunnelUrl = data.url;
        iconEl.innerText = '🌐';
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
        iconEl.innerText = '🏠';
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

// --- FEEDBACK LIVE HUB CONTROLLER ---
let unreadFeedbackCount = 0;

function incrementFeedbackBadge() {
    unreadFeedbackCount++;
    const badge = document.getElementById('feedbackBadge');
    if (badge) {
        badge.innerText = unreadFeedbackCount;
        badge.style.display = 'inline-block';
    }
}

function createFeedbackCard(item) {
    const card = document.createElement('div');
    card.className = 'feedback-entry-card';

    const catIcons = { bug: '🐛', feature: '💡', question: '❓', general: '⭐' };
    const icon = catIcons[item.category] || '💬';
    const tagClass = `badge-${item.category || 'general'}`;

    let starsHtml = '';
    if (item.rating && item.rating > 0) {
        starsHtml = `<span>${'⭐'.repeat(item.rating)}</span>`;
    }

    const timeStr = item.created_at ? item.created_at.split(' ')[1] : '--:--';
    const dateStr = item.created_at ? item.created_at.split(' ')[0] : '';
    const contactStr = item.contact ? `<span>👤 ${escapeHtml(item.contact)}</span>` : '';
    const ipStr = item.client_ip ? `<span>🌐 ${escapeHtml(item.client_ip)}</span>` : '';
    const devStr = item.device && item.device.os ? `<span>📱 ${escapeHtml(item.device.os)} / ${escapeHtml(item.device.browser || '')}</span>` : '';

    card.innerHTML = `
        <div class="feedback-entry-header">
            <span class="feedback-category-badge ${tagClass}">${icon} ${escapeHtml(item.category)}</span>
            <div style="display:flex; align-items:center; gap:6px;">
                ${starsHtml}
                <span class="log-timestamp" style="font-size:10px;">${escapeHtml(timeStr)}</span>
            </div>
        </div>
        <div class="feedback-entry-msg">${escapeHtml(item.message)}</div>
        <div class="feedback-entry-meta">
            ${dateStr ? `<span>📅 ${escapeHtml(dateStr)}</span>` : ''}
            ${contactStr}
            ${ipStr}
            ${devStr}
        </div>
    `;
    return card;
}

async function loadFeedbackList() {
    try {
        const res = await fetch('/api/feedback');
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById('feedbackListContainer');
        if (!container) return;

        const items = data.items || [];
        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state" style="padding:16px 0; font-size:12px;">No feedback submissions yet</div>';
            return;
        }

        container.innerHTML = '';
        items.forEach(item => {
            container.appendChild(createFeedbackCard(item));
        });

        // Reset badge once viewed
        const badge = document.getElementById('feedbackBadge');
        if (badge) {
            badge.style.display = 'none';
            unreadFeedbackCount = 0;
        }
    } catch (e) {}
}

function prependFeedbackCard(item) {
    const container = document.getElementById('feedbackListContainer');
    if (!container) return;
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const card = createFeedbackCard(item);
    container.prepend(card);
}

// Initial fetch of existing feedback items on load
loadFeedbackList();

