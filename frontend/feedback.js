/* ==========================================================================
   PyShare v4.9.2 - Universal Feedback & Help System
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
                <span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span> Help &amp; Feedback
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
                    <span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="6" width="8" height="14" rx="4"/><path d="M19 9h-2M7 9H5M19 15h-2M7 15H5M16 3l-2 3M8 3l2 3M12 6V3"/></svg></span> Problem / Bug
                </button>
                <button type="button" class="category-chip" id="catBtn-feature" onclick="selectFeedbackCategory('feature')">
                    <span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 22h4"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A7 7 0 1 0 7.5 11.5c.76.76 1.23 1.52 1.41 2.5"/></svg></span> Feature Idea
                </button>
                <button type="button" class="category-chip" id="catBtn-question" onclick="selectFeedbackCategory('question')">
                    <span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span> Question / Help
                </button>
                <button type="button" class="category-chip" id="catBtn-general" onclick="selectFeedbackCategory('general')">
                    <span><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></span> General Feedback
                </button>
            </div>

            <!-- 2. Star Rating -->
            <label style="font-size: 11px; font-weight: 700; color: var(--text-sub); display: block; margin-bottom: 6px; letter-spacing: 0.5px;">
                RATE YOUR EXPERIENCE
            </label>
            <div class="star-rating-row" id="feedbackStarRow">
                <button type="button" class="star-btn active" data-rating="1" onclick="setFeedbackRating(1)" title="1 Star"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
                <button type="button" class="star-btn active" data-rating="2" onclick="setFeedbackRating(2)" title="2 Stars"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
                <button type="button" class="star-btn active" data-rating="3" onclick="setFeedbackRating(3)" title="3 Stars"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
                <button type="button" class="star-btn active" data-rating="4" onclick="setFeedbackRating(4)" title="4 Stars"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
                <button type="button" class="star-btn active" data-rating="5" onclick="setFeedbackRating(5)" title="5 Stars"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></button>
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
            <div style="margin-bottom: 14px;"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#00e676" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>
            <h3 style="font-size: 20px; font-weight: 800; margin-bottom: 8px;">Thank You!</h3>
            <p id="feedbackSuccessDesc" style="color: var(--text-sub); font-size: 13px; line-height: 1.5; margin-bottom: 24px; max-width: 380px; margin-left: auto; margin-right: auto;">
                Your report has been saved to the host PC's PyShare Feedback folder.
            </p>
            <div id="feedbackGhAction" style="display:none; margin-bottom: 20px;">
                <a id="feedbackGhLink" href="#" target="_blank" class="btn-secondary" style="display:inline-flex; align-items:center; gap:8px; padding:10px 18px; font-size:13px; text-decoration:none; border-radius:12px;">
                    <span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg></span> Open on GitHub Issues
                </a>
            </div>
            <button class="btn-primary" onclick="closeFeedbackModal()" style="padding:10px 28px; font-size:13px; border-radius:12px;">
                Done
            </button>
        </div>

        <div class="modal-footer" id="feedbackModalFooter">
            <button class="btn-secondary" onclick="closeFeedbackModal()">Cancel</button>
            <button class="btn-primary" id="btnSubmitFeedback" onclick="submitFeedback()" style="display:flex; align-items:center; gap:6px; padding:10px 22px;">
                <span>Send Feedback</span> <span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg></span>
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
            if (arrow) arrow.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
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

    let submitted = false;

    // Send directly to Public Formspree Endpoint (Delivered to developer inbox)
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
                submitted = true;
            }
        } catch (err) {
            submitted = false;
        }
    }

    // Prepare GitHub Issue pre-fill link as fallback if offline
    const issueTitle = encodeURIComponent(`[${currentFeedbackCategory.toUpperCase()}] ${message.slice(0, 50)}`);
    const diagStr = includeDiag ? ('\n\n### System Diagnostics\n```json\n' + JSON.stringify(diagnostics, null, 2) + '\n```') : '';
    const issueBody = encodeURIComponent(
        `### Category\n${currentFeedbackCategory.toUpperCase()}\n\n` +
        `### Rating\n${currentFeedbackRating} / 5 ⭐\n\n` +
        `### Description\n${message}\n\n` +
        (contact ? `### Contact\n${contact}\n` : '') +
        diagStr
    );
    const ghUrl = `https://github.com/pattanayakpratik/PyShare/issues/new?title=${issueTitle}&body=${issueBody}`;

    // Show Success State
    document.getElementById('feedbackFormContainer').style.display = 'none';
    document.getElementById('feedbackModalFooter').style.display = 'none';
    const successBox = document.getElementById('feedbackSuccessState');
    const successDesc = document.getElementById('feedbackSuccessDesc');
    const ghAction = document.getElementById('feedbackGhAction');
    const ghLink = document.getElementById('feedbackGhLink');

    if (submitted) {
        if (successDesc) {
            successDesc.innerText = 'Thank you! Your feedback has been sent directly to the PyShare developer.';
        }
        if (ghAction) ghAction.style.display = 'none';
        if (typeof showToast === 'function') {
            showToast('Feedback sent! Thank you 🙏', '💬');
        }
    } else {
        if (successDesc) {
            successDesc.innerText = 'Could not reach the feedback service. Please check your internet connection or open an issue on GitHub directly:';
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
        submitBtn.innerHTML = '<span>Send Feedback</span> <span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg></span>';
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


/* ==========================================================================
   PyShare Universal In-App Confirmation & Alert Modal
   Replaces ugly browser/webview "127.0.0.1:8010 says" with branded Cyberpunk Glass
   ========================================================================== */
