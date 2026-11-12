import os
import sys
import json
import time
import socket
import hashlib
import subprocess
import mimetypes
from pathlib import Path
from datetime import datetime
from send2trash import send2trash

APP_VERSION = "v1.7.6"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def detect_onedrive_paths():
    user_home = os.path.expanduser("~")
    cfg = load_config()

    # 1. Privates OneDrive
    personal_path = cfg.get("onedrive_personal") or os.environ.get("OneDriveConsumer") or os.environ.get("OneDrive") or os.path.join(user_home, "OneDrive")
    if not os.path.exists(personal_path):
        personal_path = os.path.join(user_home, "OneDrive")

    # 2. Geschäftliches OneDrive
    business_path = cfg.get("onedrive_business") or os.environ.get("OneDriveCommercial")

    if not business_path or not os.path.exists(business_path):
        # Automatisch im Benutzerordner nach 'OneDrive - *' suchen
        try:
            for item in os.listdir(user_home):
                item_lower = item.lower()
                if item_lower.startswith("onedrive -") or item_lower.startswith("onedrive-"):
                    cand = os.path.join(user_home, item)
                    if os.path.isdir(cand):
                        business_path = cand
                        break
        except Exception:
            pass

    # Fallback / Platzhalter falls noch nicht existiert
    if not business_path:
        business_path = os.path.join(user_home, "OneDrive - Geschaeft")

    # 3. Transfer-Hub Ordner (für einfachen Austausch mit iPad/iPhone & Geschäft/Zuhause)
    base_cloud = personal_path if os.path.exists(personal_path) else (business_path if os.path.exists(business_path) else user_home)
    transfer_path = os.path.join(base_cloud, "Transfer_Zuhause_Geschaeft_iPad")
    if not os.path.exists(transfer_path):
        try:
            os.makedirs(transfer_path, exist_ok=True)
        except Exception:
            pass

    # 4. iCloud Drive (Apple)
    icloud_path = cfg.get("icloud_drive") or os.path.join(user_home, "iCloudDrive")
    icloud_exists = os.path.exists(icloud_path)

    # 5. Google Drive
    gdrive_path = cfg.get("google_drive")
    if not gdrive_path:
        for cand in [
            "G:\\Meine Ablage",
            "G:\\My Drive",
            "G:\\",
            os.path.join(user_home, "Google Drive"),
            os.path.join(user_home, "GoogleDrive"),
        ]:
            if os.path.exists(cand):
                gdrive_path = cand
                break
    if not gdrive_path:
        gdrive_path = "G:\\Meine Ablage"
    gdrive_exists = os.path.exists(gdrive_path)

    return {
        "personal": {
            "name": "OneDrive Privat",
            "path": personal_path,
            "exists": os.path.exists(personal_path)
        },
        "business": {
            "name": "OneDrive Geschäftlich",
            "path": business_path,
            "exists": os.path.exists(business_path)
        },
        "transfer": {
            "name": "Transfer-Hub (Zuhause ⇄ Geschäft)",
            "path": transfer_path,
            "exists": os.path.exists(transfer_path)
        },
        "icloud": {
            "name": "iCloud Drive",
            "path": icloud_path,
            "exists": icloud_exists
        },
        "gdrive": {
            "name": "Google Drive",
            "path": gdrive_path,
            "exists": gdrive_exists
        }
    }

ONEDRIVE_INFO = detect_onedrive_paths()
ONEDRIVE_PATH = ONEDRIVE_INFO["personal"]["path"]

