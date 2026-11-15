// ==========================================
// DATEI-SUCHMASCHINE PRO - FRONTEND ENGINE
// ==========================================

let state = {
  currentFiles: [],
  allRawFiles: [],
  selectedFilePaths: new Set(),
  currentCategory: 'all',
  activeTab: 'search',
  viewMode: 'table',
  sortCol: 'name',
  sortAsc: true,
  searchScope: 'pc',
  systemLocations: [],
  savedPaths: [],
  networkPaths: [],
  allDrives: ['C:\\', 'D:\\'],
  onedrivePath: '',
  onedriveInfo: null,
  gitInfo: null,
  networkUrl: '',
  localIp: '',
  duplicateData: null,
  duplicateSelectedPaths: new Set(),
  renameFiles: [],
  currentRenameRule: 'replace',
  renamePreview: [],
  searchHistory: [],
  savedSearches: [],
  emailClient: 'thunderbird',
  sevenFolderOptions: [],
  activeTimeframe: '',
  activeSizePreset: '',
  previewVisible: false,
  activePreviewPath: '',
  targetModalPaths: [],
  targetModalMode: 'copy'
};

// Initialisierung bei DOM-Ready
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSystemInfo();
  updateStickyHeaderPositions();
  // Lucide icons init if available
  if (window.lucide) {
    lucide.createIcons();
  }
  
  // Enter-Taste im Pfad-Eingabefeld löst ebenfalls sofortige Suche aus
  const dirInput = document.getElementById('target-directory');
  if (dirInput) {
    dirInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        executeSearch();
      }
    });
  }

  // Escape-Taste schließt geöffnete Vorschau und alle Modals sofort
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePreviewModal();
      if (typeof closeSingleRenameModal === 'function') closeSingleRenameModal();
      if (typeof closeSavePathModal === 'function') closeSavePathModal();
      if (typeof closeAddNetworkModal === 'function') closeAddNetworkModal();
      if (typeof closeOneDriveSettingsModal === 'function') closeOneDriveSettingsModal();
      if (typeof closeSettingsModal === 'function') closeSettingsModal();
      if (typeof closeGdriveSettingsModal === 'function') closeGdriveSettingsModal();
      if (typeof closeShareModal === 'function') closeShareModal();
      if (typeof closeTargetFolderModal === 'function') closeTargetFolderModal();
      if (typeof closeGitModal === 'function') closeGitModal();
      if (typeof closeMobileModal === 'function') closeMobileModal();
    }
  });
});

// ==========================================
// STICKY HEADER DOCKING ("hier anlaufen")
// ==========================================
function updateStickyHeaderPositions() {
  const header = document.querySelector('header');
  const toolbar = document.getElementById('results-toolbar');
  if (!header) return;
  const headerHeight = header.offsetHeight || 68;
  if (toolbar) {
    toolbar.style.top = `${headerHeight}px`;
    const isVisible = !toolbar.classList.contains('hidden') && toolbar.offsetHeight > 0;
    const toolbarHeight = isVisible ? toolbar.offsetHeight : 0;
    // Wenn Toolbar sichtbar ist, dockt der Tabellen-Header direkt unter der Toolbar an ("hier anlaufen")
    const tableTop = isVisible ? (headerHeight + toolbarHeight) : headerHeight;
    document.documentElement.style.setProperty('--sticky-table-top', `${tableTop}px`);
  } else {
    document.documentElement.style.setProperty('--sticky-table-top', `${headerHeight}px`);
  }
}

window.addEventListener('resize', updateStickyHeaderPositions);
window.addEventListener('scroll', updateStickyHeaderPositions, { passive: true });

// Systeminformationen (OneDrive etc.) laden
async function initSystemInfo() {
  try {
    const res = await fetch('/api/system-info');
    const data = await res.json();
    state.systemLocations = data.locations || [];
    state.savedPaths = data.saved_paths || [];
    state.networkPaths = data.network_paths || [];
    state.allDrives = data.all_drives || ['C:\\', 'D:\\'];
    state.onedriveInfo = data.onedrive_info || {};
    state.gitInfo = data.git_info || {};
    state.networkUrl = data.network_url || '';
    state.localIp = data.local_ip || '';
    state.searchHistory = data.search_history || [];
    state.savedSearches = data.saved_searches || [];
    state.emailClient = data.email_client || 'thunderbird';
    state.usbStickDir = data.usb_stick_dir || '';
    state.usbDrives = data.usb_drives || [];
    state.sevenFolderOptions = data.seven_folder_options || [];

    // Version im Header aktualisieren
    const vTag = document.getElementById('header-version-tag');
    if (vTag && data.app_version) {
      vTag.textContent = data.app_version;
    }
    const gitV = document.getElementById('git-modal-version');
    if (gitV && data.app_version) {
      gitV.textContent = data.app_version;
    }

    renderLocationShortcuts();
    renderSearchHistoryAndSaved();
    updateEmailClientUI();

    // Brücke aus 7-Ordner-Pro: Direktziel via ?open_path=... sofort öffnen und suchen
    const urlParams = new URLSearchParams(window.location.search);
    const openPath = (urlParams.get('open_path') || '').trim();
    if (openPath) {
      try {
        window.history.replaceState({}, document.title, window.location.pathname);
      } catch (_e) {}
      setLocation(openPath, 'custom');
    } else {
      // Standard-Suchverzeichnis: DIESER PC (Alle Laufwerke C:, D: etc.)
      setSearchScope('pc');
    }
    startBridgePollLoop();
    if (!window._usbFocusRefreshBound) {
      window._usbFocusRefreshBound = true;
      window.addEventListener('focus', refreshUsbStickShortcut);
    }
  } catch (err) {
    console.error('System-Info Fehler:', err);
  }
}

async function refreshUsbStickShortcut() {
  try {
    const res = await fetch('/api/usb-drives');
    if (!res.ok) return;
    const d = await res.json();
    const nextDir = d.usb_stick_dir || '';
    if (nextDir !== (state.usbStickDir || '')) {
      state.usbStickDir = nextDir;
      state.usbDrives = d.drives || [];
      renderLocationShortcuts();
    }
  } catch (_e) {}
}

const _bridgeClientId = 'sm_' + Math.random().toString(36).slice(2) + '_' + Date.now();
let _bridgePollTimer = null;

function startBridgePollLoop() {
  if (_bridgePollTimer) return;
  const pollOnce = async () => {
    try {
      const res = await fetch('/api/bridge/poll?client_id=' + encodeURIComponent(_bridgeClientId), { cache: 'no-store' });
      if (!res.ok) return;
      const d = await res.json();
      if (d && d.command) {
        if (d.command.open_path) {
          setLocation(d.command.open_path, 'custom');
          showToast(`Ordner aus 7-Ordner-Pro geladen: ${d.command.open_path}`, 'info');
        } else if (d.command.focus) {
          showToast('ℹ️ Datei-Suchmaschine ist bereits geöffnet.', 'info');
        }
        try { window.focus(); } catch (_e) {}
      }
    } catch (_e) {}
  };
  pollOnce();
  _bridgePollTimer = setInterval(pollOnce, 1800);
}

