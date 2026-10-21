/* ==========================================================================
   PyShare v4.6.0 - Universal Feedback & Help System
   Client, Host & Web P2P Universal Support
   ========================================================================== */

// Public Formspree endpoint for instant email notifications
const PUBLIC_FEEDBACK_ENDPOINT = 'https://formspree.io/f/xzedlljr';

let currentFeedbackCategory = 'bug';
let currentFeedbackRating = 5;
let isSubmittingFeedback = false;

// 1. Collect Anonymous Device Diagnostics
function getDeviceDiagnostics() {
    const ua = navigator.userAgent || '';
    let os = 'Unknown OS';
    if (/Windows/i.test(ua)) os = 'Windows';
    else if (/Android/i.test(ua)) os = 'Android';
    else if (/iPhone|iPad|iPod/i.test(ua)) os = 'iOS';
    else if (/Macintosh|Mac OS/i.test(ua)) os = 'macOS';
    else if (/Linux/i.test(ua)) os = 'Linux';

    let browser = 'Unknown Browser';
    if (/Edg/i.test(ua)) browser = 'Edge';
    else if (/Chrome/i.test(ua)) browser = 'Chrome';
    else if (/Safari/i.test(ua)) browser = 'Safari';
    else if (/Firefox/i.test(ua)) browser = 'Firefox';

    const screenRes = `${window.screen.width || 0}x${window.screen.height || 0}`;
    const viewportRes = `${window.innerWidth}x${window.innerHeight}`;
    const page = window.location.pathname.split('/').pop() || 'index.html';
    const isMobile = window.innerWidth <= 600 || /Android|iPhone|iPad|iPod/i.test(ua);

    return {
        os: os,
        browser: browser,
        screen: screenRes,
        viewport: viewportRes,
        deviceType: isMobile ? 'Mobile' : 'Desktop',
        page: page,
        protocol: window.location.protocol,
        host: window.location.host
    };
}