def get_local_ip():
    """Ermittelt die lokale Netzwerk-IP für iPad / iPhone Zugriff"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

CATEGORY_EXTENSIONS = {
    "pdf": {".pdf"},
    "word": {".docx", ".doc", ".rtf", ".odt", ".dot", ".dotx"},
    "excel": {".xlsx", ".xls", ".csv", ".ods", ".xlsm", ".xlsb"},
    "powerpoint": {".pptx", ".ppt", ".pps", ".ppsx", ".odp"},
    "access": {".accdb", ".mdb", ".accde", ".accdr"},
    "office": {".pdf", ".docx", ".doc", ".rtf", ".odt", ".xlsx", ".xls", ".csv", ".ods", ".accdb", ".mdb", ".accde", ".accdr", ".pptx", ".ppt"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff", ".tif", ".heic", ".raw"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".m2ts", ".3gp", ".vob"},
    "audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"},
    "email": {".msg", ".eml", ".pst", ".ost", ".vcf", ".ics"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"},
    "setup": {".exe", ".msi", ".iso", ".bat", ".cmd", ".appx", ".msix"},
    "code": {".txt", ".srt", ".vtt", ".sub", ".nfo", ".cfg", ".ini", ".conf", ".env", ".toml", ".log", ".py", ".js", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".ps1", ".md"},
}

def format_size(size_bytes):
    if size_bytes is None:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}" if unit != 'B' else f"{int(size_bytes)} B"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def resolve_german_alias_path(path_str):
    """Löst deutsche Pfadnamen wie Dokumente automatisch in den echten Windows-Pfad Documents auf"""
    if not path_str or not isinstance(path_str, str):
        return path_str
    
    clean_p = path_str.strip()
    if os.path.exists(clean_p):
        return clean_p

    # Mapping von deutschen Anzeigenamen auf reale Windows-Dateinamen
    replacements = [
        ("\\Dokumente", "\\Documents"),
        ("/Dokumente", "/Documents"),
        ("\\dokumente", "\\Documents"),
        ("/dokumente", "/Documents"),
        ("\\Bilder", "\\Pictures"),
        ("/Bilder", "/Pictures"),
        ("\\bilder", "\\Pictures"),
        ("/bilder", "/Pictures"),
        ("\\Benutzer", "\\Users"),
        ("/Benutzer", "/Users")
    ]
    cand = clean_p
    for de, en in replacements:
        cand = cand.replace(de, en)
        if os.path.exists(cand):
            return cand

    return clean_p

def to_german_display_path(path_str):
    """Macht Windows-Pfade für die Anzeige im UI 100% deutsch (z.B. Documents -> Dokumente)"""
    if not path_str or not isinstance(path_str, str):
        return path_str
    import re
    return re.sub(r'[\\/]Documents\b', lambda m: m.group(0)[0] + 'Dokumente', path_str, flags=re.IGNORECASE)

def get_saved_paths():
    r"""Gibt gespeicherte Suchpfade zurück (inkl. D:\01\Dokumente Standard-Favorit)"""
    cfg = load_config()
    paths = cfg.get("saved_paths", [])
    if not paths and os.path.exists("D:\\01\\Documents"):
        paths = [
            {"id": "fav_d_doc", "name": "Dokumente (D:)", "path": "D:\\01\\Documents\\", "icon": "folder"}
        ]
        cfg["saved_paths"] = paths
        save_config(cfg)
    return paths

def get_all_local_drives():
    """Findet alle verfügbaren lokalen Windows-Laufwerke (C:, D:, etc.)"""
    import string
    drives = []
    for letter in string.ascii_uppercase:
        d_path = f"{letter}:\\"
        if os.path.exists(d_path):
            drives.append(d_path)
    return drives

def get_network_paths():
    """Liest gemappte Netzlaufwerke sowie in config.json hinterlegte Netzwerk-Freigaben"""
    cfg = load_config()
    saved_net = cfg.get("network_paths", [])
    
    # Automatisch gemappte Netzlaufwerke über net use / PowerShell prüfen
    auto_net = []
    try:
        import string
        for letter in string.ascii_uppercase:
            # Übliche Netzlaufwerk-Buchstaben Z bis S
            if letter in {'Z', 'Y', 'X', 'W', 'V', 'U', 'T', 'S'}:
                p = f"{letter}:\\"
                if os.path.exists(p):
                    auto_net.append({"id": f"net_{letter}", "name": f"Netzlaufwerk ({letter}:)", "path": p, "auto": True})
    except Exception:
        pass

    # Kombiniere beide
    combined = auto_net + [p for p in saved_net if not any(a["path"].lower() == p["path"].lower() for a in auto_net)]
    return combined

def add_network_path(path_str, name=""):
    """Fügt einen neuen Netzwerk-Suchpfad hinzu (z.B. \\\\NAS\\Freigabe oder Z:\\)"""
    cfg = load_config()
    net_paths = cfg.get("network_paths", [])
    clean_p = path_str.strip()
    
    import uuid
    new_item = {
        "id": f"net_{uuid.uuid4().hex[:8]}",
        "name": name.strip() or os.path.basename(clean_p) or clean_p,
        "path": clean_p,
        "exists": os.path.exists(clean_p)
    }
    net_paths.append(new_item)
    cfg["network_paths"] = net_paths
    save_config(cfg)
    return {"success": True, "network_paths": get_network_paths(), "item": new_item}

def remove_network_path(path_id):
    """Löscht einen hinterlegten Netzwerk-Pfad"""
    cfg = load_config()
    net_paths = cfg.get("network_paths", [])
    new_list = [p for p in net_paths if p.get("id") != path_id and p.get("path") != path_id]
    cfg["network_paths"] = new_list
    save_config(cfg)
    return {"success": True, "network_paths": get_network_paths()}

def add_saved_path(name, path_str):
    """Speichert einen neuen Suchpfad dauerhaft"""
    cfg = load_config()
    paths = cfg.get("saved_paths", [])
    clean_path = os.path.abspath(path_str.strip())
    
    # Prüfe ob bereits existiert
    for p in paths:
        if os.path.normcase(p["path"]) == os.path.normcase(clean_path):
            p["name"] = name.strip()
            save_config(cfg)
            return {"success": True, "saved_paths": paths, "updated": True}

    import uuid
    new_item = {
        "id": f"fav_{uuid.uuid4().hex[:8]}",
        "name": name.strip() or os.path.basename(clean_path) or clean_path,
        "path": clean_path,
        "icon": "star",
        "exists": os.path.exists(clean_path)
    }
    paths.append(new_item)
    cfg["saved_paths"] = paths
    save_config(cfg)
    return {"success": True, "saved_paths": paths, "item": new_item}

def remove_saved_path(path_id):
    """Entfernt einen gespeicherten Suchpfad"""
    cfg = load_config()
    paths = cfg.get("saved_paths", [])
    new_paths = [p for p in paths if p.get("id") != path_id and p.get("path") != path_id]
    cfg["saved_paths"] = new_paths
    save_config(cfg)
    return {"success": True, "saved_paths": new_paths}

# ==========================================
# SUCH-VERLAUF (HISTORY) & GESPEICHERTE SUCHEN
# ==========================================
def get_search_history():
    """Gibt die letzten Suchanfragen zurück"""
    cfg = load_config()
    return cfg.get("search_history", [])

def add_search_history(query, category="all"):
    """Speichert eine ausgeführte Suche automatisch im Verlauf (max. 15 Einträge)"""
    q = (query or "").strip()
    if not q:
        return get_search_history()
    cfg = load_config()
    history = cfg.get("search_history", [])
    cat = (category or "all").strip().lower()
    # Vorhandenen identischen Eintrag entfernen (damit er nach vorne rückt)
    history = [h for h in history if not (h.get("query", "").lower() == q.lower() and h.get("category", "all") == cat)]
    import uuid
    new_entry = {
        "id": f"hist_{uuid.uuid4().hex[:8]}",
        "query": q,
        "category": cat,
        "timestamp": datetime.now().strftime("%d.%m. %H:%M")
    }
    history.insert(0, new_entry)
    history = history[:15]
    cfg["search_history"] = history
    save_config(cfg)
    return history

def remove_search_history(item_id=None, clear_all=False):
    """Löscht einen einzelnen Verlaufseintrag oder leert den gesamten Such-Verlauf"""
    cfg = load_config()
    if clear_all:
        cfg["search_history"] = []
    else:
        history = cfg.get("search_history", [])
        cfg["search_history"] = [h for h in history if h.get("id") != item_id and h.get("query") != item_id]
    save_config(cfg)
    return {"success": True, "search_history": cfg.get("search_history", [])}

def get_saved_searches():
    """Gibt dauerhaft gespeicherte Suchanfragen (Favoriten-Suchen) zurück"""
    cfg = load_config()
    return cfg.get("saved_searches", [])

def add_saved_search(query, category="all", name=""):
    """Speichert eine wiederkehrende Dateisuche dauerhaft ab"""
    q = (query or "").strip()
    if not q:
        return {"success": False, "error": "Bitte zuerst einen Suchbegriff eingeben"}
    cfg = load_config()
    saved = cfg.get("saved_searches", [])
    cat = (category or "all").strip().lower()
    for s in saved:
        if s.get("query", "").lower() == q.lower() and s.get("category", "all") == cat:
            if name.strip():
                s["name"] = name.strip()
                save_config(cfg)
            return {"success": True, "saved_searches": saved, "updated": True}
    import uuid
    new_item = {
        "id": f"ssearch_{uuid.uuid4().hex[:8]}",
        "name": name.strip() or q,
        "query": q,
        "category": cat
    }
    saved.append(new_item)
    cfg["saved_searches"] = saved
    save_config(cfg)
    return {"success": True, "saved_searches": saved, "item": new_item}

def remove_saved_search(search_id):
    """Entfernt eine gespeicherte Suche"""
    cfg = load_config()
    saved = cfg.get("saved_searches", [])
    new_saved = [s for s in saved if s.get("id") != search_id and s.get("query") != search_id]
    cfg["saved_searches"] = new_saved
    save_config(cfg)
    return {"success": True, "saved_searches": new_saved}

def get_system_locations():
    user_home = os.path.expanduser("~")
    od_info = detect_onedrive_paths()
    
    locations = [
        {"id": "onedrive_personal", "name": "OneDrive Privat", "path": od_info["personal"]["path"], "icon": "cloud", "badge": "Privat", "exists": od_info["personal"]["exists"]},
        {"id": "onedrive_business", "name": "OneDrive Geschäftlich", "path": od_info["business"]["path"], "icon": "building", "badge": "Business", "exists": od_info["business"]["exists"]},
        {"id": "transfer_hub", "name": "Transfer-Hub (Sync)", "path": od_info["transfer"]["path"], "icon": "arrows-rotate", "badge": "iPad/iPhone", "exists": od_info["transfer"]["exists"]},
        {"id": "icloud_drive", "name": "iCloud Drive", "path": od_info["icloud"]["path"], "icon": "cloud", "badge": "iCloud", "exists": od_info["icloud"]["exists"]},
        {"id": "gdrive", "name": "Google Drive", "path": od_info["gdrive"]["path"], "icon": "google-drive", "badge": "Google", "exists": od_info["gdrive"]["exists"]},
        {"id": "documents", "name": "Dokumente (C:)", "path": os.path.join(user_home, "Documents") + "\\", "icon": "folder", "exists": (os.path.exists(os.path.join(user_home, "Documents")) or os.path.exists(os.path.join(user_home, "Dokumente")))},
    ]

    # Spezielle Erkennung für D:\01\Documents
    d_doc = "D:\\01\\Documents"
    if os.path.exists(d_doc) or os.path.exists("D:\\01\\Dokumente"):
        locations.append({"id": "d_documents", "name": "Dokumente (D:)", "path": "D:\\01\\Documents\\", "icon": "folder", "badge": "D:", "exists": True})

    locations.extend([
        {"id": "downloads", "name": "Downloads", "path": os.path.join(user_home, "Downloads"), "icon": "download", "exists": os.path.exists(os.path.join(user_home, "Downloads"))},
        {"id": "desktop", "name": "Desktop", "path": os.path.join(user_home, "Desktop"), "icon": "monitor", "exists": os.path.exists(os.path.join(user_home, "Desktop"))},
        {"id": "pictures", "name": "Bilder", "path": os.path.join(user_home, "Pictures"), "icon": "image", "exists": os.path.exists(os.path.join(user_home, "Pictures"))},
        {"id": "c_drive", "name": "Festplatte (C:)", "path": "C:\\", "icon": "hard-drive", "exists": os.path.exists("C:\\")},
    ])

    # Check other drives
    import string
    for letter in string.ascii_uppercase:
        if letter == 'C':
            continue
        d_path = f"{letter}:\\"
        if os.path.exists(d_path):
            locations.append({"id": f"drive_{letter}", "name": f"Laufwerk ({letter}:)", "path": d_path, "icon": "hard-drive", "exists": True})
    return locations

def is_onedrive_path(path_str):
    od_info = detect_onedrive_paths()
    try:
        norm_file = os.path.normcase(os.path.abspath(path_str))
        p_pers = od_info["personal"]["path"]
        if p_pers and os.path.exists(p_pers):
            if norm_file.startswith(os.path.normcase(os.path.abspath(p_pers))):
                return "personal"
        p_biz = od_info["business"]["path"]
        if p_biz and os.path.exists(p_biz):
            if norm_file.startswith(os.path.normcase(os.path.abspath(p_biz))):
                return "business"
    except Exception:
        pass
    return None

def get_file_category(ext):
    ext_lower = ext.lower()
    for cat, exts in CATEGORY_EXTENSIONS.items():
        if cat == "office":
            continue
        if ext_lower in exts:
            return cat
    return "other"

def fast_search(
    root_dir,
    query="",
    category="all",
    custom_extensions=None,
    min_size_bytes=None,
    max_size_bytes=None,
    modified_after_ts=None,
    modified_before_ts=None,
    only_onedrive=False,
    max_results=5000,
    stop_event=None
):
    results = []

    # Mehrere Start-Ordner unterstützen (z.B. Ganzer PC: C:\ und D:\ gleichzeitig)
    start_dirs = []
    root_str_lower = str(root_dir).strip().lower()

    if isinstance(root_dir, list):
        start_dirs = [os.path.abspath(d) for d in root_dir if os.path.exists(d)]
    elif root_str_lower in ("this_pc", "pc", "all_drives") or "dieser pc" in root_str_lower or "alle laufwerke" in root_str_lower:
        start_dirs = [d for d in get_all_local_drives() if os.path.exists(d)]
    elif root_str_lower in ("onedrive_all", "onedrive", "cloud", "all_cloud", "iclouddrive", "icloud") or any(k in root_str_lower for k in ("onedrive", "icloud", "cloud")):
        od_info = detect_onedrive_paths()
        if "icloud" in root_str_lower and "onedrive" not in root_str_lower:
            if od_info.get("icloud", {}).get("exists"):
                start_dirs.append(od_info["icloud"]["path"])
        elif "onedrive" in root_str_lower and "icloud" not in root_str_lower:
            if od_info["personal"]["exists"]:
                start_dirs.append(od_info["personal"]["path"])
            if od_info["business"]["exists"]:
                start_dirs.append(od_info["business"]["path"])
        else:
            if od_info["personal"]["exists"]:
                start_dirs.append(od_info["personal"]["path"])
            if od_info["business"]["exists"]:
                start_dirs.append(od_info["business"]["path"])
            if od_info.get("icloud", {}).get("exists"):
                start_dirs.append(od_info["icloud"]["path"])
    elif root_str_lower in ("network", "netzwerk") or "netzwerk" in root_str_lower:
        net_list = get_network_paths()
        start_dirs = [n["path"] for n in net_list if os.path.exists(n["path"])]
    else:
        real_root = resolve_german_alias_path(root_dir)
        abs_p = os.path.abspath(real_root)
        if os.path.exists(abs_p):
            start_dirs = [abs_p]

    if not start_dirs:
        return results

    query_parts = [q.strip().lower() for q in query.split() if q.strip()]
    allowed_exts = None
    if custom_extensions:
        allowed_exts = {ext.strip().lower() if ext.startswith('.') else f".{ext.strip().lower()}" for ext in custom_extensions.split(',') if ext.strip()}
    elif category and category != "all" and category in CATEGORY_EXTENSIONS:
        allowed_exts = CATEGORY_EXTENSIONS[category]

    norm_onedrive = os.path.normcase(os.path.abspath(ONEDRIVE_PATH)) if ONEDRIVE_PATH and os.path.exists(ONEDRIVE_PATH) else None
    od_info = detect_onedrive_paths()
    p_personal = os.path.normcase(os.path.abspath(od_info["personal"]["path"])) if od_info["personal"]["exists"] else None
    p_business = os.path.normcase(os.path.abspath(od_info["business"]["path"])) if od_info["business"]["exists"] else None
    p_icloud = os.path.normcase(os.path.abspath(od_info["icloud"]["path"])) if od_info.get("icloud", {}).get("exists") else None
    p_gdrive = os.path.normcase(os.path.abspath(od_info["gdrive"]["path"])) if od_info.get("gdrive", {}).get("exists") else None

    # Skip heavy system / program / cache directories unless user explicitly searches inside them
    skip_dirs = {"$recycle.bin", "system volume information", "windows", "appdata", "node_modules", ".git", "__pycache__"}
    start_dirs_lower = [sd.lower() for sd in start_dirs]
    system_prefixes = (
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
        "c:\\programdata",
        "c:\\python",
        "c:\\recovery",
        "c:\\msocache",
    )

    count = 0
    stack = list(start_dirs)

    while stack and count < max_results:
        if stop_event and stop_event.is_set():
            break
        current_dir = stack.pop()

        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if count >= max_results:
                        break
                    
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                    except (PermissionError, OSError):
                        continue

                    if is_dir:
                        dirname = entry.name
                        dirname_lower = dirname.lower()
                        # Skip hidden/system directories
                        if dirname_lower.startswith('$') or dirname_lower in skip_dirs:
                            continue
                        full_entry_path = entry.path.lower()
                        # Skip internal Windows/Program installation folders unless user explicitly searched inside them
                        matched_sp = next((sp for sp in system_prefixes if full_entry_path.startswith(sp)), None)
                        if matched_sp and not any(sd.startswith(matched_sp) for sd in start_dirs_lower):
                            continue
                        if "\\.gemini\\antigravity-" in full_entry_path:
                            continue
                        stack.append(entry.path)

                        # Ordner als Suchtreffer aufnehmen:
                        # - Wenn Kategorie 'folder' gewählt ist
                        # - Oder wenn Kategorie 'all' (ohne custom_extensions) gewählt ist und entweder nach Namen gesucht wird
                        #   oder ein einzelner spezifischer Ordner durchsucht wird (direkte Unterordner)
                        include_folder = False
                        if category == "folder":
                            include_folder = (not query_parts) or all(qp in dirname_lower for qp in query_parts)
                        elif (not category or category == "all") and not custom_extensions and min_size_bytes is None and max_size_bytes is None:
                            if query_parts:
                                include_folder = all(qp in dirname_lower for qp in query_parts)
                            elif len(start_dirs) == 1 and os.path.normcase(current_dir) == os.path.normcase(start_dirs[0]) and len( current_dir ) > 3:
                                include_folder = True

                        if include_folder:
                            try:
                                stat_res = entry.stat(follow_symlinks=False)
                                mtime = stat_res.st_mtime
                            except (PermissionError, OSError):
                                continue

                            if modified_after_ts is not None and mtime < modified_after_ts:
                                continue
                            if modified_before_ts is not None and mtime > modified_before_ts:
                                continue

                            norm_entry = os.path.normcase(os.path.abspath(entry.path))
                            cloud_type = None
                            if p_gdrive and norm_entry.startswith(p_gdrive):
                                cloud_type = "gdrive"
                            elif p_icloud and norm_entry.startswith(p_icloud):
                                cloud_type = "icloud"
                            elif p_personal and norm_entry.startswith(p_personal):
                                cloud_type = "personal"
                            elif p_business and norm_entry.startswith(p_business):
                                cloud_type = "business"
                            is_onedrive_type = cloud_type if cloud_type in ("personal", "business") else None

                            if only_onedrive:
                                if only_onedrive == "business" and is_onedrive_type != "business":
                                    continue
                                elif only_onedrive == "personal" and is_onedrive_type != "personal":
                                    continue
                                elif only_onedrive in (True, "any") and not is_onedrive_type:
                                    continue

                            mtime_dt = datetime.fromtimestamp(mtime)
                            results.append({
                                "name": dirname,
                                "path": entry.path,
                                "folder": to_german_display_path(os.path.dirname(entry.path)),
                                "ext": "ORDNER",
                                "category": "folder",
                                "is_dir": True,
                                "size": 0,
                                "size_formatted": "Ordner",
                                "modified": mtime_dt.isoformat(),
                                "modified_formatted": mtime_dt.strftime("%d.%m.%y %H:%M"),
                                "is_onedrive": bool(is_onedrive_type),
                                "onedrive_type": is_onedrive_type,
                                "cloud_type": cloud_type,
                                "is_icloud": cloud_type == "icloud",
                                "is_gdrive": cloud_type == "gdrive"
                            })
                            count += 1
                    else:
                        if category == "folder":
                            continue
                        # File matching
                        filename = entry.name
                        filename_lower = filename.lower()

                        # Query match (all words must match)
                        if query_parts:
                            if not all(qp in filename_lower for qp in query_parts):
                                continue

                        # Extension match (interne .lnk Verknüpfungen und Office-Sperrdateien .laccdb / ~$ ignorieren)
                        _, ext = os.path.splitext(filename_lower)
                        if ext in (".lnk", ".laccdb", ".ldb") or filename_lower.startswith("~$"):
                            continue
                        if allowed_exts is not None and ext not in allowed_exts:
                            continue

                        # Stat
                        try:
                            stat_res = entry.stat(follow_symlinks=False)
                            size = stat_res.st_size
                            mtime = stat_res.st_mtime
                        except (PermissionError, OSError):
                            continue

                        # Size filters
                        if min_size_bytes is not None and size < min_size_bytes:
                            continue
                        if max_size_bytes is not None and size > max_size_bytes:
                            continue

                        # Date filters
                        if modified_after_ts is not None and mtime < modified_after_ts:
                            continue
                        if modified_before_ts is not None and mtime > modified_before_ts:
                            continue

                        # Cloud-Check (OneDrive vs iCloud)
                        norm_entry = os.path.normcase(os.path.abspath(entry.path))
                        cloud_type = None
                        if p_gdrive and norm_entry.startswith(p_gdrive):
                            cloud_type = "gdrive"
                        elif p_icloud and norm_entry.startswith(p_icloud):
                            cloud_type = "icloud"
                        elif p_personal and norm_entry.startswith(p_personal):
                            cloud_type = "personal"
                        elif p_business and norm_entry.startswith(p_business):
                            cloud_type = "business"
                        is_onedrive_type = cloud_type if cloud_type in ("personal", "business") else None

                        if only_onedrive:
                            if only_onedrive == "business" and is_onedrive_type != "business":
                                continue
                            elif only_onedrive == "personal" and is_onedrive_type != "personal":
                                continue
                            elif only_onedrive in (True, "any") and not is_onedrive_type:
                                continue

                        cat = get_file_category(ext)
                        mtime_dt = datetime.fromtimestamp(mtime)

                        results.append({
                            "name": filename,
                            "path": entry.path,
                            "folder": to_german_display_path(os.path.dirname(entry.path)),
                            "ext": ext.replace(".", "").upper() or "DATEI",
                            "category": cat,
                            "size": size,
                            "size_formatted": format_size(size),
                            "modified": mtime_dt.isoformat(),
                            "modified_formatted": mtime_dt.strftime("%d.%m.%y %H:%M"),
                            "is_onedrive": bool(is_onedrive_type),
                            "onedrive_type": is_onedrive_type,
                            "cloud_type": cloud_type,
                            "is_icloud": cloud_type == "icloud",
                            "is_gdrive": cloud_type == "gdrive"
                        })
                        count += 1
        except (PermissionError, OSError):
            continue

    return results

def compute_file_hash(filepath, block_size=65536, partial=False):
    """Berechnet SHA-256 Hash. Bei partial=True nur die ersten 64KB (für Vorab-Filterung)"""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            if partial:
                buf = f.read(block_size)
                hasher.update(buf)
            else:
                while True:
                    buf = f.read(block_size)
                    if not buf:
                        break
                    hasher.update(buf)
        return hasher.hexdigest()
    except (PermissionError, OSError):
        return None

def find_duplicates(file_list_or_path, progress_callback=None):
    """
    Findet Duplikate entweder aus einer Liste von Dateien oder durch Durchsuchen eines Pfads.
    Verwendet 2-stufigen Hash:
    1. Gruppierung nach Dateigröße
    2. Gruppierung nach erstem 64KB Hash
    3. Vollständiger SHA-256 Hash für exakte Treffer
    """
    if isinstance(file_list_or_path, str):
        # Scan dir
        files = fast_search(file_list_or_path, max_results=10000)
    else:
        files = file_list_or_path

    # Phase 1: Gruppierung nach Dateigröße (nur Dateien > 0 Bytes)
    size_groups = {}
    for f in files:
        sz = f.get("size", 0)
        if sz > 0:
            size_groups.setdefault(sz, []).append(f)

    potential_duplicates = [g for g in size_groups.values() if len(g) > 1]
    
    # Phase 2 & 3: Hashing
    hash_groups = {}
    total_to_hash = sum(len(g) for g in potential_duplicates)
    hashed_count = 0

    for group in potential_duplicates:
        # Partial hash first
        partial_map = {}
        for f in group:
            p_hash = compute_file_hash(f["path"], partial=True)
            if p_hash:
                partial_map.setdefault(p_hash, []).append(f)
            hashed_count += 1
            if progress_callback and hashed_count % 20 == 0:
                progress_callback(hashed_count, total_to_hash)

        # For partial hash collisions, compute full hash
        for p_hash, candidates in partial_map.items():
            if len(candidates) > 1:
                for c in candidates:
                    full_hash = compute_file_hash(c["path"], partial=False)
                    if full_hash:
                        c["hash"] = full_hash
                        hash_groups.setdefault(full_hash, []).append(c)

    # Resultate strukturieren
    duplicate_sets = []
    group_id = 1
    total_wasted_bytes = 0

    for f_hash, members in hash_groups.items():
        if len(members) > 1:
            # Sortieren: z.B. nach Änderungsdatum (älteste zuerst)
            members.sort(key=lambda x: x.get("modified", ""))
            
            # Kennzeichnung: das 1. Element ist "original" (behalten), die restlichen sind Duplikate
            wasted = members[0]["size"] * (len(members) - 1)
            total_wasted_bytes += wasted

            duplicate_sets.append({
                "group_id": group_id,
                "hash": f_hash,
                "file_size": members[0]["size"],
                "file_size_formatted": members[0]["size_formatted"],
                "duplicate_count": len(members),
                "wasted_bytes": wasted,
                "wasted_formatted": format_size(wasted),
                "files": members
            })
            group_id += 1

    return {
        "sets": duplicate_sets,
        "total_duplicate_files": sum(s["duplicate_count"] for s in duplicate_sets),
        "total_groups": len(duplicate_sets),
        "total_wasted_bytes": total_wasted_bytes,
        "total_wasted_formatted": format_size(total_wasted_bytes)
    }

def delete_to_trash(file_paths):
    """Sicheres Löschen in den Windows Papierkorb mit send2trash"""
    results = {"success": [], "errors": []}
    for p in file_paths:
        try:
            if os.path.exists(p):
                send2trash(p)
                results["success"].append(p)
            else:
                results["errors"].append({"path": p, "error": "Datei existiert nicht"})
        except Exception as e:
            results["errors"].append({"path": p, "error": str(e)})
    return results

def rename_single_file(old_path, new_name):
    """Benennt eine einzelne Datei um"""
    try:
        if not os.path.exists(old_path):
            return {"success": False, "error": "Datei nicht gefunden"}
        
        dir_name = os.path.dirname(old_path)
        new_path = os.path.join(dir_name, new_name)
        
        if os.path.exists(new_path) and os.path.normcase(old_path) != os.path.normcase(new_path):
            return {"success": False, "error": "Eine Datei mit diesem Namen existiert bereits im Ordner."}

        os.rename(old_path, new_path)
        return {"success": True, "old_path": old_path, "new_path": new_path, "new_name": new_name}
    except Exception as e:
        return {"success": False, "error": str(e)}

def batch_rename_preview(files, rule_type, params):
    """
    Erzeugt Vorschau für Batch-Umbenennung ohne Änderungen auf der Platte.
    rule_type:
      - 'replace': search, replace, case_sensitive
      - 'prefix_suffix': prefix, suffix
      - 'numbering': pattern ('{name}_{index}', '{index}_{name}'), start_num, digits
      - 'case': 'upper', 'lower', 'title'
      - 'date': position ('prefix', 'suffix'), date_format
    """
    preview = []
    
    start_num = int(params.get("start_num", 1))
    digits = int(params.get("digits", 2))

    for idx, f in enumerate(files):
        old_name = f["name"]
        stem, ext = os.path.splitext(old_name)
        new_stem = stem

        if rule_type == "replace":
            search_str = params.get("search", "")
            repl_str = params.get("replace", "")
            case_sens = params.get("case_sensitive", False)
            if search_str:
                if case_sens:
                    new_stem = stem.replace(search_str, repl_str)
                else:
                    import re
                    new_stem = re.sub(re.escape(search_str), repl_str, stem, flags=re.IGNORECASE)

        elif rule_type == "prefix_suffix":
            prefix = params.get("prefix", "")
            suffix = params.get("suffix", "")
            new_stem = f"{prefix}{stem}{suffix}"

        elif rule_type == "numbering":
            num_str = str(start_num + idx).zfill(digits)
            pattern = params.get("pattern", "{name}_{index}")
            new_stem = pattern.replace("{name}", stem).replace("{index}", num_str)

        elif rule_type == "case":
            case_mode = params.get("mode", "lower")
            if case_mode == "upper":
                new_stem = stem.upper()
            elif case_mode == "lower":
                new_stem = stem.lower()
            elif case_mode == "title":
                new_stem = stem.title()

        elif rule_type == "date":
            date_fmt = params.get("format", "%Y-%m-%d")
            now_str = datetime.now().strftime(date_fmt)
            pos = params.get("position", "prefix")
            if pos == "prefix":
                new_stem = f"{now_str}_{stem}"
            else:
                new_stem = f"{stem}_{now_str}"

        new_name = f"{new_stem}{ext}"
        dir_name = os.path.dirname(f["path"])
        new_path = os.path.join(dir_name, new_name)

        preview.append({
            "original_path": f["path"],
            "original_name": old_name,
            "new_name": new_name,
            "new_path": new_path,
            "changed": old_name != new_name,
            "conflict": os.path.exists(new_path) and os.path.normcase(f["path"]) != os.path.normcase(new_path)
        })

    return preview

def execute_batch_rename(preview_items):
    """Wendet die Batch-Umbenennung an"""
    results = {"success": [], "errors": []}
    for item in preview_items:
        if not item.get("changed", True):
            continue
        old_path = item["original_path"]
        new_name = item["new_name"]
        res = rename_single_file(old_path, new_name)
        if res["success"]:
            results["success"].append(res)
        else:
            results["errors"].append({"path": old_path, "error": res["error"]})
    return results

QUEUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "open_queue.json")

def ensure_protocol_registered():
    """Registriert das lokale 'suchmaschine://' URL-Protokoll in HKCU\\Software\\Classes,
    damit der Browser auf dem echten Benutzer-Desktop den Windows Explorer und Standard-Apps
    (Word, Excel, Bilder etc.) direkt mit Vordergrund-Fokus öffnen kann."""
    try:
        import winreg
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        launcher_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher.pyw")
        cmd_str = f'"{pythonw}" "{launcher_script}" "%1"'

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\suchmaschine") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Datei-Suchmaschine Desktop-Starter")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\suchmaschine\shell\open\command") as cmd_key:
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd_str)
        return True
    except Exception:
        return False

ensure_protocol_registered()

def _create_launcher_ticket(action, filepath):
    """Erstellt ein einmaliges Start-Ticket für launcher.pyw über das suchmaschine:// Protokoll."""
    ensure_protocol_registered()
    import uuid
    ticket_id = uuid.uuid4().hex[:12]
    now = time.time()
    queue = {}
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                raw_q = json.load(f)
                # Alte Tickets (> 5 Minuten) bereinigen
                queue = {k: v for k, v in raw_q.items() if isinstance(v, dict) and now - v.get("ts", 0) < 300}
        except Exception:
            queue = {}
    queue[ticket_id] = {
        "action": action,
        "path": os.path.abspath(filepath),
        "ts": now
    }
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return f"suchmaschine://run/{ticket_id}"