function toGermanDisplayPath(path) {
  if (!path || typeof path !== 'string') return path || '';
  return path.replace(/\\Documents\b/gi, '\\Dokumente').replace(/\/Documents\b/gi, '/Dokumente');
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(1)} ${units[i]}`;
}

// Suchbereich (Scope) umschalten: pc, onedrive, network, folder
function setSearchScope(scope) {
  state.searchScope = scope;
  const dirInput = document.getElementById('target-directory');
  const btnPc = document.getElementById('scope-btn-pc');
  const btnOd = document.getElementById('scope-btn-onedrive');
  const btnNet = document.getElementById('scope-btn-network');
  const btnFold = document.getElementById('scope-btn-folder');

  // Alle zurücksetzen
  [btnPc, btnOd, btnNet, btnFold].forEach(b => {
    if (b) {
      b.className = 'scope-btn p-3 rounded-xl border border-slate-700 bg-slate-800/60 hover:bg-slate-800 text-slate-300 font-medium text-xs flex items-center gap-2.5 transition';
    }
  });

  if (scope === 'pc') {
    if (btnPc) btnPc.className = 'scope-btn active p-3 rounded-xl border border-indigo-500/50 bg-indigo-500/20 text-white font-bold text-xs flex items-center gap-2.5 transition shadow-md shadow-indigo-500/20';
    if (dirInput) dirInput.value = 'Dieser PC (Alle lokalen Laufwerke: C:\\, D:\\)';
    showToast('💻 Suchbereich: Ganzer PC (Alle Laufwerke C:, D: ...)', 'info');
  } else if (scope === 'onedrive') {
    if (btnOd) btnOd.className = 'scope-btn active p-3 rounded-xl border border-sky-500/50 bg-sky-500/20 text-white font-bold text-xs flex items-center gap-2.5 transition shadow-md shadow-sky-500/20';
    if (dirInput) dirInput.value = 'OneDrive (Privat & Geschäft)';
    showToast('☁️ Suchbereich: Nur OneDrive (Privat & Geschäft)', 'info');
  } else if (scope === 'network') {
    if (btnNet) btnNet.className = 'scope-btn active p-3 rounded-xl border border-emerald-500/50 bg-emerald-500/20 text-white font-bold text-xs flex items-center gap-2.5 transition shadow-md shadow-emerald-500/20';
    if (dirInput) dirInput.value = 'Netzwerk (Alle Netzlaufwerke & Freigaben)';
    showToast('🌐 Suchbereich: Nur Netzwerk (Freigaben & Netzlaufwerke)', 'info');
  } else if (scope === 'folder') {
    if (btnFold) btnFold.className = 'scope-btn active p-3 rounded-xl border border-amber-500/50 bg-amber-500/20 text-white font-bold text-xs flex items-center gap-2.5 transition shadow-md shadow-amber-500/20';
    const curVal = dirInput ? dirInput.value.trim() : '';
    const isScopePlaceholder = (
      !curVal ||
      curVal.startsWith('Dieser PC (') ||
      curVal.startsWith('OneDrive (') ||
      curVal.startsWith('Netzwerk (') ||
      ['THIS_PC', 'ONEDRIVE_ALL', 'NETWORK'].includes(curVal)
    );
    if (dirInput && isScopePlaceholder) {
      dirInput.value = 'C:\\Users\\01\\Documents\\';
    }
  }
}

// Rendert alle Schnellzugriff-Buttons (System + Gespeicherte eigene Favoriten)
function renderLocationShortcuts() {
  const container = document.getElementById('location-shortcuts');
  if (!container) return;

  container.innerHTML = '';

  // 1. OneDrive Privat
  const odPers = state.onedriveInfo?.personal;
  if (odPers && odPers.exists) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'loc-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-sky-950/60 hover:bg-sky-900/60 text-sky-300 border border-sky-800/80 transition';
    btn.title = 'Privates OneDrive';
    btn.innerHTML = `<i class="fa-solid fa-cloud text-sky-400"></i><span>OneDrive Privat</span>`;
    btn.onclick = () => setLocation(odPers.path, 'personal');
    container.appendChild(btn);
  }

  // 2. OneDrive Geschäftlich
  const odBiz = state.onedriveInfo?.business;
  const bizWrapper = document.createElement('div');
  bizWrapper.className = 'inline-flex rounded-lg border border-purple-800/80 bg-purple-950/60 p-0.5';
  bizWrapper.innerHTML = `
    <button type="button" class="flex items-center gap-1.5 px-2 py-0.5 text-xs font-semibold text-purple-300 hover:text-white transition" title="Geschäftliches OneDrive">
      <i class="fa-solid fa-building text-purple-400"></i>
      <span>OneDrive Geschäft</span>
    </button>
    <button type="button" onclick="openOneDriveSettingsModal()" class="px-1.5 py-0.5 text-[11px] text-purple-400 hover:text-white hover:bg-purple-900/50 rounded transition" title="Geschäftlichen Pfad anpassen">
      <i class="fa-solid fa-gear"></i>
    </button>
  `;
  bizWrapper.querySelector('button').onclick = () => setLocation(odBiz?.path || 'C:\\Users\\01\\OneDrive - Geschaeft', 'business');
  container.appendChild(bizWrapper);

  // 3. iCloud Drive
  const icloud = state.onedriveInfo?.icloud || state.systemLocations?.find(l => l.id === 'icloud_drive');
  if (icloud && icloud.exists) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'loc-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-sky-950/60 hover:bg-sky-900/60 text-sky-300 border border-sky-800/80 transition';
    btn.title = 'iCloud Drive durchsuchen (Apple)';
    btn.innerHTML = `<i class="fa-brands fa-apple text-sky-300 text-sm"></i><span>iCloud Drive</span>`;
    btn.onclick = () => setLocation(icloud.path, 'icloud');
    container.appendChild(btn);
  }

  // 4. Google Drive
  const gdrive = state.onedriveInfo?.gdrive || state.systemLocations?.find(l => l.id === 'gdrive');
  const gdriveWrapper = document.createElement('div');
  gdriveWrapper.className = 'inline-flex items-center rounded-lg border border-emerald-500/40 bg-emerald-950/50 p-0.5 shadow-sm group';
  gdriveWrapper.innerHTML = `
    <button type="button" class="flex items-center gap-1.5 px-2 py-0.5 text-xs font-semibold text-emerald-300 hover:text-white transition" title="${gdrive?.exists ? 'Google Drive durchsuchen: ' + gdrive.path : 'Google Drive Pfad einrichten'}">
      <i class="fa-brands fa-google-drive text-emerald-400"></i>
      <span>Google Drive</span>
    </button>
    <button type="button" onclick="openGdriveSettingsModal()" class="px-1.5 py-0.5 text-[11px] text-emerald-400 hover:text-white hover:bg-emerald-900/50 rounded transition" title="Google Drive Pfad anpassen">
      <i class="fa-solid fa-gear"></i>
    </button>
  `;
  gdriveWrapper.querySelector('button').onclick = () => {
    if (gdrive?.exists) {
      setLocation(gdrive.path, 'gdrive');
    } else {
      openGdriveSettingsModal();
    }
  };
  container.appendChild(gdriveWrapper);

  // 5. Transfer-Hub (Sync)
  const transfer = state.onedriveInfo?.transfer;
  if (transfer) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'loc-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-950/60 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/80 transition';
    btn.title = 'Gemeinsamer Transfer-Hub für PC Zuhause, PC Geschäft, iPad & iPhone';
    btn.innerHTML = `<i class="fa-solid fa-arrows-rotate text-emerald-400"></i><span>Transfer-Hub (Sync)</span>`;
    btn.onclick = () => setLocation(transfer.path, false);
    container.appendChild(btn);
  }

  // 5b. Dynamischer USB_Stick Schnell-Button (unabhängig vom Laufwerksbuchstaben)
  if (state.usbStickDir) {
    const driveLabel = state.usbStickDir.slice(0, 2);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'loc-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-cyan-950/60 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-700/80 transition shadow-sm';
    btn.title = `USB-Stick Datenordner (${state.usbStickDir}) – erkennt Laufwerksbuchstaben automatisch`;
    btn.innerHTML = `<i class="fa-solid fa-hard-drive text-cyan-400"></i><span>USB_Stick (${driveLabel})</span>`;
    btn.onclick = async () => {
      await refreshUsbStickShortcut();
      setLocation(state.usbStickDir || `${driveLabel}\\USB_Stick`, false);
    };
    container.appendChild(btn);
  }

  // 5. Standard Systemordner
  state.systemLocations.forEach(loc => {
    if (loc.id.startsWith('onedrive') || loc.id === 'transfer_hub' || loc.id === 'icloud_drive' || loc.id === 'gdrive') return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'loc-btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition';
    let iconHtml = '<i class="fa-solid fa-folder text-amber-400"></i>';
    if (loc.icon === 'download') iconHtml = '<i class="fa-solid fa-download text-emerald-400"></i>';
    if (loc.icon === 'monitor') iconHtml = '<i class="fa-solid fa-desktop text-blue-400"></i>';
    if (loc.icon === 'image') iconHtml = '<i class="fa-solid fa-image text-purple-400"></i>';
    if (loc.icon === 'hard-drive') iconHtml = '<i class="fa-solid fa-hard-drive text-slate-400"></i>';

    btn.innerHTML = `${iconHtml}<span>${loc.name}</span>`;
    btn.onclick = () => setLocation(loc.path, false);
    container.appendChild(btn);
  });

  // 5. Gespeicherte Pfade (Favoriten)
  (state.savedPaths || []).forEach(fav => {
    // Falls Dokumente (D:) schon in den System-Buttons vorhanden ist, kein Duplikat anzeigen
    if (fav.id === 'fav_d_doc' && state.systemLocations.some(l => l.id === 'd_documents')) return;
    const wrap = document.createElement('div');
    wrap.className = 'inline-flex items-center rounded-lg border border-amber-500/50 bg-amber-950/40 p-0.5 shadow-sm group';
    wrap.innerHTML = `
      <button type="button" class="flex items-center gap-1 px-2 py-0.5 text-xs font-bold text-amber-300 hover:text-white transition" title="${toGermanDisplayPath(fav.path)}">
        <i class="fa-solid fa-star text-amber-400 text-[11px]"></i>
        <span>${fav.name}</span>
      </button>
      <button type="button" class="px-1.5 py-0.5 text-[11px] text-amber-400 hover:text-red-400 hover:bg-red-500/20 rounded transition" title="Diesen Favorit löschen">
        <i class="fa-solid fa-xmark"></i>
      </button>
    `;
    wrap.querySelector('button:first-child').onclick = () => setLocation(fav.path, false);
    wrap.querySelector('button:last-child').onclick = (e) => deleteSavedPath(fav.id, fav.name, e);
    container.appendChild(wrap);
  });

  // 6. Gespeicherte Netzwerk-Pfade
  state.networkPaths.forEach(net => {
    const wrap = document.createElement('div');
    wrap.className = 'inline-flex items-center rounded-lg border border-emerald-500/40 bg-emerald-950/40 p-0.5 shadow-sm group';
    wrap.innerHTML = `
      <button type="button" class="flex items-center gap-1 px-2 py-0.5 text-xs font-bold text-emerald-200 hover:text-white transition" title="${net.path}">
        <i class="fa-solid fa-network-wired text-emerald-400 text-[11px]"></i>
        <span>${net.name}</span>
      </button>
      <button type="button" class="px-1.5 py-0.5 text-[11px] text-emerald-400 hover:text-red-400 hover:bg-red-500/20 rounded transition" title="Diesen Netzwerkpfad löschen">
        <i class="fa-solid fa-xmark"></i>
      </button>
    `;
    wrap.querySelector('button:first-child').onclick = () => setLocation(net.path, false);
    wrap.querySelector('button:last-child').onclick = (e) => deleteNetworkPath(net.id, net.name, e);
    container.appendChild(wrap);
  });
}

// Netzwerk-Freigaben Modal Funktionen
function openAddNetworkModal() {
  document.getElementById('modal-add-network-path').classList.remove('hidden');
  setTimeout(() => document.getElementById('net-path-name').focus(), 100);
}

function closeAddNetworkModal() {
  document.getElementById('modal-add-network-path').classList.add('hidden');
}

async function submitAddNetworkPath() {
  const name = document.getElementById('net-path-name').value.trim();
  const dirPath = document.getElementById('net-path-dir').value.trim();

  if (!dirPath) {
    showToast('Bitte einen Netzwerk-Pfad eingeben', 'error');
    return;
  }

  try {
    const res = await fetch('/api/add-network-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name || dirPath, path: dirPath })
    });
    const d = await res.json();
    if (d.success) {
      state.networkPaths = d.network_paths || [];
      renderLocationShortcuts();
      showToast(`🌐 Netzwerk-Pfad "${name || dirPath}" gespeichert!`, 'success');
      closeAddNetworkModal();
    } else {
      showToast(d.error || 'Fehler beim Speichern', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function deleteNetworkPath(pathId, name, event) {
  if (event) event.stopPropagation();
  const confirmed = await showConfirmDialog({
    title: 'Netzwerkpfad entfernen',
    message: `Soll der Netzwerkpfad "${name}" wirklich aus den Favoriten entfernt werden?`,
    confirmText: 'Entfernen',
    cancelText: 'Abbrechen',
    type: 'warning'
  });
  if (!confirmed) return;

  try {
    const res = await fetch('/api/delete-network-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: pathId })
    });
    const d = await res.json();
    if (d.success) {
      state.networkPaths = d.network_paths || [];
      renderLocationShortcuts();
      showToast('Netzwerk-Pfad entfernt.', 'info');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

function openSavePathModal() {
  const cur = document.getElementById('target-directory').value.trim();
  document.getElementById('save-path-dir').value = cur;
  // Default Name Vorschlag aus letztem Ordnernamen
  let nameSuggest = '';
  if (cur) {
    const parts = cur.replace(/\\+$/, '').split('\\');
    nameSuggest = parts[parts.length - 1] || cur;
    if (nameSuggest.toLowerCase() === 'documents') {
      nameSuggest = 'Dokumente';
    }
    if (cur.toLowerCase().includes('d:\\')) {
      nameSuggest += ' (D:)';
    } else if (cur.toLowerCase().includes('c:\\')) {
      nameSuggest += ' (C:)';
    }
  }
  document.getElementById('save-path-name').value = nameSuggest;
  document.getElementById('modal-save-custom-path').classList.remove('hidden');
  setTimeout(() => document.getElementById('save-path-name').focus(), 100);
}

function closeSavePathModal() {
  document.getElementById('modal-save-custom-path').classList.add('hidden');
}

async function submitSaveCustomPath() {
  const name = document.getElementById('save-path-name').value.trim();
  const dirPath = document.getElementById('save-path-dir').value.trim();

  if (!dirPath) {
    showToast('Bitte einen Pfad eingeben', 'error');
    return;
  }

  try {
    const res = await fetch('/api/save-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name || dirPath, path: dirPath })
    });
    const d = await res.json();
    if (d.success) {
      state.savedPaths = d.saved_paths || [];
      renderLocationShortcuts();
      showToast(`⭐ Suchpfad "${name || dirPath}" als Favorit gespeichert!`, 'success');
      closeSavePathModal();
    } else {
      showToast(d.error || 'Fehler beim Speichern', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function deleteCustomPath(pathId, name, event) {
  if (event) event.stopPropagation();
  const confirmed = await showConfirmDialog({
    title: 'Suchpfad-Favorit entfernen',
    message: `Soll der gespeicherte Suchpfad "${name}" aus den Schnell-Buttons entfernt werden?`,
    confirmText: 'Entfernen',
    cancelText: 'Abbrechen',
    type: 'warning'
  });
  if (!confirmed) return;

  try {
    const res = await fetch('/api/delete-saved-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: pathId })
    });
    const d = await res.json();
    if (d.success) {
      state.savedPaths = d.saved_paths || [];
      renderLocationShortcuts();
      showToast('Pfad-Favorit entfernt.', 'info');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// ==========================================
// TAB-NAVIGATION
// ==========================================
function switchTab(tabName) {
  state.activeTab = tabName;

  // View Containers
  document.getElementById('view-search').classList.toggle('hidden', tabName !== 'search');
  document.getElementById('view-duplicates').classList.toggle('hidden', tabName !== 'duplicates');
  document.getElementById('view-rename').classList.toggle('hidden', tabName !== 'rename');

  // Nav Buttons
  document.getElementById('tab-search').classList.toggle('active', tabName === 'search');
  document.getElementById('tab-duplicates').classList.toggle('active', tabName === 'duplicates');
  document.getElementById('tab-rename').classList.toggle('active', tabName === 'rename');

  if (tabName === 'rename' && state.renameFiles.length === 0 && state.selectedFilePaths.size > 0) {
    openBatchRenameWithSelected();
  }
}

// ==========================================
// FILTER & SPEICHERORT-LOGIK
// ==========================================
function applyClientCategoryFilter() {
  if (!state.allRawFiles || state.allRawFiles.length === 0) return;

  const cat = state.currentCategory;
  if (!cat || cat === 'all') {
    state.currentFiles = [...state.allRawFiles];
  } else if (cat === 'folder') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'folder' || f.ext === 'ORDNER' || f.is_dir);
  } else if (cat === 'pdf') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'pdf' || f.ext === 'PDF');
  } else if (cat === 'word') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'word' || ['DOCX', 'DOC', 'ODT', 'RTF'].includes(f.ext));
  } else if (cat === 'excel') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'excel' || ['XLSX', 'XLS', 'CSV', 'ODS', 'XLSM'].includes(f.ext));
  } else if (cat === 'access') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'access' || ['ACCDB', 'MDB', 'ACCDE', 'ACCDR'].includes(f.ext));
  } else if (cat === 'powerpoint') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'powerpoint' || ['PPTX', 'PPT', 'PPSX', 'PPS', 'ODP'].includes(f.ext));
  } else if (cat === 'office') {
    state.currentFiles = state.allRawFiles.filter(f => ['pdf', 'word', 'excel', 'access', 'powerpoint'].includes(f.category) || ['PDF', 'DOCX', 'DOC', 'XLSX', 'XLS', 'CSV', 'ACCDB', 'MDB', 'ACCDE', 'ACCDR', 'PPTX', 'PPT', 'ODT', 'ODS'].includes(f.ext));
  } else if (cat === 'image') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'image' || ['JPG', 'JPEG', 'PNG', 'WEBP', 'GIF', 'BMP', 'SVG', 'HEIC', 'TIFF', 'TIF'].includes(f.ext));
  } else if (cat === 'video') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'video' || ['MP4', 'MKV', 'AVI', 'MOV', 'WMV', 'FLV', 'WEBM', 'M4V', 'MPG', 'MPEG', 'TS', 'M2TS', '3GP', 'VOB'].includes(f.ext));
  } else if (cat === 'audio') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'audio' || ['MP3', 'WAV', 'FLAC', 'M4A', 'AAC', 'OGG', 'WMA'].includes(f.ext));
  } else if (cat === 'email') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'email' || ['MSG', 'EML', 'PST', 'OST', 'VCF', 'ICS'].includes(f.ext));
  } else if (cat === 'archive') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'archive' || ['ZIP', 'RAR', '7Z', 'TAR', 'GZ'].includes(f.ext));
  } else if (cat === 'setup') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'setup' || ['EXE', 'MSI', 'ISO', 'BAT', 'CMD', 'APPX', 'MSIX'].includes(f.ext));
  } else if (cat === 'code') {
    state.currentFiles = state.allRawFiles.filter(f => f.category === 'code' || ['TXT', 'SRT', 'VTT', 'SUB', 'NFO', 'CFG', 'INI', 'CONF', 'LOG', 'MD', 'PY', 'JS', 'JSON', 'HTML', 'CSS', 'XML', 'PS1', 'SQL', 'YML', 'YAML'].includes(f.ext));
  } else {
    state.currentFiles = state.allRawFiles.filter(f => f.category === cat);
  }

  // Live-Suchfilter (wie in 7-Ordner-Pro: z. B. "Berge, Alm" oder Leerzeichen/Komma-getrennte Begriffe)
  const liveRaw = (document.getElementById('live-filter-query')?.value || '').trim().toLowerCase();
  if (liveRaw) {
    const tokens = liveRaw.split(/[\s,;]+/).filter(Boolean);
    if (tokens.length > 0) {
      state.currentFiles = state.currentFiles.filter(f => {
        const hay = `${f.name || ''} ${f.folder || ''} ${f.category_label || ''} ${f.target_sub || ''} ${f.ext || ''}`.toLowerCase();
        // Wenn Komma benutzt wurde -> ODER-Suche (z. B. "Berge, Alm"); bei reinem Leerzeichen -> UND-Suche
        if (liveRaw.includes(',')) {
          return tokens.some(t => hay.includes(t));
        }
        return tokens.every(t => hay.includes(t));
      });
    }
  }

  // Zähler sofort aktualisieren
  const statCount = document.getElementById('stat-count');
  if (statCount) statCount.textContent = state.currentFiles.length;

  const statSize = document.getElementById('stat-size');
  if (statSize) {
    const totalBytes = state.currentFiles.reduce((acc, cur) => acc + (cur.size || 0), 0);
    statSize.textContent = formatBytes(totalBytes);
  }

  const emptyState = document.getElementById('empty-state');
  const tableWrapper = document.getElementById('view-table-wrapper');
  const gridWrapper = document.getElementById('view-grid-wrapper');
  const resultsToolbar = document.getElementById('results-toolbar');

  if (state.currentFiles.length === 0) {
    if (emptyState) emptyState.classList.remove('hidden');
    if (tableWrapper) tableWrapper.classList.add('hidden');
    if (gridWrapper) gridWrapper.classList.add('hidden');
  } else {
    if (emptyState) emptyState.classList.add('hidden');
    if (resultsToolbar) resultsToolbar.classList.remove('hidden');
    applySorting();
    renderResults();
  }
}

// ==========================================
// FLUENT SCHNELLFILTER (ZEITRAUM, DATUM, GRÖSSE)
// ==========================================
function _formatDateDE(d) {
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

function _formatDateISO(d) {
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${yyyy}-${mm}-${dd}`;
}

function _updateQuickFilterPillsUI() {
  document.querySelectorAll('#fluent-quick-filters [data-zeitraum]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.zeitraum === state.activeTimeframe);
  });
  const minVal = (document.getElementById('filter-min-size')?.value || '').trim().toUpperCase().replace(/\s+/g, ' ');
  document.querySelectorAll('#fluent-quick-filters [data-size-preset]').forEach(btn => {
    const p = (btn.dataset.sizePreset || '').trim().toUpperCase();
    btn.classList.toggle('active', minVal !== '' && (minVal === p || state.activeSizePreset === p));
  });
}

function setQuickTimeframe(key) {
  const fromEl = document.getElementById('filter-date-from');
  const toEl = document.getElementById('filter-date-to');
  const natFrom = document.getElementById('native-date-from');
  const natTo = document.getElementById('native-date-to');

  if (state.activeTimeframe === key) {
    state.activeTimeframe = '';
    if (fromEl) fromEl.value = '';
    if (toEl) toEl.value = '';
    if (natFrom) natFrom.value = '';
    if (natTo) natTo.value = '';
  } else {
    state.activeTimeframe = key;
    const now = new Date();
    let start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (key === 'week') {
      const day = (now.getDay() + 6) % 7; // Montag = 0
      start.setDate(start.getDate() - day);
    } else if (key === 'month') {
      start = new Date(now.getFullYear(), now.getMonth(), 1);
    } else if (key === 'year') {
      start = new Date(now.getFullYear(), 0, 1);
    }
    if (fromEl) fromEl.value = _formatDateDE(start);
    if (toEl) toEl.value = _formatDateDE(now);
    if (natFrom) natFrom.value = _formatDateISO(start);
    if (natTo) natTo.value = _formatDateISO(now);
  }
  _updateQuickFilterPillsUI();
  executeSearch();
}

function openNativeDatePicker(which) {
  const el = document.getElementById(which === 'from' ? 'native-date-from' : 'native-date-to');
  if (!el) return;
  try {
    if (typeof el.showPicker === 'function') {
      el.showPicker();
      return;
    }
  } catch (_e) {}
  el.click();
}

function syncFromNativeDate(which, isoVal) {
  if (!isoVal) return;
  const parts = isoVal.split('-');
  if (parts.length !== 3) return;
  const de = `${parts[2]}.${parts[1]}.${parts[0]}`;
  const target = document.getElementById(which === 'from' ? 'filter-date-from' : 'filter-date-to');
  if (target) target.value = de;
  state.activeTimeframe = '';
  _updateQuickFilterPillsUI();
  executeSearch();
}

function onDateTextChanged() {
  state.activeTimeframe = '';
  _updateQuickFilterPillsUI();
}

function onMinSizeInput() {
  state.activeSizePreset = '';
  _updateQuickFilterPillsUI();
}

function toggleMinSizePreset(preset) {
  const input = document.getElementById('filter-min-size');
  const normP = preset.trim().toUpperCase();
  if (state.activeSizePreset === normP) {
    state.activeSizePreset = '';
    if (input) input.value = '';
  } else {
    state.activeSizePreset = normP;
    if (input) input.value = preset;
  }
  _updateQuickFilterPillsUI();
  executeSearch();
}

function onLiveFilterInput() {
  if (state.allRawFiles && state.allRawFiles.length > 0) {
    applyClientCategoryFilter();
  }
}

function clearAllQuickFilters() {
  state.activeTimeframe = '';
  state.activeSizePreset = '';
  ['live-filter-query', 'filter-date-from', 'filter-date-to', 'native-date-from', 'native-date-to', 'filter-min-size', 'max-size-input', 'custom-extensions'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  _updateQuickFilterPillsUI();
  if (state.allRawFiles && state.allRawFiles.length > 0) {
    executeSearch();
  }
}

function setCategoryFilter(category, btnElement) {
  const prevSearchedCat = state.lastSearchedCategory || 'all';
  state.currentCategory = category;

  document.querySelectorAll('#category-filter-group .cat-pill').forEach(btn => {
    btn.classList.remove('active');
  });
  if (btnElement) {
    btnElement.classList.add('active');
  }

  // Wenn vorherige Suche bereits alle Typen ('all') geladen hat und nicht speziell nach Ordnern gesucht wird,
  // zuerst im Speicher filtern; falls vorher ein spezifischer Filter aktiv war oder 'folder' gewählt wurde -> neu suchen
  if (state.allRawFiles && state.allRawFiles.length > 0 && prevSearchedCat === 'all' && category !== 'folder') {
    applyClientCategoryFilter();
    if (state.currentFiles.length > 0 || category === 'all') {
      showToast(`Filter aktiv: ${category.toUpperCase()} (${state.currentFiles.length} von ${state.allRawFiles.length} Treffern)`, 'info');
      return;
    }
  }
  executeSearch();
}

function setLocation(path, isOneDrive) {
  const dirInput = document.getElementById('target-directory');
  if (dirInput) {
    dirInput.value = path;
  }
  
  if (isOneDrive === 'personal' || isOneDrive === 'business') {
    setSearchScope('onedrive');
  } else if (isOneDrive === 'icloud') {
    setSearchScope('folder');
  } else if (path === 'THIS_PC') {
    setSearchScope('pc');
  } else if (path === 'NETWORK') {
    setSearchScope('network');
  } else {
    setSearchScope('folder');
  }

  showToast(`Verzeichnis gewählt: ${path}`, 'info');
  executeSearch();
}

function onOneDriveToggleChange() {
  const toggle = document.getElementById('toggle-only-onedrive');
  if (toggle && toggle.checked && state.onedrivePath) {
    document.getElementById('target-directory').value = state.onedrivePath;
  }
  executeSearch();
}

function toggleAdvancedFilters() {
  const filterBox = document.getElementById('advanced-filters');
  const chevron = document.getElementById('adv-chevron');
  const isHidden = filterBox.classList.contains('hidden');
  filterBox.classList.toggle('hidden', !isHidden);
  if (chevron) {
    chevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
  }
}

// ==========================================
// DATEISUCHE AUSFÜHREN
// ==========================================
async function executeSearch() {
  const query = document.getElementById('search-query')?.value.trim() || '';
  const directory = document.getElementById('target-directory')?.value.trim() || '';
  const onlyOneDrive = (state.searchScope === 'onedrive') || (document.getElementById('toggle-only-onedrive')?.checked ?? false);
  const customExts = document.getElementById('custom-extensions')?.value.trim() || '';
  const minSizeText = document.getElementById('filter-min-size')?.value.trim() || '';
  const maxSizeText = document.getElementById('max-size-input')?.value.trim() || '';
  const modifiedAfter = document.getElementById('filter-date-from')?.value.trim() || null;
  const modifiedBefore = document.getElementById('filter-date-to')?.value.trim() || null;

  if (!directory) {
    showToast('Bitte ein Suchverzeichnis angeben!', 'error');
    return;
  }

  // UI Vorbereiten (Loading)
  document.getElementById('search-spinner').classList.remove('hidden');
  document.getElementById('empty-state').classList.add('hidden');
  document.getElementById('results-toolbar').classList.add('hidden');
  document.getElementById('view-table-wrapper').classList.add('hidden');
  document.getElementById('view-grid-wrapper').classList.add('hidden');
  document.getElementById('search-spinner-path').textContent = `Verzeichnis: ${directory}`;

  state.selectedFilePaths.clear();
  updateSelectedCounter();

  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        directory: directory,
        query: query,
        category: state.currentCategory,
        extensions: customExts,
        min_size_text: minSizeText,
        max_size_text: maxSizeText,
        modified_after: modifiedAfter,
        modified_before: modifiedBefore,
        only_onedrive: onlyOneDrive,
        max_results: 3000
      })
    });

    const data = await response.json();
    state.lastSearchedCategory = state.currentCategory || 'all';
    if (data.search_history) state.searchHistory = data.search_history;
    if (data.saved_searches) state.savedSearches = data.saved_searches;
    renderSearchHistoryAndSaved();

    state.allRawFiles = data.results || [];
    const hasLiveText = Boolean((document.getElementById('live-filter-query')?.value || '').trim());
    if ((state.currentCategory && state.currentCategory !== 'all') || hasLiveText) {
      applyClientCategoryFilter();
    } else {
      state.currentFiles = [...state.allRawFiles];
    }

    // Stats aktualisieren
    document.getElementById('stat-count').textContent = state.currentFiles.length;
    if (!hasLiveText) {
      document.getElementById('stat-size').textContent = data.total_size_formatted || '0 B';
    }
    document.getElementById('stat-time').textContent = `${data.elapsed_seconds || 0}s`;

    if (state.currentFiles.length === 0) {
      document.getElementById('empty-state').classList.remove('hidden');
    } else {
      document.getElementById('results-toolbar').classList.remove('hidden');
      updateStickyHeaderPositions();
      applySorting();
      renderResults();
    }
  } catch (err) {
    showToast(`Fehler bei der Suche: ${err.message}`, 'error');
    document.getElementById('empty-state').classList.remove('hidden');
  } finally {
    document.getElementById('search-spinner').classList.add('hidden');
  }
}

