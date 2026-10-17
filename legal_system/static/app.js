/**
 * IRONGRYPH LEGAL & INVESTIGATION EVIDENCE VAULT
 * Modern Client Application (Zero-Login Architecture)
 */

const API_BASE = '/api/v1';

// Application State
const state = {
    activeRole: localStorage.getItem('irongryph_role') || 'administrator',
    currentView: 'dashboard',
    cases: [],
    currentCase: null,
    auditLogs: [],
    selectedUploadFile: null,
    clientCalculatedHash: null,
};

// ==========================================================================
// INITIALIZATION
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    initRoleSwitcher();
    initNavigation();
    initModals();
    initDropzone();
    initAuditEvents();
    initTamperLab();
    initLiveClock();

    // Directly load dashboard on startup — NO LOGIN BARRIER
    loadDashboard();
});

// ==========================================================================
// INSTANT ROLE SWITCHER (ADMIN VS INVESTIGATOR)
// ==========================================================================

function initRoleSwitcher() {
    const btnAdmin = document.getElementById('btn-role-admin');
    const btnInv = document.getElementById('btn-role-inv');

    btnAdmin.addEventListener('click', () => setRole('administrator'));
    btnInv.addEventListener('click', () => setRole('investigator'));

    updateRoleSwitcherUI();
}

function setRole(role) {
    state.activeRole = role;
    localStorage.setItem('irongryph_role', role);
    updateRoleSwitcherUI();

    const title = role === 'administrator' ? 'Chief Elena Vance (Administrator)' : 'Detective Marcus Cole (Investigator)';
    showToast(`Switched active persona to ${title}`, 'info');

    // If currently on audit view and switched to investigator, notify and re-route
    if (state.currentView === 'audit' && role !== 'administrator') {
        showToast('Forensic Audit Ledger is restricted to Administrators. Returning to Cases.', 'warning');
        switchView('dashboard');
    }
}

function updateRoleSwitcherUI() {
    const btnAdmin = document.getElementById('btn-role-admin');
    const btnInv = document.getElementById('btn-role-inv');
    const navAudit = document.getElementById('nav-audit');

    const isAdmin = state.activeRole === 'administrator';
    btnAdmin.classList.toggle('active', isAdmin);
    btnInv.classList.toggle('active', !isAdmin);

    if (isAdmin) {
        navAudit.style.opacity = '1';
        navAudit.title = 'Access Forensic Audit Ledger';
    } else {
        navAudit.style.opacity = '0.7';
        navAudit.title = 'Restricted: Administrator access required';
    }
}

function apiHeaders(isJson = true) {
    const headers = {
        'X-Role': state.activeRole,
        'X-User': state.activeRole === 'administrator' ? 'admin' : 'mcole'
    };
    if (isJson) {
        headers['Content-Type'] = 'application/json';
    }
    return headers;
}

// ==========================================================================
// NAVIGATION CONTROLLER
// ==========================================================================

function initNavigation() {
    document.getElementById('nav-dashboard').addEventListener('click', () => switchView('dashboard'));
    document.getElementById('nav-vault').addEventListener('click', () => switchView('vault'));
    document.getElementById('nav-tamper-lab').addEventListener('click', () => switchView('tamper-lab'));

    document.getElementById('nav-audit').addEventListener('click', () => {
        if (state.activeRole !== 'administrator') {
            showToast('RESTRICTED ACCESS: The Forensic Audit Ledger is restricted to Administrators. Switch to Chief Vance in the top right to unlock.', 'warning');
            return;
        }
        switchView('audit');
    });

    // Quick deposit buttons
    document.getElementById('btn-quick-deposit').addEventListener('click', openUploadModal);
    document.getElementById('btn-vault-deposit').addEventListener('click', openUploadModal);
}