def _is_isolated_desktop():
    """Prüft, ob der Server-Prozess in einem isolierten Sandbox-Desktop (z.B. exebox) statt auf dem Hauptmonitor ('Default') läuft."""
    try:
        import ctypes
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        hdesk = u.GetThreadDesktop(k.GetCurrentThreadId())
        buf = ctypes.create_unicode_buffer(256)
        u.GetUserObjectInformationW(hdesk, 2, buf, 512, None)
        desk_name = (buf.value or "").strip().lower()
        return bool(desk_name and desk_name != "default")
    except Exception:
        return False

def _find_msaccess_exe():
    candidates = [
        r"C:\Program Files\Microsoft Office\root\Office16\MSACCESS.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\MSACCESS.EXE",
        r"C:\Program Files\Microsoft Office\Office16\MSACCESS.EXE",
        r"C:\Program Files (x86)\Microsoft Office\Office16\MSACCESS.EXE",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def _is_likely_text_file(filepath):
    """Prüft anhand der ersten 4 KB, ob eine Datei (z.B. ohne Dateiendung oder .srt) lesbarer Text ist."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(4096)
        if not chunk:
            return True
        if b"\x00" in chunk:
            return False
        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            pass
        non_printable = sum(1 for b in chunk if b < 32 and b not in (9, 10, 13))
        return (non_printable / len(chunk)) < 0.05
    except Exception:
        return False

def _has_windows_association(ext):
    if not ext:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext) as k:
            val, _ = winreg.QueryValueEx(k, "")
            return bool(val and str(val).strip())
    except Exception:
        return False

def open_file_in_system(filepath):
    """Öffnet Datei direkt in PDF X (für PDFs), Microsoft Access (.accdb/.mdb), Word, Excel,
    oder im Windows-Editor (für .srt, Konfigurations- und Textdateien ohne Endung)."""
    filepath = resolve_german_alias_path(filepath)
    if not filepath or not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    
    abs_p = os.path.abspath(filepath)

    # Falls es ein Ordner ist -> Direkt im Windows Explorer öffnen
    if os.path.isdir(abs_p):
        if _is_isolated_desktop():
            protocol_url = _create_launcher_ticket("open", abs_p)
            return {
                "success": True,
                "use_browser_protocol": True,
                "protocol_url": protocol_url,
                "open_path": abs_p,
                "message": "Ordner wird im Windows Explorer geöffnet..."
            }
        try:
            subprocess.Popen(f'explorer.exe "{abs_p}"')
            return {"success": True, "open_path": abs_p, "message": "Ordner im Windows Explorer geöffnet."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    ext = os.path.splitext(abs_p)[1].lower().strip()
    notepad_exts = {".srt", ".vtt", ".sub", ".nfo", ".cfg", ".ini", ".conf", ".log", ".env", ".yml", ".yaml", ".toml", ".sql", ".md", ".txt"}

    if ext == ".pdf":
        app_name = "PDF X"
    elif ext in [".accdb", ".mdb", ".accde", ".accdr"]:
        app_name = "Microsoft Access"
    elif ext in [".docx", ".doc", ".rtf", ".odt"]:
        app_name = "Microsoft Word"
    elif ext in [".xlsx", ".xls", ".csv", ".ods"]:
        app_name = "Microsoft Excel"
    elif ext in [".pptx", ".ppt"]:
        app_name = "PowerPoint"
    elif ext in notepad_exts:
        app_name = "Windows-Editor (Untertitel / Text)" if ext in {".srt", ".vtt", ".sub"} else "Windows-Editor"
    elif not ext or not _has_windows_association(ext):
        if _is_likely_text_file(abs_p):
            app_name = "Windows-Editor (Textdatei)"
        else:
            app_name = "Windows 'Öffnen mit…'-Auswahl"
    else:
        app_name = "Standard-App"

    # UWP/MSIX-Sandbox-Schutz: Store-Apps (wie PDF X) virtualisieren AppData\Local (inkl. $env:TEMP und Outlook-Attachments)
    # und finden dort abgelegte Dateien nicht. Daher immer in Documents\Suchmaschine_Temp spiegeln:
    target_open_path = abs_p
    if "\\appdata\\" in abs_p.lower():
        import shutil
        safe_dir = os.path.join(os.path.expanduser("~"), "Documents", "Suchmaschine_Temp")
        os.makedirs(safe_dir, exist_ok=True)
        safe_path = os.path.join(safe_dir, os.path.basename(abs_p))
        try:
            shutil.copy2(abs_p, safe_path)
            target_open_path = safe_path
        except Exception:
            pass

    # Direktes App-Protokoll konstruieren:
    # - Für PDFs: pdflab-service-editor://open/?fpath=... (umgeht den Windows 11 '.pdf -> Nur einmal' Dialog)
    # - Für alle anderen Dateien (Access, Word, Excel, .srt, endungslose Dateien etc.): suchmaschine://run/<ticket_id>
    import urllib.parse
    if ext == ".pdf":
        encoded_path = urllib.parse.quote(target_open_path, safe="")
        protocol_url = f"pdflab-service-editor://open/?fpath={encoded_path}"
    else:
        protocol_url = _create_launcher_ticket("open", target_open_path)

    # Wenn der Python-Server aus einer isolierten Terminal-Sandbox (exebox) gestartet wurde,
    # übergibt der Server die Protokoll-URL direkt an den Browser auf dem echten Desktop:
    if _is_isolated_desktop():
        return {
            "success": True,
            "use_browser_protocol": True,
            "protocol_url": protocol_url,
            "open_path": target_open_path,
            "message": f"Wird direkt in {app_name} geöffnet..."
        }

    # Wenn der Server regulär auf dem Benutzer-Desktop ('Default') läuft:
    if ext == ".pdf":
        try:
            escaped_uri = protocol_url.replace("'", "''")
            cmd = f"Start-Process '{escaped_uri}'"
            res = subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return {"success": True, "open_path": target_open_path, "message": f"In {app_name} geöffnet."}
        except Exception:
            pass

    if ext in [".accdb", ".mdb", ".accde", ".accdr"]:
        msaccess = _find_msaccess_exe()
        if msaccess:
            try:
                subprocess.Popen([msaccess, target_open_path])
                return {"success": True, "open_path": target_open_path, "message": f"In {app_name} geöffnet."}
            except Exception:
                pass

    if ext in notepad_exts or ((not ext or not _has_windows_association(ext)) and _is_likely_text_file(target_open_path)):
        try:
            subprocess.Popen(["notepad.exe", target_open_path])
            return {"success": True, "open_path": target_open_path, "message": f"In {app_name} geöffnet."}
        except Exception:
            pass

    if not ext or not _has_windows_association(ext):
        try:
            subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", target_open_path])
            return {"success": True, "open_path": target_open_path, "message": "Unbekannter Dateityp – Windows 'Öffnen mit…' geöffnet."}
        except Exception:
            pass

    try:
        os.startfile(target_open_path)
        return {"success": True, "open_path": target_open_path, "message": f"In {app_name} geöffnet."}
    except Exception:
        pass

    try:
        subprocess.Popen(["cmd.exe", "/c", "start", "", target_open_path])
        return {"success": True, "open_path": target_open_path, "message": f"In {app_name} geöffnet."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_folder_and_select(filepath):
    """Öffnet Windows Explorer auf dem Benutzer-Desktop und markiert die Datei."""
    filepath = resolve_german_alias_path(filepath)
    if not filepath or not os.path.exists(filepath):
        return {"success": False, "error": "Pfad nicht gefunden"}
    abs_p = os.path.abspath(filepath)

    if _is_isolated_desktop():
        protocol_url = _create_launcher_ticket("select", abs_p)
        return {
            "success": True,
            "use_browser_protocol": True,
            "protocol_url": protocol_url,
            "message": "Im Windows Explorer geöffnet."
        }

    try:
        subprocess.Popen(f'explorer.exe /select,"{abs_p}"')
        return {"success": True, "message": "Im Windows Explorer geöffnet."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_default_apps_settings():
    """Öffnet die Windows-Einstellungen für Standard-Apps (ms-settings:defaultapps)"""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", "Start-Process 'ms-settings:defaultapps'"], check=False)
        return {"success": True, "message": "Windows Standard-Apps Einstellungen geöffnet."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_with_dialog(filepath):
    """Öffnet den nativen Windows 'Öffnen mit...'-Dialog"""
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    try:
        abs_p = os.path.abspath(filepath)
        subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", abs_p])
        return {"success": True, "message": "'Öffnen mit...'-Dialog geöffnet. Bitte Fenster in der Taskleiste beachten."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def edit_file_in_system(filepath):
    """Öffnet die Datei im Standard-Bearbeitungsprogramm (Windows Edit Verb oder Notepad)"""
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    try:
        # Versuche zuerst Windows 'Edit' Verb
        ps_cmd = f"Start-Process -FilePath '{filepath}' -Verb Edit"
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False, timeout=5)
        if res.returncode == 0:
            return {"success": True, "message": "Im Bearbeitungsprogramm geöffnet."}
    except Exception:
        pass
    
    # Fallback für Textdateien oder Allgemein
    try:
        subprocess.run(["notepad.exe", filepath], check=False)
        return {"success": True, "message": "Im Windows-Editor geöffnet."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_text_file(filepath, content):
    """Speichert bearbeiteten Textinhalt direkt zurück in die Datei"""
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        stat = os.stat(filepath)
        mtime_dt = datetime.fromtimestamp(stat.st_mtime)
        return {
            "success": True, 
            "size": stat.st_size,
            "size_formatted": format_size(stat.st_size),
            "modified": mtime_dt.isoformat(),
            "modified_formatted": mtime_dt.strftime("%d.%m.%y %H:%M")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==========================================
# GITHUB AKTUALISIERUNG (WIE IN PORTFOLIO-MANAGER)
# ==========================================
def get_git_info():
    """Liest aktuellen Git-Status, Version und Remote-URL"""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    info = {
        "version": APP_VERSION,
        "is_git": os.path.exists(os.path.join(repo_dir, ".git")),
        "remote_url": "",
        "branch": "master",
        "last_commit": "",
        "commit_date": "",
        "dirty": False
    }

    if not info["is_git"]:
        return info

    try:
        # Remote URL
        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0:
            info["remote_url"] = res.stdout.strip()
        
        # Branch
        res = subprocess.run(["git", "branch", "--show-current"], cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            info["branch"] = res.stdout.strip()

        # Last commit
        res = subprocess.run(["git", "log", "-1", "--format=%h - %s • %ad", "--date=format:%d.%m.%y %H:%M"], cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0:
            info["last_commit"] = res.stdout.strip()

        # Status check
        res = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True)
        info["dirty"] = bool(res.stdout.strip())
    except Exception as e:
        info["error"] = str(e)

    return info

def git_pull_update():
    """Führt git pull aus, um die neueste Version von GitHub zu laden"""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        # Check if remote exists
        check_rem = subprocess.run(["git", "remote", "-v"], cwd=repo_dir, capture_output=True, text=True)
        if not check_rem.stdout.strip():
            return {
                "success": False, 
                "error": "Kein GitHub-Remote konfiguriert."
            }

        res = subprocess.run(["git", "pull", "origin", "main"], cwd=repo_dir, capture_output=True, text=True, timeout=25)
        output = (res.stdout + "\n" + res.stderr).strip()
        success = res.returncode == 0

        # Wenn main fehlschlägt, versuche git pull direkt
        if not success:
            res2 = subprocess.run(["git", "pull"], cwd=repo_dir, capture_output=True, text=True, timeout=25)
            output = (res2.stdout + "\n" + res2.stderr).strip()
            success = res2.returncode == 0

        msg = "Update erfolgreich eingespielt!"
        if "Already up to date" in output:
            msg = "Bereits auf dem neuesten Stand! Keine neuen Änderungen auf GitHub vorhanden."

        return {
            "success": success,
            "output": output,
            "message": msg
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def git_push_upload():
    """Führt git push aus, um den aktuellen Stand nach GitHub zu übertragen"""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        res = subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dir, capture_output=True, text=True, timeout=30)
        output = (res.stdout + "\n" + res.stderr).strip()
        return {
            "success": res.returncode == 0,
            "output": output,
            "message": "Stand erfolgreich nach GitHub hochgeladen!" if res.returncode == 0 else output
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def git_set_remote(remote_url):
    """Setzt oder ändert die GitHub Remote URL"""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        # Remove existing if any
        subprocess.run(["git", "remote", "remove", "origin"], cwd=repo_dir, capture_output=True)
        res = subprocess.run(["git", "remote", "add", "origin", remote_url.strip()], cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0:
            return {"success": True, "remote_url": remote_url.strip()}
        else:
            return {"success": False, "error": res.stderr.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_uploaded_file(uploaded_file, target_dir=None):
    """Speichert vom iPad/iPhone hochgeladene Dateien"""
    od_info = detect_onedrive_paths()
    if not target_dir or not os.path.exists(target_dir):
        target_dir = od_info["transfer"]["path"]
    
    os.makedirs(target_dir, exist_ok=True)
    filename = uploaded_file.filename
    # Sanitize filename
    filename = os.path.basename(filename)
    dest_path = os.path.join(target_dir, filename)

    # Avoid overwrite if exists
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
        counter += 1

    uploaded_file.save(dest_path)
    stat = os.stat(dest_path)
    return {
        "success": True,
        "name": os.path.basename(dest_path),
        "path": dest_path,
        "size": format_size(stat.st_size),
        "folder": target_dir
    }

def print_file_in_windows(filepath):
    """Druckt Datei über Windows Standard-Druckbefehl"""
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    try:
        # PowerShell Start-Process -Verb Print
        ps_cmd = f"Start-Process -FilePath '{filepath}' -Verb Print"
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True, timeout=10)
        return {"success": True, "message": "Druckauftrag an Windows-Standarddrucker übergeben."}
    except Exception as e:
        # Fallback to os.startfile print
        try:
            os.startfile(filepath, "print")
            return {"success": True, "message": "Druckauftrag gestartet."}
        except Exception as e2:
            return {"success": False, "error": f"Drucken fehlgeschlagen: {str(e2)}"}

def copy_file_for_teams(filepath):
    """
    Kopiert Datei als CF_HDROP Dateiobjekt in die Zwischenablage.
    Damit kann der Benutzer in MS Teams einfach Strg+V drücken und die Datei wird direkt angehängt!
    """
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    try:
        abs_p = os.path.abspath(filepath).replace("'", "''")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"$c = New-Object System.Collections.Specialized.StringCollection; "
            f"$c.Add('{abs_p}'); "
            f"[System.Windows.Forms.Clipboard]::SetFileDropList($c)"
        )
        subprocess.run(["powershell", "-STA", "-NoProfile", "-Command", ps_cmd], check=True, timeout=8)
        return {
            "success": True,
            "message": "Datei in Windows-Zwischenablage kopiert! Wechsle zu MS Teams und drücke einfach [Strg + V] zum Senden."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_email_client():
    """Gibt das konfigurierte Standard-E-Mail-Programm zurück (thunderbird, gmail, outlook, default)"""
    cfg = load_config()
    client = cfg.get("email_client")
    if not client:
        # Prüfen ob Thunderbird installiert ist
        tb_paths = [
            r"C:\Program Files\Mozilla Thunderbird\thunderbird.exe",
            r"C:\Program Files (x86)\Mozilla Thunderbird\thunderbird.exe"
        ]
        if any(os.path.exists(p) for p in tb_paths):
            client = "thunderbird"
        else:
            client = "default"
    return client

def set_email_client(client):
    """Speichert das bevorzugte E-Mail-Programm in config.json"""
    cfg = load_config()
    cfg["email_client"] = client
    save_config(cfg)
    return {"success": True, "email_client": client}

def send_file_via_email(filepath, recipient="", client=None):
    """
    Erstellt E-Mail Entwurf mit Anhang für das gewählte E-Mail-Programm:
    - thunderbird: Mozilla Thunderbird mit -compose und echtem Anhang
    - gmail: Google Mail Web-Compose im Browser + Datei in Zwischenablage
    - outlook: Microsoft Outlook COM Automation mit echtem Anhang
    - default: Windows Standard mailto: + Datei in Zwischenablage
    """
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    
    if not client:
        client = get_email_client()
        
    abs_p = os.path.abspath(filepath)
    abs_p_win = abs_p.replace("/", "\\")
    filename = os.path.basename(filepath)
    clean_filename = filename.replace("'", "")
    clean_path = abs_p_win.replace("'", "")

    # 1. MOZILLA THUNDERBIRD
    if client == "thunderbird":
        tb_paths = [
            r"C:\Program Files\Mozilla Thunderbird\thunderbird.exe",
            r"C:\Program Files (x86)\Mozilla Thunderbird\thunderbird.exe"
        ]
        tb_exe = next((p for p in tb_paths if os.path.exists(p)), None)
        if not tb_exe:
            import shutil
            tb_exe = shutil.which("thunderbird.exe") or shutil.which("thunderbird")
            
        if tb_exe:
            try:
                # 1. Datei für zusätzliche Sicherheit in Windows-Zwischenablage legen
                copy_file_for_teams(filepath)
                
                # 2. Thunderbird mit -compose starten (Nativer Windows-Pfad ohne file:///)
                # Format: thunderbird.exe -compose "attachment='C:\path\to\file',subject='...'"
                compose_arg = f"attachment='{clean_path}',subject='Datei: {clean_filename}'"
                if recipient:
                    compose_arg = f"to='{recipient}'," + compose_arg
                
                # Direkt über cmd /c start aufrufen, damit Windows das Thunderbird-Verfassen-Fenster sofort in den Vordergrund holt
                cmd_line = f'start "" "{tb_exe}" -compose "{compose_arg}"'
                subprocess.Popen(f'cmd.exe /c {cmd_line}', shell=True)
                
                return {
                    "success": True,
                    "method": "thunderbird",
                    "message": f"Mozilla Thunderbird mit angehängter Datei '{filename}' geöffnet!"
                }
            except Exception as e:
                pass # Weiter zu mailto Fallback

    # 2. GOOGLE MAIL (GMAIL)
    elif client == "gmail":
        try:
            import urllib.parse
            import webbrowser
            copy_file_for_teams(filepath)
            subject = urllib.parse.quote(f"Datei: {filename}")
            body = urllib.parse.quote(f"Hallo,\n\nanbei die Datei {filename}.\n\nPfad: {filepath}\n\n(Die Datei befindet sich bereits in der Windows-Zwischenablage - im GMail-Fenster einfach [Strg + V] drücken!)")
            # Google Mail direkte Verfassen-URL auf Account 0
            gmail_url = f"https://mail.google.com/mail/u/0/?view=cm&fs=1&to={urllib.parse.quote(recipient)}&su={subject}&body={body}"
            
            try:
                webbrowser.open(gmail_url)
            except Exception:
                pass
                
            return {
                "success": True,
                "method": "gmail",
                "web_url": gmail_url,
                "message": f"Google Mail im Browser geöffnet & '{filename}' in Zwischenablage kopiert! Im GMail-Fenster einfach [Strg + V] drücken."
            }
        except Exception as e:
            return {"success": False, "error": f"Fehler beim Öffnen von Google Mail: {str(e)}"}

    # 3. MICROSOFT OUTLOOK
    elif client == "outlook":
        try:
            ps_cmd = (
                f"$ol = New-Object -ComObject Outlook.Application; "
                f"$mail = $ol.CreateItem(0); "
                f"$mail.Subject = 'Datei: {filename}'; "
                f"$mail.Body = 'Hallo,`n`nim Anhang erhalten Sie die Datei {filename}.`n`nViele Grüße'; "
                f"if ('{recipient}') {{ $mail.To = '{recipient}' }}; "
                f"$mail.Attachments.Add('{abs_p.replace(chr(39), chr(39)+chr(39))}'); "
                f"$mail.Display()"
            )
            subprocess.run(["powershell", "-STA", "-NoProfile", "-Command", ps_cmd], check=True, timeout=8)
            return {"success": True, "method": "outlook", "message": f"Outlook E-Mail mit Anhang '{filename}' geöffnet!"}
        except Exception:
            pass # Weiter zu mailto Fallback

    # 4. WINDOWS STANDARD (MAILTO:) FALLBACK
    copy_file_for_teams(filepath)
    import urllib.parse
    subject = urllib.parse.quote(f"Datei: {filename}")
    body = urllib.parse.quote(f"Hallo,\n\nanbei die Datei {filename} (in Zwischenablage, einfach Strg+V drücken).\n\nPfad: {filepath}")
    mailto_url = f"mailto:{recipient}?subject={subject}&body={body}"
    try:
        os.startfile(mailto_url)
    except Exception:
        pass
    return {
        "success": True,
        "method": "clipboard_mailto",
        "message": f"E-Mail-Programm geöffnet & '{filename}' in Zwischenablage kopiert (in E-Mail einfach [Strg + V] drücken)!"
    }