// ==========================================
// SUCH-HISTORY & GESPEICHERTE SUCHEN
// ==========================================
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getCategoryBadgeLabel(cat) {
  const map = {
    folder: 'Ordner',
    pdf: 'PDF',
    word: 'Word',
    excel: 'Excel',
    access: 'Access',
    powerpoint: 'PowerPoint',
    office: 'Office',
    image: 'Bilder',
    video: 'Video',
    audio: 'Audio',
    email: 'E-Mail',
    archive: 'Archiv',
    setup: 'Program',
    code: 'Text'
  };
  return map[cat] || '';
}

function renderSearchHistoryAndSaved() {
  const panel = document.getElementById('search-history-panel');
  const savedRow = document.getElementById('saved-searches-row');
  const savedList = document.getElementById('saved-searches-list');
  const recentRow = document.getElementById('recent-searches-row');
  const recentList = document.getElementById('recent-searches-list');
  if (!panel || !savedRow || !savedList || !recentRow || !recentList) return;

  const saved = state.savedSearches || [];
  const history = state.searchHistory || [];

  if (saved.length === 0 && history.length === 0) {
    panel.classList.add('hidden');
    return;
  }
  panel.classList.remove('hidden');

  // 1. Gespeicherte Suchen (Favoriten)
  savedList.innerHTML = '';
  if (saved.length > 0) {
    savedRow.classList.remove('hidden');
    saved.forEach(item => {
      const catLabel = getCategoryBadgeLabel(item.category);
      const chip = document.createElement('div');
      chip.className = 'inline-flex items-center rounded-lg border border-amber-500/40 bg-amber-950/40 hover:bg-amber-900/50 transition overflow-hidden';

      const btnRun = document.createElement('button');
      btnRun.type = 'button';
      btnRun.className = 'flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold text-amber-200 hover:text-white transition';
      btnRun.title = `Gespeicherte Suche ausführen: "${item.query}"`;
      btnRun.innerHTML = `<i class="fa-solid fa-star text-amber-400 text-[10px]"></i><span>${escapeHtml(item.name || item.query)}</span>` +
        (catLabel ? `<span class="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-bold">${catLabel}</span>` : '');
      btnRun.onclick = () => applySavedOrHistorySearch(item.query, item.category || 'all');

      const btnDel = document.createElement('button');
      btnDel.type = 'button';
      btnDel.className = 'px-1.5 py-1 text-[10px] text-amber-400/70 hover:text-red-400 hover:bg-red-950/50 border-l border-amber-500/20 transition';
      btnDel.title = 'Gespeicherte Suche entfernen';
      btnDel.innerHTML = '<i class="fa-solid fa-xmark"></i>';
      btnDel.onclick = (e) => {
        e.stopPropagation();
        deleteSavedSearch(item.id);
      };

      chip.appendChild(btnRun);
      chip.appendChild(btnDel);
      savedList.appendChild(chip);
    });
  } else {
    savedRow.classList.add('hidden');
  }

  // 2. Letzte Suchen (Such-History)
  recentList.innerHTML = '';
  if (history.length > 0) {
    recentRow.classList.remove('hidden');
    history.slice(0, 12).forEach(item => {
      const catLabel = getCategoryBadgeLabel(item.category);
      const isAlreadySaved = saved.some(s =>
        (s.query || '').toLowerCase() === (item.query || '').toLowerCase() &&
        (s.category || 'all') === (item.category || 'all')
      );

      const chip = document.createElement('div');
      chip.className = 'inline-flex items-center rounded-lg border border-slate-700/80 bg-slate-900/90 hover:bg-slate-800 transition overflow-hidden';

      const btnRun = document.createElement('button');
      btnRun.type = 'button';
      btnRun.className = 'flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white transition';
      btnRun.title = `Erneut suchen: "${item.query}"`;
      btnRun.innerHTML = `<i class="fa-solid fa-magnifying-glass text-slate-500 text-[10px]"></i><span>${escapeHtml(item.query)}</span>` +
        (catLabel ? `<span class="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-semibold">${catLabel}</span>` : '');
      btnRun.onclick = () => applySavedOrHistorySearch(item.query, item.category || 'all');
      chip.appendChild(btnRun);

      if (!isAlreadySaved) {
        const btnPin = document.createElement('button');
        btnPin.type = 'button';
        btnPin.className = 'px-1.5 py-1 text-[10px] text-slate-500 hover:text-amber-400 hover:bg-amber-950/40 border-l border-slate-800 transition';
        btnPin.title = 'Für wiederkehrende Suche dauerhaft speichern';
        btnPin.innerHTML = '<i class="fa-regular fa-star"></i>';
        btnPin.onclick = (e) => {
          e.stopPropagation();
          pinHistorySearch(item.query, item.category || 'all');
        };
        chip.appendChild(btnPin);
      }

      const btnDel = document.createElement('button');
      btnDel.type = 'button';
      btnDel.className = 'px-1.5 py-1 text-[10px] text-slate-500 hover:text-red-400 hover:bg-red-950/40 border-l border-slate-800 transition';
      btnDel.title = 'Aus Such-History entfernen';
      btnDel.innerHTML = '<i class="fa-solid fa-xmark"></i>';
      btnDel.onclick = (e) => {
        e.stopPropagation();
        deleteSearchHistoryItem(item.id);
      };
      chip.appendChild(btnDel);

      recentList.appendChild(chip);
    });
  } else {
    recentRow.classList.add('hidden');
  }
}

function applySavedOrHistorySearch(query, category) {
  const input = document.getElementById('search-query');
  if (input) input.value = query || '';

  const targetCat = category || 'all';
  state.currentCategory = targetCat;
  document.querySelectorAll('#category-filter-group .cat-pill').forEach(btn => {
    btn.classList.remove('active');
    const onclickAttr = btn.getAttribute('onclick') || '';
    if (onclickAttr.includes(`'${targetCat}'`)) {
      btn.classList.add('active');
    }
  });

  executeSearch();
}

async function saveCurrentSearch() {
  const query = document.getElementById('search-query')?.value.trim() || '';
  if (!query) {
    showToast('Bitte zuerst einen Suchbegriff eingeben, um ihn zu speichern!', 'error');
    document.getElementById('search-query')?.focus();
    return;
  }
  await pinHistorySearch(query, state.currentCategory || 'all');
}

