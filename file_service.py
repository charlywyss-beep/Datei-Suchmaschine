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

APP_VERSION = "v1.3.3"
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
    "office": {".pdf", ".docx", ".doc", ".rtf", ".odt", ".xlsx", ".xls", ".csv", ".ods", ".pptx", ".ppt"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff", ".tif", ".heic", ".raw"},
    "audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".iso"},
    "code": {".txt", ".log", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".bat", ".ps1", ".md"},
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
    return path_str.replace("\\Documents", "\\Dokumente").replace("/Documents", "/Dokumente")
    cfg = load_config()
    paths = cfg.get("saved_paths", [])
    if not paths and os.path.exists("D:\\01\\Documents"):
        paths = [
            {"id": "fav_d_doc", "name": "Dokumente (D:)", "path": "D:\\01\\Documents", "icon": "folder"}
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
    paths = cfg.get("saved_paths", [])
    # Falls noch leer, Standard-Vorschläge wie D:\01\Documents prüfen
    if not paths and os.path.exists("D:\\01\\Documents"):
        paths = [
            {"id": "fav_d_doc", "name": "Documents (D:)", "path": "D:\\01\\Documents", "icon": "folder"}
        ]
        cfg["saved_paths"] = paths
        save_config(cfg)
    return paths

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

def get_system_locations():
    user_home = os.path.expanduser("~")
    od_info = detect_onedrive_paths()
    
    locations = [
        {"id": "onedrive_personal", "name": "OneDrive Privat", "path": od_info["personal"]["path"], "icon": "cloud", "badge": "Privat", "exists": od_info["personal"]["exists"]},
        {"id": "onedrive_business", "name": "OneDrive Geschäftlich", "path": od_info["business"]["path"], "icon": "building", "badge": "Business", "exists": od_info["business"]["exists"]},
        {"id": "transfer_hub", "name": "Transfer-Hub (Sync)", "path": od_info["transfer"]["path"], "icon": "arrows-rotate", "badge": "iPad/iPhone", "exists": od_info["transfer"]["exists"]},
        {"id": "documents", "name": "Dokumente (C:)", "path": os.path.join(user_home, "Documents"), "icon": "folder", "exists": os.path.exists(os.path.join(user_home, "Documents"))},
    ]

    # Spezielle Erkennung für D:\01\Documents
    d_doc = "D:\\01\\Documents"
    if os.path.exists(d_doc):
        locations.append({"id": "d_documents", "name": "Dokumente (D:)", "path": d_doc, "icon": "folder", "badge": "D:", "exists": True})

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
    elif root_str_lower in ("onedrive_all", "onedrive") or "onedrive" in root_str_lower and ("privat" in root_str_lower or "geschäft" in root_str_lower):
        od_info = detect_onedrive_paths()
        if od_info["personal"]["exists"]:
            start_dirs.append(od_info["personal"]["path"])
        if od_info["business"]["exists"]:
            start_dirs.append(od_info["business"]["path"])
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

    # Skip heavy system / cache directories if searching C:\
    skip_dirs = {"$recycle.bin", "system volume information", "windows", "appdata\\local\\temp", "node_modules", ".git"}

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
                        dirname_lower = entry.name.lower()
                        # Skip hidden/system directories
                        if dirname_lower.startswith('$') or dirname_lower in skip_dirs:
                            continue
                        # If scanning C:\ avoid recursing into C:\Windows
                        full_entry_path = entry.path.lower()
                        if "c:\\windows" in full_entry_path or "c:\\programdata\\microsoft" in full_entry_path:
                            continue
                        stack.append(entry.path)
                    else:
                        # File matching
                        filename = entry.name
                        filename_lower = filename.lower()

                        # Query match (all words must match)
                        if query_parts:
                            if not all(qp in filename_lower for qp in query_parts):
                                continue

                        # Extension match
                        _, ext = os.path.splitext(filename_lower)
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

                        # OneDrive check (Personal vs Business)
                        norm_entry = os.path.normcase(os.path.abspath(entry.path))
                        is_onedrive_type = None
                        if p_personal and norm_entry.startswith(p_personal):
                            is_onedrive_type = "personal"
                        elif p_business and norm_entry.startswith(p_business):
                            is_onedrive_type = "business"

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
                            "ext": ext.replace(".", "").upper(),
                            "category": cat,
                            "size": size,
                            "size_formatted": format_size(size),
                            "modified": mtime_dt.isoformat(),
                            "modified_formatted": mtime_dt.strftime("%d.%m.%y %H:%M"),
                            "is_onedrive": bool(is_onedrive_type),
                            "onedrive_type": is_onedrive_type
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

def open_file_in_system(filepath):
    """Öffnet Datei in der Windows-Standardanwendung"""
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    try:
        os.startfile(filepath)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_folder_and_select(filepath):
    """Öffnet Explorer und wählt die Datei aus"""
    if not os.path.exists(filepath):
        return {"success": False, "error": "Pfad nicht gefunden"}
    try:
        subprocess.run(["explorer", f"/select,{os.path.abspath(filepath)}"], check=False)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_with_dialog(filepath):
    """Öffnet den nativen Windows 'Öffnen mit...'-Dialog"""
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    try:
        abs_p = os.path.abspath(filepath)
        subprocess.run(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", abs_p], check=False)
        return {"success": True, "message": "'Öffnen mit...'-Dialog geöffnet."}
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

def send_file_via_email(filepath, recipient=""):
    """
    Erstellt Outlook E-Mail Entwurf mit Anhang falls Outlook verfügbar,
    ansonsten mailto Fallback und Kopie in Zwischenablage.
    """
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    abs_p = os.path.abspath(filepath).replace("'", "''")
    filename = os.path.basename(filepath).replace("'", "''")
    
    # Try Outlook COM
    try:
        ps_cmd = (
            f"$ol = New-Object -ComObject Outlook.Application; "
            f"$mail = $ol.CreateItem(0); "
            f"$mail.Subject = 'Datei: {filename}'; "
            f"$mail.Body = 'Hallo,`n`nim Anhang erhalten Sie die Datei {filename}.`n`nViele Grüße'; "
            f"if ('{recipient}') {{ $mail.To = '{recipient}' }}; "
            f"$mail.Attachments.Add('{abs_p}'); "
            f"$mail.Display()"
        )
        subprocess.run(["powershell", "-STA", "-NoProfile", "-Command", ps_cmd], check=True, timeout=8)
        return {"success": True, "method": "outlook", "message": "Outlook E-Mail mit Anhang wurde geöffnet!"}
    except Exception:
        # Fallback: kopiere Datei in Zwischenablage und öffne mailto
        copy_file_for_teams(filepath)
        import urllib.parse
        subject = urllib.parse.quote(f"Datei: {os.path.basename(filepath)}")
        body = urllib.parse.quote(f"Hallo,\n\nanbei die Datei {os.path.basename(filepath)} (bereits in der Zwischenablage, einfach Strg+V drücken).\n\nPfad: {filepath}")
        mailto_url = f"mailto:{recipient}?subject={subject}&body={body}"
        try:
            os.startfile(mailto_url)
        except Exception:
            pass
        return {
            "success": True,
            "method": "clipboard_mailto",
            "message": "E-Mail-Programm geöffnet & Datei in Zwischenablage kopiert (in E-Mail einfach [Strg + V] drücken)!"
        }
