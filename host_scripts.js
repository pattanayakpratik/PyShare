// --- 1. OVERRIDE DRAG & DROP BEHAVIOR ---
window.handleFiles = handleFilesHost;

document.getElementById('host-ip').innerText = window.location.host;

// --- Host Specific Logic ---
function handleFilesHost(files) {
    if (!files.length) return;
    Array.from(files).forEach(file => {
        uploadFileCustom(file, "/?dest=host");
    });
}

function uploadFileCustom(file, url) {
    const xhr = new XMLHttpRequest();
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
    const status = document.getElementById('status');
    const pct = document.getElementById('percent-text');

    // 1. Open connection using the provided url
    xhr.open("POST", url); 
    
    // 2. Set headers
    xhr.setRequestHeader("X-File-Name", encodeURIComponent(file.name));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");

    container.style.display = 'block';
    status.innerText = `Adding: ${file.name}...`;

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            bar.style.width = percent + "%";
            pct.innerText = Math.round(percent) + "%";
        }
    };
    
    xhr.onload = () => {
        status.innerText = "✅ Added!";
        loadFiles();
        setTimeout(() => { container.style.display = 'none'; bar.style.width = '0%'; }, 2000);
    };
    
    xhr.send(file);
}

// Live Poll (Logs + Progress)
setInterval(async () => {
    try {
        const res = await fetch('/api/updates');
        const data = await res.json();

        // Update Logs
        const log = document.getElementById('notif-log');
        if (data.events.length > 0) {
            // REMOVED REDUNDANT DECLARATION HERE
            log.innerHTML = ""; // Clear to rebuild

            data.events.forEach(e => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                entry.innerHTML = `<span class="log-time">${e.time}</span> <span class="log-msg">${e.msg}</span>`;
                log.prepend(entry);
            });

            if (data.events.some(e => e.msg.includes("received") || e.msg.includes("Added"))) loadFiles();
        }

        // Update Incoming Progress
        const rxBox = document.getElementById('rx-container');
        const rxBar = document.getElementById('rx-bar');
        const rxName = document.getElementById('rx-filename');

        if (data.upload) {
            rxBox.style.display = 'block';
            rxName.innerText = data.upload.filename;
            const pct = (data.upload.current / data.upload.total) * 100;
            rxBar.style.width = pct + "%";
        } else {
            rxBox.style.display = 'none';
        }

    } catch (e) { console.error(e); }
}, 1000);

setInterval(async () => {
    try {
        const res = await fetch('/api/pin');
        if (res.ok) {
            const data = await res.json();

            // Update PIN
            document.getElementById('live-pin').innerText = data.pin;

            // Update Timer Text
            document.getElementById('pin-timer-text').innerText = data.ttl + "s";

            // Update Timer Bar
            const pct = (data.ttl / 30) * 100;
            document.getElementById('pin-timer-bar').style.width = pct + "%";

            // Color Logic
            const bar = document.getElementById('pin-timer-bar');
            if (data.ttl < 5) bar.style.background = "#ef4444";
            else bar.style.background = "var(--accent-blue)";
        }
    } catch (e) { }
}, 1000);