async function pinHistorySearch(query, category) {
  try {
    const res = await fetch('/api/save-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query, category: category || 'all' })
    });
    const d = await res.json();
    if (d.success) {
      state.savedSearches = d.saved_searches || [];
      renderSearchHistoryAndSaved();
      showToast(`⭐ Suche "${query}" dauerhaft gespeichert!`, 'success');
    } else {
      showToast(d.error || 'Suche konnte nicht gespeichert werden', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function deleteSavedSearch(id) {
  try {
    const res = await fetch('/api/delete-saved-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: id })
    });
    const d = await res.json();
    if (d.success) {
      state.savedSearches = d.saved_searches || [];
      renderSearchHistoryAndSaved();
      showToast('Gespeicherte Suche entfernt.', 'info');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function deleteSearchHistoryItem(id) {
  try {
    const res = await fetch('/api/delete-search-history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: id })
    });
    const d = await res.json();
    if (d.success) {
      state.searchHistory = d.search_history || [];
      renderSearchHistoryAndSaved();
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function clearSearchHistory() {
  try {
    const res = await fetch('/api/delete-search-history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clear_all: true })
    });
    const d = await res.json();
    if (d.success) {
      state.searchHistory = [];
      renderSearchHistoryAndSaved();
      showToast('Such-History geleert.', 'info');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// ==========================================
// ERGEBNISSE RENDERN (TABELLE / KACHELN)
// ==========================================
function setViewMode(mode) {
  state.viewMode = mode;
  document.getElementById('btn-view-table').classList.toggle('bg-slate-700', mode === 'table');
  document.getElementById('btn-view-table').classList.toggle('text-white', mode === 'table');
  document.getElementById('btn-view-grid').classList.toggle('bg-slate-700', mode === 'grid');
  document.getElementById('btn-view-grid').classList.toggle('text-white', mode === 'grid');
  renderResults();
}

function renderResults() {
  const tableWrapper = document.getElementById('view-table-wrapper');
  const gridWrapper = document.getElementById('view-grid-wrapper');
  const tbody = document.getElementById('results-tbody');
  const emptyState = document.getElementById('empty-state');

  if (emptyState) {
    emptyState.classList.add('hidden');
  }

  if (state.viewMode === 'table') {
    tableWrapper.classList.remove('hidden');
    gridWrapper.classList.add('hidden');
    tbody.innerHTML = '';

    state.currentFiles.forEach((file) => {
      const isSelected = state.selectedFilePaths.has(file.path);
      const isPreviewActive = state.activePreviewPath === file.path;
      const isDup = file.dup_status === 'Duplikat';
      const row = document.createElement('tr');
      row.className = `result-row transition cursor-pointer select-none ${isSelected ? 'selected' : ''} ${isPreviewActive ? 'active-preview-row' : ''} ${isDup && !isSelected && !isPreviewActive ? 'row-dup-highlight' : ''}`;
      row.onclick = () => selectPreviewRow(file);
      row.ondblclick = () => openFile(file.path);

      const fileIcon = getCategoryIconHtml(file.category, file.ext);
      let cloudTag = '';
      if (file.is_gdrive || file.cloud_type === 'gdrive' || (file.path && (file.path.toLowerCase().includes('google drive') || file.path.toLowerCase().includes('meine ablage')))) {
        cloudTag = `<span class="inline-flex items-center text-[10px] text-emerald-300 bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-500/30 ml-1.5 font-semibold" title="In Google Drive gesichert"><i class="fa-brands fa-google-drive mr-1"></i>Drive</span>`;
      } else if (file.is_icloud || file.cloud_type === 'icloud' || (file.path && file.path.toLowerCase().includes('\\iclouddrive'))) {
        cloudTag = `<span class="inline-flex items-center text-[10px] text-sky-300 bg-sky-500/15 px-1.5 py-0.5 rounded border border-sky-500/30 ml-1.5 font-semibold" title="In iCloud Drive gesichert"><i class="fa-brands fa-apple mr-1"></i>iCloud</span>`;
      } else if (file.onedrive_type === 'personal') {
        cloudTag = `<span class="inline-flex items-center text-[10px] text-sky-400 bg-sky-500/10 px-1.5 py-0.5 rounded border border-sky-500/20 ml-1.5" title="In OneDrive Privat gesichert"><i class="fa-solid fa-cloud mr-1"></i>Privat</span>`;
      } else if (file.onedrive_type === 'business') {
        cloudTag = `<span class="inline-flex items-center text-[10px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20 ml-1.5" title="In OneDrive Geschäft gesichert"><i class="fa-solid fa-building mr-1"></i>Geschäft</span>`;
      } else if (file.is_onedrive) {
        cloudTag = `<span class="inline-flex items-center text-[10px] text-sky-400 bg-sky-500/10 px-1.5 py-0.5 rounded border border-sky-500/20 ml-1.5" title="OneDrive"><i class="fa-solid fa-cloud mr-1"></i>OneDrive</span>`;
      }

      const dupStatus = file.dup_status || '—';
      let dupCellHtml = `<span class="text-slate-400">—</span>`;
      if (dupStatus === 'Original') {
        dupCellHtml = `<span class="text-blue-500 font-semibold">Original</span>`;
      } else if (dupStatus === 'Duplikat') {
        dupCellHtml = `<span class="text-amber-500 font-semibold">Duplikat</span>`;
      } else if (dupStatus.includes('Cloud')) {
        dupCellHtml = `<span class="text-sky-500 font-medium whitespace-nowrap"><i class="fa-solid fa-cloud mr-1 text-[10px]"></i>Cloud</span>`;
      }

      const catLabel = file.category_label || 'Unbekannt -> Inbox';
      const targetSub = file.target_sub || '01_Eingang_Inbox';

      row.innerHTML = `
        <td class="py-1.5 px-2.5 text-center" onclick="event.stopPropagation()">
          <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleSelectFile('${escapeJs(file.path)}', this)" class="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 cursor-pointer">
        </td>
        <td class="py-1.5 px-3 font-medium text-slate-100 max-w-[230px] truncate" title="${file.name} (Doppelklick: öffnen · Klick: Vorschau)">
          <span class="inline-flex items-center gap-1.5 max-w-full truncate">
            ${fileIcon}
            <span class="truncate">${file.name}</span>
          </span>
          ${cloudTag}
        </td>
        <td class="py-1.5 px-2.5 text-center whitespace-nowrap">
          <span class="ext-badge text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/70">${file.ext || 'DATEI'}</span>
        </td>
        <td class="py-1.5 px-2.5 text-right text-slate-300 font-mono text-[11px] whitespace-nowrap">
          ${file.size_formatted}
        </td>
        <td class="py-1.5 px-2.5 text-center text-[11px] whitespace-nowrap">
          ${dupCellHtml}
        </td>
        <td class="py-1.5 px-3 text-[11px] text-slate-300 truncate max-w-[175px]" title="${catLabel}">
          ${catLabel}
        </td>
        <td class="py-1.5 px-3 text-[11px] truncate max-w-[185px]" onclick="event.stopPropagation(); openTargetFolderModal(['${escapeJs(file.path)}'])" title="Klicken zum Ändern oder direkt dorthin kopieren: ${targetSub}">
          <span class="cursor-pointer hover:underline text-blue-400 font-medium">${targetSub}</span>
        </td>
        <td class="py-1.5 px-2.5 text-center text-slate-400 whitespace-nowrap text-[11px]">
          ${file.modified_formatted}
        </td>
        <td class="py-1.5 px-3 text-slate-300 font-mono text-[11px] truncate max-w-[220px] cursor-pointer hover:text-yellow-400 transition" onclick="event.stopPropagation(); openFolder('${escapeJs(file.path)}')" title="Im Windows Explorer öffnen: ${toGermanDisplayPath(file.folder)}">
          ${toGermanDisplayPath(file.folder)}
        </td>
        <td class="py-1.5 px-3 text-right action-cell whitespace-nowrap" onclick="event.stopPropagation()">
          <div class="flex items-center justify-end gap-0.5">
            <!-- Direktes Öffnen in Standard-App -->
            <button onclick="openFile('${escapeJs(file.path)}')" class="p-1.5 rounded-lg text-blue-400 hover:text-blue-300 hover:bg-blue-500/20 transition" title="In ${getAppLabelForExt(file.ext)} öffnen">
              <i class="fa-solid fa-play text-xs"></i>
            </button>
            <!-- Speicher-Ordner wählen / kopieren -->
            <button onclick="openTargetFolderModal(['${escapeJs(file.path)}'])" class="p-1.5 rounded-lg text-sky-400 hover:text-sky-300 hover:bg-sky-500/20 transition" title="Speicher-Ordner wählen & kopieren/verschieben">
              <i class="fa-solid fa-folder-plus text-xs"></i>
            </button>
            <!-- In Explorer zeigen -->
            <button onclick="openFolder('${escapeJs(file.path)}')" class="p-1.5 rounded-lg text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/20 transition" title="Im Windows Explorer anzeigen">
              <i class="fa-solid fa-folder-open text-xs"></i>
            </button>
            <!-- Teams / Mail Teilen -->
            <button onclick="openShareModal('${escapeJs(file.path)}', '${escapeJs(file.name)}')" class="p-1.5 rounded-lg text-violet-400 hover:text-violet-300 hover:bg-violet-500/20 transition" title="Per Teams oder E-Mail senden">
              <i class="fa-solid fa-paper-plane text-xs"></i>
            </button>
            <!-- Umbenennen -->
            <button onclick="openSingleRename('${escapeJs(file.path)}', '${escapeJs(file.name)}')" class="p-1.5 rounded-lg text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/20 transition" title="Umbenennen">
              <i class="fa-solid fa-pen text-xs"></i>
            </button>
            <!-- In Papierkorb -->
            <button onclick="deleteSingleFile('${escapeJs(file.path)}')" class="p-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/20 transition" title="In Windows-Papierkorb löschen">
              <i class="fa-solid fa-trash-can text-xs"></i>
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(row);
    });
  } else {
    // Grid View
    tableWrapper.classList.add('hidden');
    gridWrapper.classList.remove('hidden');
    gridWrapper.innerHTML = '';

    state.currentFiles.forEach((file) => {
      const isSelected = state.selectedFilePaths.has(file.path);
      const card = document.createElement('div');
      card.className = `glass-card p-4 rounded-xl border border-slate-800/80 bg-slate-900/40 hover:border-indigo-500/50 transition flex flex-col justify-between space-y-3 cursor-pointer ${isSelected ? 'ring-2 ring-indigo-500 bg-indigo-950/20' : ''}`;
      card.ondblclick = () => openFile(file.path);
      
      const fileIcon = getCategoryIconHtml(file.category, file.ext, true);

      card.innerHTML = `
        <div class="flex items-start justify-between">
          <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleSelectFile('${escapeJs(file.path)}', this)" class="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 cursor-pointer" onclick="event.stopPropagation()">
          ${(file.is_icloud || file.cloud_type === 'icloud' || (file.path && file.path.toLowerCase().includes('\\iclouddrive'))) ? '<span class="text-[11px] text-sky-300 bg-sky-500/15 px-2 py-0.5 rounded border border-sky-500/30 font-semibold"><i class="fa-brands fa-apple mr-1"></i>iCloud</span>' : (file.is_onedrive ? '<span class="text-[11px] text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20 font-medium"><i class="fa-solid fa-cloud mr-1"></i>OneDrive</span>' : '')}
        </div>
        <div class="flex flex-col items-center text-center py-2 space-y-2" onclick="openFile('${escapeJs(file.path)}')">
          ${fileIcon}
          <h4 class="text-xs font-bold text-white truncate w-full" title="In ${getAppLabelForExt(file.ext)} öffnen: ${file.name}">${file.name}</h4>
          <span class="text-[11px] text-slate-300 font-mono font-medium">${file.size_formatted} &bull; ${file.modified_formatted}</span>
        </div>
        <div class="pt-2 border-t border-slate-800/80 flex items-center justify-around text-xs" onclick="event.stopPropagation()">
          <button onclick="openFile('${escapeJs(file.path)}')" class="text-blue-400 hover:text-blue-300 p-1.5" title="In ${getAppLabelForExt(file.ext)} öffnen"><i class="fa-solid fa-play"></i></button>
          <button onclick="openFolder('${escapeJs(file.path)}')" class="text-yellow-400 hover:text-yellow-300 p-1.5" title="Im Windows Explorer anzeigen"><i class="fa-solid fa-folder-open"></i></button>
          <button onclick="openShareModal('${escapeJs(file.path)}', '${escapeJs(file.name)}')" class="text-violet-400 hover:text-violet-300 p-1.5" title="Per Teams oder E-Mail senden"><i class="fa-solid fa-paper-plane"></i></button>
          <button onclick="openSingleRename('${escapeJs(file.path)}', '${escapeJs(file.name)}')" class="text-cyan-400 hover:text-cyan-300 p-1.5" title="Umbenennen"><i class="fa-solid fa-pen"></i></button>
          <button onclick="deleteSingleFile('${escapeJs(file.path)}')" class="text-rose-400 hover:text-rose-300 p-1.5" title="In Windows-Papierkorb löschen"><i class="fa-solid fa-trash-can"></i></button>
        </div>
      `;
      gridWrapper.appendChild(card);
    });
  }
  updateStickyHeaderPositions();
}

// Kategorie anhand der Dateiendung ermitteln
function getCategoryForExt(ext) {
  const e = (ext || '').replace(/^\./, '').toUpperCase().trim();
  if (e === 'ORDNER' || e === 'DIR' || e === 'FOLDER') return 'folder';
  if (['PDF'].includes(e)) return 'pdf';
  if (['DOCX', 'DOC', 'ODT', 'RTF'].includes(e)) return 'word';
  if (['XLSX', 'XLS', 'CSV', 'ODS', 'XLSM', 'XLSB'].includes(e)) return 'excel';
  if (['ACCDB', 'MDB', 'ACCDE', 'ACCDR'].includes(e)) return 'access';
  if (['PPTX', 'PPT', 'ODP', 'PPSX'].includes(e)) return 'powerpoint';
  if (['JPG', 'JPEG', 'PNG', 'WEBP', 'GIF', 'BMP', 'SVG', 'ICO', 'HEIC', 'TIFF', 'TIF'].includes(e)) return 'image';
  if (['MP4', 'MKV', 'AVI', 'MOV', 'WMV', 'WEBM', 'M4V'].includes(e)) return 'video';
  if (['MP3', 'WAV', 'FLAC', 'M4A', 'AAC', 'OGG', 'WMA'].includes(e)) return 'audio';
  if (['MSG', 'EML', 'PST', 'OST', 'VCF', 'ICS'].includes(e)) return 'email';
  if (['ZIP', 'RAR', '7Z', 'TAR', 'GZ'].includes(e)) return 'archive';
  if (['EXE', 'MSI', 'ISO', 'BAT', 'CMD', 'APPX', 'MSIX'].includes(e)) return 'setup';
  if (['TXT', 'SRT', 'VTT', 'SUB', 'NFO', 'CFG', 'INI', 'CONF', 'LOG', 'MD', 'PY', 'JS', 'TS', 'JSON', 'HTML', 'CSS', 'XML', 'PS1', 'SQL', 'YML', 'YAML', 'ENV', 'TOML'].includes(e)) return 'code';
  return 'other';
}

// App-Bezeichnung ermitteln je nach Dateiendung
function getAppLabelForExt(ext) {
  const e = (ext || '').replace(/^\./, '').toLowerCase().trim();
  if (e === 'ordner' || e === 'dir' || e === 'folder') return 'Windows Explorer (Ordner)';
  if (e === 'pdf') return 'PDF X';
  if (['accdb', 'mdb', 'accde', 'accdr'].includes(e)) return 'Microsoft Access';
  if (['docx', 'doc', 'rtf', 'odt'].includes(e)) return 'Microsoft Word';
  if (['xlsx', 'xls', 'csv', 'ods', 'xlsm', 'xlsb'].includes(e)) return 'Microsoft Excel';
  if (['pptx', 'ppt', 'ppsx', 'odp'].includes(e)) return 'PowerPoint';
  if (['msg', 'eml', 'pst', 'ost', 'vcf', 'ics'].includes(e)) return 'Outlook / Mail';
  if (['exe', 'msi', 'iso', 'cmd', 'appx', 'msix'].includes(e)) return 'Programm / Anwendung';
  if (['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg', 'wma'].includes(e)) return 'Audio-Player';
  if (['mp4', 'mkv', 'avi', 'mov', 'wmv', 'webm', 'flv', 'm4v'].includes(e)) return 'Video-Player';
  if (['srt', 'vtt', 'sub'].includes(e)) return 'Windows-Editor (Untertitel)';
  if (['txt', 'log', 'json', 'xml', 'md', 'ini', 'cfg', 'conf', 'nfo', 'yml', 'yaml', 'sql', 'bat', 'ps1', 'py', 'js', 'ts', 'html', 'css', 'env', 'toml'].includes(e)) return 'Windows-Editor';
  if (!e || e === 'datei') return 'Editor / Öffnen mit…';
  return 'Standard-App';
}

// Icon Helfer je nach Kategorie & Dateiendung
function getCategoryIconHtml(category, ext, large = false) {
  const sizeClass = large ? 'text-3xl' : 'text-base';
  const e = (ext || '').replace(/^\./, '').toUpperCase().trim();

  // Ordner / Verzeichnisse (Gelbes / goldenes Ordner-Symbol statt graues Blatt!)
  if (category === 'folder' || e === 'ORDNER' || e === 'DIR' || e === 'FOLDER') {
    return `<i class="fa-solid fa-folder text-amber-400 ${sizeClass}" title="Ordner / Verzeichnis"></i>`;
  }

  if (category === 'access' || ['ACCDB', 'MDB', 'ACCDE', 'ACCDR'].includes(e)) {
    return `<i class="fa-solid fa-database text-rose-500 ${sizeClass}" title="Microsoft Access Datenbank (.${e.toLowerCase()})"></i>`;
  }
  if (['SRT', 'VTT', 'SUB'].includes(e)) {
    return `<i class="fa-solid fa-closed-captioning text-amber-400 ${sizeClass}" title="Untertitel-Textdatei (.${e.toLowerCase()})"></i>`;
  }
  if (category === 'powerpoint' || ['PPTX', 'PPT', 'PPSX', 'ODP'].includes(e)) {
    return `<i class="fa-solid fa-file-powerpoint text-orange-500 ${sizeClass}" title="PowerPoint (.${e.toLowerCase()})"></i>`;
  }
  if (category === 'video' || ['MP4', 'MKV', 'AVI', 'MOV', 'WMV', 'WEBM'].includes(e)) {
    return `<i class="fa-solid fa-file-video text-pink-400 ${sizeClass}" title="Video (.${e.toLowerCase()})"></i>`;
  }
  if (category === 'audio' || ['MP3', 'WAV', 'FLAC', 'M4A', 'AAC', 'OGG', 'WMA'].includes(e)) {
    return `<i class="fa-solid fa-file-audio text-teal-400 ${sizeClass}" title="Audio (.${e.toLowerCase()})"></i>`;
  }
  if (category === 'email' || ['MSG', 'EML', 'PST', 'OST', 'VCF', 'ICS'].includes(e)) {
    return `<i class="fa-solid fa-envelope text-sky-400 ${sizeClass}" title="E-Mail / Kontakt (.${e.toLowerCase()})"></i>`;
  }
  if (category === 'setup' || ['EXE', 'MSI', 'ISO', 'BAT', 'CMD', 'APPX', 'MSIX'].includes(e)) {
    return `<i class="fa-solid fa-box text-emerald-400 ${sizeClass}" title="Programme / Setup (.${e.toLowerCase()})"></i>`;
  }

  switch (category) {
    case 'folder':
      return `<i class="fa-solid fa-folder text-amber-400 ${sizeClass}" title="Ordner / Verzeichnis"></i>`;
    case 'pdf':
      return `<i class="fa-solid fa-file-pdf text-red-500 ${sizeClass}" title="PDF-Dokument"></i>`;
    case 'word':
      return `<i class="fa-solid fa-file-word text-blue-500 ${sizeClass}" title="Microsoft Word"></i>`;
    case 'excel':
      return `<i class="fa-solid fa-file-excel text-emerald-500 ${sizeClass}" title="Microsoft Excel"></i>`;
    case 'image':
      return `<i class="fa-solid fa-file-image text-purple-400 ${sizeClass}" title="Bild (${e})"></i>`;
    case 'archive':
      return `<i class="fa-solid fa-file-zipper text-yellow-500 ${sizeClass}" title="Archiv (${e})"></i>`;
    case 'code':
      return `<i class="fa-solid fa-file-lines text-cyan-400 ${sizeClass}" title="Text / Skript (${e})"></i>`;
    default:
      if (!e || e === 'DATEI') {
        return `<i class="fa-solid fa-file-circle-question text-slate-400 ${sizeClass}" title="Datei ohne Endung (wird bei Text im Editor geöffnet)"></i>`;
      }
      return `<i class="fa-solid fa-file text-slate-400 ${sizeClass}" title="Dateityp: .${e.toLowerCase()}"></i>`;
  }
}

// ==========================================
// AUSWAHL & SORTIERUNG
// ==========================================
function toggleSelectFile(path, checkbox) {
  if (checkbox.checked) {
    state.selectedFilePaths.add(path);
  } else {
    state.selectedFilePaths.delete(path);
  }
  updateSelectedCounter();
  renderResults();
}

function toggleSelectAll(masterCheckbox) {
  if (masterCheckbox.checked) {
    state.currentFiles.forEach(f => state.selectedFilePaths.add(f.path));
  } else {
    state.selectedFilePaths.clear();
  }
  updateSelectedCounter();
  renderResults();
}

function updateSelectedCounter() {
  const count = state.selectedFilePaths.size;
  const counterEl = document.getElementById('selected-counter');
  if (counterEl) {
    counterEl.textContent = `${count} ausgewählt`;
  }
  const renameBadge = document.getElementById('badge-rename-count');
  if (renameBadge) {
    renameBadge.textContent = count;
    renameBadge.classList.toggle('hidden', count === 0);
  }
  const sevenBadge = document.getElementById('badge-seven-folder-count');
  if (sevenBadge) {
    sevenBadge.textContent = count;
    sevenBadge.classList.toggle('hidden', count === 0);
  }
  const tfBadge = document.getElementById('badge-target-folder-count');
  if (tfBadge) {
    tfBadge.textContent = count;
    tfBadge.classList.toggle('hidden', count === 0);
  }
  const deleteBtn = document.getElementById('btn-delete-selected');
  const deleteCountEl = document.getElementById('delete-selected-count');
  if (deleteBtn) {
    if (deleteCountEl) {
      deleteCountEl.textContent = count;
    }
    deleteBtn.classList.toggle('hidden', count === 0);
  }
  updateStickyHeaderPositions();
}

function sortResults(column) {
  if (state.sortCol === column) {
    state.sortAsc = !state.sortAsc;
  } else {
    state.sortCol = column;
    state.sortAsc = true;
  }
  applySorting();
  renderResults();

  const colNames = {
    ext: 'Dateityp',
    name: 'Dateiname',
    folder: 'Gefunden in (Pfad)',
    size: 'Dateigröße',
    modified: 'Änderungsdatum',
    dup_status: 'Original / Duplikat',
    category_label: 'Erkannte Kategorie',
    target_sub: 'Zielordner'
  };
  const dirLabel = state.sortAsc ? 'aufsteigend ▲' : 'absteigend ▼';
  showToast(`Sortiert nach ${colNames[column] || column} (${dirLabel})`, 'info');
}

function applySorting() {
  state.currentFiles.sort((a, b) => {
    if (state.sortCol === 'ext') {
      const extA = ((a.ext && a.ext !== 'DATEI') ? a.ext : 'ZZZ_DATEI').toLowerCase();
      const extB = ((b.ext && b.ext !== 'DATEI') ? b.ext : 'ZZZ_DATEI').toLowerCase();
      if (extA < extB) return state.sortAsc ? -1 : 1;
      if (extA > extB) return state.sortAsc ? 1 : -1;
      const nameA = (a.name || '').toLowerCase();
      const nameB = (b.name || '').toLowerCase();
      return nameA.localeCompare(nameB, 'de');
    }

    if (state.sortCol === 'dup_status') {
      const rank = s => (s === 'Original' ? 0 : s === 'Duplikat' ? 1 : (s && s.includes('Cloud') ? 2 : 3));
      const rA = rank(a.dup_status);
      const rB = rank(b.dup_status);
      if (rA !== rB) return state.sortAsc ? (rA - rB) : (rB - rA);
      const gA = (a.dup_group || a.name || '').toLowerCase();
      const gB = (b.dup_group || b.name || '').toLowerCase();
      return gA.localeCompare(gB, 'de');
    }

    if (state.sortCol === 'size') {
      const sA = Number(a.size || 0);
      const sB = Number(b.size || 0);
      return state.sortAsc ? (sA - sB) : (sB - sA);
    }

    let valA = a[state.sortCol] ?? '';
    let valB = b[state.sortCol] ?? '';
    if (typeof valA === 'string' && typeof valB === 'string') {
      const cmp = valA.localeCompare(valB, 'de', { sensitivity: 'base' });
      if (cmp !== 0) return state.sortAsc ? cmp : -cmp;
      if (state.sortCol === 'name') {
        const dRank = s => (s === 'Original' ? 0 : s === 'Duplikat' ? 1 : 2);
        return dRank(a.dup_status) - dRank(b.dup_status);
      }
      return 0;
    }
    if (valA < valB) return state.sortAsc ? -1 : 1;
    if (valA > valB) return state.sortAsc ? 1 : -1;
    return 0;
  });
}

// ==========================================
// DATEIAKTIONEN: ÖFFNEN, ÖFFNEN MIT, BEARBEITEN, DRUCKEN, TEAMS, MAIL
// ==========================================
function triggerDesktopProtocol(url) {
  const a = document.createElement('a');
  a.href = url;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => a.remove(), 1000);
}

async function openFile(path) {
  try {
    const res = await fetch('/api/open-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });
    const d = await res.json();
    if (d.success) {
      if (d.use_browser_protocol && d.protocol_url) {
        triggerDesktopProtocol(d.protocol_url);
      }
      showToast(d.message || 'Datei wird in App geöffnet...', 'success');
    } else {
      showToast(d.error || 'Fehler beim Öffnen', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function openWith(path) {
  try {
    const res = await fetch('/api/open-with', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });
    const d = await res.json();
    if (d.success) {
      showToast(d.message || 'Windows "App auswählen" geöffnet. Bitte Taskleiste beachten.', 'info');
    } else {
      showToast(d.error || 'Fehler beim Aufrufen', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function editFile(path) {
  try {
    const res = await fetch('/api/edit-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });
    const d = await res.json();
    if (d.success) {
      showToast(d.message || 'Datei im Bearbeitungsprogramm geöffnet', 'info');
    } else {
      showToast(d.error || 'Fehler beim Bearbeiten', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function saveFileContent(path, content) {
  try {
    const res = await fetch('/api/save-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, content: content })
    });
    const d = await res.json();
    if (d.success) {
      showToast('💾 Änderungen erfolgreich auf Festplatte gespeichert!', 'success');
      // Update metadata in preview
      const meta = document.getElementById('preview-modal-meta');
      if (meta) {
        meta.textContent = `${d.size_formatted} • ${d.modified_formatted} • ${path}`;
      }
    } else {
      showToast(d.error || 'Fehler beim Speichern', 'error');
    }
  } catch (err) {
    showToast(`Fehler beim Speichern: ${err.message}`, 'error');
  }
}

async function openFolder(path) {
  try {
    const res = await fetch('/api/open-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });
    const d = await res.json();
    if (d.success) {
      if (d.use_browser_protocol && d.protocol_url) {
        triggerDesktopProtocol(d.protocol_url);
      }
      showToast(d.message || 'Im Windows Explorer geöffnet', 'info');
    } else {
      showToast(d.error || 'Pfad konnte nicht geöffnet werden', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function printSingleFile(path) {
  try {
    showToast('Druckauftrag wird an Windows übergeben...', 'info');
    const res = await fetch('/api/print-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });
    const d = await res.json();
    if (d.success) {
      showToast('Druckauftrag erfolgreich an Standarddrucker gesendet!', 'success');
    } else {
      showToast(d.error || 'Druckfehler', 'error');
    }
  } catch (err) {
    showToast(`Druckfehler: ${err.message}`, 'error');
  }
}

function printSearchResults() {
  window.print();
}

// MS Teams Integration: Datei in Clipboard ablegen für direktes Strg+V
async function copyTeams(path) {
  try {
    const res = await fetch('/api/copy-teams', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path })
    });
    const d = await res.json();
    if (d.success) {
      showToast('✨ Datei für Teams kopiert! Wechsle zu MS Teams und drücke einfach [Strg + V] zum Senden.', 'success', 6000);
    } else {
      showToast(d.error || 'Kopierfehler', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function sendEmail(path) {
  try {
    const clientLabel = getEmailClientLabel(state.emailClient);
    showToast(`Bereite E-Mail vor (${clientLabel})...`, 'info');
    const res = await fetch('/api/send-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, client: state.emailClient })
    });
    let d;
    try {
      d = await res.json();
    } catch (parseErr) {
      d = { success: false, error: 'Server-Antwort konnte nicht verarbeitet werden.' };
    }
    if (d.success) {
      if (d.web_url) {
        window.open(d.web_url, '_blank');
      }
      showToast(d.message || 'E-Mail geöffnet!', 'success', 6000);
    } else {
      showToast(d.error || 'Mail-Fehler', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// ==========================================
// E-MAIL CLIENT VERWALTUNG (Thunderbird, GMail, Outlook, Standard)
// ==========================================
function getEmailClientLabel(client) {
  switch (client) {
    case 'icloud': return 'Apple iCloud Mail';
    case 'gmail': return 'Google Mail (GMail)';
    case 'thunderbird': return 'Thunderbird';
    case 'outlook': return 'Outlook (klassisch)';
    case 'outlook_new': return 'Outlook (neu)';
    default: return 'Windows-Standard';
  }
}

function updateEmailClientUI() {
  const client = state.emailClient || 'gmail';

  // 1. Settings Modal
  const currentTextEl = document.getElementById('settings-email-current');
  if (currentTextEl) currentTextEl.textContent = getEmailClientLabel(client);

  const clients = ['gmail', 'icloud', 'thunderbird', 'outlook', 'outlook_new', 'default'];
  clients.forEach(c => {
    const btn = document.getElementById(`btn-email-${c}`);
    if (btn) {
      if (c === client) {
        btn.className = 'py-2 px-3 rounded-lg border border-indigo-500/60 bg-indigo-500/25 text-white font-bold flex items-center justify-center gap-2 transition text-xs shadow-sm active:scale-95';
      } else {
        btn.className = 'py-2 px-3 rounded-lg border border-slate-700 bg-slate-900 text-slate-300 font-medium flex items-center justify-center gap-2 transition hover:bg-slate-800 text-xs active:scale-95';
      }
    }

    // 2. Share Modal Pills
    const pill = document.getElementById(`share-pill-${c}`);
    if (pill) {
      if (c === client) {
        pill.className = 'py-1 px-1.5 rounded-lg text-[11px] font-bold border border-indigo-500/60 bg-indigo-500/25 text-white flex items-center justify-center gap-1 transition shadow-sm';
      } else {
        pill.className = 'py-1 px-1.5 rounded-lg text-[11px] font-medium border border-slate-700 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800 flex items-center justify-center gap-1 transition';
      }
    }
  });

  // 3. Share Modal Main Option
  const badgeEl = document.getElementById('share-email-badge');
  if (badgeEl) badgeEl.textContent = getEmailClientLabel(client);

  const descEl = document.getElementById('share-email-desc');
  if (descEl) {
    if (client === 'icloud') {
      descEl.textContent = 'Öffnet iCloud Mail im Browser & kopiert Datei für [Strg + V]';
    } else if (client === 'gmail') {
      descEl.textContent = 'Öffnet Google Mail im Browser & kopiert Datei für [Strg + V]';
    } else if (client === 'thunderbird') {
      descEl.textContent = 'Öffnet Thunderbird & kopiert Datei für [Strg + V]';
    } else if (client === 'outlook_new') {
      descEl.textContent = 'Öffnet neues Outlook & kopiert Datei für [Strg + V]';
    } else if (client === 'outlook') {
      descEl.textContent = 'Öffnet klassisches Outlook mit angehängter Datei';
    } else {
      descEl.textContent = 'Öffnet Standard-Mail-App & kopiert Datei für [Strg + V]';
    }
  }

  const iconEl = document.getElementById('share-email-icon');
  const iconBox = document.getElementById('share-email-icon-box');
  if (iconEl && iconBox) {
    if (client === 'icloud') {
      iconEl.className = 'fa-solid fa-cloud text-sky-400';
      iconBox.className = 'w-10 h-10 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center text-lg';
    } else if (client === 'gmail') {
      iconEl.className = 'fa-solid fa-envelope text-red-500';
      iconBox.className = 'w-10 h-10 rounded-xl bg-red-500/20 text-red-400 flex items-center justify-center text-lg';
    } else if (client === 'thunderbird') {
      iconEl.className = 'fa-solid fa-dove text-sky-400';
      iconBox.className = 'w-10 h-10 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center text-lg';
    } else if (client === 'outlook_new') {
      iconEl.className = 'fa-solid fa-envelope-open-text text-sky-400';
      iconBox.className = 'w-10 h-10 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center text-lg';
    } else if (client === 'outlook') {
      iconEl.className = 'fa-solid fa-envelope-open-text text-blue-400';
      iconBox.className = 'w-10 h-10 rounded-xl bg-blue-500/20 text-blue-400 flex items-center justify-center text-lg';
    } else {
      iconEl.className = 'fa-solid fa-desktop text-emerald-400';
      iconBox.className = 'w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-lg';
    }
  }
}

async function setEmailClient(client, showNotice = true) {
  state.emailClient = client;
  updateEmailClientUI();
  try {
    const res = await fetch('/api/set-email-client', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client: client })
    });
    const d = await res.json();
    if (d.success && showNotice) {
      showToast(`Standard-Mail: ${getEmailClientLabel(client)} ausgewählt`, 'info');
    }
  } catch (err) {
    console.error('Fehler beim Speichern des Mail-Clients:', err);
  }
}

// ==========================================
// MODAL: TEILEN & VERSENDEN
// ==========================================
function openShareModal(path, filename) {
  document.getElementById('share-modal-path').value = path;
  document.getElementById('share-modal-filename').textContent = filename;
  updateEmailClientUI();
  document.getElementById('modal-share').classList.remove('hidden');
}

function closeShareModal() {
  document.getElementById('modal-share').classList.add('hidden');
}

function actionCopyTeamsFromModal() {
  const p = document.getElementById('share-modal-path').value;
  closeShareModal();
  copyTeams(p);
}

function actionSendEmailFromModal() {
  const p = document.getElementById('share-modal-path').value;
  closeShareModal();
  sendEmail(p);
}

function actionPrintFromModal() {
  const p = document.getElementById('share-modal-path').value;
  closeShareModal();
  printSingleFile(p);
}

function actionOpenWithFromModal() {
  const p = document.getElementById('share-modal-path').value;
  closeShareModal();
  openWith(p);
}

function actionEditFromModal() {
  const p = document.getElementById('share-modal-path').value;
  closeShareModal();
  editFile(p);
}

function openWithFromPreview() {
  if (currentPreviewPath) {
    openWith(currentPreviewPath);
  }
}

function editFileFromPreview() {
  if (currentPreviewPath) {
    editFile(currentPreviewPath);
  }
}

// ==========================================
// DATEI VORSCHAU MODAL
// ==========================================
let currentPreviewPath = '';

async function previewFile(path) {
  if (path) {
    openFile(path);
  }
}

function openInBrowserViewer() {
  if (currentPreviewPath) {
    window.open('/api/preview?path=' + encodeURIComponent(currentPreviewPath), '_blank');
  }
}

function openInPdfXAutomated(path) {
  const targetPath = path || currentPreviewPath;
  if (!targetPath) return;
  openFile(targetPath);
}

function openFileFromPreview() {
  if (currentPreviewPath) {
    openFile(currentPreviewPath);
  }
}

function closePreviewModal() {
  const modal = document.getElementById('modal-preview');
  if (modal) modal.classList.add('hidden');
  const body = document.getElementById('preview-modal-body');
  if (body) body.innerHTML = '';
  currentPreviewPath = '';
}

// ==========================================
// EINZEL-UMBENENNUNG
// ==========================================
function openSingleRename(path, name) {
  document.getElementById('single-rename-oldpath').value = path;
  document.getElementById('single-rename-input').value = name;
  document.getElementById('modal-single-rename').classList.remove('hidden');
  setTimeout(() => document.getElementById('single-rename-input').focus(), 100);
}

function closeSingleRenameModal() {
  document.getElementById('modal-single-rename').classList.add('hidden');
}

async function submitSingleRename() {
  const oldPath = document.getElementById('single-rename-oldpath').value;
  const newName = document.getElementById('single-rename-input').value.trim();
  if (!newName) {
    showToast('Bitte einen neuen Namen eingeben', 'error');
    return;
  }

  try {
    const res = await fetch('/api/rename-file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: oldPath, new_name: newName })
    });
    const d = await res.json();
    if (d.success) {
      showToast('Datei erfolgreich umbenannt!', 'success');
      closeSingleRenameModal();
      executeSearch();
    } else {
      showToast(d.error || 'Fehler beim Umbenennen', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// In Windows Papierkorb werfen
async function deleteSingleFile(path) {
  const filename = path.split('\\').pop().split('/').pop();
  const confirmed = await showConfirmDialog({
    title: 'Datei in den Papierkorb verschieben',
    message: `Soll "${filename}" sicher in den Windows-Papierkorb verschoben werden?`,
    detail: `Pfad: ${toGermanDisplayPath(path)}\n\nDie Datei kann jederzeit aus dem Windows-Papierkorb wiederhergestellt werden.`,
    confirmText: 'In den Papierkorb',
    cancelText: 'Abbrechen',
    type: 'danger'
  });
  if (!confirmed) return;
  try {
    const res = await fetch('/api/delete-files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: [path] })
    });
    const d = await res.json();
    if (d.success && d.success.length > 0) {
      showToast('Datei in Papierkorb verschoben.', 'info');
      state.currentFiles = state.currentFiles.filter(f => f.path !== path);
      if (state.allRawFiles) {
        state.allRawFiles = state.allRawFiles.filter(f => f.path !== path);
      }
      state.selectedFilePaths.delete(path);
      updateSelectedCounter();
      const statCount = document.getElementById('stat-count');
      if (statCount) statCount.textContent = state.currentFiles.length;
      const statSize = document.getElementById('stat-size');
      if (statSize) {
        const totalBytes = state.currentFiles.reduce((acc, cur) => acc + (cur.size || 0), 0);
        statSize.textContent = formatBytes(totalBytes);
      }
      renderResults();
    } else {
      showToast('Löschfehler aufgetreten', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// Massen-Löschen: Alle ausgewählten Dateien in den Windows-Papierkorb verschieben
async function deleteSelectedFiles() {
  const count = state.selectedFilePaths.size;
  if (count === 0) {
    showToast('Keine Dateien ausgewählt.', 'warning');
    return;
  }
  const pathsToDelete = Array.from(state.selectedFilePaths);
  const confirmed = await showConfirmDialog({
    title: `${count} Datei${count > 1 ? 'en' : ''} in den Papierkorb verschieben`,
    message: `Sollen wirklich alle ${count} ausgewählten Dateien sicher in den Windows-Papierkorb verschoben werden?`,
    detail: `Betroffene Dateien: ${count}\n\nDateien können jederzeit aus dem Windows-Papierkorb wiederhergestellt werden.`,
    confirmText: `${count} Datei${count > 1 ? 'en' : ''} löschen`,
    cancelText: 'Abbrechen',
    type: 'danger'
  });
  if (!confirmed) return;

  try {
    const res = await fetch('/api/delete-files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: pathsToDelete })
    });
    const d = await res.json();
    if (d.success && d.success.length > 0) {
      const deletedCount = d.success.length;
      const deletedSet = new Set(d.success);
      state.currentFiles = state.currentFiles.filter(f => !deletedSet.has(f.path));
      if (state.allRawFiles) {
        state.allRawFiles = state.allRawFiles.filter(f => !deletedSet.has(f.path));
      }
      state.selectedFilePaths.clear();
      updateSelectedCounter();

      const statCount = document.getElementById('stat-count');
      if (statCount) statCount.textContent = state.currentFiles.length;
      const statSize = document.getElementById('stat-size');
      if (statSize) {
        const totalBytes = state.currentFiles.reduce((acc, cur) => acc + (cur.size || 0), 0);
        statSize.textContent = formatBytes(totalBytes);
      }

      const masterCb = document.getElementById('select-all-checkbox');
      if (masterCb) masterCb.checked = false;

      applySorting();
      renderResults();

      if (d.errors && d.errors.length > 0) {
        showToast(`${deletedCount} Datei(en) in den Papierkorb verschoben (${d.errors.length} Fehler).`, 'warning');
      } else {
        showToast(`🗑️ ${deletedCount} Datei(en) sicher in den Papierkorb verschoben!`, 'success');
      }
    } else {
      showToast(d.error || 'Fehler beim Löschen der ausgewählten Dateien.', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// ==========================================
// DOPPEL-ELIMINIERUNG (DUPLIKATE FINDEN)
// ==========================================
async function analyzeDuplicatesFromSearch() {
  if (state.currentFiles.length === 0) {
    showToast('Führe zuerst eine Suche aus!', 'info');
    return;
  }
  switchTab('duplicates');
  runDuplicateDetection(state.currentFiles);
}

function startDuplicateScanFromCurrentPath() {
  const dir = document.getElementById('target-directory').value.trim();
  if (!dir) {
    showToast('Kein Verzeichnis angegeben', 'error');
    return;
  }
  runDuplicateDetection(dir);
}

async function runDuplicateDetection(target) {
  const spinner = document.getElementById('dup-spinner');
  const emptyState = document.getElementById('dup-empty-state');
  const statsBar = document.getElementById('dup-stats-bar');
  const groupsContainer = document.getElementById('dup-groups-container');

  spinner.classList.remove('hidden');
  emptyState.classList.add('hidden');
  statsBar.classList.add('hidden');
  groupsContainer.innerHTML = '';
  state.duplicateSelectedPaths.clear();

  try {
    const isList = Array.isArray(target);
    const body = isList ? { files: target } : { directory: target };

    const res = await fetch('/api/find-duplicates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    state.duplicateData = data;

    if (!data.sets || data.sets.length === 0) {
      emptyState.classList.remove('hidden');
      document.getElementById('badge-duplicates-count').classList.add('hidden');
    } else {
      statsBar.classList.remove('hidden');
      document.getElementById('dup-stat-groups').textContent = data.total_groups;
      document.getElementById('dup-stat-total-files').textContent = data.total_duplicate_files;
      document.getElementById('dup-stat-wasted').textContent = data.total_wasted_formatted;

      const badge = document.getElementById('badge-duplicates-count');
      badge.textContent = data.total_groups;
      badge.classList.remove('hidden');

      // Auto-Select: Markiere standardmäßig alle Duplikate außer dem ältesten
      autoSelectDuplicates('keep_oldest');
    }
  } catch (err) {
    showToast(`Fehler bei Duplikat-Analyse: ${err.message}`, 'error');
    emptyState.classList.remove('hidden');
  } finally {
    spinner.classList.add('hidden');
  }
}

function autoSelectDuplicates(mode) {
  if (!state.duplicateData || !state.duplicateData.sets) return;

  state.duplicateSelectedPaths.clear();

  state.duplicateData.sets.forEach(group => {
    const files = [...group.files];

    if (mode === 'keep_oldest') {
      // Sortiere nach Erstellungsdatum (ältestes zuerst)
      files.sort((a, b) => (a.modified || '').localeCompare(b.modified || ''));
      // Behalte das erste (Index 0), markiere alle weiteren zum Löschen
      for (let i = 1; i < files.length; i++) {
        state.duplicateSelectedPaths.add(files[i].path);
      }
    } else if (mode === 'keep_newest') {
      files.sort((a, b) => (b.modified || '').localeCompare(a.modified || ''));
      for (let i = 1; i < files.length; i++) {
        state.duplicateSelectedPaths.add(files[i].path);
      }
    } else if (mode === 'keep_onedrive') {
      // Behalte OneDrive Datei falls vorhanden
      const oneDriveFile = files.find(f => f.is_onedrive);
      if (oneDriveFile) {
        files.forEach(f => {
          if (f.path !== oneDriveFile.path) {
            state.duplicateSelectedPaths.add(f.path);
          }
        });
      } else {
        // Fallback: keep oldest
        for (let i = 1; i < files.length; i++) {
          state.duplicateSelectedPaths.add(files[i].path);
        }
      }
    } else if (mode === 'select_copy_names') {
      // Markiere Dateien mit '(1)', ' - Kopie', '_copy' etc.
      files.forEach(f => {
        const lower = f.name.toLowerCase();
        if (lower.includes('(1)') || lower.includes('(2)') || lower.includes('kopie') || lower.includes('copy')) {
          state.duplicateSelectedPaths.add(f.path);
        }
      });
    }
  });

  renderDuplicateGroups();
}

function renderDuplicateGroups() {
  const container = document.getElementById('dup-groups-container');
  container.innerHTML = '';

  state.duplicateData.sets.forEach(group => {
    const groupCard = document.createElement('div');
    groupCard.className = 'glass-card rounded-2xl border border-slate-800/80 bg-slate-900/50 p-5 space-y-3';

    let filesHtml = '';
    group.files.forEach(file => {
      const isMarked = state.duplicateSelectedPaths.has(file.path);
      filesHtml += `
        <div class="flex items-center justify-between p-2.5 rounded-xl ${isMarked ? 'bg-red-500/10 border border-red-500/30' : 'bg-slate-950/60 border border-slate-800'} transition">
          <div class="flex items-center gap-3 flex-1 min-w-0 pr-4">
            <input type="checkbox" ${isMarked ? 'checked' : ''} onchange="toggleDuplicateSelection('${escapeJs(file.path)}', this)" class="rounded border-slate-700 text-red-600 focus:ring-red-500 cursor-pointer">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-xs font-semibold text-slate-200 truncate" title="${file.name}">${file.name}</span>
                ${isMarked ? '<span class="text-[10px] px-1.5 py-0.2 rounded bg-red-500/20 text-red-300 font-bold">Löschen</span>' : '<span class="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-bold">Behalten</span>'}
                ${file.is_onedrive ? '<span class="text-[10px] text-sky-400 bg-sky-500/10 px-1 py-0.2 rounded"><i class="fa-solid fa-cloud"></i> OneDrive</span>' : ''}
              </div>
              <p class="text-[11px] text-slate-400 font-mono truncate" title="${file.path}">${toGermanDisplayPath(file.folder)}</p>
            </div>
          </div>
          <div class="flex items-center gap-4 text-xs">
            <span class="text-slate-400 font-mono text-[11px]">${file.modified_formatted}</span>
            <div class="flex items-center gap-1">
              <button onclick="openFile('${escapeJs(file.path)}')" class="p-1 rounded text-blue-400 hover:text-blue-300" title="In ${getAppLabelForExt(file.ext)} öffnen"><i class="fa-solid fa-play"></i></button>
              <button onclick="openFolder('${escapeJs(file.path)}')" class="p-1 rounded text-yellow-400 hover:text-yellow-300" title="Im Windows Explorer anzeigen"><i class="fa-solid fa-folder-open"></i></button>
            </div>
          </div>
        </div>
      `;
    });

    groupCard.innerHTML = `
      <div class="flex items-center justify-between pb-2 border-b border-slate-800">
        <div class="flex items-center gap-2 text-xs">
          <span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">Gruppe #${group.group_id}</span>
          <span class="text-slate-400 font-mono">${group.file_size_formatted}</span>
          <span class="text-slate-500">&bull;</span>
          <span class="text-slate-400">${group.duplicate_count} identische Kopien</span>
        </div>
        <span class="text-xs text-amber-400 font-mono font-medium">Verschwendet: ${group.wasted_formatted}</span>
      </div>
      <div class="space-y-2">
        ${filesHtml}
      </div>
    `;

    container.appendChild(groupCard);
  });

  const delBtn = document.getElementById('btn-delete-duplicates');
  if (delBtn) {
    delBtn.disabled = state.duplicateSelectedPaths.size === 0;
    delBtn.innerHTML = `<i class="fa-solid fa-trash-can"></i><span>${state.duplicateSelectedPaths.size} Duplikate in den Papierkorb werfen</span>`;
  }
}

function toggleDuplicateSelection(path, checkbox) {
  if (checkbox.checked) {
    state.duplicateSelectedPaths.add(path);
  } else {
    state.duplicateSelectedPaths.delete(path);
  }
  renderDuplicateGroups();
}

async function deleteSelectedDuplicates() {
  const count = state.duplicateSelectedPaths.size;
  if (count === 0) return;

  const countText = count === 1 ? '1 ausgewähltes Duplikat' : `${count} ausgewählte Duplikate`;
  const confirmed = await showConfirmDialog({
    title: 'Duplikate in den Papierkorb verschieben',
    message: `Möchten Sie ${countText} sicher in den Windows-Papierkorb verschieben?`,
    detail: 'Hinweis: Die Dateien werden nicht sofort gelöscht, sondern können bei Bedarf jederzeit aus dem Windows-Papierkorb wiederhergestellt werden.',
    confirmText: 'In den Papierkorb verschieben',
    cancelText: 'Abbrechen',
    type: 'danger'
  });
  if (!confirmed) return;

  try {
    const pathsToDelete = Array.from(state.duplicateSelectedPaths);
    const res = await fetch('/api/delete-files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths: pathsToDelete })
    });
    const d = await res.json();
    if (d.success) {
      showToast(`🎉 ${d.success.length} Duplikate erfolgreich in Papierkorb verschoben!`, 'success');
      // Duplikat-Ansicht aktualisieren
      if (Array.isArray(state.currentFiles)) {
        state.currentFiles = state.currentFiles.filter(f => !state.duplicateSelectedPaths.has(f.path));
        renderResults();
      }
      runDuplicateDetection(state.currentFiles);
    }
  } catch (err) {
    showToast(`Fehler beim Löschen: ${err.message}`, 'error');
  }
}

// ==========================================
// BATCH-UMBENENNUNG (MASSEN-UMBENENNUNG)
// ==========================================
function openBatchRenameWithSelected() {
  if (state.selectedFilePaths.size === 0) {
    // Alle aktuellen Dateien nehmen falls keine selektiert
    state.renameFiles = [...state.currentFiles];
  } else {
    state.renameFiles = state.currentFiles.filter(f => state.selectedFilePaths.has(f.path));
  }

  document.getElementById('rename-selected-count').textContent = state.renameFiles.length;
  switchTab('rename');
  updateRenamePreview();
}

function setRenameRule(rule, btn) {
  state.currentRenameRule = rule;

  document.querySelectorAll('#rename-rules-tabs .rule-btn').forEach(b => {
    b.className = 'rule-btn px-4 py-2 rounded-xl text-xs font-semibold transition border border-slate-700 bg-slate-800/60 text-slate-300 hover:bg-slate-700';
  });
  if (btn) {
    btn.className = 'rule-btn active px-4 py-2 rounded-xl text-xs font-semibold transition border border-indigo-500/30 bg-indigo-500/20 text-indigo-300';
  }

  // Formulare umschalten
  document.getElementById('rule-form-replace').classList.toggle('hidden', rule !== 'replace');
  document.getElementById('rule-form-prefix-suffix').classList.toggle('hidden', rule !== 'prefix_suffix');
  document.getElementById('rule-form-numbering').classList.toggle('hidden', rule !== 'numbering');
  document.getElementById('rule-form-date').classList.toggle('hidden', rule !== 'date');
  document.getElementById('rule-form-case').classList.toggle('hidden', rule !== 'case');

  updateRenamePreview();
}

async function updateRenamePreview() {
  if (state.renameFiles.length === 0) return;

  const rule = state.currentRenameRule;
  let params = {};

  if (rule === 'replace') {
    params.search = document.getElementById('rename-search').value;
    params.replace = document.getElementById('rename-replace').value;
    params.case_sensitive = document.getElementById('rename-case-sensitive')?.checked ?? false;
  } else if (rule === 'prefix_suffix') {
    params.prefix = document.getElementById('rename-prefix').value;
    params.suffix = document.getElementById('rename-suffix').value;
  } else if (rule === 'numbering') {
    params.pattern = document.getElementById('rename-num-pattern').value;
    params.start_num = document.getElementById('rename-num-start').value;
    params.digits = document.getElementById('rename-num-digits').value;
  } else if (rule === 'date') {
    params.position = document.getElementById('rename-date-pos').value;
    params.format = document.getElementById('rename-date-fmt').value;
  } else if (rule === 'case') {
    params.mode = document.getElementById('rename-case-mode').value;
  }

  try {
    const res = await fetch('/api/batch-rename-preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        files: state.renameFiles,
        rule_type: rule,
        params: params
      })
    });
    const d = await res.json();
    state.renamePreview = d.preview || [];

    const tbody = document.getElementById('rename-preview-tbody');
    tbody.innerHTML = '';
    let changeCount = 0;

    state.renamePreview.forEach(item => {
      if (item.changed) changeCount++;
      const tr = document.createElement('tr');
      tr.className = 'border-b border-slate-800/60 hover:bg-slate-900/40';

      const statusBadge = item.conflict
        ? '<span class="text-[10px] bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded font-bold">Konflikt</span>'
        : item.changed
          ? '<span class="text-[10px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded font-bold">Ändert sich</span>'
          : '<span class="text-[10px] text-slate-500">Unverändert</span>';

      tr.innerHTML = `
        <td class="py-2.5 px-4 text-slate-400 truncate max-w-xs" title="${item.original_name}">${item.original_name}</td>
        <td class="py-2.5 px-4 font-semibold ${item.changed ? 'text-indigo-300' : 'text-slate-300'} truncate max-w-xs" title="${item.new_name}">
          ${item.new_name}
        </td>
        <td class="py-2.5 px-4 text-center">${statusBadge}</td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById('rename-change-count').textContent = `${changeCount} von ${state.renamePreview.length} Dateien werden umbenannt`;
    document.getElementById('btn-execute-rename').disabled = changeCount === 0;
  } catch (err) {
    console.error('Rename Preview Fehler:', err);
  }
}

async function executeBatchRename() {
  if (!state.renamePreview || state.renamePreview.length === 0) return;

  const changedItems = state.renamePreview.filter(i => i.changed);
  if (changedItems.length === 0) {
    showToast('Keine Änderungen vorzunehmen.', 'info');
    return;
  }
  const confirmed = await showConfirmDialog({
    title: 'Massen-Umbenennung anwenden',
    message: `Möchten Sie wirklich ${changedItems.length} Dateien umbenennen?`,
    detail: 'Die neuen Dateinamen werden direkt auf der Festplatte angewendet.',
    confirmText: 'Jetzt umbenennen',
    cancelText: 'Abbrechen',
    type: 'warning'
  });
  if (!confirmed) return;

  try {
    const res = await fetch('/api/batch-rename-execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preview: state.renamePreview })
    });
    const d = await res.json();
    if (d.success) {
      showToast(`✅ ${d.success.length} Dateien erfolgreich umbenannt!`, 'success');
      switchTab('search');
      executeSearch();
    } else {
      showToast('Einige Dateien konnten nicht umbenannt werden.', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// ==========================================
// TOAST-NOTIFIKATIONSSYSTEM & HILFSFUNKTIONEN
// ==========================================
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  
  let bgClass = 'bg-slate-900 border-slate-700 text-slate-100';
  let icon = 'fa-info-circle text-sky-400';

  if (type === 'success') {
    bgClass = 'bg-slate-900 border-emerald-500/40 text-emerald-200';
    icon = 'fa-circle-check text-emerald-400';
  } else if (type === 'error') {
    bgClass = 'bg-slate-900 border-red-500/40 text-red-200';
    icon = 'fa-circle-exclamation text-red-400';
  }

  toast.className = `pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl text-xs max-w-md transition-all duration-300 transform translate-y-2 opacity-0 ${bgClass}`;
  toast.innerHTML = `
    <i class="fa-solid ${icon} text-base flex-shrink-0"></i>
    <span class="flex-1">${message}</span>
  `;

  container.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function getCurrentThemeName() {
  return document.documentElement.classList.contains('light') ? 'light' : 'dark';
}

function initTheme() {
  const savedTheme = localStorage.getItem('suchmaschine_theme') || 'dark';
  applyTheme(savedTheme, false);
}

function applyTheme(theme, showNotice = false) {
  const html = document.documentElement;
  const icon = document.getElementById('theme-icon');
  const btn = document.getElementById('theme-toggle-btn');

  if (theme === 'light') {
    html.classList.remove('dark');
    html.classList.add('light');
    if (icon) {
      icon.className = 'fa-solid fa-sun text-amber-500';
    }
    if (btn) {
      btn.title = 'Zu dunklem Design wechseln';
    }
  } else {
    html.classList.remove('light');
    html.classList.add('dark');
    if (icon) {
      icon.className = 'fa-solid fa-moon text-indigo-400';
    }
    if (btn) {
      btn.title = 'Zu hellem Design wechseln';
    }
  }
  localStorage.setItem('suchmaschine_theme', theme);
  updateSettingsThemeBtns();
  fetch('/api/bridge/theme', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme })
  }).catch(() => {});
  if (showNotice) {
    showToast(theme === 'light' ? 'Helles Design aktiviert ☀️' : 'Dunkles Design aktiviert 🌙', 'info');
  }
}

function toggleTheme() {
  const isLight = document.documentElement.classList.contains('light');
  const newTheme = isLight ? 'dark' : 'light';
  applyTheme(newTheme, true);
}

function openSettingsModal() {
  updateSettingsThemeBtns();
  const el = document.getElementById('modal-settings');
  if (el) el.classList.remove('hidden');
}

function closeSettingsModal() {
  const el = document.getElementById('modal-settings');
  if (el) el.classList.add('hidden');
}

function updateSettingsThemeBtns() {
  const isLight = document.documentElement.classList.contains('light');
  const btnDark = document.getElementById('btn-theme-dark');
  const btnLight = document.getElementById('btn-theme-light');
  if (!btnDark || !btnLight) return;

  if (isLight) {
    btnLight.className = 'flex-1 py-2 px-3 rounded-lg border border-amber-500/50 bg-amber-500/20 text-amber-700 font-semibold flex items-center justify-center gap-2 shadow-sm transition';
    btnDark.className = 'flex-1 py-2 px-3 rounded-lg border border-slate-300 bg-slate-100 text-slate-600 hover:text-slate-900 font-medium flex items-center justify-center gap-2 transition';
  } else {
    btnDark.className = 'flex-1 py-2 px-3 rounded-lg border border-indigo-500/50 bg-indigo-500/20 text-white font-semibold flex items-center justify-center gap-2 shadow-sm transition';
    btnLight.className = 'flex-1 py-2 px-3 rounded-lg border border-slate-700 bg-slate-900 text-slate-400 hover:text-white font-medium flex items-center justify-center gap-2 transition';
  }
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeJs(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ==========================================
// GITHUB UPDATE MODAL (MIT SYNC-STATUS & RETOUR-SICHERHEIT)
// ==========================================
function applyGitInfoToModal(data) {
  state.gitInfo = data;
  const appVer = data.version || 'v1.7.20';

  const topTagEl = document.getElementById('app-version-tag');
  if (topTagEl) topTagEl.textContent = appVer;
  const modalVerEl = document.getElementById('git-modal-version');
  if (modalVerEl) modalVerEl.textContent = appVer;
  const appVerEl = document.getElementById('git-app-version');
  if (appVerEl) appVerEl.textContent = appVer;

  document.getElementById('git-branch').textContent = data.branch || 'main';
  document.getElementById('git-last-commit').textContent = data.last_commit || 'Keine Commit-Information';

  const remoteInput = document.getElementById('git-remote-input');
  if (remoteInput) {
    remoteInput.value = data.remote_url || 'https://github.com/charlywyss-beep/Datei-Suchmaschine.git';
  }

  const exeLbl = document.getElementById('git-exe-download-label');
  if (exeLbl) {
    const sizeText = data.exe_size_mb ? ` (${data.exe_size_mb})` : '';
    exeLbl.textContent = `GitHub .exe laden${sizeText}`;
  }

  // Deutlicher Sync-Banner
  const banner = document.getElementById('git-sync-banner');
  const iconEl = document.getElementById('git-sync-icon');
  const titleEl = document.getElementById('git-sync-title');
  const detailEl = document.getElementById('git-sync-detail');
  const badgeEl = document.getElementById('git-version-badge');
  const pushBtn = document.getElementById('btn-run-git-push');

  if (banner && titleEl && detailEl && badgeEl && iconEl) {
    const st = data.sync_state || (data.is_git ? 'unknown' : 'no_git');
    titleEl.textContent = data.sync_title || (st === 'in_sync' ? `Auf dem neuesten Stand mit GitHub (${appVer})` : 'GitHub-Status konnte nicht vollständig gelesen werden');
    detailEl.textContent = data.sync_detail || '';

    if (st === 'local_newer' || st === 'local_ahead') {
      banner.className = 'git-sync-warn p-2.5 rounded-xl border border-amber-500/50 bg-amber-950/30 text-xs flex items-start gap-2.5';
      iconEl.className = 'fa-solid fa-triangle-exclamation text-base text-amber-400 mt-0.5 shrink-0';
      badgeEl.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 shrink-0';
      const refVer = data.remote_version || data.git_version || 'älter';
      badgeEl.textContent = st === 'local_newer' ? `Lokal ${appVer} > GitHub ${refVer}` : 'Ungesicherter Stand';
      if (pushBtn) {
        pushBtn.className = 'px-3.5 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 border border-amber-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-amber-600/25';
      }
    } else if (st === 'remote_newer') {
      banner.className = 'git-sync-info p-2.5 rounded-xl border border-sky-500/50 bg-sky-950/30 text-xs flex items-start gap-2.5';
      iconEl.className = 'fa-solid fa-cloud-arrow-down text-base text-sky-400 mt-0.5 shrink-0';
      badgeEl.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/40 shrink-0';
      badgeEl.textContent = `GitHub neuer (${data.remote_version || '+' + (data.behind || 1)})`;
      if (pushBtn) {
        pushBtn.className = 'px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold transition flex items-center gap-1.5';
      }
    } else if (st === 'in_sync') {
      banner.className = 'git-sync-ok p-2.5 rounded-xl border border-emerald-500/40 bg-emerald-950/25 text-xs flex items-start gap-2.5';
      iconEl.className = 'fa-solid fa-circle-check text-base text-emerald-400 mt-0.5 shrink-0';
      badgeEl.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shrink-0';
      badgeEl.textContent = `Synchron (${appVer})`;
      if (pushBtn) {
        pushBtn.className = 'px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold transition flex items-center gap-1.5';
      }
    } else {
      banner.className = 'p-2.5 rounded-xl border border-slate-700 bg-slate-800/60 text-xs flex items-start gap-2.5';
      iconEl.className = 'fa-solid fa-circle-info text-base text-slate-400 mt-0.5 shrink-0';
      badgeEl.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-700 text-slate-200 shrink-0';
      badgeEl.textContent = st === 'offline' ? 'Offline' : (st === 'no_git' ? 'Kein Git' : 'Status unvollständig');
    }
  }

  // Commit-Historie für optionales Retour befüllen (aktuellsten Eintrag markieren)
  const sel = document.getElementById('git-rollback-select');
  if (sel) {
    sel.innerHTML = '';
    const hist = Array.isArray(data.history) ? data.history : [];
    if (hist.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'Keine Commit-Historie verfügbar';
      sel.appendChild(opt);
    } else {
      hist.forEach((item, idx) => {
        const opt = document.createElement('option');
        opt.value = item.hash;
        const label = idx === 0 ? '[Aktueller Commit] ' : '';
        opt.textContent = `${label}${item.short} — ${item.subject} (${item.date})`;
        if (idx === 1) opt.selected = true; // Praktisch: vorangehende Version vorauswählen
        sel.appendChild(opt);
      });
    }
  }
}

async function openGitUpdateModal() {
  document.getElementById('modal-git-update').classList.remove('hidden');
  loadUsbDrives();
  const pushBtn = document.getElementById('btn-run-git-push');
  if (pushBtn) {
    pushBtn.disabled = false;
    pushBtn.innerHTML = '<i class="fa-solid fa-arrow-up-from-bracket"></i><span>Stand nach GitHub hochladen</span>';
  }
  const updateBtn = document.getElementById('btn-run-git-update');
  if (updateBtn) {
    updateBtn.disabled = false;
    updateBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i><span>Jetzt von GitHub aktualisieren</span>';
  }
  try {
    const res = await fetch('/api/git-info');
    const data = await res.json();
    applyGitInfoToModal(data);
  } catch (err) {
    console.error('Git-Info Fehler:', err);
  }
}

async function runGitPush() {
  const btn = document.getElementById('btn-run-git-push');
  const logContainer = document.getElementById('git-log-container');
  const logOutput = document.getElementById('git-log-output');

  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Committe &amp; übertrage nach GitHub...</span>';
  logContainer.classList.remove('hidden');
  logOutput.textContent = 'Erstelle Commit (falls nötig) und führe "git push" nach GitHub aus...\n';

  try {
    const res = await fetch('/api/git-push', { method: 'POST' });
    const d = await res.json();
    logOutput.textContent = d.output || d.message || d.error || 'Fertig';

    if (d.success) {
      showToast(d.message || 'Stand erfolgreich nach GitHub übertragen!', 'success');
      btn.innerHTML = '<i class="fa-solid fa-check"></i><span>Übertragen!</span>';
      if (d.git_info) {
        applyGitInfoToModal(d.git_info);
      } else {
        openGitUpdateModal();
      }
    } else {
      showToast(d.message || d.error || 'Upload fehlgeschlagen', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-arrow-up-from-bracket"></i><span>Erneut versuchen</span>';
    }
  } catch (err) {
    logOutput.textContent = `Fehler: ${err.message}`;
    showToast(`Fehler: ${err.message}`, 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-arrow-up-from-bracket"></i><span>Stand nach GitHub hochladen</span>';
  }
}

function closeGitUpdateModal() {
  document.getElementById('modal-git-update').classList.add('hidden');
}

let _lastUsbDeployedDir = '';

function onUsbTargetChange() {
  const sel = document.getElementById('git-usb-target-select');
  const inp = document.getElementById('git-usb-custom-path');
  if (!sel || !inp) return;
  if (sel.value === '__custom__') {
    inp.classList.remove('hidden');
    inp.focus();
  } else {
    inp.classList.add('hidden');
  }
}

async function loadUsbDrives() {
  const sel = document.getElementById('git-usb-target-select');
  const inp = document.getElementById('git-usb-custom-path');
  if (!sel) return;
  try {
    const res = await fetch('/api/usb-drives');
    const data = await res.json();
    const drives = Array.isArray(data.drives) ? data.drives : [];
    sel.innerHTML = '';
    if (drives.length > 0) {
      drives.forEach((d, idx) => {
        const opt = document.createElement('option');
        opt.value = d.default_dir;
        const badge = d.has_exe ? ' (Update vorhanden)' : ' (Ordner wird erstellt)';
        opt.textContent = `${d.display} -> ${d.default_dir}${badge}`;
        if (idx === 0) opt.selected = true;
        sel.appendChild(opt);
      });
      const customOpt = document.createElement('option');
      customOpt.value = '__custom__';
      customOpt.textContent = 'Anderen Zielordner eingeben...';
      sel.appendChild(customOpt);
      if (inp) inp.classList.add('hidden');
    } else {
      const opt = document.createElement('option');
      opt.value = '__custom__';
      opt.textContent = 'Kein USB-Stick erkannt – Zielordner eingeben';
      opt.selected = true;
      sel.appendChild(opt);
      if (inp) inp.classList.remove('hidden');
    }
  } catch (err) {
    console.error('USB-Suche Fehler:', err);
  }
}

async function deployExeToUsb() {
  const btn = document.getElementById('btn-usb-deploy');
  const sel = document.getElementById('git-usb-target-select');
  const inp = document.getElementById('git-usb-custom-path');
  const statusEl = document.getElementById('git-usb-status');
  const statusTxt = document.getElementById('git-usb-status-text');

  let targetRoot = '';
  if (sel && sel.value && sel.value !== '__custom__') {
    targetRoot = sel.value;
  } else if (inp) {
    targetRoot = inp.value.trim();
  }
  if (!targetRoot) {
    showToast('Bitte USB-Stick einstecken oder einen Zielordner eingeben.', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Kopiere auf USB...</span>';
  try {
    const res = await fetch('/api/usb-install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_root: targetRoot })
    });
    const d = await res.json();
    if (d.success) {
      _lastUsbDeployedDir = d.target_dir || '';
      if (statusEl && statusTxt) {
        statusTxt.textContent = d.message || `Abgelegt in ${d.target_dir}`;
        statusEl.classList.remove('hidden');
        statusEl.classList.add('flex');
      }
      showToast(d.message || 'EXE erfolgreich auf USB-Stick abgelegt!', 'success');
      loadUsbDrives();
    } else {
      showToast(d.error || 'Kopieren auf USB-Stick fehlgeschlagen.', 'error');
    }
  } catch (err) {
    showToast(`USB-Fehler: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-usb text-sm shrink-0"></i><span>Auf USB-Stick ablegen</span>';
  }
}

async function openDeployedUsbDir() {
  if (!_lastUsbDeployedDir) return;
  try {
    await fetch('/api/open-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: _lastUsbDeployedDir })
    });
  } catch (err) {}
}

async function saveGitRemote() {
  const url = document.getElementById('git-remote-input').value.trim();
  if (!url) {
    showToast('Bitte eine gültige Git-URL angeben', 'error');
    return;
  }
  try {
    const res = await fetch('/api/git-set-remote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remote_url: url })
    });
    const d = await res.json();
    if (d.success) {
      showToast('GitHub Remote-Repository erfolgreich gespeichert!', 'success');
    } else {
      showToast(d.error || 'Fehler beim Speichern des Remotes', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

async function runGitUpdate() {
  const info = state.gitInfo || {};
  if (info.local_is_newer) {
    const confirmed = await showConfirmDialog({
      type: 'warning',
      title: 'Achtung: Lokale Version ist neuer als GitHub!',
      message: info.sync_title || `Die lokale Version (${info.version || ''}) ist neuer als der Stand auf GitHub.`,
      detail: 'Wenn Sie jetzt „von GitHub aktualisieren“ statt „Stand nach GitHub hochladen“, erhalten Sie eventuell einen älteren Stand oder lokale Änderungen blockieren das Pull. Möchten Sie wirklich von GitHub laden?',
      confirmText: 'Trotzdem von GitHub laden',
      cancelText: 'Abbrechen'
    });
    if (!confirmed) return;
  }

  const btn = document.getElementById('btn-run-git-update');
  const logContainer = document.getElementById('git-log-container');
  const logOutput = document.getElementById('git-log-output');

  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Aktualisiere von GitHub...</span>';
  logContainer.classList.remove('hidden');
  logOutput.textContent = 'Verbinde mit GitHub und führe "git pull" aus...\n';

  try {
    const res = await fetch('/api/git-update', { method: 'POST' });
    const d = await res.json();

    logOutput.textContent = d.output || d.message || d.error || 'Keine Rückmeldung';

    if (d.success) {
      if (d.already_up_to_date) {
        showToast(d.message || 'Bereits auf dem neuesten Stand!', 'info');
        btn.innerHTML = '<i class="fa-solid fa-check"></i><span>Aktuell!</span>';
      } else if (d.self_updating) {
        showToast(d.message || 'Update geladen – App wird ersetzt und startet gleich neu...', 'success');
        btn.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i><span>Neustart läuft...</span>';
      } else {
        showToast('Erfolgreich auf den neuesten GitHub-Stand aktualisiert!', 'success');
        btn.innerHTML = '<i class="fa-solid fa-check"></i><span>Aktuell!</span>';
        setTimeout(() => location.reload(), 2500);
      }
    } else {
      showToast(d.message || d.error || 'Update fehlgeschlagen', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i><span>Erneut versuchen</span>';
    }
  } catch (err) {
    logOutput.textContent = `Fehler: ${err.message}`;
    showToast(`Update-Fehler: ${err.message}`, 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i><span>Jetzt von GitHub aktualisieren</span>';
  }
}

async function runGitRollback() {
  const sel = document.getElementById('git-rollback-select');
  const commitHash = sel ? sel.value : '';
  const commitLabel = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].textContent : '';
  if (!commitHash) {
    showToast('Bitte zuerst eine frühere Version auswählen.', 'error');
    return;
  }

  const confirmed = await showConfirmDialog({
    type: 'warning',
    title: 'Zurück zu einer früheren Version? (Retour)',
    message: `Möchten Sie den Programmstand wirklich auf diesen Commit zurücksetzen?\n\n${commitLabel}`,
    detail: 'Sicherheitsnetz: Ungesicherte lokale Änderungen werden automatisch im Git-Stash gesichert, Ihre Einstellungen (config.json) bleiben erhalten, und mit „Jetzt von GitHub aktualisieren“ können Sie später wieder vorwärts wechseln.',
    confirmText: 'Ja, Version wiederherstellen',
    cancelText: 'Abbrechen'
  });
  if (!confirmed) return;

  const btn = document.getElementById('btn-run-git-rollback');
  const logContainer = document.getElementById('git-log-container');
  const logOutput = document.getElementById('git-log-output');

  btn.disabled = true;
  const origHtml = btn.innerHTML;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Setze zurück...</span>';
  logContainer.classList.remove('hidden');
  logOutput.textContent = `Setze sicher zurück auf Commit ${commitHash.slice(0, 7)}...\n`;

  try {
    const res = await fetch('/api/git-rollback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commit_hash: commitHash })
    });
    const d = await res.json();
    logOutput.textContent = d.output || d.message || d.error || 'Fertig';
    if (d.success) {
      showToast(d.message || 'Auf frühere Version zurückgesetzt – starte neu...', 'success');
      setTimeout(() => location.reload(), 2500);
    } else {
      showToast(d.error || 'Zurücksetzen fehlgeschlagen', 'error');
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  } catch (err) {
    logOutput.textContent = `Fehler: ${err.message}`;
    showToast(`Fehler: ${err.message}`, 'error');
    btn.disabled = false;
    btn.innerHTML = origHtml;
  }
}

// ==========================================
// IPAD, IPHONE & DATENAUSTAUSCH MODAL
// ==========================================
function openMobileSyncModal() {
  const url = state.networkUrl || `http://${window.location.hostname}:5005`;
  const qrImg = document.getElementById('qr-code-img');
  const netLink = document.getElementById('mobile-network-link');

  if (qrImg) {
    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(url)}`;
  }
  if (netLink) {
    netLink.href = url;
    netLink.querySelector('span').textContent = url;
  }

  document.getElementById('modal-mobile-sync').classList.remove('hidden');
}

function closeMobileSyncModal() {
  document.getElementById('modal-mobile-sync').classList.add('hidden');
}

// ==========================================
// TRANSFER-HUB & SYNC ANLEITUNG MODAL
// ==========================================
function openTransferGuideModal() {
  const m = document.getElementById('modal-transfer-guide');
  if (m) m.classList.remove('hidden');
}

function closeTransferGuideModal() {
  const m = document.getElementById('modal-transfer-guide');
  if (m) m.classList.add('hidden');
}

async function uploadMobileFile() {
  const fileInput = document.getElementById('mobile-upload-input');
  if (!fileInput.files || fileInput.files.length === 0) {
    showToast('Bitte eine Datei oder ein Foto auswählen!', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  if (state.onedriveInfo?.transfer?.path) {
    formData.append('target_dir', state.onedriveInfo.transfer.path);
  }

  showToast('Übertrage Datei...', 'info');

  try {
    const res = await fetch('/api/upload-file', {
      method: 'POST',
      body: formData
    });
    const d = await res.json();
    if (d.success) {
      showToast(`✅ "${d.name}" erfolgreich übertragen! Liegt im Transfer-Hub.`, 'success');
      fileInput.value = '';
      closeMobileSyncModal();
      // Wenn wir im Transfer-Ordner suchen, aktualisieren
      executeSearch();
    } else {
      showToast(d.error || 'Übertragung fehlgeschlagen', 'error');
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// ==========================================
// ONEDRIVE GESCHÄFTLICH EINSTELLUNGEN
// ==========================================
function openOneDriveSettingsModal() {
  const input = document.getElementById('input-business-onedrive');
  if (input && state.onedriveInfo?.business?.path) {
    input.value = state.onedriveInfo.business.path;
  }
  document.getElementById('modal-onedrive-settings').classList.remove('hidden');
}

function closeOneDriveSettingsModal() {
  document.getElementById('modal-onedrive-settings').classList.add('hidden');
}

async function saveOneDriveSettings() {
  const bizPath = document.getElementById('input-business-onedrive').value.trim();
  if (!bizPath) {
    showToast('Bitte einen Pfad eingeben', 'error');
    return;
  }

  try {
    const res = await fetch('/api/save-onedrive-paths', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ business: bizPath })
    });
    const d = await res.json();
    if (d.success) {
      state.onedriveInfo = d.onedrive_info;
      showToast('Pfad für geschäftliches OneDrive gespeichert!', 'success');
      closeOneDriveSettingsModal();
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}


// ==========================================
// BESTÄTIGUNGS-MODAL (ZENTRIERT & MODERN)
// ==========================================
function showConfirmDialog({
  title = 'Bestätigung erforderlich',
  message = '',
  detail = '',
  confirmText = 'Bestätigen',
  cancelText = 'Abbrechen',
  type = 'danger' // 'danger', 'warning', 'info'
}) {
  return new Promise((resolve) => {
    const modal = document.getElementById('modal-confirm-dialog');
    const titleEl = document.getElementById('confirm-modal-title');
    const msgEl = document.getElementById('confirm-modal-message');
    const detailEl = document.getElementById('confirm-modal-detail');
    const iconContainer = document.getElementById('confirm-modal-icon-container');
    const iconEl = document.getElementById('confirm-modal-icon');
    const btnConfirm = document.getElementById('confirm-modal-btn-confirm');
    const btnCancel = document.getElementById('confirm-modal-btn-cancel');

    if (!modal) {
      resolve(window.confirm(`${title}\n\n${message}`));
      return;
    }

    titleEl.textContent = title;
    msgEl.textContent = message;
    if (detail) {
      detailEl.textContent = detail;
      detailEl.classList.remove('hidden');
    } else {
      detailEl.classList.add('hidden');
    }
    btnConfirm.innerHTML = `<i class="fa-solid fa-check"></i><span>${confirmText}</span>`;
    btnCancel.textContent = cancelText;

    if (type === 'danger') {
      iconContainer.className = 'w-12 h-12 rounded-2xl bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center text-xl shrink-0';
      iconEl.className = 'fa-solid fa-trash-can';
      btnConfirm.className = 'px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 text-white text-xs font-bold transition shadow-lg shadow-rose-600/30 flex items-center gap-2 active:scale-95';
    } else {
      iconContainer.className = 'w-12 h-12 rounded-2xl bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center text-xl shrink-0';
      iconEl.className = 'fa-solid fa-triangle-exclamation';
      btnConfirm.className = 'px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white text-xs font-bold transition shadow-lg shadow-amber-600/30 flex items-center gap-2 active:scale-95';
    }

    const cleanup = (result) => {
      modal.classList.add('hidden');
      btnConfirm.onclick = null;
      btnCancel.onclick = null;
      document.removeEventListener('keydown', handleKey);
      resolve(result);
    };

    const handleKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        cleanup(false);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        cleanup(true);
      }
    };

    btnConfirm.onclick = () => cleanup(true);
    btnCancel.onclick = () => cleanup(false);
    document.addEventListener('keydown', handleKey);

    modal.classList.remove('hidden');
  });
}


function openGdriveSettingsModal() {
  const gdrive = state.onedriveInfo?.gdrive;
  const input = document.getElementById('input-gdrive-path');
  if (input && gdrive) {
    input.value = gdrive.path || 'G:\\Meine Ablage';
  }
  const modal = document.getElementById('modal-gdrive-settings');
  if (modal) modal.classList.remove('hidden');
}

function closeGdriveSettingsModal() {
  const modal = document.getElementById('modal-gdrive-settings');
  if (modal) modal.classList.add('hidden');
}

async function saveGdriveSettings() {
  const input = document.getElementById('input-gdrive-path');
  const path = input ? input.value.trim() : '';
  if (!path) {
    showToast('Bitte einen Pfad eingeben', 'warning');
    return;
  }
  try {
    const res = await fetch('/api/save-gdrive-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    const d = await res.json();
    if (d.success) {
      state.onedriveInfo = d.onedrive_info;
      renderLocationShortcuts();
      showToast('Google Drive Pfad erfolgreich gespeichert!', 'success');
      closeGdriveSettingsModal();
    }
  } catch (err) {
    showToast(`Fehler: ${err.message}`, 'error');
  }
}

// ==========================================
// BRÜCKE ZU 7-ORDNER-PRO
// ==========================================
async function sendToSevenFolder() {
  let paths = Array.from(state.selectedFilePaths || []);
  if (paths.length === 0) {
    const visiblePaths = (state.currentFiles || []).map(f => f.path).filter(Boolean);
    if (visiblePaths.length === 0) {
      await sendFolderToSevenFolder();
      return;
    }
    const ok = await showConfirmDialog({
      title: 'Alle Treffer an 7-Ordner-Pro übergeben?',
      message: `Es sind keine einzelnen Dateien markiert. Sollen alle ${visiblePaths.length} gefundenen Dateien an 7-Ordner-Pro zur Sortier-Vorschau übergeben werden?`,
      confirmText: `${visiblePaths.length} Dateien übergeben`,
      cancelText: 'Abbrechen',
      type: 'info'
    });
    if (!ok) return;
    paths = visiblePaths;
  }

  try {
    showToast('🚀 Starte 7-Ordner-Pro mit Übergabeliste...', 'info');
    const res = await fetch('/api/handoff-seven-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths, theme: getCurrentThemeName() })
    });
    const d = await res.json();
    if (d.success) {
      showToast(`✅ ${d.count} Dateien an 7-Ordner-Pro übergeben!`, 'success');
    } else {
      showToast(d.error || '7-Ordner-Pro konnte nicht gestartet werden', 'error');
    }
  } catch (err) {
    showToast(`Fehler bei Übergabe: ${err.message}`, 'error');
  }
}

async function sendFolderToSevenFolder() {
  const dirInput = document.getElementById('target-directory');
  const rawVal = dirInput ? dirInput.value.trim() : '';
  const isScopeLabel = (
    !rawVal ||
    rawVal.startsWith('Dieser PC (') ||
    rawVal.startsWith('OneDrive (') ||
    rawVal.startsWith('Netzwerk (') ||
    ['THIS_PC', 'ONEDRIVE_ALL', 'NETWORK'].includes(rawVal)
  );
  const payload = isScopeLabel ? { theme: getCurrentThemeName() } : { folder_path: rawVal, theme: getCurrentThemeName() };

  try {
    showToast('📂 Öffne 7-Ordner-Pro...', 'info');
    const res = await fetch('/api/handoff-seven-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    if (d.success) {
      const info = d.folder ? ` (${d.folder})` : '';
      showToast(`✅ 7-Ordner-Pro gestartet${info}`, 'success');
    } else {
      showToast(d.error || '7-Ordner-Pro konnte nicht gestartet werden', 'error');
    }
  } catch (err) {
    showToast(`Fehler beim Start: ${err.message}`, 'error');
  }
}

// ==========================================
// RECHTE DATEIVORSCHAU-SEITENLEISTE (7-ORDNER-PRO)
// ==========================================
function togglePreviewPane(forceState = null) {
  const next = forceState === null ? !state.previewVisible : Boolean(forceState);
  state.previewVisible = next;
  const pane = document.getElementById('preview-pane');
  const btn = document.getElementById('btn-toggle-preview');
  if (pane) pane.classList.toggle('hidden', !next);
  if (btn) btn.classList.toggle('active', next);
  if (next && state.activePreviewPath) {
    loadPreviewPaneForPath(state.activePreviewPath);
  }
}

function selectPreviewRow(file) {
  if (!file || !file.path) return;
  state.activePreviewPath = file.path;
  // Zeilen-Highlight schnell aktualisieren ohne DOM komplett neu aufzubauen
  const rows = document.querySelectorAll('#results-tbody tr.result-row');
  state.currentFiles.forEach((f, idx) => {
    if (rows[idx]) {
      rows[idx].classList.toggle('active-preview-row', f.path === file.path);
    }
  });
  if (state.previewVisible) {
    loadPreviewPaneForPath(file.path, file);
  }
}

async function loadPreviewPaneForPath(path, fileHint = null) {
  const stage = document.getElementById('preview-pane-stage');
  const badgeEl = document.getElementById('preview-pane-badge');
  const nameEl = document.getElementById('preview-pane-name');
  const typeSizeEl = document.getElementById('preview-pane-typesize');
  const dateEl = document.getElementById('preview-pane-date');
  const catEl = document.getElementById('preview-pane-cat');
  const targetEl = document.getElementById('preview-pane-target');
  const folderEl = document.getElementById('preview-pane-folder');
  const appBtn = document.getElementById('btn-preview-open-app');
  const expBtn = document.getElementById('btn-preview-open-exp');

  if (!stage) return;
  if (appBtn) appBtn.disabled = !path;
  if (expBtn) expBtn.disabled = !path;

  const fileObj = fileHint || state.currentFiles.find(f => f.path === path);
  if (fileObj) {
    if (nameEl) nameEl.textContent = fileObj.name || '';
    if (typeSizeEl) typeSizeEl.textContent = `${fileObj.ext || 'DATEI'} · ${fileObj.size_formatted || '—'}`;
    if (dateEl) dateEl.textContent = fileObj.modified_formatted || '—';
    if (catEl) catEl.textContent = fileObj.category_label || '—';
    if (targetEl) targetEl.textContent = fileObj.target_sub || '—';
    if (folderEl) folderEl.textContent = toGermanDisplayPath(fileObj.folder || '');
  }

  stage.innerHTML = `<div class="text-xs text-slate-400 py-8"><i class="fa-solid fa-spinner fa-spin mr-1.5"></i>Lade Vorschau...</div>`;

  try {
    const res = await fetch('/api/preview-info?path=' + encodeURIComponent(path));
    const info = await res.json();
    if (!info || !info.success) {
      stage.textContent = info?.error || 'Vorschau nicht verfügbar.';
      return;
    }
    if (badgeEl) {
      badgeEl.textContent = info.badge || '';
      badgeEl.classList.toggle('hidden', !info.badge);
    }
    if (nameEl) nameEl.textContent = info.name || '';
    if (typeSizeEl) typeSizeEl.textContent = `${info.ext} · ${info.size_formatted}`;
    if (dateEl) dateEl.textContent = info.modified_formatted;
    if (catEl) catEl.textContent = info.category_label;
    if (targetEl) targetEl.textContent = (fileObj?.target_sub) || info.target_sub || '—';
    if (folderEl) folderEl.textContent = toGermanDisplayPath(info.folder || '');

    if (info.kind === 'image') {
      const imgUrl = '/api/preview?path=' + encodeURIComponent(path);
      stage.innerHTML = `<img src="${imgUrl}" alt="${escapeHtml(info.name)}" class="max-w-full max-h-[340px] object-contain rounded-lg shadow-sm mx-auto">`;
    } else if (info.kind === 'pdf') {
      const pdfUrl = '/api/preview?path=' + encodeURIComponent(path) + '#toolbar=0&navpanes=0';
      stage.innerHTML = `<iframe src="${pdfUrl}" class="w-full h-[320px] rounded-lg border border-slate-700/50 bg-white"></iframe>`;
    } else if (info.kind === 'text') {
      stage.innerHTML = `<pre class="w-full h-full max-h-[320px] overflow-auto text-left text-[11px] font-mono whitespace-pre-wrap break-words p-2">${escapeHtml(info.text || '')}</pre>`;
    } else {
      stage.innerHTML = `<div class="p-4 text-xs text-slate-400 whitespace-pre-line">${escapeHtml(info.text || 'Keine direkte Vorschau.')}</div>`;
    }
  } catch (err) {
    stage.textContent = `Vorschau-Fehler: ${err.message}`;
  }
}

function previewPaneOpenApp() {
  if (state.activePreviewPath) openFile(state.activePreviewPath);
}

function previewPaneOpenExplorer() {
  if (state.activePreviewPath) openFolder(state.activePreviewPath);
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ==========================================
// SPEICHER-ORDNER WÄHLEN & DATEIEN KOPIEREN / VERSCHIEBEN
// ==========================================
function openTargetFolderModal(explicitPaths = null) {
  let targetPaths = [];
  if (Array.isArray(explicitPaths) && explicitPaths.length > 0) {
    targetPaths = explicitPaths;
  } else if (state.selectedFilePaths.size > 0) {
    targetPaths = Array.from(state.selectedFilePaths);
  } else if (state.currentFiles && state.currentFiles.length > 0) {
    targetPaths = state.currentFiles.map(f => f.path);
  }

  if (targetPaths.length === 0) {
    showToast('Bitte zuerst Dateien suchen oder markieren.', 'warning');
    return;
  }

  state.targetModalPaths = targetPaths;
  const firstFile = state.currentFiles.find(f => f.path === targetPaths[0]);
  const subEl = document.getElementById('target-folder-modal-subtitle');
  if (subEl) {
    if (targetPaths.length === 1 && firstFile) {
      subEl.textContent = `Auswahl: „${firstFile.name}“ (${state.selectedFilePaths.size === 0 ? 'einzelne Zeile' : '1 Datei'})`;
    } else {
      const scopeHint = state.selectedFilePaths.size > 0 ? 'ausgewählte Dateien' : 'sichtbare Treffer';
      subEl.textContent = `${targetPaths.length} ${scopeHint} bearbeiten`;
    }
  }

  // USB_Stick Quick-Button aktualisieren
  const usbBtn = document.getElementById('btn-tf-usb-quick');
  const usbLbl = document.getElementById('lbl-tf-usb-quick');
  if (usbBtn) {
    usbBtn.classList.toggle('hidden', !state.usbStickDir);
    if (usbLbl && state.usbStickDir) {
      const drv = state.usbStickDir.slice(0, 2);
      usbLbl.textContent = `USB_Stick (${drv})`;
    }
  }

  // Standardpfad vorbelegen (z. B. USB_Stick falls vorhanden, sonst Desktop)
  const pathInput = document.getElementById('target-folder-modal-path');
  if (pathInput && !pathInput.value.trim()) {
    pathInput.value = state.usbStickDir || '';
  }

  // 7-Ordner Schnellziele rendern
  const presetsEl = document.getElementById('target-folder-presets');
  if (presetsEl) {
    const opts = state.sevenFolderOptions && state.sevenFolderOptions.length > 0
      ? state.sevenFolderOptions
      : [
          ['01_Eingang_Inbox', 'Unbekannt -> Inbox'],
          ['07_Bilder', 'Bilder & Fotos'],
          ['08_Programme_Installer', 'Programme & Installer'],
          ['09_Videos_Medien', 'Videos & Medien'],
          ['10_Ordner_Projekte', 'Ordner & Projekte']
        ];
    presetsEl.innerHTML = opts.map(([sub, lbl]) => `
      <button
        type="button"
        onclick="pickSevenPresetInModal('${escapeJs(sub)}', '${escapeJs(lbl)}')"
        class="tf-preset-btn px-2.5 py-1.5 rounded-lg border border-slate-700/80 bg-slate-950/60 hover:border-blue-500 text-left transition flex flex-col"
      >
        <span class="font-semibold text-[11px] truncate">${escapeHtml(lbl)}</span>
        <span class="text-[10px] opacity-70 font-mono truncate">${escapeHtml(sub)}</span>
      </button>
    `).join('');
  }

  setTargetFolderModalMode(state.targetModalMode || 'copy');
  document.getElementById('modal-target-folder')?.classList.remove('hidden');
}

function closeTargetFolderModal() {
  document.getElementById('modal-target-folder')?.classList.add('hidden');
}

function setTargetFolderModalMode(mode) {
  state.targetModalMode = mode;
  document.querySelectorAll('#modal-target-folder .tf-mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tfMode === mode);
    const active = btn.dataset.tfMode === mode;
    btn.classList.toggle('border-blue-500', active);
    btn.classList.toggle('bg-blue-600/20', active);
    btn.classList.toggle('text-blue-200', active);
    btn.classList.toggle('border-slate-700', !active);
    btn.classList.toggle('bg-slate-950/50', !active);
    btn.classList.toggle('text-slate-300', !active);
  });

  const destSection = document.getElementById('target-folder-dest-section');
  const confirmBtn = document.getElementById('btn-tf-confirm');
  if (destSection) destSection.classList.toggle('opacity-50', mode === 'assign');
  if (confirmBtn) {
    const span = confirmBtn.querySelector('span');
    if (span) {
      if (mode === 'move') span.textContent = 'Dateien dorthin verschieben';
      else if (mode === 'assign') span.textContent = 'Zielordner in Tabelle übernehmen';
      else span.textContent = 'Dateien hierher kopieren';
    }
  }
}

async function browseTargetFolderInModal() {
  const pathInput = document.getElementById('target-folder-modal-path');
  const initialDir = (pathInput?.value || '').trim() || state.usbStickDir || '';
  try {
    const res = await fetch('/api/browse-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_dir: initialDir })
    });
    const d = await res.json();
    if (d.success && d.path && pathInput) {
      pathInput.value = d.path;
    }
  } catch (err) {
    showToast(`Ordnerauswahl fehlgeschlagen: ${err.message}`, 'error');
  }
}

async function pickUsbStickInTargetModal() {
  await refreshUsbStickShortcut();
  const pathInput = document.getElementById('target-folder-modal-path');
  if (state.usbStickDir && pathInput) {
    pathInput.value = state.usbStickDir;
    showToast(`Zielordner gesetzt: ${state.usbStickDir}`, 'info');
  } else {
    showToast('Kein USB-Stick mit Ordner USB_Stick erkannt.', 'warning');
  }
}

function pickSevenPresetInModal(sub, lbl) {
  const pathSet = new Set(state.targetModalPaths || []);
  const applySub = (arr) => {
    (arr || []).forEach(f => {
      if (pathSet.has(f.path)) {
        f.target_sub = sub;
        if (lbl) f.category_label = lbl;
      }
    });
  };
  applySub(state.currentFiles);
  applySub(state.allRawFiles);

  if (state.targetModalMode === 'assign') {
    renderResults();
    if (state.previewVisible && state.activePreviewPath && pathSet.has(state.activePreviewPath)) {
      const f = state.currentFiles.find(x => x.path === state.activePreviewPath);
      if (f) document.getElementById('preview-pane-target').textContent = f.target_sub;
    }
    closeTargetFolderModal();
    showToast(`✅ Zielordner auf „${sub}“ gesetzt (${pathSet.size} Dateien).`, 'success');
  } else {
    const baseInput = document.getElementById('target-folder-modal-path');
    const subCheck = document.getElementById('target-folder-use-sub');
    if (subCheck) subCheck.checked = true;
    const baseVal = (baseInput?.value || '').trim();
    if (!baseVal && state.usbStickDir && baseInput) {
      baseInput.value = state.usbStickDir;
    }
    showToast(`Kategorie-Unterordner „${sub}“ ausgewählt – jetzt Zielordner prüfen & bestätigen.`, 'info');
  }
}

async function confirmTargetFolderModal() {
  const paths = state.targetModalPaths || [];
  if (paths.length === 0) return;

  const targetDir = (document.getElementById('target-folder-modal-path')?.value || '').trim();
  const mode = state.targetModalMode || 'copy';
  const useSub = Boolean(document.getElementById('target-folder-use-sub')?.checked);

  if (mode === 'assign') {
    if (!targetDir) {
      showToast('Bitte zuerst einen Zielordner angeben oder oben eine 7-Ordner-Kategorie wählen.', 'warning');
      return;
    }
    const pathSet = new Set(paths);
    [state.currentFiles, state.allRawFiles].forEach(list => {
      (list || []).forEach(f => {
        if (pathSet.has(f.path)) f.target_sub = targetDir;
      });
    });
    renderResults();
    closeTargetFolderModal();
    showToast(`✅ Zielordner „${targetDir}“ für ${paths.length} Datei(en) vorgemerkt.`, 'success');
    return;
  }

  if (!targetDir) {
    showToast('Bitte einen Speicher-Ordner angeben oder über „Ordner wählen…“ auswählen.', 'warning');
    return;
  }

  if (mode === 'move') {
    const ok = await showConfirmDialog({
      title: `${paths.length} Datei${paths.length > 1 ? 'en' : ''} verschieben`,
      message: `Sollen ${paths.length} ausgewählte Datei(en) wirklich nach „${targetDir}“ verschoben werden?`,
      detail: 'Die Originaldateien werden am Quellort entfernt und im gewählten Speicher-Ordner abgelegt.',
      confirmText: 'Jetzt verschieben',
      cancelText: 'Abbrechen',
      type: 'warning'
    });
    if (!ok) return;
  }

  const items = paths.map(p => {
    const f = state.currentFiles.find(x => x.path === p);
    return { path: p, target_sub: f?.target_sub || '' };
  });

  try {
    const res = await fetch('/api/copy-or-move-files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items,
        target_dir: targetDir,
        mode,
        use_category_subfolder: useSub
      })
    });
    const d = await res.json();
    closeTargetFolderModal();
    if (d.success) {
      const verb = mode === 'move' ? 'verschoben' : 'kopiert';
      showToast(`✅ ${d.processed_count} Datei(en) erfolgreich nach „${d.target_dir}“ ${verb}!`, 'success');
      if (mode === 'move' && Array.isArray(d.processed)) {
        const movedMap = new Map(d.processed.filter(x => !x.unchanged).map(x => [x.src, x.dest]));
        if (movedMap.size > 0) {
          executeSearch();
        }
      }
    } else {
      showToast(d.error || 'Kopieren/Verschieben fehlgeschlagen', 'error');
    }
  } catch (err) {
    showToast(`Fehler beim Kopieren/Verschieben: ${err.message}`, 'error');
  }
}
