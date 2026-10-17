/**
 * IronGryph Legal Evidence Vault - Client-side Controller
 * Zero-Login Architecture with Real-Time Cryptographic Verification
 */

// Global State
let currentRole = localStorage.getItem('vault_role') || 'administrator';
let activeView = 'cases';
let allCases = [];
let activeCase = null;
let allAuditLogs = [];
let allExhibits = [];
let currentPriorityFilter = 'ALL';
let calculatedPreUploadHash = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  initLiveClock();
  setPersona(currentRole, false);
  loadAllCases();
  loadAuditLogs();
});

// ============================================================================
// Zero-Login Persona Management
// ============================================================================

function setPersona(role, reload = true) {
  currentRole = role;
  localStorage.setItem('vault_role', role);

  const btnAdmin = document.getElementById('persona-admin');
  const btnInv = document.getElementById('persona-inv');
  const telemetryRole = document.getElementById('telemetry-role');
  const userBanner = document.getElementById('current-user-banner');

  if (role === 'administrator') {
    btnAdmin.classList.add('active');
    btnInv.classList.remove('active');
    if (telemetryRole) telemetryRole.textContent = 'CHIEF ADMINISTRATOR';
    if (userBanner) userBanner.textContent = 'Chief Elena Vance (Admin)';
  } else {
    btnInv.classList.add('active');
    btnAdmin.classList.remove('active');
    if (telemetryRole) telemetryRole.textContent = 'LEAD INVESTIGATOR';
    if (userBanner) userBanner.textContent = 'Detective Marcus Cole (Investigator)';
  }

  showToast(`Active persona: ${role === 'administrator' ? 'Chief Vance (Admin)' : 'Det. Cole (Investigator)'}`, 'info');

  if (reload) {
    if (activeView === 'cases') loadAllCases();
    else if (activeView === 'vault' && activeCase) loadCaseVault(activeCase.id);
    else if (activeView === 'audit') loadAuditLogs();
  }
}

function getAuthHeaders(extra = {}) {
  return {
    'X-Role': currentRole,
    'X-User': currentRole === 'administrator' ? 'admin' : 'mcole',
    ...extra
  };
}

// ============================================================================
// View Navigation
// ============================================================================

function switchView(viewName) {
  activeView = viewName;

  document.querySelectorAll('.view-panel').forEach(panel => panel.classList.add('hidden'));
  document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));

  const activePanel = document.getElementById(`view-${viewName}`);
  if (activePanel) activePanel.classList.remove('hidden');

  const activeNav = document.getElementById(`nav-${viewName}`);
  if (activeNav) activeNav.classList.add('active');

  if (viewName === 'cases') {
    loadAllCases();
  } else if (viewName === 'audit') {
    loadAuditLogs();
  } else if (viewName === 'tamper') {
    loadTamperLab();
  }

  setTimeout(() => lucide.createIcons(), 50);
}

// ============================================================================
// Cases Management
// ============================================================================