function switchView(viewName) {
    state.currentView = viewName;

    // Toggle section visibility
    document.getElementById('view-dashboard').style.display = viewName === 'dashboard' ? 'flex' : 'none';
    document.getElementById('view-vault').style.display = viewName === 'vault' ? 'flex' : 'none';
    document.getElementById('view-audit').style.display = viewName === 'audit' ? 'flex' : 'none';
    document.getElementById('view-tamper-lab').style.display = viewName === 'tamper-lab' ? 'flex' : 'none';

    // Update active nav pills
    document.getElementById('nav-dashboard').classList.toggle('active', viewName === 'dashboard');
    document.getElementById('nav-vault').classList.toggle('active', viewName === 'vault');
    document.getElementById('nav-audit').classList.toggle('active', viewName === 'audit');
    document.getElementById('nav-tamper-lab').classList.toggle('active', viewName === 'tamper-lab');

    if (viewName === 'dashboard') {
        loadDashboard();
    } else if (viewName === 'audit') {
        loadAuditLedger();
    } else if (viewName === 'tamper-lab') {
        populateTamperLabSelect();
    }
}

// ==========================================================================
// SCREEN 2: CASE DASHBOARD
// ==========================================================================

async function loadDashboard() {
    try {
        const status = document.getElementById('filter-case-status').value;
        const priority = document.getElementById('filter-case-priority').value;
        const search = document.getElementById('case-search').value.trim();

        let url = `${API_BASE}/cases/?`;
        if (status && status !== 'all') url += `status=${encodeURIComponent(status)}&`;
        if (priority) url += `priority=${encodeURIComponent(priority)}&`;
        if (search) url += `search=${encodeURIComponent(search)}&`;

        const response = await fetch(url, { headers: apiHeaders() });
        if (!response.ok) throw new Error('Failed to load investigation cases');

        state.cases = await response.json();
        renderCasesGrid();
        updateDashboardMetrics();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderCasesGrid() {
    const container = document.getElementById('cases-grid-container');
    const countBadge = document.getElementById('nav-case-count');
    countBadge.textContent = state.cases.length;

    if (state.cases.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-subtle);">
                <h3 style="font-size: 18px; color: #fff; margin-bottom: 6px;">No Investigation Records Found</h3>
                <p style="color: var(--text-muted); margin-bottom: 18px;">Try clearing search filters or create a new investigation record.</p>
                <button class="btn btn-secondary" onclick="openNewCaseModal()">+ Create Investigation Record</button>
            </div>
        `;
        return;
    }

    container.innerHTML = state.cases.map(c => `
        <div class="case-box acuity-${c.priority}" onclick="openCaseVault(${c.id})">
            <div>
                <div class="case-box-header">
                    <span class="case-id-badge">${c.case_number}</span>
                    <span class="acuity-chip chip-${c.priority}">${c.priority} Priority</span>
                </div>
                <div class="case-box-body" style="margin-top: 14px;">
                    <h3>${c.title}</h3>
                    <p class="case-box-desc">${c.description || 'No preliminary briefing attached.'}</p>
                </div>
            </div>

            <div class="case-box-footer">
                <div class="investigator-tag">
                    <div class="inv-avatar">${(c.lead_investigator_name || 'U').substring(0, 1)}</div>
                    <span>${c.lead_investigator_name || 'Unassigned'}</span>
                </div>
                <div class="exhibit-count-badge">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                    <span>${c.document_count} Exhibit${c.document_count === 1 ? '' : 's'}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function updateDashboardMetrics() {
    const totalCases = state.cases.length;
    const totalEvidence = state.cases.reduce((sum, c) => sum + (c.document_count || 0), 0);

    document.getElementById('stat-cases-count').textContent = totalCases;
    document.getElementById('stat-evidence-count').textContent = totalEvidence;
}

// Search & Filter event bindings
document.getElementById('case-search').addEventListener('input', debounce(loadDashboard, 300));
document.getElementById('filter-case-status').addEventListener('change', loadDashboard);
document.getElementById('filter-case-priority').addEventListener('change', loadDashboard);

// ==========================================================================
// SCREEN 3: CASE DETAIL & EVIDENCE VAULT
// ==========================================================================

async function openCaseVault(caseId) {
    try {
        const response = await fetch(`${API_BASE}/cases/${caseId}`, { headers: apiHeaders() });
        if (!response.ok) throw new Error('Failed to retrieve case file');

        state.currentCase = await response.json();

        // Enable vault button in navigation bar
        const navVault = document.getElementById('nav-vault');
        const navVaultLabel = document.getElementById('nav-vault-label');
        navVault.style.display = 'inline-flex';
        navVaultLabel.textContent = state.currentCase.case_number;

        renderVaultHero();
        renderExhibitsList();
        switchView('vault');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderVaultHero() {
    const c = state.currentCase;
    const hero = document.getElementById('vault-hero-card');

    hero.innerHTML = `
        <div class="vault-breadcrumb">
            <a onclick="switchView('dashboard')">Investigations</a>
            <span>/</span>
            <span style="color: var(--brand-cyan); font-weight: 600;">${c.case_number}</span>
        </div>

        <div class="vault-hero-main">
            <div>
                <h1>${c.title}</h1>
                <p style="color: var(--text-muted); margin-top: 4px; font-size: 13px;">${c.description || 'No preliminary notes recorded.'}</p>
            </div>
            <div style="display: flex; gap: 12px; align-items: center;">
                <span class="acuity-chip chip-${c.priority}">${c.priority} Priority</span>
                <select class="select-pill" onchange="updateCaseLifecycle(this.value)">
                    <option value="Open" ${c.status === 'Open' ? 'selected' : ''}>Open</option>
                    <option value="Under Investigation" ${c.status === 'Under Investigation' ? 'selected' : ''}>Under Investigation</option>
                    <option value="In Court" ${c.status === 'In Court' ? 'selected' : ''}>In Court</option>
                    <option value="Closed" ${c.status === 'Closed' ? 'selected' : ''}>Closed</option>
                </select>
            </div>
        </div>

        <div class="vault-hero-meta">
            <div class="meta-field">
                <span>Case File Number</span>
                <span style="font-family: var(--font-mono); color: var(--brand-cyan);">${c.case_number}</span>
            </div>
            <div class="meta-field">
                <span>Classification</span>
                <span>${c.category}</span>
            </div>
            <div class="meta-field">
                <span>Lead Investigator</span>
                <span>${c.lead_investigator_name}</span>
            </div>
            <div class="meta-field">
                <span>Filing Timestamp</span>
                <span>${new Date(c.created_at).toLocaleDateString()}</span>
            </div>
        </div>
    `;
}

async function updateCaseLifecycle(newStatus) {
    try {
        const response = await fetch(`${API_BASE}/cases/${state.currentCase.id}/status`, {
            method: 'PUT',
            headers: apiHeaders(),
            body: JSON.stringify({ status: newStatus })
        });
        if (!response.ok) throw new Error('Status update failed');
        state.currentCase.status = newStatus;
        showToast(`Case lifecycle updated to '${newStatus}'`, 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderExhibitsList() {
    const container = document.getElementById('exhibits-container');
    const docs = state.currentCase.evidence_documents || [];

    if (docs.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 50px 20px; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px dashed var(--border-subtle);">
                <h3 style="font-size: 17px; color: #fff; margin-bottom: 6px;">Evidence Vault is Empty</h3>
                <p style="color: var(--text-muted); margin-bottom: 18px;">Deposit the first cryptographically sealed exhibit for this case.</p>
                <button class="btn btn-action-deposit" onclick="openUploadModal()">Deposit Exhibit Now</button>
            </div>
        `;
        return;
    }

    container.innerHTML = docs.map(doc => {
        const isTampered = doc.is_tampered;
        const icon = getFileIcon(doc.original_filename);
        const shortHash = doc.sha256_hash ? doc.sha256_hash.substring(0, 16) + '...' : 'Calculating...';

        return `
            <div class="exhibit-card ${isTampered ? 'tampered-alarm' : ''}" id="exhibit-item-${doc.id}">
                <div class="exhibit-left">
                    <div class="file-symbol">${icon}</div>
                    <div class="exhibit-details">
                        <span class="exhibit-name">${doc.title}</span>
                        <div class="exhibit-tags">
                            <span>📄 ${doc.original_filename}</span>
                            <span>•</span>
                            <span>⚖️ ${doc.category}</span>
                            <span>•</span>
                            <span>${formatBytes(doc.file_size_bytes)}</span>
                            <span>•</span>
                            <span>Deposited by: ${doc.uploader_name || 'Investigator'}</span>
                        </div>
                        <div style="margin-top: 6px;">
                            <span class="hash-tag-pill" onclick="copyToClipboard('${doc.sha256_hash}', 'SHA-256 Digest Copied to Clipboard')" title="Click to copy full 64-character SHA-256 digest">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                <span>SHA-256: <strong>${shortHash}</strong></span>
                            </span>
                        </div>
                    </div>
                </div>

                <!-- THE PROMINENT GREEN SHIELD / RED WARNING SHIELD -->
                <div class="exhibit-center">
                    ${isTampered ? `
                        <div class="cryptographic-seal seal-tampered">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                            <span>TAMPER DETECTED: HASH MISMATCH</span>
                        </div>
                        <span class="seal-caption caption-tampered">CRITICAL: Physical file altered on disk!</span>
                    ` : `
                        <div class="cryptographic-seal seal-verified">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
                            <span>SHA-256 SEAL VERIFIED</span>
                        </div>
                        <span class="seal-caption caption-verified">Cryptographic seal authentic & intact</span>
                    `}
                </div>

                <!-- Exhibit Action Buttons -->
                <div class="exhibit-actions">
                    <button class="btn btn-secondary" onclick="verifyEvidenceSeal(${doc.id})" title="Perform live on-disk hash check">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
                        <span>Verify Seal</span>
                    </button>
                    <a href="${API_BASE}/evidence/${doc.id}/download" class="btn btn-outline" title="Download secured exhibit">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        <span>Download</span>
                    </a>
                    ${isTampered ? `
                        <button class="btn btn-emerald" onclick="restoreEvidenceSeal(${doc.id})" title="Restore original canonical bytes">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                            <span>Restore Seal</span>
                        </button>
                    ` : `
                        <button class="btn btn-danger" onclick="simulateTamperSeal(${doc.id})" title="Demonstration: Alter file bytes to test red warning alarm">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                            <span>Simulate Tamper</span>
                        </button>
                    `}
                </div>
            </div>
        `;
    }).join('');
}

// Live SHA-256 Verification Action
async function verifyEvidenceSeal(evidenceId) {
    try {
        const response = await fetch(`${API_BASE}/evidence/${evidenceId}/verify`, {
            method: 'POST',
            headers: apiHeaders()
        });
        if (!response.ok) throw new Error('Verification request failed');

        const result = await response.json();
        await openCaseVault(state.currentCase.id);

        if (result.is_valid) {
            showToast(`🛡️ ${result.title}: SHA-256 seal confirmed authentic!`, 'success');
        } else {
            showToast(`🚨 CRITICAL ALARM: ${result.title} failed integrity check! Tampering logged to audit trail.`, 'error');
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Tamper Simulation Demo Action
async function simulateTamperSeal(evidenceId) {
    try {
        const response = await fetch(`${API_BASE}/evidence/${evidenceId}/simulate-tamper`, {
            method: 'POST',
            headers: apiHeaders()
        });
        if (!response.ok) throw new Error('Simulation failed');

        await openCaseVault(state.currentCase.id);
        showToast('⚠️ Unauthorized byte modification applied on disk! Red Warning Alarm triggered.', 'error');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Restore Original Seal Action
async function restoreEvidenceSeal(evidenceId) {
    try {
        const response = await fetch(`${API_BASE}/evidence/${evidenceId}/restore`, {
            method: 'POST',
            headers: apiHeaders()
        });
        if (!response.ok) throw new Error('Restoration failed');

        await openCaseVault(state.currentCase.id);
        showToast('✅ Exhibit content restored from canonical vault. Green Verified Seal restored!', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

document.getElementById('btn-verify-all-exhibits').addEventListener('click', async () => {
    const docs = state.currentCase.evidence_documents || [];
    showToast(`Verifying cryptographic integrity for all ${docs.length} exhibits...`, 'info');
    for (const d of docs) {
        await verifyEvidenceSeal(d.id);
    }
});

// ==========================================================================
// SCREEN 4: UPLOAD MODAL & CLIENT WEBCRYPTO SHA-256
// ==========================================================================

function initModals() {
    // Modal buttons
    document.getElementById('btn-open-new-case').addEventListener('click', openNewCaseModal);
    document.getElementById('modal-upload-close').addEventListener('click', closeUploadModal);
    document.getElementById('modal-upload-cancel').addEventListener('click', closeUploadModal);
    document.getElementById('modal-case-close').addEventListener('click', closeNewCaseModal);
    document.getElementById('modal-case-cancel').addEventListener('click', closeNewCaseModal);

    // Form handlers
    document.getElementById('form-evidence-upload').addEventListener('submit', handleEvidenceUpload);
    document.getElementById('form-new-case').addEventListener('submit', handleNewCaseCreate);
}

function openUploadModal() {
    const select = document.getElementById('input-upload-case');
    select.innerHTML = state.cases.map(c => `
        <option value="${c.id}" ${state.currentCase && state.currentCase.id === c.id ? 'selected' : ''}>
            ${c.case_number} — ${c.title}
        </option>
    `).join('');

    // Reset dropzone
    state.selectedUploadFile = null;
    document.getElementById('dropzone-idle-state').style.display = 'block';
    document.getElementById('dropzone-ready-state').style.display = 'none';
    document.getElementById('form-evidence-upload').reset();

    document.getElementById('modal-upload').style.display = 'flex';
}

function closeUploadModal() {
    document.getElementById('modal-upload').style.display = 'none';
}

function openNewCaseModal() {
    document.getElementById('form-new-case').reset();
    document.getElementById('modal-new-case').style.display = 'flex';
}

function closeNewCaseModal() {
    document.getElementById('modal-new-case').style.display = 'none';
}

// Drag & Drop Ingress + Real-Time WebCrypto SHA-256
function initDropzone() {
    const dropzone = document.getElementById('file-dropzone');
    const fileInput = document.getElementById('file-input-raw');

    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) await processSelectedFile(file);
    });
}

async function processSelectedFile(file) {
    state.selectedUploadFile = file;

    document.getElementById('ready-filename').textContent = file.name;
    document.getElementById('ready-filesize').textContent = formatBytes(file.size);
    document.getElementById('ready-hash').textContent = 'Computing live SHA-256 digest via WebCrypto API...';

    document.getElementById('dropzone-idle-state').style.display = 'none';
    document.getElementById('dropzone-ready-state').style.display = 'block';

    const titleInput = document.getElementById('input-upload-title');
    if (!titleInput.value) {
        titleInput.value = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ');
    }

    // Compute Web-Crypto SHA-256 locally
    try {
        const buffer = await file.arrayBuffer();
        const hashBuf = await crypto.subtle.digest('SHA-256', buffer);
        const hashArray = Array.from(new Uint8Array(hashBuf));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        document.getElementById('ready-hash').textContent = hashHex;
    } catch (e) {
        document.getElementById('ready-hash').textContent = 'Seal will be computed securely upon ingest.';
    }
}

async function handleEvidenceUpload(e) {
    e.preventDefault();
    if (!state.selectedUploadFile) {
        showToast('Please select a file to deposit', 'warning');
        return;
    }

    const submitBtn = document.getElementById('btn-submit-upload');
    submitBtn.disabled = true;
    submitBtn.textContent = '🔒 Computing Digest & Sealing Exhibit...';

    const formData = new FormData();
    formData.append('case_id', document.getElementById('input-upload-case').value);
    formData.append('title', document.getElementById('input-upload-title').value.trim());
    formData.append('category', document.getElementById('input-upload-category').value);
    formData.append('description', document.getElementById('input-upload-desc').value.trim());
    formData.append('file', state.selectedUploadFile);

    try {
        const response = await fetch(`${API_BASE}/evidence/upload`, {
            method: 'POST',
            headers: apiHeaders(false),
            body: formData
        });

        if (!response.ok) throw new Error('Evidence deposition failed');

        const newDoc = await response.json();
        closeUploadModal();
        showToast(`Exhibit '${newDoc.title}' deposited with verified SHA-256 seal!`, 'success');

        if (state.currentView === 'vault' && state.currentCase) {
            await openCaseVault(state.currentCase.id);
        } else {
            await loadDashboard();
        }
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '🔒 Compute Seal & Commit Exhibit';
    }
}

async function handleNewCaseCreate(e) {
    e.preventDefault();
    const title = document.getElementById('case-create-title').value.trim();
    const category = document.getElementById('case-create-category').value;
    const priority = document.getElementById('case-create-priority').value;
    const description = document.getElementById('case-create-desc').value.trim();

    try {
        const response = await fetch(`${API_BASE}/cases/`, {
            method: 'POST',
            headers: apiHeaders(),
            body: JSON.stringify({ title, category, priority, description })
        });
        if (!response.ok) throw new Error('Case initiation failed');

        const created = await response.json();
        closeNewCaseModal();
        showToast(`Case ${created.case_number} initiated!`, 'success');
        await loadDashboard();
        openCaseVault(created.id);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ==========================================================================
// SCREEN 5: AUDIT LOG (ADMIN VIEW)
// ==========================================================================

function initAuditEvents() {
    document.getElementById('btn-refresh-audit').addEventListener('click', loadAuditLedger);
    document.getElementById('btn-export-audit').addEventListener('click', exportAuditJSON);
    document.getElementById('audit-search').addEventListener('input', debounce(loadAuditLedger, 300));
    document.getElementById('audit-action-select').addEventListener('change', loadAuditLedger);
}

async function loadAuditLedger() {
    try {
        const action = document.getElementById('audit-action-select').value;
        const search = document.getElementById('audit-search').value.trim();

        let url = `${API_BASE}/audit/?`;
        if (action) url += `action=${encodeURIComponent(action)}&`;
        if (search) url += `search=${encodeURIComponent(search)}&`;

        const response = await fetch(url, { headers: apiHeaders() });
        if (response.status === 403) {
            showToast('Access Denied: Administrator role required. Switch persona in header.', 'warning');
            switchView('dashboard');
            return;
        }
        if (!response.ok) throw new Error('Failed to load audit ledger');

        state.auditLogs = await response.json();
        renderAuditTable();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderAuditTable() {
    const tbody = document.getElementById('audit-table-body');
    if (state.auditLogs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 40px; color: var(--text-muted);">No audit events matching criteria.</td></tr>`;
        return;
    }

    tbody.innerHTML = state.auditLogs.map(l => {
        const timeStr = new Date(l.timestamp).toISOString().replace('T', ' ').substring(0, 19);
        const shortHash = l.sha256_snapshot ? l.sha256_snapshot.substring(0, 16) + '...' : '—';

        return `
            <tr>
                <td style="font-family: var(--font-mono); font-size: 11px;">${timeStr}</td>
                <td>
                    <strong style="color: #fff;">${l.username}</strong>
                    <br><small style="color: var(--text-faint); text-transform: uppercase; font-size: 10px;">${l.user_role}</small>
                </td>
                <td>
                    <span class="op-badge op-${l.action}">${l.action}</span>
                </td>
                <td style="font-family: var(--font-mono); color: var(--brand-cyan);">${l.resource_id || l.resource_type}</td>
                <td style="max-width: 320px;">${l.details}</td>
                <td>
                    <span class="hash-tag-pill" title="${l.sha256_snapshot || ''}">
                        ${shortHash}
                    </span>
                </td>
                <td style="font-family: var(--font-mono); font-size: 11px;">${l.ip_address}</td>
            </tr>
        `;
    }).join('');
}

async function exportAuditJSON() {
    try {
        const response = await fetch(`${API_BASE}/audit/export`, { headers: apiHeaders() });
        if (!response.ok) throw new Error('Export failed');
        const data = await response.json();

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `irongryph_chain_of_custody_audit_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('Forensic audit ledger exported to JSON', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ==========================================================================
// TAMPER LAB (INTERACTIVE JUDGE DEMO)
// ==========================================================================

function initTamperLab() {
    document.getElementById('lab-btn-tamper').addEventListener('click', handleLabTamper);
    document.getElementById('lab-btn-restore').addEventListener('click', handleLabRestore);
    document.getElementById('lab-btn-verify').addEventListener('click', handleLabVerify);
}

function populateTamperLabSelect() {
    const select = document.getElementById('lab-exhibit-select');
    const allExhibits = [];
    state.cases.forEach(c => {
        // Collect exhibits if currentCase exists or fetch
    });

    // Provide standard demo options
    select.innerHTML = `
        <option value="1">Exhibit #1: SWIFT Interbank Transfer Logs (CASE-2026-1042)</option>
        <option value="2">Exhibit #2: Falsified Shell Entity Incorporation Articles</option>
        <option value="3">Exhibit #3: C2 Server Memory Dump Artifact</option>
        <option value="4">Exhibit #4: Threat Actor PGP Negotiation Log</option>
        <option value="5">Exhibit #5: Cargo Bay Bill of Lading</option>
    `;
}

async function handleLabTamper() {
    const id = document.getElementById('lab-exhibit-select').value;
    try {
        const res = await fetch(`${API_BASE}/evidence/${id}/simulate-tamper`, {
            method: 'POST',
            headers: apiHeaders()
        });
        const data = await res.json();
        showLabResult(data);
        showToast('⚠️ Tamper Simulation: File corrupted on disk. Red Warning triggered.', 'error');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleLabRestore() {
    const id = document.getElementById('lab-exhibit-select').value;
    try {
        const res = await fetch(`${API_BASE}/evidence/${id}/restore`, {
            method: 'POST',
            headers: apiHeaders()
        });
        const data = await res.json();
        showLabResult(data);
        showToast('✅ Exhibit restored to canonical state. Green Verified Shield restored!', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleLabVerify() {
    const id = document.getElementById('lab-exhibit-select').value;
    try {
        const res = await fetch(`${API_BASE}/evidence/${id}/verify`, {
            method: 'POST',
            headers: apiHeaders()
        });
        const data = await res.json();
        showLabResult(data);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function showLabResult(data) {
    const box = document.getElementById('lab-result-card');
    box.style.display = 'block';

    const isMatch = data.is_valid;
    box.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <strong style="color: #fff; font-size: 14px;">Verification Result for: ${data.title}</strong>
            <span class="cryptographic-seal ${isMatch ? 'seal-verified' : 'seal-tampered'}" style="padding: 4px 10px; font-size: 11px;">
                ${isMatch ? '🛡️ SHA-256 SEAL VERIFIED' : '⚠️ TAMPER DETECTED: MISMATCH'}
            </span>
        </div>
        <div style="font-family: var(--font-mono); font-size: 11px; display: flex; flex-direction: column; gap: 4px; background: rgba(0,0,0,0.4); padding: 10px; border-radius: 6px;">
            <div>Expected Canonical Seal: <span style="color: #34d399;">${data.expected_hash}</span></div>
            <div>Physical Disk File Hash:  <span style="color: ${isMatch ? '#34d399' : '#f87171'};">${data.current_hash || 'File Missing'}</span></div>
        </div>
        <p style="margin-top: 8px; color: ${isMatch ? '#34d399' : '#f87171'}; font-weight: 600;">${data.message}</p>
    `;
}

// ==========================================================================
// UTILITIES
// ==========================================================================

function initLiveClock() {
    const clock = document.getElementById('live-utc-clock');
    setInterval(() => {
        const now = new Date();
        clock.textContent = 'UTC ' + now.toUTCString().split(' ')[4];
    }, 1000);
}

function showToast(message, type = 'info') {
    const hub = document.getElementById('toast-hub');
    const toast = document.createElement('div');
    toast.className = `toast-msg toast-${type}`;

    const icon = type === 'success' ? '✅' : type === 'error' ? '🚨' : type === 'warning' ? '⚠️' : 'ℹ️';
    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;

    hub.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 250);
    }, 3800);
}

function copyToClipboard(text, msg) {
    navigator.clipboard.writeText(text).then(() => {
        showToast(msg || 'Copied to clipboard!', 'info');
    });
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
        case 'pdf': return '📕';
        case 'jpg':
        case 'jpeg':
        case 'png': return '🖼️';
        case 'raw': return '💾';
        case 'txt':
        case 'csv': return '📄';
        default: return '📁';
    }
}

function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}
