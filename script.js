// --- THEME LOGIC (Auto + Toggle + Memory) ---
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const target = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', target);
    localStorage.setItem('theme', target);
}

// Init Theme on Load
(function () {
    const saved = localStorage.getItem('theme');
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (saved) { document.documentElement.setAttribute('data-theme', saved); }
    else if (sysDark) { document.documentElement.setAttribute('data-theme', 'dark'); }
})();

// --- PAGE: Upload Logic ---
const dropZone = document.getElementById('dropZone');
if (dropZone) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, e => { e.preventDefault(); e.stopPropagation(); }, false);
    });

    dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });
}

function handleFiles(files) {
    if (files.length === 0) return;
    uploadQueue(Array.from(files));
}

function uploadQueue(files) {
    if (files.length === 0) {
        const status = document.getElementById('status');
        if (status) {
            status.innerText = "✅ All uploads finished!";
            status.style.color = "#27ae60";
            setTimeout(() => status.innerText = "", 3000);
        }
        return;
    }
    const file = files.shift();
    uploadSingleFile(file, () => uploadQueue(files));
}

function uploadSingleFile(file, onComplete) {
    const formData = new FormData();
    formData.append("file", file);
    const xhr = new XMLHttpRequest();
    const bar = document.getElementById('progress-bar');
    const container = document.getElementById('progress-container');
    const status = document.getElementById('status');

    if (container) container.style.display = 'block';
    if (status) {
        status.innerText = `Uploading: ${file.name}...`;
        status.style.color = "var(--sub)";
    }

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && bar) {
            const percent = (e.loaded / e.total) * 100;
            bar.style.width = percent + "%";
        }
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            onComplete();
        } else {
            if (status) {
                status.innerText = `❌ Error uploading ${file.name}`;
                status.style.color = "#e74c3c";
            }
        }
    };

    xhr.onerror = () => { if (status) status.innerText = "❌ Network Error"; };
    xhr.open("POST", "/");
    xhr.send(formData);
}

// --- PAGE: File Manager Logic ---
function deleteFile(name) {
    if (confirm('Delete ' + name + '?')) {
        fetch('/delete/' + encodeURIComponent(name)).then(() => location.reload());
    }
}

function doSearch() {
    let val = document.getElementById('search').value.toLowerCase();
    document.querySelectorAll('.file-item').forEach(li => {
        li.style.display = li.getAttribute('data-name').includes(val) ? 'block' : 'none';
    });
}

function disconnectServer() {
    if (confirm("Stop the server?")) {
        fetch('/shutdown').then(() => {
            document.body.innerHTML = "<h2 style='text-align:center;margin-top:50px;color:#e74c3c;'>Disconnected</h2>";
        }).catch(() => window.close());
    }
}