async function loadAllCases() {
  try {
    const res = await fetch('/api/v1/cases', { headers: getAuthHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allCases = await res.json();

    const countEl = document.getElementById('metric-total-cases');
    const navCountEl = document.getElementById('nav-case-count');
    if (countEl) countEl.textContent = allCases.length;
    if (navCountEl) navCountEl.textContent = allCases.length;

    renderCasesGrid(allCases);
    populateCaseDropdowns(allCases);
    calculateOverallMetrics();
  } catch (err) {
    console.error('Failed to load cases:', err);
    showToast('Failed to load cases from vault.', 'error');
  }
}

function renderCasesGrid(cases) {
  const container = document.getElementById('cases-grid');
  if (!container) return;

  const filtered = cases.filter(c => {
    const matchesPriority = (currentPriorityFilter === 'ALL' || c.priority === currentPriorityFilter);
    const searchVal = (document.getElementById('case-search-input')?.value || '').toLowerCase();
    const matchesSearch = !searchVal || 
      c.case_number.toLowerCase().includes(searchVal) || 
      c.title.toLowerCase().includes(searchVal) || 
      c.category.toLowerCase().includes(searchVal);
    return matchesPriority && matchesSearch;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-16 text-center text-gray-500 bg-white rounded-3xl border border-gray-200">
        <i data-lucide="folder-search" class="w-10 h-10 text-gray-400 mx-auto mb-3"></i>
        <h4 class="font-bold text-gray-700">No matching cases found</h4>
        <p class="text-xs text-gray-400 mt-1">Try clearing your search query or filter tags.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = filtered.map(c => {
    const priorityColor = getPriorityBadgeClass(c.priority);
    const count = c.evidence_count || (c.evidence_documents ? c.evidence_documents.length : 0);

    return `
      <div class="case-card bg-white p-6 rounded-3xl border border-gray-200/90 shadow-sm flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between gap-2 mb-3">
            <span class="font-mono text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-lg">
              ${escapeHtml(c.case_number)}
            </span>
            <div class="flex items-center gap-1.5">
              <span class="text-xs font-bold px-2.5 py-0.5 rounded-lg border ${priorityColor}">
                ${escapeHtml(c.priority)}
              </span>
              <span class="text-xs font-semibold text-gray-500 bg-gray-100 px-2.5 py-0.5 rounded-lg">
                ${escapeHtml(c.status)}
              </span>
            </div>
          </div>

          <h3 class="text-xl font-bold text-gray-900 font-['Space_Grotesk'] mb-2 leading-snug">
            ${escapeHtml(c.title)}
          </h3>

          <p class="text-gray-600 text-xs line-clamp-2 mb-4 leading-relaxed">
            ${escapeHtml(c.description || 'No classified synopsis provided.')}
          </p>

          <div class="inline-flex items-center gap-1.5 bg-gray-50 text-gray-700 border border-gray-200 px-2.5 py-1 rounded-lg text-xs font-medium">
            <i data-lucide="tag" class="w-3 h-3 text-emerald-600"></i>
            <span>${escapeHtml(c.category)}</span>
          </div>
        </div>

        <div class="border-t border-gray-100 mt-5 pt-4 flex items-center justify-between">
          <div class="text-xs text-gray-500">
            <span class="font-bold text-gray-800">${count}</span> exhibit${count === 1 ? '' : 's'} secured
          </div>
          <button 
            onclick="openCaseVault(${c.id})" 
            class="bg-gray-900 hover:bg-emerald-700 text-white px-3.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <span>Open Vault</span>
            <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');

  lucide.createIcons();
}

function getPriorityBadgeClass(priority) {
  switch (priority) {
    case 'Critical': return 'bg-red-50 text-red-700 border-red-200';
    case 'High': return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'Medium': return 'bg-blue-50 text-blue-700 border-blue-200';
    default: return 'bg-gray-50 text-gray-700 border-gray-200';
  }
}

function setPriorityFilter(priority) {
  currentPriorityFilter = priority;
  document.querySelectorAll('.priority-filter').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.trim().toUpperCase() === priority.toUpperCase());
  });
  renderCasesGrid(allCases);
}

function filterCases() {
  renderCasesGrid(allCases);
}

// ============================================================================
// Case Detail & Evidence Vault View
// ============================================================================

async function openCaseVault(caseId) {
  try {
    const res = await fetch(`/api/v1/cases/${caseId}`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Case not found');
    activeCase = await res.json();

    document.getElementById('vault-case-number').textContent = activeCase.case_number;
    document.getElementById('vault-case-title').textContent = activeCase.title;
    document.getElementById('vault-case-desc').textContent = activeCase.description || 'No additional synopsis.';
    document.getElementById('vault-case-priority').textContent = activeCase.priority;
    document.getElementById('vault-case-priority').className = `text-xs font-bold px-2.5 py-0.5 rounded-lg border ${getPriorityBadgeClass(activeCase.priority)}`;
    document.getElementById('vault-case-status').textContent = activeCase.status;
    document.getElementById('vault-case-category').textContent = activeCase.category;
    document.getElementById('vault-case-lead').textContent = activeCase.lead_investigator ? activeCase.lead_investigator.full_name : 'Assigned Staff';

    const navVault = document.getElementById('nav-vault');
    const navVaultLabel = document.getElementById('nav-vault-label');
    navVault.classList.remove('hidden');
    navVaultLabel.textContent = activeCase.case_number;

    await loadCaseVault(caseId);
    switchView('vault');
  } catch (err) {
    console.error('Error loading case detail:', err);
    showToast('Failed to load case detail', 'error');
  }
}

async function loadCaseVault(caseId) {
  try {
    const res = await fetch(`/api/v1/cases/${caseId}/evidence`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error('Failed to load exhibits');
    const exhibits = await res.json();
    allExhibits = exhibits;

    document.getElementById('vault-case-count').textContent = exhibits.length;
    renderExhibits(exhibits);
  } catch (err) {
    console.error('Error loading exhibits:', err);
    showToast('Error loading evidence exhibits', 'error');
  }
}

function renderExhibits(exhibits) {
  const container = document.getElementById('exhibits-list');
  if (!container) return;

  if (exhibits.length === 0) {
    container.innerHTML = `
      <div class="bg-white p-12 rounded-3xl border border-gray-200 text-center text-gray-500">
        <i data-lucide="archive" class="w-10 h-10 text-gray-300 mx-auto mb-3"></i>
        <h4 class="font-bold text-gray-700">No exhibits deposited in this vault yet</h4>
        <p class="text-xs text-gray-400 mt-1">Click 'Deposit Exhibit to Case' to seal new physical or digital evidence.</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = exhibits.map(ex => {
    const isTampered = (ex.status_badge === 'TAMPERED_RED' || ex.is_tampered === true);
    const badgeClass = isTampered ? 'badge-tampered' : 'badge-verified';
    const badgeIcon = isTampered ? 'alert-triangle' : 'shield-check';
    const badgeText = isTampered ? 'TAMPER DETECTED (SHA-256 Mismatch)' : 'Cryptographically Verified (SHA-256 Match)';
    const sizeKb = ex.file_size ? `${(ex.file_size / 1024).toFixed(1)} KB` : '12 KB';

    return `
      <div class="bg-white p-6 rounded-3xl border ${isTampered ? 'border-red-300 bg-red-50/10' : 'border-gray-200/90'} shadow-sm transition-all" id="exhibit-card-${ex.id}">
        <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 rounded-2xl ${isTampered ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-700'} flex items-center justify-center shrink-0">
              <i data-lucide="${isTampered ? 'file-warning' : 'file-check'}" class="w-6 h-6"></i>
            </div>
            
            <div>
              <div class="flex items-center gap-2 flex-wrap mb-1">
                <span class="font-bold text-base text-gray-900">${escapeHtml(ex.title)}</span>
                <span class="text-[11px] bg-gray-100 text-gray-700 px-2 py-0.5 rounded font-medium">${escapeHtml(ex.category)}</span>
                <span class="text-[11px] text-gray-400 font-mono">${escapeHtml(ex.filename)} • ${sizeKb}</span>
              </div>
              <p class="text-xs text-gray-600 max-w-2xl leading-relaxed mb-3">
                ${escapeHtml(ex.description || 'Verified evidence record deposited under chain of custody.')}
              </p>

              <!-- SHA-256 Fingerprint Display -->
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Intake SHA-256:</span>
                <span class="hash-pill" title="Click to copy hash" onclick="copyHash('${ex.sha256_hash}')">
                  ${escapeHtml(ex.sha256_hash)}
                </span>
                <button onclick="copyHash('${ex.sha256_hash}')" class="text-gray-400 hover:text-emerald-700 text-xs" title="Copy SHA-256">
                  <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                </button>
              </div>
            </div>
          </div>

          <!-- Status Seal & Action Buttons -->
          <div class="flex flex-col sm:items-end gap-3 shrink-0">
            <!-- Seal Badge -->
            <div class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold ${badgeClass}">
              <i data-lucide="${badgeIcon}" class="w-4 h-4"></i>
              <span>${badgeText}</span>
            </div>

            <!-- Action Buttons -->
            <div class="flex items-center gap-2 flex-wrap">
              <button 
                onclick="verifyExhibit(${ex.id})" 
                class="bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1 transition-colors"
                title="Live verify disk hash against intake hash"
              >
                <i data-lucide="shield-check" class="w-3.5 h-3.5"></i>
                <span>Verify</span>
              </button>

              ${isTampered ? `
                <button 
                  onclick="restoreExhibit(${ex.id})" 
                  class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1 transition-colors shadow-sm"
                  title="Restore pristine backup and restore green seal"
                >
                  <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
                  <span>Restore Seal</span>
                </button>
              ` : `
                <button 
                  onclick="simulateTamper(${ex.id})" 
                  class="bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1 transition-colors"
                  title="Corrupt 1 byte on disk to demonstrate red tamper alert"
                >
                  <i data-lucide="zap" class="w-3.5 h-3.5"></i>
                  <span>Simulate Tamper</span>
                </button>
              `}

              <a 
                href="/api/v1/evidence/${ex.id}/download" 
                class="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1 transition-colors"
                title="Download original secured exhibit"
              >
                <i data-lucide="download" class="w-3.5 h-3.5"></i>
                <span>Download</span>
              </a>
            </div>

          </div>

        </div>
      </div>
    `;
  }).join('');

  lucide.createIcons();
}

// ============================================================================
// Cryptographic Verification & Tamper Demonstration
// ============================================================================

async function verifyExhibit(docId) {
  try {
    const res = await fetch(`/api/v1/evidence/${docId}/verify`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    const result = await res.json();

    if (result.is_valid) {
      showToast('🛡️ Cryptographic Integrity Confirmed: SHA-256 match!', 'success');
    } else {
      showToast('⚠️ TAMPER ALERT! On-disk digest does NOT match intake seal!', 'error');
    }

    if (activeCase) loadCaseVault(activeCase.id);
    if (activeView === 'tamper') loadTamperLab();
    loadAuditLogs();
    calculateOverallMetrics();
  } catch (err) {
    console.error('Verify failed:', err);
    showToast('Failed to perform cryptographic verification', 'error');
  }
}

async function simulateTamper(docId) {
  try {
    const res = await fetch(`/api/v1/evidence/${docId}/simulate-tamper`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    const result = await res.json();

    showToast('⚡ Tamper Injected! File content altered on disk. Seal is now RED.', 'warning');
    if (activeCase) loadCaseVault(activeCase.id);
    if (activeView === 'tamper') loadTamperLab();
    loadAuditLogs();
    calculateOverallMetrics();
  } catch (err) {
    console.error('Tamper simulation failed:', err);
    showToast('Error simulating file tamper', 'error');
  }
}

async function restoreExhibit(docId) {
  try {
    const res = await fetch(`/api/v1/evidence/${docId}/restore`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    const result = await res.json();

    showToast('✓ Canonical backup restored. Green verified seal reinstated.', 'success');
    if (activeCase) loadCaseVault(activeCase.id);
    if (activeView === 'tamper') loadTamperLab();
    loadAuditLogs();
    calculateOverallMetrics();
  } catch (err) {
    console.error('Restore failed:', err);
    showToast('Error restoring exhibit', 'error');
  }
}

// ============================================================================
// Tamper Lab View
// ============================================================================

async function loadTamperLab() {
  const container = document.getElementById('tamper-exhibits-grid');
  if (!container) return;

  try {
    const res = await fetch('/api/v1/cases', { headers: getAuthHeaders() });
    const cases = await res.json();

    let allDocs = [];
    for (const c of cases) {
      const evRes = await fetch(`/api/v1/cases/${c.id}/evidence`, { headers: getAuthHeaders() });
      if (evRes.ok) {
        const docs = await evRes.json();
        docs.forEach(d => d.case_number = c.case_number);
        allDocs.push(...docs);
      }
    }

    if (allDocs.length === 0) {
      container.innerHTML = `<div class="col-span-full p-8 text-center text-gray-500">No exhibits available.</div>`;
      return;
    }

    container.innerHTML = allDocs.map(doc => {
      const isTampered = (doc.status_badge === 'TAMPERED_RED' || doc.is_tampered === true);

      return `
        <div class="bg-white p-6 rounded-3xl border ${isTampered ? 'border-red-300 bg-red-50/10' : 'border-gray-200'} shadow-sm flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="font-mono text-xs font-bold text-gray-500">${escapeHtml(doc.case_number)}</span>
              <span class="text-xs font-bold px-2.5 py-0.5 rounded-lg ${isTampered ? 'bg-red-100 text-red-800' : 'bg-emerald-100 text-emerald-800'}">
                ${isTampered ? 'TAMPERED' : 'VERIFIED'}
              </span>
            </div>

            <h4 class="font-bold text-gray-900 text-base mb-1">${escapeHtml(doc.title)}</h4>
            <p class="text-xs text-gray-500 font-mono mb-3">${escapeHtml(doc.filename)}</p>

            <div class="space-y-2 mb-4 bg-gray-50 p-3 rounded-2xl text-xs">
              <div>
                <span class="font-bold text-gray-500 block text-[10px] uppercase">Intake Authority Hash:</span>
                <span class="font-mono text-[11px] text-emerald-800 break-all">${doc.sha256_hash}</span>
              </div>
              <div>
                <span class="font-bold text-gray-500 block text-[10px] uppercase">Current Live Disk Hash:</span>
                <span class="font-mono text-[11px] ${isTampered ? 'text-red-700 font-bold' : 'text-gray-700'} break-all">
                  ${isTampered ? 'Corrupted [Checksum Mismatch Detected]' : doc.sha256_hash}
                </span>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 pt-3 border-t border-gray-100">
            ${isTampered ? `
              <button onclick="restoreExhibit(${doc.id})" class="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm transition-all">
                <i data-lucide="shield-check" class="w-4 h-4"></i>
                Restore Canonical Seal
              </button>
            ` : `
              <button onclick="simulateTamper(${doc.id})" class="flex-1 bg-amber-500 hover:bg-amber-600 text-white py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm transition-all">
                <i data-lucide="zap" class="w-4 h-4"></i>
                Inject Tamper Byte
              </button>
            `}
            <button onclick="verifyExhibit(${doc.id})" class="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1">
              <i data-lucide="check" class="w-3.5 h-3.5"></i>
              Verify
            </button>
          </div>
        </div>
      `;
    }).join('');

    lucide.createIcons();
  } catch (err) {
    console.error('Tamper lab load failed:', err);
  }
}

// ============================================================================
// Chain-of-Custody Audit Ledger
// ============================================================================

async function loadAuditLogs() {
  try {
    const res = await fetch('/api/v1/audit/logs', { headers: getAuthHeaders() });
    if (!res.ok) {
      if (res.status === 403) {
        renderAuditRestricted();
        return;
      }
      throw new Error(`HTTP ${res.status}`);
    }

    allAuditLogs = await res.json();
    const metricEl = document.getElementById('metric-audit-count');
    if (metricEl) metricEl.textContent = allAuditLogs.length;

    renderAuditTable(allAuditLogs);
  } catch (err) {
    console.error('Failed to load audit trail:', err);
  }
}

function renderAuditRestricted() {
  const tbody = document.getElementById('audit-table-body');
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="p-8 text-center text-gray-500">
          <i data-lucide="shield-alert" class="w-8 h-8 text-amber-500 mx-auto mb-2"></i>
          <p class="font-bold text-gray-700">Administrator Credentials Required</p>
          <p class="text-xs text-gray-400 mt-1">Switch to Chief Vance (Admin) in the top header to review the court audit ledger.</p>
        </td>
      </tr>
    `;
    lucide.createIcons();
  }
}

function renderAuditTable(logs) {
  const tbody = document.getElementById('audit-table-body');
  if (!tbody) return;

  const searchVal = (document.getElementById('audit-search-input')?.value || '').toLowerCase();
  const actionFilter = document.getElementById('audit-action-filter')?.value || 'ALL';

  const filtered = logs.filter(log => {
    const matchesAction = (actionFilter === 'ALL' || log.action === actionFilter);
    const matchesSearch = !searchVal || 
      (log.actor_badge && log.actor_badge.toLowerCase().includes(searchVal)) ||
      (log.actor_name && log.actor_name.toLowerCase().includes(searchVal)) ||
      (log.action && log.action.toLowerCase().includes(searchVal)) ||
      (log.details && log.details.toLowerCase().includes(searchVal));
    return matchesAction && matchesSearch;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="p-8 text-center text-gray-400">No matching audit events recorded.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(log => {
    const actionClass = getActionBadgeClass(log.action);
    const timeFormatted = new Date(log.timestamp).toISOString().replace('T', ' ').substring(0, 19);

    return `
      <tr class="hover:bg-gray-50/80 transition-colors">
        <td class="py-3 px-4 font-mono text-[11px] text-gray-500 whitespace-nowrap">${timeFormatted}</td>
        <td class="py-3 px-4 whitespace-nowrap">
          <div class="font-semibold text-gray-800">${escapeHtml(log.actor_name || 'System')}</div>
          <div class="text-[10px] text-gray-400 font-mono">${escapeHtml(log.actor_badge || 'SYS-AUTO')}</div>
        </td>
        <td class="py-3 px-4 whitespace-nowrap">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold ${actionClass}">${escapeHtml(log.action)}</span>
        </td>
        <td class="py-3 px-4 text-gray-700 font-medium whitespace-nowrap">
          ${escapeHtml(log.target_record || '--')}
        </td>
        <td class="py-3 px-4 font-mono text-[11px] text-gray-500 max-w-xs truncate" title="${log.sha256_snapshot || ''}">
          ${log.sha256_snapshot ? escapeHtml(log.sha256_snapshot.substring(0, 16) + '...') : '<span class="text-gray-300">N/A</span>'}
        </td>
        <td class="py-3 px-4 text-gray-600 text-xs">${escapeHtml(log.details || '')}</td>
      </tr>
    `;
  }).join('');
}

function getActionBadgeClass(action) {
  switch (action) {
    case 'TAMPER_ALERT': return 'bg-red-100 text-red-800 border border-red-200';
    case 'VERIFY_SUCCESS': return 'bg-emerald-100 text-emerald-800';
    case 'EVIDENCE_DEPOSIT': return 'bg-blue-100 text-blue-800';
    case 'EVIDENCE_DOWNLOAD': return 'bg-purple-100 text-purple-800';
    default: return 'bg-gray-100 text-gray-700';
  }
}

function filterAuditLogs() {
  renderAuditTable(allAuditLogs);
}

function exportAuditLedger() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(allAuditLogs, null, 2));
  const dlAnchor = document.createElement('a');
  dlAnchor.setAttribute("href", dataStr);
  dlAnchor.setAttribute("download", `judicial_chain_of_custody_ledger_${new Date().toISOString().substring(0, 10)}.json`);
  document.body.appendChild(dlAnchor);
  dlAnchor.click();
  dlAnchor.remove();
  showToast('Judicial Audit Ledger downloaded (Court Discovery JSON)', 'success');
}

// ============================================================================
// Modal & Evidence Deposit Ingress (Client-Side WebCrypto SHA-256)
// ============================================================================

function openDepositModal() {
  const modal = document.getElementById('modal-deposit');
  if (modal) modal.classList.remove('hidden');
  resetDepositForm();
  lucide.createIcons();
}

function openDepositModalForCurrentCase() {
  openDepositModal();
  if (activeCase) {
    const select = document.getElementById('deposit-case-select');
    if (select) select.value = activeCase.id;
  }
}

function closeDepositModal() {
  const modal = document.getElementById('modal-deposit');
  if (modal) modal.classList.add('hidden');
  resetDepositForm();
}

function resetDepositForm() {
  const form = document.getElementById('deposit-form');
  if (form) form.reset();
  const fileLabel = document.getElementById('file-label-main');
  if (fileLabel) fileLabel.textContent = 'Click or drag & drop evidence file';
  const cryptoBox = document.getElementById('crypto-preview-box');
  if (cryptoBox) cryptoBox.classList.add('hidden');
  calculatedPreUploadHash = null;
}

function populateCaseDropdowns(cases) {
  const select = document.getElementById('deposit-case-select');
  if (!select) return;
  select.innerHTML = cases.map(c => `
    <option value="${c.id}">${escapeHtml(c.case_number)} — ${escapeHtml(c.title)}</option>
  `).join('');
}

// Client-Side WebCrypto SHA-256 Pre-Calculation
async function handleFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  const fileLabel = document.getElementById('file-label-main');
  if (fileLabel) fileLabel.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

  const cryptoBox = document.getElementById('crypto-preview-box');
  const cryptoHashEl = document.getElementById('crypto-hash-preview');
  if (cryptoBox) cryptoBox.classList.remove('hidden');
  if (cryptoHashEl) cryptoHashEl.textContent = 'Calculating client-side SHA-256 hash...';

  try {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    calculatedPreUploadHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    
    if (cryptoHashEl) {
      cryptoHashEl.textContent = calculatedPreUploadHash;
    }
  } catch (err) {
    console.error('WebCrypto error:', err);
    if (cryptoHashEl) cryptoHashEl.textContent = 'Calculation fallback to server-side.';
  }
}

async function handleDepositSubmit(event) {
  event.preventDefault();

  const caseId = document.getElementById('deposit-case-select').value;
  const title = document.getElementById('deposit-title').value;
  const description = document.getElementById('deposit-desc').value;
  const category = document.getElementById('deposit-category').value;
  const fileInput = document.getElementById('file-input');

  if (!fileInput.files || fileInput.files.length === 0) {
    showToast('Please attach an evidence file.', 'error');
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('case_id', caseId);
  formData.append('title', title);
  formData.append('description', description);
  formData.append('category', category);
  formData.append('file', file);

  const submitBtn = document.getElementById('deposit-submit-btn');
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Sealing Exhibit...`;

  try {
    const res = await fetch('/api/v1/evidence/upload', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const doc = await res.json();
    showToast(`✓ Exhibit '${doc.title}' deposited with SHA-256 seal!`, 'success');
    closeDepositModal();

    if (activeCase && String(activeCase.id) === String(caseId)) {
      loadCaseVault(activeCase.id);
    }
    loadAllCases();
    loadAuditLogs();
  } catch (err) {
    console.error('Deposit error:', err);
    showToast(`Deposit failed: ${err.message}`, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<i data-lucide="shield" class="w-4 h-4"></i> Deposit & Seal Exhibit`;
    lucide.createIcons();
  }
}

// Drag & Drop Setup
const dropZone = document.getElementById('drop-zone');
if (dropZone) {
  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.add('border-emerald-500', 'bg-emerald-50/40');
    });
  });
  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-emerald-500', 'bg-emerald-50/40');
    });
  });
  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      document.getElementById('file-input').files = files;
      handleFileSelected({ target: { files } });
    }
  });
}

// ============================================================================
// Utilities
// ============================================================================

function calculateOverallMetrics() {
  if (allCases.length === 0) return;
  let totalExhibits = 0;
  allCases.forEach(c => {
    totalExhibits += (c.evidence_count || (c.evidence_documents ? c.evidence_documents.length : 0));
  });

  const exhibitMetric = document.getElementById('metric-total-exhibits');
  if (exhibitMetric) exhibitMetric.textContent = totalExhibits;
}

function copyHash(hash) {
  navigator.clipboard.writeText(hash).then(() => {
    showToast('SHA-256 digest copied to clipboard!', 'info');
  });
}

function initLiveClock() {
  const clockEl = document.getElementById('live-clock');
  function update() {
    if (clockEl) {
      clockEl.textContent = 'UTC ' + new Date().toISOString().substring(11, 19);
    }
  }
  update();
  setInterval(update, 1000);
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const borderClass = type === 'success' ? 'border-emerald-500 bg-white text-emerald-900' :
                      type === 'error' ? 'border-red-500 bg-white text-red-900' :
                      type === 'warning' ? 'border-amber-500 bg-white text-amber-900' :
                      'border-blue-500 bg-white text-gray-900';

  const iconName = type === 'success' ? 'check-circle' :
                   type === 'error' ? 'alert-octagon' :
                   type === 'warning' ? 'alert-triangle' : 'info';

  toast.className = `toast-alert border-l-4 p-4 rounded-2xl shadow-xl flex items-center gap-3 animate-fade-in ${borderClass}`;
  toast.innerHTML = `
    <i data-lucide="${iconName}" class="w-5 h-5 shrink-0"></i>
    <span class="text-xs font-semibold flex-1">${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  lucide.createIcons();

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.4s ease';
    setTimeout(() => toast.remove(), 400);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
