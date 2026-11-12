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
  emailClient: 'thunderbird'
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

    // Standard-Suchverzeichnis: DIESER PC (Alle Laufwerke C:, D: etc.)
    setSearchScope('pc');
  } catch (err) {
    console.error('System-Info Fehler:', err);
  }
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
    if (dirInput && (dirInput.value.includes('Dieser PC') || dirInput.value.includes('OneDrive') || dirInput.value.includes('Netzwerk') || ['THIS_PC', 'ONEDRIVE_ALL', 'NETWORK'].includes(dirInput.value))) {
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
  const minSizeMb = document.getElementById('min-size-mb')?.value || null;
  const maxSizeMb = document.getElementById('max-size-mb')?.value || null;
  const modifiedAfter = document.getElementById('modified-after')?.value || null;

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
        min_size_mb: minSizeMb,
        max_size_mb: maxSizeMb,
        modified_after: modifiedAfter,
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
    if (state.currentCategory && state.currentCategory !== 'all') {
      applyClientCategoryFilter();
    } else {
      state.currentFiles = [...state.allRawFiles];
    }

    // Stats aktualisieren
    document.getElementById('stat-count').textContent = state.currentFiles.length;
    document.getElementById('stat-size').textContent = data.total_size_formatted || '0 B';
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

    state.currentFiles.forEach((file, index) => {
      const isSelected = state.selectedFilePaths.has(file.path);
      const row = document.createElement('tr');
      row.className = `result-row transition cursor-pointer select-none ${isSelected ? 'selected' : ''}`;
      row.ondblclick = () => openFile(file.path);
      
      const fileIcon = getCategoryIconHtml(file.category, file.ext);
      let onedriveBadge = '';
      if (file.is_gdrive || file.cloud_type === 'gdrive' || (file.path && (file.path.toLowerCase().includes('google drive') || file.path.toLowerCase().includes('meine ablage')))) {
        onedriveBadge = `<span class="inline-flex items-center text-[10px] text-emerald-300 bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-500/30 ml-2 font-semibold" title="In Google Drive gesichert"><i class="fa-brands fa-google-drive mr-1"></i>Google Drive</span>`;
      } else if (file.is_icloud || file.cloud_type === 'icloud' || (file.path && file.path.toLowerCase().includes('\\iclouddrive'))) {
        onedriveBadge = `<span class="inline-flex items-center text-[10px] text-sky-300 bg-sky-500/15 px-1.5 py-0.5 rounded border border-sky-500/30 ml-2 font-semibold" title="In iCloud Drive gesichert"><i class="fa-brands fa-apple mr-1"></i>iCloud</span>`;
      } else if (file.onedrive_type === 'personal') {
        onedriveBadge = `<span class="inline-flex items-center text-[10px] text-sky-400 bg-sky-500/10 px-1.5 py-0.5 rounded border border-sky-500/20 ml-2" title="In OneDrive Privat gesichert"><i class="fa-solid fa-cloud mr-1"></i>Privat</span>`;
      } else if (file.onedrive_type === 'business') {
        onedriveBadge = `<span class="inline-flex items-center text-[10px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20 ml-2" title="In OneDrive Geschäft gesichert"><i class="fa-solid fa-building mr-1"></i>Geschäft</span>`;
      } else if (file.is_onedrive) {
        onedriveBadge = `<span class="inline-flex items-center text-[10px] text-sky-400 bg-sky-500/10 px-1.5 py-0.5 rounded border border-sky-500/20 ml-2" title="OneDrive"><i class="fa-solid fa-cloud mr-1"></i>OneDrive</span>`;
      }

      row.innerHTML = `
        <td class="py-2.5 px-4 text-center" onclick="event.stopPropagation()">
          <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleSelectFile('${escapeJs(file.path)}', this)" class="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 cursor-pointer">
        </td>
        <td class="py-2.5 px-4 text-left whitespace-nowrap">
          <div class="inline-flex items-center gap-1.5" title="Dateityp: ${file.ext || 'DATEI'} (${getAppLabelForExt(file.ext)})">
            ${fileIcon}
            <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/70">${file.ext || 'DATEI'}</span>
          </div>
        </td>
        <td class="py-2.5 px-4 font-medium text-slate-100 max-w-xs md:max-w-md truncate" onclick="openFile('${escapeJs(file.path)}')">
          <span class="hover:text-indigo-400 transition underline-offset-2 hover:underline cursor-pointer" title="In ${getAppLabelForExt(file.ext)} öffnen: ${file.name}">
            ${file.name}
          </span>
          ${onedriveBadge}
        </td>
        <td class="py-2.5 px-4 text-slate-300 font-mono text-[11px] truncate max-w-xs cursor-pointer hover:text-yellow-400 transition" onclick="event.stopPropagation(); openFolder('${escapeJs(file.path)}')" title="Im Windows Explorer öffnen: ${toGermanDisplayPath(file.folder)}">
          ${toGermanDisplayPath(file.folder)}
        </td>
        <td class="py-2.5 px-4 text-right text-slate-400 font-mono text-[11px] whitespace-nowrap">
          ${file.size_formatted}
        </td>
        <td class="py-2.5 px-4 text-slate-400 whitespace-nowrap text-[11px]">
          ${file.modified_formatted}
        </td>
        <td class="py-2.5 px-4 text-right action-cell whitespace-nowrap" onclick="event.stopPropagation()">
          <div class="flex items-center justify-end gap-1">
            <!-- Direktes Öffnen in Standard-App (Blau / Play) -->
            <button onclick="openFile('${escapeJs(file.path)}')" class="p-1.5 rounded-lg text-blue-400 hover:text-blue-300 hover:bg-blue-500/20 transition" title="In ${getAppLabelForExt(file.ext)} öffnen">
              <i class="fa-solid fa-play text-xs"></i>
            </button>
            <!-- In Explorer zeigen (Gelb / Ordner) -->
            <button onclick="openFolder('${escapeJs(file.path)}')" class="p-1.5 rounded-lg text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/20 transition" title="Im Windows Explorer anzeigen">
              <i class="fa-solid fa-folder-open text-xs"></i>
            </button>
            <!-- Teams / Mail Teilen (Violett / Teams) -->
            <button onclick="openShareModal('${escapeJs(file.path)}', '${escapeJs(file.name)}')" class="p-1.5 rounded-lg text-violet-400 hover:text-violet-300 hover:bg-violet-500/20 transition" title="Per Teams oder E-Mail senden">
              <i class="fa-solid fa-paper-plane text-xs"></i>
            </button>
            <!-- Umbenennen (Cyan / Türkis) -->
            <button onclick="openSingleRename('${escapeJs(file.path)}', '${escapeJs(file.name)}')" class="p-1.5 rounded-lg text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/20 transition" title="Umbenennen">
              <i class="fa-solid fa-pen text-xs"></i>
            </button>
            <!-- In Papierkorb (Rot / Rose) -->
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
    folder: 'Ordner-Pfad',
    size: 'Größe',
    modified: 'Änderungsdatum'
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
      // Sekundäre Sortierung nach Dateiname innerhalb desselben Dateityps
      const nameA = (a.name || '').toLowerCase();
      const nameB = (b.name || '').toLowerCase();
      return nameA.localeCompare(nameB, 'de');
    }

    let valA = a[state.sortCol];
    let valB = b[state.sortCol];
    if (typeof valA === 'string') valA = valA.toLowerCase();
    if (typeof valB === 'string') valB = valB.toLowerCase();
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
    case 'outlook': return 'Outlook';
    default: return 'Windows-Standard';
  }
}

function updateEmailClientUI() {
  const client = state.emailClient || 'gmail';

  // 1. Settings Modal
  const currentTextEl = document.getElementById('settings-email-current');
  if (currentTextEl) currentTextEl.textContent = getEmailClientLabel(client);

  const clients = ['gmail', 'icloud', 'thunderbird', 'outlook', 'default'];
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
    } else if (client === 'outlook') {
      descEl.textContent = 'Öffnet Microsoft Outlook mit angehängter Datei';
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
// GITHUB UPDATE MODAL (WIE IN PORTFOLIO-MANAGER)
// ==========================================
async function openGitUpdateModal() {
  document.getElementById('modal-git-update').classList.remove('hidden');
  try {
    const res = await fetch('/api/git-info');
    const data = await res.json();
    state.gitInfo = data;
    document.getElementById('git-branch').textContent = data.branch || 'main';
    document.getElementById('git-last-commit').textContent = data.last_commit || 'Keine Commit-Information';
    const remoteInput = document.getElementById('git-remote-input');
    if (remoteInput) {
      remoteInput.value = data.remote_url || 'https://github.com/charlywyss-beep/Datei-Suchmaschine.git';
    }
  } catch (err) {
    console.error('Git-Info Fehler:', err);
  }
}

async function runGitPush() {
  const btn = document.getElementById('btn-run-git-push');
  const logContainer = document.getElementById('git-log-container');
  const logOutput = document.getElementById('git-log-output');

  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Übertrage nach GitHub...</span>';
  logContainer.classList.remove('hidden');
  logOutput.textContent = 'Führe "git push -u origin main" aus...\n';

  try {
    const res = await fetch('/api/git-push', { method: 'POST' });
    const d = await res.json();
    logOutput.textContent = d.output || d.message || d.error || 'Fertig';

    if (d.success) {
      showToast('🎉 Stand erfolgreich nach GitHub übertragen!', 'success');
      btn.innerHTML = '<i class="fa-solid fa-check"></i><span>Übertragen!</span>';
    } else {
      showToast(d.message || d.error || 'Upload fehlgeschlagen', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-arrow-up-from-bracket"></i><span>Erneut versuchen</span>';
    }
  } catch (err) {
    logOutput.textContent = `Fehler: ${err.message}`;
    showToast(`Fehler: ${err.message}`, 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-arrow-up-from-bracket"></i><span>Stand hochladen</span>';
  }
}

function closeGitUpdateModal() {
  document.getElementById('modal-git-update').classList.add('hidden');
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
      showToast('🎉 Erfolgreich auf den neuesten GitHub-Stand aktualisiert!', 'success');
      btn.innerHTML = '<i class="fa-solid fa-check"></i><span>Aktuell!</span>';
      setTimeout(() => location.reload(), 2500);
    } else {
      showToast(d.message || d.error || 'Update fehlgeschlagen', 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i><span>Erneut versuchen</span>';
    }
  } catch (err) {
    logOutput.textContent = `Fehler: ${err.message}`;
    showToast(`Update-Fehler: ${err.message}`, 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i><span>Jetzt aktualisieren</span>';
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