function showPyShareConfirm({
    title = 'PyShare',
    message = 'Are you sure?',
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    isDanger = false,
    onConfirm = null,
    onCancel = null
} = {}) {
    return new Promise((resolve) => {
        let modal = document.getElementById('pyshareConfirmModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'pyshareConfirmModal';
            modal.className = 'modal-backdrop';
            modal.style.zIndex = '10005';
            modal.innerHTML = `
                <div class="modal-box" style="max-width: 440px; padding: 0; border-radius: 20px; overflow: hidden; box-shadow: 0 16px 48px rgba(0,0,0,0.6);">
                    <div class="modal-header" style="padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-color);">
                        <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; color: var(--text-main);">
                            <img src="app_icon.png" alt="PyShare" style="width: 22px; height: 22px; border-radius: 5px; object-fit: contain;">
                            <span id="pyshareConfirmTitle">PyShare</span>
                        </div>
                        <button type="button" class="action-circle-btn" id="pyshareConfirmCloseBtn" style="width: 28px; height: 28px; font-size: 12px; cursor: pointer;">✕</button>
                    </div>
                    <div style="padding: 22px 20px; color: var(--text-sub); font-size: 14px; line-height: 1.5;" id="pyshareConfirmMessage">
                    </div>
                    <div class="modal-footer" style="padding: 14px 20px; display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--border-color); background: rgba(0, 0, 0, 0.15);">
                        <button type="button" class="btn-secondary" id="pyshareConfirmCancelBtn" style="padding: 8px 18px; font-size: 13px; font-weight: 600; border-radius: 10px; cursor: pointer;">Cancel</button>
                        <button type="button" class="btn-primary" id="pyshareConfirmOkBtn" style="padding: 8px 20px; font-size: 13px; font-weight: 700; border-radius: 10px; cursor: pointer;">Confirm</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        const titleEl = document.getElementById('pyshareConfirmTitle');
        const msgEl = document.getElementById('pyshareConfirmMessage');
        const okBtn = document.getElementById('pyshareConfirmOkBtn');
        const cancelBtn = document.getElementById('pyshareConfirmCancelBtn');
        const closeBtn = document.getElementById('pyshareConfirmCloseBtn');

        titleEl.innerText = title || 'PyShare';
        msgEl.innerText = message || '';
        okBtn.innerText = confirmText || 'Confirm';

        if (cancelText) {
            cancelBtn.style.display = 'inline-block';
            cancelBtn.innerText = cancelText;
        } else {
            cancelBtn.style.display = 'none';
        }

        if (isDanger) {
            okBtn.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
            okBtn.style.color = '#ffffff';
            okBtn.style.boxShadow = '0 0 16px rgba(239, 68, 68, 0.4)';
            okBtn.style.border = 'none';
        } else {
            okBtn.style.background = '';
            okBtn.style.color = '';
            okBtn.style.boxShadow = '';
            okBtn.style.border = '';
        }

        const close = (result) => {
            modal.classList.remove('open');
            modal.style.display = 'none';
            cleanup();
            if (result) {
                if (typeof onConfirm === 'function') onConfirm();
                resolve(true);
            } else {
                if (typeof onCancel === 'function') onCancel();
                resolve(false);
            }
        };

        const onOk = () => close(true);
        const onCancelClick = () => close(false);
        const onKeyDown = (e) => {
            if (modal.style.display === 'flex') {
                if (e.key === 'Escape') {
                    e.stopPropagation();
                    close(false);
                } else if (e.key === 'Enter') {
                    e.stopPropagation();
                    close(true);
                }
            }
        };
        const onBackdrop = (e) => {
            if (e.target === modal) close(false);
        };

        function cleanup() {
            okBtn.removeEventListener('click', onOk);
            cancelBtn.removeEventListener('click', onCancelClick);
            closeBtn.removeEventListener('click', onCancelClick);
            document.removeEventListener('keydown', onKeyDown);
            modal.removeEventListener('click', onBackdrop);
        }

        okBtn.addEventListener('click', onOk);
        cancelBtn.addEventListener('click', onCancelClick);
        closeBtn.addEventListener('click', onCancelClick);
        document.addEventListener('keydown', onKeyDown);
        modal.addEventListener('click', onBackdrop);

        modal.style.display = 'flex';
        modal.classList.add('open');
        okBtn.focus();
    });
}

function showPyShareAlert(message, title = 'PyShare') {
    return showPyShareConfirm({
        title: title,
        message: message,
        confirmText: 'OK',
        cancelText: ''
    });
}

function showPySharePrompt({
    title = 'PyShare',
    message = 'Enter value:',
    defaultValue = '',
    placeholder = 'Type here...',
    confirmText = 'Save',
    cancelText = 'Cancel',
    maxLength = 32
} = {}) {
    return new Promise((resolve) => {
        let modal = document.getElementById('pysharePromptModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'pysharePromptModal';
            modal.className = 'modal-backdrop';
            modal.style.zIndex = '10006';
            modal.innerHTML = `
                <div class="modal-box" style="max-width: 420px; padding: 0; border-radius: 20px; overflow: hidden; box-shadow: 0 16px 48px rgba(0,0,0,0.6);">
                    <div class="modal-header" style="padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-color);">
                        <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px; color: var(--text-main);">
                            <img src="app_icon.png" alt="PyShare" style="width: 22px; height: 22px; border-radius: 5px; object-fit: contain;">
                            <span id="pysharePromptTitle">PyShare</span>
                        </div>
                        <button type="button" class="action-circle-btn" id="pysharePromptCloseBtn" style="width: 28px; height: 28px; font-size: 12px; cursor: pointer;" aria-label="Close">✕</button>
                    </div>
                    <form id="pysharePromptForm" onsubmit="event.preventDefault();" style="margin: 0; padding: 0;">
                        <div style="padding: 20px; display:flex; flex-direction:column; gap:12px;">
                            <label id="pysharePromptMessage" style="color: var(--text-sub); font-size: 13px; line-height: 1.4;"></label>
                            <input type="text" id="pysharePromptInput" class="search-input-box" style="margin: 0; width: 100%; box-sizing: border-box; font-size: 14px;" />
                        </div>
                        <div class="modal-footer" style="padding: 14px 20px; display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid var(--border-color); background: rgba(0, 0, 0, 0.15);">
                            <button type="button" class="btn-secondary" id="pysharePromptCancelBtn" style="padding: 8px 18px; font-size: 13px; font-weight: 600; border-radius: 10px; cursor: pointer;">Cancel</button>
                            <button type="submit" class="btn-primary" id="pysharePromptOkBtn" style="padding: 8px 20px; font-size: 13px; font-weight: 700; border-radius: 10px; cursor: pointer;">Save</button>
                        </div>
                    </form>
                </div>
            `;
            document.body.appendChild(modal);
        }

        const titleEl = document.getElementById('pysharePromptTitle');
        const msgEl = document.getElementById('pysharePromptMessage');
        const inputEl = document.getElementById('pysharePromptInput');
        const okBtn = document.getElementById('pysharePromptOkBtn');
        const cancelBtn = document.getElementById('pysharePromptCancelBtn');
        const closeBtn = document.getElementById('pysharePromptCloseBtn');
        const formEl = document.getElementById('pysharePromptForm');

        if (titleEl) titleEl.innerText = title;
        if (msgEl) msgEl.innerText = message;
        if (inputEl) {
            inputEl.value = defaultValue || '';
            inputEl.placeholder = placeholder || '';
            inputEl.maxLength = maxLength;
        }
        if (okBtn) okBtn.innerText = confirmText;
        if (cancelBtn) cancelBtn.innerText = cancelText;

        let closed = false;
        function close(result) {
            if (closed) return;
            closed = true;
            modal.style.display = 'none';
            modal.classList.remove('open');
            cleanup();
            resolve(result);
        }

        const onOk = (e) => {
            if (e) e.preventDefault();
            const val = inputEl ? inputEl.value.trim() : '';
            close(val);
        };
        const onCancelClick = () => close(null);
        const onKeyDown = (e) => {
            if (e.key === 'Escape') close(null);
        };
        const onBackdrop = (e) => {
            if (e.target === modal) close(null);
        };

        function cleanup() {
            if (formEl) formEl.removeEventListener('submit', onOk);
            if (okBtn) okBtn.removeEventListener('click', onOk);
            if (cancelBtn) cancelBtn.removeEventListener('click', onCancelClick);
            if (closeBtn) closeBtn.removeEventListener('click', onCancelClick);
            document.removeEventListener('keydown', onKeyDown);
            modal.removeEventListener('click', onBackdrop);
        }

        if (formEl) formEl.addEventListener('submit', onOk);
        if (okBtn) okBtn.addEventListener('click', onOk);
        if (cancelBtn) cancelBtn.addEventListener('click', onCancelClick);
        if (closeBtn) closeBtn.addEventListener('click', onCancelClick);
        document.addEventListener('keydown', onKeyDown);
        modal.addEventListener('click', onBackdrop);

        modal.style.display = 'flex';
        modal.classList.add('open');
        setTimeout(() => {
            if (inputEl) {
                inputEl.focus();
                inputEl.select();
            }
        }, 50);
    });
}

window.showPyShareConfirm = showPyShareConfirm;
window.showPyShareAlert = showPyShareAlert;
window.showPySharePrompt = showPySharePrompt;

// --- Universal Navbar Menu Dropdown Controller ---
function toggleNavMenu(e) {
    if (e) {
        if (typeof e.stopPropagation === 'function') e.stopPropagation();
        if (typeof e.preventDefault === 'function') e.preventDefault();
    }
    const menu = document.getElementById('navDropdownMenu');
    if (!menu) return;
    menu.classList.toggle('open');
}

function closeNavMenu() {
    const menu = document.getElementById('navDropdownMenu');
    if (menu) menu.classList.remove('open');
}

document.addEventListener('click', (e) => {
    const menu = document.getElementById('navDropdownMenu');
    const btn = document.getElementById('navMenuBtn');
    if (menu && menu.classList.contains('open')) {
        if (!menu.contains(e.target) && (!btn || !btn.contains(e.target))) {
            menu.classList.remove('open');
        }
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeNavMenu();
    }
});

window.toggleNavMenu = toggleNavMenu;
window.closeNavMenu = closeNavMenu;

// ==========================================================================
// In-App Update Checker & Release Modal
// ==========================================================================

function ensureUpdateModal(data) {
    let modal = document.getElementById('updateModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'updateModal';
        modal.className = 'modal-backdrop';
        modal.onclick = (e) => {
            if (e.target === modal) closeUpdateModal();
        };
        document.body.appendChild(modal);
    }

    const currentV = data.current_version || '4.9.2';
    const latestV = data.latest_version || currentV;
    const releaseUrl = data.release_url || 'https://github.com/pattanayakpratik/PyShare/releases';
    const rawNotes = data.release_notes || 'A new updated version of PyShare is available for download with new features and performance enhancements.';
    const notes = String(rawNotes).replace(/</g, '&lt;').replace(/>/g, '&gt;');

    modal.innerHTML = `
        <div class="modal-box" style="max-width: 480px; text-align: left;" onclick="event.stopPropagation()">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:24px;">🚀</span>
                    <div>
                        <h3 style="margin:0; font-size:18px; font-weight:700; color:var(--text-main);">New Update Available</h3>
                        <span style="font-size:12px; color:var(--accent-cyan); font-weight:600;">v${latestV} &bull; Current: v${currentV}</span>
                    </div>
                </div>
                <button onclick="closeUpdateModal()" class="icon-btn" style="border:none; background:transparent; cursor:pointer;" aria-label="Close">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>

            <div style="background:var(--card-bg-subtle, rgba(0,0,0,0.25)); border:1px solid var(--border-color); border-radius:12px; padding:12px 14px; font-size:13px; color:var(--text-muted); max-height:160px; overflow-y:auto; line-height:1.5; white-space:pre-wrap; margin-bottom:18px;">
${notes}
            </div>

            <div style="display:flex; gap:10px; justify-content:flex-end;">
                <button type="button" class="btn-secondary" onclick="closeUpdateModal()" style="padding:10px 16px; border-radius:12px; font-size:13px;">Later</button>
                <a href="${releaseUrl}" target="_blank" rel="noopener noreferrer" class="btn-primary" style="display:inline-flex; align-items:center; gap:6px; padding:10px 18px; border-radius:12px; font-size:13px; text-decoration:none; font-weight:600;" onclick="closeUpdateModal()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    <span>Download Installer</span>
                </a>
            </div>
        </div>
    `;

    modal.classList.add('open');
}

function closeUpdateModal() {
    const modal = document.getElementById('updateModal');
    if (modal) modal.classList.remove('open');
}

async function checkForUpdates(manual = false) {
    try {
        const resp = await fetch('/api/check_update');
        if (!resp.ok) {
            if (manual) {
                if (typeof showToast === 'function') showToast('Could not reach update server', '⚠️');
                else alert('Could not check for updates');
            }
            return;
        }
        const data = await resp.json();
        if (data && data.has_update) {
            const badge = document.getElementById('navUpdateBadge');
            if (badge) badge.style.display = 'inline-block';
            ensureUpdateModal(data);
        } else if (manual) {
            const msg = `PyShare is up to date (v${data.current_version || '4.9.2'}) ✓`;
            if (typeof showToast === 'function') showToast(msg, '✅');
            else alert(msg);
        }
    } catch (e) {
        if (manual) {
            if (typeof showToast === 'function') showToast('Network error checking updates', '⚠️');
            else alert('Network error checking updates');
        }
    }
}

// Register globals & auto-check silently on startup
if (typeof window !== 'undefined') {
    window.checkForUpdates = checkForUpdates;
    window.closeUpdateModal = closeUpdateModal;
    setTimeout(() => {
        checkForUpdates(false);
    }, 3000);
}


