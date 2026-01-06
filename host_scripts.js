// --- 1. OVERRIDE DRAG & DROP BEHAVIOR ---
// This ensures files dragged onto the Host Dashboard go to "Shared" (Sending_Files)
// instead of "Received" (Recieved_Files).
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
    const formData = new FormData();
    formData.append("file", file);
    const xhr = new XMLHttpRequest();
    const container = document.getElementById('progress-container');
    const bar = document.getElementById('progress-bar');
    const status = document.getElementById('status');
    const pct = document.getElementById('percent-text');

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
        loadFiles(); // Refresh lists immediately
        setTimeout(() => { container.style.display = 'none'; bar.style.width = '0%'; }, 2000);
    };
    xhr.open("POST", url);
    xhr.send(formData);
}

// Live Poll (Logs + Progress)
setInterval(async () => {
    try {
        const res = await fetch('/api/updates');
        const data = await res.json();

        // Update Logs
        const log = document.getElementById('notif-log');
        if (data.events.length > 0) {
            const log = document.getElementById('notif-log');

            // Clear the log completely to rebuild it with the full history
            log.innerHTML = "";

            data.events.forEach(e => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                // Ensure you use e.msg (or e.message) consistently with your python code
                entry.innerHTML = `<span class="log-time">${e.time}</span> <span class="log-msg">${e.msg}</span>`;
                log.prepend(entry);
            });
            // Auto-refresh file lists if needed
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