// 2. Ensure Modal is in the DOM
function ensureFeedbackModal() {
    let modal = document.getElementById('feedbackModal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'feedbackModal';
    modal.className = 'modal-backdrop';
    modal.onclick = (e) => {
        if (e.target === modal) closeFeedbackModal();
    };

    const diag = getDeviceDiagnostics();

    modal.innerHTML = `
    <div class="modal-box feedback-modal-box">
        <div class="modal-header">
            <span class="modal-title-text" style="display:flex; align-items:center; gap:8px;">
                <span>💬</span> Help &amp; Feedback
            </span>
            <button class="icon-btn" onclick="closeFeedbackModal()" style="width:34px; height:34px;" title="Close">✕</button>
        </div>

        <div id="feedbackFormContainer" style="padding: 20px; overflow-y: auto; max-height: calc(85vh - 120px);">
            <!-- 1. Category Selector -->
            <label style="font-size: 11px; font-weight: 700; color: var(--text-sub); display: block; margin-bottom: 8px; letter-spacing: 0.5px;">
                WHAT WOULD YOU LIKE TO SHARE?
            </label>
            <div class="feedback-category-grid">
                <button type="button" class="category-chip active" id="catBtn-bug" onclick="selectFeedbackCategory('bug')">
                    <span>🐛</span> Problem / Bug
                </button>
                <button type="button" class="category-chip" id="catBtn-feature" onclick="selectFeedbackCategory('feature')">
                    <span>💡</span> Feature Idea
                </button>
                <button type="button" class="category-chip" id="catBtn-question" onclick="selectFeedbackCategory('question')">
                    <span>❓</span> Question / Help
                </button>
                <button type="button" class="category-chip" id="catBtn-general" onclick="selectFeedbackCategory('general')">
                    <span>⭐</span> General Feedback
                </button>
            </div>

            <!-- 2. Star Rating -->
            <label style="font-size: 11px; font-weight: 700; color: var(--text-sub); display: block; margin-bottom: 6px; letter-spacing: 0.5px;">
                RATE YOUR EXPERIENCE
            </label>
            <div class="star-rating-row" id="feedbackStarRow">
                <button type="button" class="star-btn active" data-rating="1" onclick="setFeedbackRating(1)" title="1 Star">⭐</button>
                <button type="button" class="star-btn active" data-rating="2" onclick="setFeedbackRating(2)" title="2 Stars">⭐</button>
                <button type="button" class="star-btn active" data-rating="3" onclick="setFeedbackRating(3)" title="3 Stars">⭐</button>
                <button type="button" class="star-btn active" data-rating="4" onclick="setFeedbackRating(4)" title="4 Stars">⭐</button>
                <button type="button" class="star-btn active" data-rating="5" onclick="setFeedbackRating(5)" title="5 Stars">⭐</button>
                <span id="feedbackRatingLabel" style="font-size: 12px; color: var(--text-sub); margin-left: 6px; font-weight: 600;">5 / 5</span>
            </div>

            <!-- 3. Message Textarea -->
            <label for="feedbackMsg" style="font-size: 11px; font-weight: 700; color: var(--text-sub); display: block; margin-bottom: 6px; letter-spacing: 0.5px;">
                YOUR MESSAGE / PROBLEM DESCRIPTION <span style="color:var(--accent-red); font-weight:bold;">*</span>
            </label>
            <textarea id="feedbackMsg" class="feedback-textarea" placeholder="Describe the problem you faced or feature you would like to see..." maxlength="2000" oninput="updateFeedbackCount()"></textarea>
            <div class="feedback-char-count"><span id="feedbackCharCount">0</span> / 2000</div>

            <!-- 4. Optional Contact -->
            <label for="feedbackContact" style="font-size: 11px; font-weight: 700; color: var(--text-sub); display: block; margin-bottom: 6px; letter-spacing: 0.5px;">
                YOUR NAME OR CONTACT (OPTIONAL)
            </label>
            <input type="text" id="feedbackContact" class="search-input-box" placeholder="Name, Email, or Discord tag (for follow-up)" style="margin-bottom: 14px;">

            <!-- 5. Diagnostics Card (Collapsible) -->
            <div class="diag-card">
                <div class="diag-header" onclick="toggleDiagnosticsView()">
                    <span style="display:flex; align-items:center; gap:6px;">
                        <input type="checkbox" id="includeDiagnostics" checked onclick="event.stopPropagation()">
                        <span>Include Device Diagnostics</span>
                    </span>
                    <span id="diagToggleArrow" style="font-size: 10px;">▼</span>
                </div>
                <div class="diag-content" id="diagDetails" style="display:flex;">
                    <span class="diag-badge">OS: ${diag.os}</span>
                    <span class="diag-badge">Browser: ${diag.browser}</span>
                    <span class="diag-badge">Screen: ${diag.screen}</span>
                    <span class="diag-badge">Mode: ${diag.deviceType}</span>
                </div>
            </div>

            <div id="feedbackError" style="display:none; color:var(--accent-red); font-size:12px; font-weight:600; margin-bottom:12px; text-align:center;"></div>
        </div>

        <!-- Success Screen State -->
        <div id="feedbackSuccessState" style="display:none; padding:36px 24px; text-align:center;">
            <div style="font-size: 52px; margin-bottom: 14px;">✅</div>
            <h3 style="font-size: 20px; font-weight: 800; margin-bottom: 8px;">Thank You!</h3>
            <p id="feedbackSuccessDesc" style="color: var(--text-sub); font-size: 13px; line-height: 1.5; margin-bottom: 24px; max-width: 380px; margin-left: auto; margin-right: auto;">
                Your report has been saved to the host PC's PyShare Feedback folder.
            </p>
            <div id="feedbackGhAction" style="display:none; margin-bottom: 20px;">
                <a id="feedbackGhLink" href="#" target="_blank" class="btn-secondary" style="display:inline-flex; align-items:center; gap:8px; padding:10px 18px; font-size:13px; text-decoration:none; border-radius:12px;">
                    <span>🚀</span> Open on GitHub Issues
                </a>
            </div>
            <button class="btn-primary" onclick="closeFeedbackModal()" style="padding:10px 28px; font-size:13px; border-radius:12px;">
                Done
            </button>
        </div>

        <div class="modal-footer" id="feedbackModalFooter">
            <button class="btn-secondary" onclick="closeFeedbackModal()">Cancel</button>
            <button class="btn-primary" id="btnSubmitFeedback" onclick="submitFeedback()" style="display:flex; align-items:center; gap:6px; padding:10px 22px;">
                <span>Send Feedback</span> <span>🚀</span>
            </button>
        </div>
    </div>
    `;

    document.body.appendChild(modal);
    return modal;
}

// 3. Modal Open / Close Controls
function openFeedbackModal(prefillCategory) {
    const modal = ensureFeedbackModal();
    
    // Reset form states
    document.getElementById('feedbackFormContainer').style.display = 'block';
    document.getElementById('feedbackModalFooter').style.display = 'flex';
    document.getElementById('feedbackSuccessState').style.display = 'none';
    document.getElementById('feedbackError').style.display = 'none';

    const msgBox = document.getElementById('feedbackMsg');
    if (msgBox) {
        msgBox.value = '';
        msgBox.style.borderColor = 'var(--border-color)';
    }
    const countEl = document.getElementById('feedbackCharCount');
    if (countEl) countEl.innerText = '0';

    if (prefillCategory) {
        selectFeedbackCategory(prefillCategory);
    } else {
        selectFeedbackCategory('bug');
    }
    setFeedbackRating(5);

    modal.classList.add('open');
    setTimeout(() => {
        if (msgBox) msgBox.focus();
    }, 150);
}

function closeFeedbackModal() {
    const modal = document.getElementById('feedbackModal');
    if (modal) {
        modal.classList.remove('open');
    }
}

// 4. Category Selector
function selectFeedbackCategory(cat) {
    currentFeedbackCategory = cat;
    ['bug', 'feature', 'question', 'general'].forEach(c => {
        const btn = document.getElementById(`catBtn-${c}`);
        if (btn) {
            if (c === cat) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    });

    const msg = document.getElementById('feedbackMsg');
    if (msg && !msg.value.trim()) {
        if (cat === 'bug') msg.placeholder = 'Describe what went wrong and how to reproduce it...';
        else if (cat === 'feature') msg.placeholder = 'What new feature or improvement would you love to see?';
        else if (cat === 'question') msg.placeholder = 'What question do you have about using PyShare?';
        else msg.placeholder = 'Share any thoughts, ideas, or feedback...';
    }
}

// 5. Rating Stars
function setFeedbackRating(rating) {
    currentFeedbackRating = rating;
    const stars = document.querySelectorAll('#feedbackStarRow .star-btn');
    stars.forEach((s) => {
        const val = parseInt(s.getAttribute('data-rating') || '0', 10);
        if (val <= rating) {
            s.classList.add('active');
        } else {
            s.classList.remove('active');
        }
    });
    const label = document.getElementById('feedbackRatingLabel');
    if (label) {
        label.innerText = `${rating} / 5`;
    }
}

// 6. Character Counter
function updateFeedbackCount() {
    const msg = document.getElementById('feedbackMsg');
    const countEl = document.getElementById('feedbackCharCount');
    if (msg && countEl) {
        countEl.innerText = msg.value.length;
    }
}

// 7. Toggle Diagnostics Preview
function toggleDiagnosticsView() {
    const details = document.getElementById('diagDetails');
    const arrow = document.getElementById('diagToggleArrow');
    if (details) {
        if (details.style.display === 'none') {
            details.style.display = 'flex';
            if (arrow) arrow.innerText = '▼';
        } else {
            details.style.display = 'none';
            if (arrow) arrow.innerText = '▶';
        }
    }
}

// 8. Submit Feedback
async function submitFeedback() {
    if (isSubmittingFeedback) return;

    const msgEl = document.getElementById('feedbackMsg');
    const contactEl = document.getElementById('feedbackContact');
    const diagCheck = document.getElementById('includeDiagnostics');
    const errEl = document.getElementById('feedbackError');
    const submitBtn = document.getElementById('btnSubmitFeedback');

    const message = (msgEl ? msgEl.value : '').trim();

    if (!message) {
        if (errEl) {
            errEl.innerText = 'Please enter a message or problem description.';
            errEl.style.display = 'block';
        }
        if (msgEl) {
            msgEl.style.borderColor = 'var(--accent-red)';
            msgEl.focus();
        }
        return;
    }

    if (errEl) errEl.style.display = 'none';
    isSubmittingFeedback = true;
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Submitting...</span>';
    }

    const contact = (contactEl ? contactEl.value : '').trim();
    const includeDiag = diagCheck ? diagCheck.checked : true;
    const diagnostics = includeDiag ? getDeviceDiagnostics() : {};

    const payload = {
        category: currentFeedbackCategory,
        rating: currentFeedbackRating,
        message: message,
        contact: contact,
        device: diagnostics
    };

    let submittedLocally = false;
    let submittedPublicly = false;

    // 1. Send to local PyShare Host if running
    try {
        const res = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            submittedLocally = true;
        }
    } catch (e) {
        submittedLocally = false;
    }

    // 2. Send to Public Formspree Endpoint (Direct email to developer)
    if (PUBLIC_FEEDBACK_ENDPOINT) {
        try {
            const formspreePayload = {
                category: currentFeedbackCategory.toUpperCase(),
                rating: `${currentFeedbackRating} / 5 ⭐`,
                message: message,
                contact: contact || 'Anonymous',
                _subject: `[PyShare Feedback] ${currentFeedbackCategory.toUpperCase()} (${currentFeedbackRating}/5 ⭐)`,
                os: diagnostics.os || 'Unknown',
                browser: diagnostics.browser || 'Unknown',
                screen: diagnostics.screen || 'Unknown',
                mode: diagnostics.deviceType || 'Web'
            };
            if (contact && contact.includes('@')) {
                formspreePayload._replyto = contact;
                formspreePayload.email = contact;
            }
            const pubRes = await fetch(PUBLIC_FEEDBACK_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(formspreePayload)
            });
            if (pubRes.ok) {
                submittedPublicly = true;
            }
        } catch (err) {
            submittedPublicly = false;
        }
    }

    // Prepare GitHub Issue pre-fill link as direct developer submission option
    const issueTitle = encodeURIComponent(`[${currentFeedbackCategory.toUpperCase()}] ${message.slice(0, 50)}`);
    const diagStr = includeDiag ? ('\n\n### System Diagnostics\n```json\n' + JSON.stringify(diagnostics, null, 2) + '\n```') : '';
    const issueBody = encodeURIComponent(
        `### Category\n${currentFeedbackCategory.toUpperCase()}\n\n` +
        `### Rating\n${currentFeedbackRating} / 5 ⭐\n\n` +
        `### Description\n${message}\n\n` +
        (contact ? `### Contact\n${contact}\n` : '') +
        diagStr
    );
    const ghUrl = `https://github.com/mrpra/PyShare/issues/new?title=${issueTitle}&body=${issueBody}`;

    // Show Success State
    document.getElementById('feedbackFormContainer').style.display = 'none';
    document.getElementById('feedbackModalFooter').style.display = 'none';
    const successBox = document.getElementById('feedbackSuccessState');
    const successDesc = document.getElementById('feedbackSuccessDesc');
    const ghAction = document.getElementById('feedbackGhAction');
    const ghLink = document.getElementById('feedbackGhLink');

    if (submittedPublicly || submittedLocally) {
        if (successDesc) {
            successDesc.innerText = 'Thank you! Your feedback has been sent directly to the PyShare developer.';
        }
        if (ghAction) ghAction.style.display = 'none';
        if (typeof showToast === 'function') {
            showToast('Feedback sent! Thank you 🙏', '💬');
        }
    } else {
        if (successDesc) {
            successDesc.innerText = 'Could not reach the server or internet. You can open an issue on GitHub directly:';
        }
        if (ghAction) ghAction.style.display = 'block';
        if (ghLink) ghLink.href = ghUrl;
        if (typeof showToast === 'function') {
            showToast('Please submit on GitHub Issues', '⚠️');
        }
    }

    if (successBox) successBox.style.display = 'block';

    isSubmittingFeedback = false;
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Send Feedback</span> <span>🚀</span>';
    }
}

// Global Escape Key Listener for Feedback Modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeFeedbackModal();
    }
});

// Window Global Exports
window.openFeedbackModal = openFeedbackModal;
window.closeFeedbackModal = closeFeedbackModal;
window.selectFeedbackCategory = selectFeedbackCategory;
window.setFeedbackRating = setFeedbackRating;
window.submitFeedback = submitFeedback;
