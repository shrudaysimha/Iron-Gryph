/**
 * MediBook Unified Clinical Client & Session State Engine
 * Handles user authentication, profile drawer, real-time toasts, and modal interactions.
 */

(function () {
  // 1. Session Management
  function getActiveUser() {
    try {
      const stored = localStorage.getItem('medibook_user');
      if (stored) return JSON.parse(stored);
    } catch (e) {}

    // Default fallback profile if not yet explicitly selected
    const fallback = {
      employee_id: "EMP-1005",
      name: "Dr. Rajiv Mehta",
      role: "doctor",
      title: "Chief Trauma Surgeon & Medical Director",
      department: "Emergency Trauma & Surgical ICU",
      specialization: "Trauma & Critical Care (DM, MD)",
      shift: "morning",
      hospital: "SIDS Hospital Surat",
      avatar_url: "https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=150&auto=format&fit=crop&q=80",
    };
    localStorage.setItem('medibook_user', JSON.stringify(fallback));
    localStorage.setItem('medibook_token', 'MEDISESSION-DEFAULT-ACTIVE');
    return fallback;
  }

  function renderHeaderUserProfile() {
    const user = getActiveUser();
    const avatarEls = document.querySelectorAll('.header-user-avatar');
    const nameEls = document.querySelectorAll('.header-user-name');
    const roleEls = document.querySelectorAll('.header-user-role');

    avatarEls.forEach(el => {
      if (el.tagName === 'IMG') {
        el.src = user.avatar_url;
      }
    });

    nameEls.forEach(el => {
      el.textContent = user.name;
    });

    roleEls.forEach(el => {
      el.textContent = user.title || user.role;
    });
  }

  // 2. Profile Drawer
  function injectProfileDrawer() {
    if (document.getElementById('staff-profile-drawer')) return;

    const drawer = document.createElement('div');
    drawer.id = 'staff-profile-drawer';
    drawer.className = 'fixed inset-0 z-50 bg-black/60 backdrop-blur-sm hidden items-center justify-center p-4 transition-all';
    drawer.innerHTML = `
      <div class="bg-surface rounded-3xl max-w-sm w-full p-6 shadow-2xl relative border border-outline-variant overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <!-- Glow accent -->
        <div class="absolute -right-12 -top-12 w-32 h-32 rounded-full bg-primary-fixed/40 blur-2xl pointer-events-none"></div>

        <div class="flex items-center justify-between pb-3 border-b border-surface-container-high">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></span>
            <span class="font-label-sm text-xs uppercase tracking-wider text-primary font-bold">Clinical Session ID</span>
          </div>
          <button onclick="window.closeProfileDrawer()" class="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high">
            <span class="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        <div class="py-4 flex flex-col items-center text-center">
          <div class="relative w-20 h-20 rounded-2xl overflow-hidden mb-3 shadow-md border-2 border-primary/20">
            <img id="drawer-avatar" class="w-full h-full object-cover" src=""/>
            <span class="absolute bottom-1 right-1 w-4 h-4 rounded-full bg-primary flex items-center justify-center text-on-primary">
              <span class="material-symbols-outlined text-[10px]">verified</span>
            </span>
          </div>
          <h3 id="drawer-name" class="font-headline-sm text-lg font-bold text-on-surface"></h3>
          <p id="drawer-title" class="font-body-sm text-xs text-primary font-semibold mt-0.5"></p>
          <span id="drawer-dept" class="text-xs text-on-surface-variant mt-1"></span>

          <!-- Duty Pill -->
          <div class="mt-3 flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary-fixed/30 text-on-primary-fixed-variant text-xs font-bold">
            <span class="w-2 h-2 rounded-full bg-primary animate-ping"></span>
            <span>ON-DUTY SHIFT ACTIVE</span>
          </div>
        </div>

        <!-- Details Grid -->
        <div class="grid grid-cols-2 gap-2 p-3 rounded-2xl bg-surface-container-low mb-4 text-left">
          <div>
            <span class="text-[10px] uppercase font-bold text-on-surface-variant">Employee ID</span>
            <span id="drawer-emp-id" class="block text-xs font-bold text-on-surface mt-0.5"></span>
          </div>
          <div>
            <span class="text-[10px] uppercase font-bold text-on-surface-variant">Station Base</span>
            <span class="block text-xs font-bold text-on-surface mt-0.5">SIDS Hospital Surat</span>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex flex-col gap-2">
          <a href="/login" class="w-full py-2.5 rounded-xl bg-primary text-on-primary font-label-md text-sm font-bold flex items-center justify-center gap-2 shadow-sm hover:bg-primary-container transition-all">
            <span class="material-symbols-outlined text-[18px]">switch_account</span>
            <span>Switch Role / Doctor</span>
          </a>
          <button onclick="window.logoutUser()" class="w-full py-2.5 rounded-xl bg-surface-container-highest text-error font-label-md text-sm font-bold flex items-center justify-center gap-2 hover:bg-error/10 transition-all">
            <span class="material-symbols-outlined text-[18px]">logout</span>
            <span>Log Out Station</span>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(drawer);
  }

  window.openProfileDrawer = function () {
    injectProfileDrawer();
    const user = getActiveUser();
    document.getElementById('drawer-avatar').src = user.avatar_url;
    document.getElementById('drawer-name').textContent = user.name;
    document.getElementById('drawer-title').textContent = user.title || user.role;
    document.getElementById('drawer-dept').textContent = user.department || "SIDS Hospital Clinical Unit";
    document.getElementById('drawer-emp-id').textContent = user.employee_id;

    const drawer = document.getElementById('staff-profile-drawer');
    drawer.classList.remove('hidden');
    drawer.classList.add('flex');
  };

  window.closeProfileDrawer = function () {
    const drawer = document.getElementById('staff-profile-drawer');
    if (drawer) {
      drawer.classList.add('hidden');
      drawer.classList.remove('flex');
    }
  };

  window.logoutUser = function () {
    localStorage.removeItem('medibook_user');
    localStorage.removeItem('medibook_token');
    window.location.href = '/login';
  };

  // 3. Global In-App Toast System
  window.showToast = function (title, message, icon = 'check_circle') {
    let toast = document.getElementById('global-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'global-toast';
      toast.className = 'fixed bottom-20 left-4 right-4 max-w-md mx-auto z-50 bg-inverse-surface text-inverse-on-surface p-4 rounded-2xl shadow-2xl flex items-center justify-between gap-3 transform translate-y-32 opacity-0 transition-all duration-300 pointer-events-none';
      toast.innerHTML = `
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary shrink-0 shadow-sm">
            <span class="material-symbols-outlined text-[20px]" id="global-toast-icon">check_circle</span>
          </div>
          <div class="flex flex-col min-w-0">
            <span class="font-headline-sm text-sm font-bold text-inverse-on-surface truncate" id="global-toast-title">Success</span>
            <span class="font-body-sm text-xs text-inverse-on-surface/85 leading-snug" id="global-toast-desc">Action completed.</span>
          </div>
        </div>
        <button onclick="window.dismissGlobalToast()" class="p-1.5 text-inverse-on-surface/70 hover:text-inverse-on-surface pointer-events-auto">
          <span class="material-symbols-outlined text-[18px]">close</span>
        </button>
      `;
      document.body.appendChild(toast);
    }

    document.getElementById('global-toast-title').textContent = title;
    document.getElementById('global-toast-desc').textContent = message;
    document.getElementById('global-toast-icon').textContent = icon;

    toast.classList.remove('translate-y-32', 'opacity-0', 'pointer-events-none');
    toast.classList.add('translate-y-0', 'opacity-100', 'pointer-events-auto');

    if (window.toastTimer) clearTimeout(window.toastTimer);
    window.toastTimer = setTimeout(window.dismissGlobalToast, 4000);
  };

  window.dismissGlobalToast = function () {
    const toast = document.getElementById('global-toast');
    if (toast) {
      toast.classList.remove('translate-y-0', 'opacity-100', 'pointer-events-auto');
      toast.classList.add('translate-y-32', 'opacity-0', 'pointer-events-none');
    }
  };

  // 4. Modal Dialog Replacement for confirm()
  window.showConfirmDialog = function ({ title, message, icon = 'help', confirmText = 'Confirm', onConfirm }) {
    let dialog = document.getElementById('global-confirm-dialog');
    if (!dialog) {
      dialog = document.createElement('div');
      dialog.id = 'global-confirm-dialog';
      dialog.className = 'fixed inset-0 z-50 bg-black/60 backdrop-blur-sm hidden items-center justify-center p-4';
      document.body.appendChild(dialog);
    }

    dialog.innerHTML = `
      <div class="bg-surface rounded-3xl max-w-sm w-full p-6 shadow-2xl relative border border-outline-variant text-center">
        <div class="w-14 h-14 rounded-2xl bg-primary/10 text-primary mx-auto flex items-center justify-center mb-3">
          <span class="material-symbols-outlined text-[30px]">${icon}</span>
        </div>
        <h3 class="font-headline-sm text-lg font-bold text-on-surface">${title}</h3>
        <p class="font-body-sm text-xs text-on-surface-variant mt-1.5 mb-5 leading-relaxed">${message}</p>
        <div class="flex items-center gap-2">
          <button onclick="document.getElementById('global-confirm-dialog').classList.add('hidden'); document.getElementById('global-confirm-dialog').classList.remove('flex');" class="flex-1 py-2.5 rounded-xl bg-surface-container text-on-surface-variant font-label-md text-sm font-bold">
            Cancel
          </button>
          <button id="dialog-confirm-action" class="flex-1 py-2.5 rounded-xl bg-primary text-on-primary font-label-md text-sm font-bold shadow-md hover:bg-primary-container">
            ${confirmText}
          </button>
        </div>
      </div>
    `;

    document.getElementById('dialog-confirm-action').onclick = function () {
      dialog.classList.add('hidden');
      dialog.classList.remove('flex');
      if (typeof onConfirm === 'function') onConfirm();
    };

    dialog.classList.remove('hidden');
    dialog.classList.add('flex');
  };

  // Run on load
  document.addEventListener('DOMContentLoaded', () => {
    renderHeaderUserProfile();
    injectProfileDrawer();
  });
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    renderHeaderUserProfile();
    injectProfileDrawer();
  }
})();
