import os
import re
import shutil
import sys
import json
import time
import socket
import hashlib
import subprocess
import mimetypes
import threading
import logging
from pathlib import Path
from datetime import datetime
from send2trash import send2trash

logger = logging.getLogger("file_service")
APP_VERSION = "v1.7.55"

def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(_get_base_dir(), "config.json")
QUEUE_FILE = os.path.join(_get_base_dir(), "open_queue.json")

def load_config():
    cfg_file = os.path.join(_get_base_dir(), "config.json")
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg):
    try:
        cfg_file = os.path.join(_get_base_dir(), "config.json")
        with open(cfg_file, "w", encoding="utf-8") as f:
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
    custom_transfer = cfg.get("transfer_hub")
    if custom_transfer and os.path.exists(os.path.dirname(custom_transfer)):
        transfer_path = custom_transfer
    else:
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


# ==========================================
# 7-ORDNER-SYSTEM KLASSIFIKATION & FILTER-HELFER
# ==========================================
SEVEN_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".gif",
    ".tif", ".tiff", ".webp", ".heic", ".heif", ".avif", ".svg", ".ico",
    ".raw", ".cr2", ".nef", ".arw", ".dng"
}
SEVEN_INSTALLER_EXTS = {".exe", ".msi", ".msix", ".appx", ".appxbundle"}
SEVEN_MEDIA_EXTS = {
    ".ts", ".mts", ".m2ts", ".mpeg", ".mpg", ".mpe", ".mp4", ".m4v",
    ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".vob", ".3gp",
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"
}

SEVEN_FOLDER_RULES = [
    ("02_Finanzen_Steuern\\01_Bank_Kontoauszuege", "Bank / Kontoauszug",
     ["kontoauszug", "sparkasse", "dkb", "ing", "comdirect", "bank", "visa", "mastercard", "paypal", "ueberweisung"]),
    ("02_Finanzen_Steuern\\02_Steuererklaerung", "Steuern / Finanzamt",
     ["steuern", "steuererklaerung", "steuererklärung", "finanzamt", "elster", "lohnsteuer", "einkommensteuer", "steuerbescheid"]),
    ("02_Finanzen_Steuern\\03_Geldanlage_Vorsorge", "Depot / Vorsorge / Boerse",
     ["depot", "trade_republic", "scalable", "aktien", "etf", "fonds", "bauspar", "rente", "altersvorsorge", "börse", "boerse", "investor", "pitchdeck", "inventur"]),
    ("02_Finanzen_Steuern\\04_Kredite_Darlehen", "Kredite & Darlehen",
     ["kredit", "darlehen", "tilgung", "zinsen", "finanzierung", "schufa"]),
    ("02_Finanzen_Steuern\\05_Quittungen_Belege", "Quittungen & Barbelege",
     ["quittung", "barzahlung", "bewirtung"]),
    ("03_Vertraege_Versicherungen\\01_Versicherungen", "Versicherungen",
     ["haftpflicht", "hausrat", "versicherung", "allianz", "huk", "ergo", "devk", "unfallversicherung", "rechtsschutz", "versicherungsbestaetigung"]),
    ("03_Vertraege_Versicherungen\\02_Vertraege_Mobilfunk_Internet", "Mobilfunk & Internet",
     ["telekom", "vodafone", "o2", "1und1", "mobilfunk", "internet", "router", "handy", "dsl", "simkarte"]),
    ("03_Vertraege_Versicherungen\\03_Fahrzeuge_Kfz", "Kfz & Fahrzeuge",
     ["kfz", "auto", "tuev", "tüv", "adac", "zulassung", "fahrzeugschein", "strafzettel", "bußgeld", "fahrzeug"]),
    ("03_Vertraege_Versicherungen\\04_Mitgliedschaften_Abos", "Mitgliedschaften & Abos",
     ["mitglied", "verein", "fitnessstudio", "abonnement", "abo", "bahncard"]),
    ("03_Vertraege_Versicherungen\\05_Vollmachten_Verfuegungen", "Vollmachten & Verfügungen",
     ["vollmacht", "patientenverfuegung", "vorsorgevollmacht", "testament", "notar"]),
    ("04_Beruf_Bildung\\01_Gehaltsabrechnungen", "Gehalt / Lohn",
     ["gehalt", "entgelt", "lohn", "lohnabrechnung", "gehaltsabrechnung", "bezuegemitteilung"]),
    ("04_Beruf_Bildung\\02_Arbeitsvertraege", "Arbeitsverträge / Aufträge",
     ["arbeitsvertrag", "anstellungsvertrag", "kuendigung", "aufhebungsvertrag", "abmahnung", "aufträge", "auftraege"]),
    ("04_Beruf_Bildung\\03_Zeugnisse_Zertifikate", "Technik & Dokumente",
     ["zeugnis", "zertifikat", "diplom", "bachelor", "master", "weiterbildung", "schulzeugnis"]),
    ("04_Beruf_Bildung\\04_Bewerbungen_Lebenslauf", "Bewerbungen & Lebenslauf",
     ["lebenslauf", "bewerbung", "anschreiben", "motivationsschreiben"]),
    ("05_Gesundheit_Familie\\01_Krankenkasse", "Krankenkasse",
     ["aok", "tk", "techniker", "barmer", "krankenkasse", "erstattung", "krankengeld", "bonusprogramm"]),
    ("05_Gesundheit_Familie\\02_Aerzte_Befunde", "Gesundheit & Ernährung",
     ["arzt", "befund", "rezept", "krankenhaus", "labor", "impfung", "zahnarzt", "patientenakte", "diagnose", "ernaehrung"]),
    ("05_Gesundheit_Familie\\03_Familienurkunden", "Familienurkunden",
     ["geburtsurkunde", "heiratsurkunde", "stammbuch", "taufschein", "sterbeurkunde"]),
    ("05_Gesundheit_Familie\\04_Impfungen_Vorsorge", "Impfungen & Vorsorge",
     ["impfpass", "impfbuch", "vorsorgepass", "mutterpass"]),
    ("06_Wohnen_Eigentum\\01_Miete_Nebenkosten", "Miete & Umzug",
     ["miete", "mietvertrag", "nebenkosten", "betriebskosten", "heizkosten", "vermieter", "strom", "gas", "wasser", "umzug"]),
    ("06_Wohnen_Eigentum\\02_Geraete_Garantien_Belege", "Belege, Rechnungen & Einkäufe",
     ["garantie", "rechnung", "kassenbon", "mediamarkt", "amazon", "saturn", "otto", "beleg", "lieferschein", "kaufbeleg", "coop", "ricardo"]),
    ("06_Wohnen_Eigentum\\03_Handwerker_Renovierung", "Handwerker & Installationen",
     ["handwerker", "renovierung", "maler", "sanitaer", "wartung", "schornsteinfeger", "installation", "sicherheitsnachweis"]),
    ("06_Wohnen_Eigentum\\04_Hausverwaltung_Grundbuch", "Hausverwaltung & Grundbuch",
     ["grundbuch", "hausverwaltung", "eigentuemer", "wohnungseigentum", "wirtschaftsplan"]),
    ("07_Archiv_Historie\\01_Ausweise_Reisepaesse", "Ausweise & Pässe",
     ["ausweis", "reisepass", "fuehrerschein", "personalausweis", "meldebescheinigung", "pass"]),
    ("07_Archiv_Historie\\02_Buecher_Medien", "Bücher & Medien",
     ["epub", "roman", "buch"]),
    ("07_Archiv_Historie\\03_Abgeschlossenes", "Archiv & Alt",
     ["archiv", "historisch", "abgeschlossen"]),
]


def get_seven_folder_options():
    """Gibt alle 7-Ordner-Standardziele (target_sub, label) für die UI zurück."""
    opts = [("01_Eingang_Inbox", "Unbekannt -> Inbox")]
    seen = {"01_Eingang_Inbox"}
    for tgt, lbl, _ in SEVEN_FOLDER_RULES:
        if tgt not in seen:
            seen.add(tgt)
            opts.append((tgt, lbl))
    for tgt, lbl in [
        ("07_Bilder", "Bilder & Fotos"),
        ("08_Programme_Installer", "Programme & Installer"),
        ("09_Videos_Medien", "Videos & Medien"),
        ("10_Ordner_Projekte", "Ordner & Projekte"),
    ]:
        if tgt not in seen:
            seen.add(tgt)
            opts.append((tgt, lbl))
    return opts


def classify_for_seven_folder(filename: str, ext: str = "", is_dir: bool = False):
    """Bestimmt Zielordner & Kategorie exakt passend zum 7-Ordner-System."""
    if is_dir:
        return "10_Ordner_Projekte", "Ordner & Projekte"
    ext_low = (ext or "").lower()
    if ext_low and not ext_low.startswith("."):
        ext_low = f".{ext_low}"
    if ext_low in SEVEN_IMAGE_EXTS:
        return "07_Bilder", "Bilder & Fotos"
    if ext_low in SEVEN_INSTALLER_EXTS:
        return "08_Programme_Installer", "Programme & Installer"
    if ext_low in SEVEN_MEDIA_EXTS:
        return "09_Videos_Medien", "Videos & Medien"
    name_low = (filename or "").lower()
    for target_sub, label, kws in SEVEN_FOLDER_RULES:
        for kw in kws:
            if kw in name_low:
                return target_sub, label
    return "01_Eingang_Inbox", "Unbekannt -> Inbox"


def annotate_search_results_duplicates(results: list):
    """Markiert blitzschnell Original / Duplikat anhand identischer (Name, Größe > 0) ohne Plattenzugriff."""
    groups = {}
    for item in results:
        if item.get("is_dir"):
            item["dup_status"] = "—"
            item["dup_group"] = ""
            continue
        sz = int(item.get("size") or 0)
        key_name = (item.get("name") or "").strip().lower()
        if sz > 0 and key_name:
            groups.setdefault((key_name, sz), []).append(item)

    for (key_name, sz), members in groups.items():
        if len(members) > 1:
            # Kürzester Pfad / ältestes Datum bekommt 'Original', Rest 'Duplikat'
            ordered = sorted(
                members,
                key=lambda x: (len(x.get("path") or ""), float(x.get("modified_ts") or 0))
            )
            grp_id = f"{key_name}|{sz}"
            ordered[0]["dup_status"] = "Original"
            ordered[0]["dup_group"] = grp_id
            for m in ordered[1:]:
                m["dup_status"] = "Duplikat"
                m["dup_group"] = grp_id

    for item in results:
        if "dup_status" not in item:
            if item.get("is_icloud") or item.get("is_gdrive") or item.get("is_onedrive"):
                item["dup_status"] = "☁ Cloud"
            else:
                item["dup_status"] = "—"
            item["dup_group"] = ""
    return results


def parse_size_to_bytes(val, default_unit="bytes"):
    """Parst z. B. '500 KB', '1.5 MB', '2 GB' oder reine Zahl in Bytes."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        v = float(val)
        if v < 0:
            return None
        if default_unit == "mb":
            return int(v * 1024 * 1024)
        if default_unit == "kb":
            return int(v * 1024)
        return int(v)
    s = str(val).strip()
    if not s:
        return None
    m = re.match(r"^(?:ab\s+|>\s*|min\s+)?([\d.,]+)\s*(b|bytes?|kb|k|mb|m|gb|g)?$", s, re.IGNORECASE)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    if num < 0:
        return None
    unit = (m.group(2) or "").lower()
    if not unit:
        unit = default_unit
    if unit.startswith("g"):
        return int(num * 1024 * 1024 * 1024)
    if unit.startswith("m"):
        return int(num * 1024 * 1024)
    if unit.startswith("k"):
        return int(num * 1024)
    return int(num)


def parse_filter_datetime(val, end_of_day=False):
    """Parst ISO (YYYY-MM-DD) und deutsches Datum (TT.MM.JJJJ) robust in einen Timestamp."""
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    has_time = ("T" in s) or (":" in s)
    dt = None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    if dt is None:
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None
    if end_of_day and not has_time:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt.timestamp()

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
                            target_sub, cat_label = classify_for_seven_folder(dirname, "", is_dir=True)
                            results.append({
                                "name": dirname,
                                "path": entry.path,
                                "folder": to_german_display_path(os.path.dirname(entry.path)),
                                "ext": "ORDNER",
                                "category": "folder",
                                "category_label": cat_label,
                                "target_sub": target_sub,
                                "is_dir": True,
                                "size": 0,
                                "size_formatted": "Ordner",
                                "modified": mtime_dt.isoformat(),
                                "modified_ts": mtime,
                                "modified_formatted": mtime_dt.strftime("%d.%m.%Y %H:%M"),
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
                        target_sub, cat_label = classify_for_seven_folder(filename, ext, is_dir=False)

                        results.append({
                            "name": filename,
                            "path": entry.path,
                            "folder": to_german_display_path(os.path.dirname(entry.path)),
                            "ext": ext.replace(".", "").upper() or "DATEI",
                            "category": cat,
                            "category_label": cat_label,
                            "target_sub": target_sub,
                            "size": size,
                            "size_formatted": format_size(size),
                            "modified": mtime_dt.isoformat(),
                            "modified_ts": mtime,
                            "modified_formatted": mtime_dt.strftime("%d.%m.%Y %H:%M"),
                            "is_onedrive": bool(is_onedrive_type),
                            "onedrive_type": is_onedrive_type,
                            "cloud_type": cloud_type,
                            "is_icloud": cloud_type == "icloud",
                            "is_gdrive": cloud_type == "gdrive"
                        })
                        count += 1
        except (PermissionError, OSError):
            continue

    annotate_search_results_duplicates(results)
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
        is_dir = bool(f.get("is_dir")) or (bool(f.get("path")) and os.path.isdir(f["path"]))
        if is_dir:
            stem, ext = old_name, ""
        else:
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

        elif rule_type == "trim":
            trim_mode = params.get("mode", "cut_from")
            raw_val = str(params.get("value", "") or "")
            clean_sep = bool(params.get("clean_sep", False))
            candidate = stem
            if trim_mode == "cut_from" and raw_val:
                pos = stem.lower().find(raw_val.lower())
                if pos > 0:
                    candidate = stem[:pos].rstrip(" ._-")
            elif trim_mode == "cut_before" and raw_val:
                pos = stem.lower().find(raw_val.lower())
                if pos > 0:
                    candidate = stem[pos:].lstrip(" ._-")
            elif trim_mode == "trim_end":
                try:
                    n = max(0, int(raw_val.strip()))
                    if 0 < n < len(stem):
                        candidate = stem[:-n].rstrip(" ._-")
                except ValueError:
                    pass
            elif trim_mode == "trim_start":
                try:
                    n = max(0, int(raw_val.strip()))
                    if 0 < n < len(stem):
                        candidate = stem[n:].lstrip(" ._-")
                except ValueError:
                    pass
            elif trim_mode == "max_len":
                try:
                    n = max(1, int(raw_val.strip()))
                    if len(stem) > n:
                        candidate = stem[:n].rstrip(" ._-")
                except ValueError:
                    pass
            elif trim_mode == "folder_from_largest_file" and is_dir:
                folder_path = f.get("path", "")
                if folder_path and os.path.isdir(folder_path):
                    video_exts = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".m2ts", ".iso"}
                    junk_exts = {".nfo", ".txt", ".jpg", ".jpeg", ".png", ".gif", ".idx", ".sub", ".srt", ".ass", ".ssa", ".vtt", ".bat", ".url", ".sfv", ".md5"}
                    best_video = None  # (size, name)
                    best_any = None    # (size, name)
                    try:
                        with os.scandir(folder_path) as it_dir:
                            for ent in it_dir:
                                if not ent.is_file():
                                    continue
                                fn = ent.name
                                fn_low = fn.lower()
                                if fn.startswith("._") or fn.startswith("~$") or fn_low in ("desktop.ini", "thumbs.db"):
                                    continue
                                try:
                                    sz = ent.stat().st_size
                                except Exception:
                                    sz = 0
                                # Kleine macOS/Rest-Dateien mit führendem Unterstrich (< 100 KB) ignorieren
                                if fn.startswith("_") and sz < 100 * 1024:
                                    continue
                                _, fext = os.path.splitext(fn_low)
                                if fext in junk_exts:
                                    continue
                                if "sample" in fn_low and sz < 100 * 1024 * 1024:
                                    continue
                                if fext in video_exts:
                                    if best_video is None or sz > best_video[0]:
                                        best_video = (sz, fn)
                                if best_any is None or sz > best_any[0]:
                                    best_any = (sz, fn)
                    except Exception:
                        pass
                    chosen = best_video or best_any
                    if chosen:
                        base_stem = os.path.splitext(chosen[1])[0].strip()
                        if raw_val:
                            pos = base_stem.lower().find(raw_val.lower())
                            if pos > 0:
                                base_stem = base_stem[:pos].rstrip(" ._-")
                        if base_stem:
                            candidate = base_stem
            if clean_sep:
                candidate = re.sub(r"[._]+", " ", candidate)
                candidate = re.sub(r"\s{2,}", " ", candidate).strip()
            if candidate.strip():
                new_stem = candidate.strip()
                # Automatischer Plex-/VLC-Untertitel-Schutz (.idx, .sub, .srt, .ass, .vtt):
                # Verhindert Namenskonflikte zwischen Komplett- und Forced-Untertiteln beim Einkürzen!
                if not is_dir and ext.lower() in {".idx", ".sub", ".srt", ".ass", ".ssa", ".vtt"} and new_stem != stem:
                    orig_low = stem.lower()
                    has_forced = bool(re.search(r"(?:^|[._\-\s])forced(?:$|[._\-\s])", orig_low))
                    has_de = bool(re.search(r"(?:^|[._\-\s])(german|deutsch|ger|deu|de)(?:$|[._\-\s])", orig_low))
                    has_en = bool(re.search(r"(?:^|[._\-\s])(english|eng|en)(?:$|[._\-\s])", orig_low))
                    tag_parts = []
                    if has_de and not re.search(r"(?:^|[._\-\s])de$", new_stem.lower()):
                        tag_parts.append("de")
                    elif not has_de and has_en and not re.search(r"(?:^|[._\-\s])en$", new_stem.lower()):
                        tag_parts.append("en")
                    if has_forced and not new_stem.lower().endswith(".forced"):
                        tag_parts.append("forced")
                    if tag_parts:
                        new_stem = f"{new_stem}.{'.'.join(tag_parts)}"

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
    """Wendet die Batch-Umbenennung an (tiefste Pfade / Dateien immer zuerst, danach übergeordnete Ordner)."""
    results = {"success": [], "errors": []}
    ordered = sorted(
        (preview_items or []),
        key=lambda it: (
            -len(os.path.normpath(it.get("original_path") or "").split(os.sep)),
            -len(it.get("original_path") or ""),
        ),
    )
    for item in ordered:
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
        if getattr(sys, 'frozen', False):
            # Standalone .exe: Die .exe selbst verarbeitet das Protokoll direkt
            cmd_str = f'"{sys.executable}" "%1"'
        else:
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
def _get_git_repo_dir():
    base = _get_base_dir()
    if os.path.exists(os.path.join(base, ".git")):
        return base
    return os.path.dirname(os.path.abspath(__file__))


def _extract_version_tag(text):
    if not text:
        return ""
    m = re.search(r"v\d+\.\d+\.\d+", str(text), re.IGNORECASE)
    return m.group(0).lower() if m else ""


def _parse_version_tuple(ver_str):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", str(ver_str or ""))
    if not m:
        return (0, 0, 0)
    return tuple(int(x) for x in m.groups())


def _bump_patch_version(ver_str):
    maj, min_v, pat = _parse_version_tuple(ver_str or APP_VERSION)
    if (maj, min_v, pat) == (0, 0, 0):
        return "v1.7.16"
    return f"v{maj}.{min_v}.{pat + 1}"


def _auto_bump_version_in_repo(repo_dir, old_ver):
    """Erhöht die Patch-Version (+1) im Code, falls neue Änderungen committet werden und old_ver <= HEAD."""
    global APP_VERSION
    new_ver = _bump_patch_version(old_ver)
    targets = [
        ("file_service.py", r'^(APP_VERSION\s*=\s*["\'])v\d+\.\d+\.\d+(["\'])', re.MULTILINE),
        (os.path.join("templates", "index.html"), r"(v\d+\.\d+\.\d+)(?='|\")", 0),
        (os.path.join("static", "js", "app.js"), r"(')v\d+\.\d+\.\d+(')", 0),
    ]
    changed_files = []
    for rel_path, pat, flags in targets:
        fpath = os.path.join(repo_dir, rel_path)
        if not os.path.isfile(fpath):
            continue
        try:
            content = open(fpath, "r", encoding="utf-8").read()
            if rel_path == "file_service.py":
                updated = re.sub(pat, rf"\g<1>{new_ver}\g<2>", content, count=1, flags=flags)
            elif rel_path.endswith("app.js"):
                updated = content.replace(f"'{old_ver}'", f"'{new_ver}'")
            else:
                updated = content.replace(f"'{old_ver}'", f"'{new_ver}'")
            if updated != content:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(updated)
                changed_files.append(rel_path)
        except Exception:
            pass
    APP_VERSION = new_ver
    return new_ver, changed_files


def _filter_meaningful_git_dirty_lines(porcelain_output):
    """Ignoriert Laufzeit-Dateien wie config.json oder __pycache__ für die Sync-Anzeige."""
    ignored_prefixes = ("__pycache__/", "build/", "dist/")
    ignored_names = {"config.json", "open_queue.json", ".DS_Store", "Thumbs.db"}
    dirty = []
    for raw in (porcelain_output or "").splitlines():
        if not raw.strip():
            continue
        path = raw[3:].strip().strip('"').replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[-1].strip().strip('"')
        if any(path.startswith(p) for p in ignored_prefixes) or path.endswith((".pyc", ".pyo")):
            continue
        if path in ignored_names or os.path.basename(path) in ignored_names:
            continue
        dirty.append(path)
    return dirty


DEFAULT_GITHUB_REMOTE_URL = "https://github.com/charlywyss-beep/Datei-Suchmaschine.git"
DEFAULT_EXE_FILENAME = "Datei-Suchmaschine-Pro.exe"


def _derive_github_urls(remote_url, branch="main"):
    clean = (remote_url or DEFAULT_GITHUB_REMOTE_URL).strip()
    if clean.startswith("git@github.com:"):
        clean = "https://github.com/" + clean[len("git@github.com:"):]
    base = clean[:-4] if clean.endswith(".git") else clean
    base = base.rstrip("/")
    branch_name = (branch or "main").strip() or "main"
    owner_repo = ""
    if "github.com/" in base:
        tail = base.split("github.com/", 1)[1].strip("/")
        parts = [p for p in tail.split("/") if p]
        if len(parts) >= 2:
            owner_repo = f"{parts[0]}/{parts[1]}"
    raw_version_url = (
        f"https://raw.githubusercontent.com/{owner_repo}/{branch_name}/file_service.py"
        if owner_repo else f"{base}/raw/{branch_name}/file_service.py"
    )
    api_commits_url = (
        f"https://api.github.com/repos/{owner_repo}/commits?sha={branch_name}&per_page=5"
        if owner_repo else ""
    )
    return {
        "repo_web_url": base,
        "raw_exe_url": f"{base}/raw/{branch_name}/{DEFAULT_EXE_FILENAME}",
        "raw_version_url": raw_version_url,
        "api_commits_url": api_commits_url,
    }


def _extract_app_version_from_source(text):
    m = re.search(r'APP_VERSION\s*=\s*["\'](v?\d+(?:\.\d+)+)["\']', text or "")
    return m.group(1) if m else ""


def _fetch_remote_release_info(remote_url=None, branch="main", timeout=5):
    """Prüft online auf GitHub die neueste APP_VERSION (ohne API-Rate-Limit via raw.githubusercontent.com)."""
    import urllib.request
    import time

    urls = _derive_github_urls(remote_url, branch)
    res = {
        "online": False,
        "remote_version": "",
        "remote_last_commit": "",
        "remote_last_date": "",
        "remote_commits": [],
        "error": "",
        "urls": urls,
    }
    raw_url = urls.get("raw_version_url") or ""
    if not raw_url:
        res["error"] = "Keine gültige GitHub-URL."
        return res

    sep = "&" if "?" in raw_url else "?"
    req = urllib.request.Request(
        f"{raw_url}{sep}t={int(time.time())}",
        headers={
            "User-Agent": "Datei-Suchmaschine-Pro-Updater/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            chunk = resp.read(16384).decode("utf-8", errors="replace")
        res["online"] = True
        res["remote_version"] = _extract_app_version_from_source(chunk)
    except Exception as e:
        res["error"] = str(e)
        return res

    api_url = urls.get("api_commits_url") or ""
    if api_url:
        try:
            api_req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "Datei-Suchmaschine-Pro-Updater/1.0", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(api_req, timeout=min(timeout, 3)) as aresp:
                commits = json.loads(aresp.read().decode("utf-8", errors="replace"))
            if isinstance(commits, list) and commits:
                items = []
                for idx, c in enumerate(commits[:5]):
                    sha = str(c.get("sha") or "")[:7]
                    commit_obj = c.get("commit") or {}
                    msg = str(commit_obj.get("message") or "").splitlines()[0]
                    dt = str((commit_obj.get("author") or {}).get("date") or "")[:10]
                    if idx == 0:
                        res["remote_last_commit"] = f"{sha} {msg}".strip()
                        res["remote_last_date"] = dt
                    items.append({"hash": sha, "date": dt, "message": msg})
                res["remote_commits"] = items
        except Exception:
            pass
    return res


def get_git_info():
    """Liest aktuellen Git-Status, Versionsvergleich und Remote-URL."""
    repo_dir = _get_git_repo_dir()
    exe_path = os.path.join(repo_dir, "Datei-Suchmaschine-Pro.exe")
    exe_size_mb = ""
    if os.path.exists(exe_path):
        try:
            exe_size_mb = f"{os.path.getsize(exe_path) / (1024 * 1024):.1f} MB"
        except Exception:
            exe_size_mb = ""

    info = {
        "version": APP_VERSION,
        "is_git": os.path.exists(os.path.join(repo_dir, ".git")),
        "remote_url": "",
        "branch": "main",
        "last_commit": "",
        "git_version": "",
        "remote_commit": "",
        "remote_version": "",
        "ahead": 0,
        "behind": 0,
        "dirty": False,
        "dirty_files": [],
        "exe_size_mb": exe_size_mb,
        "local_is_newer": False,
        "sync_state": "no_git",
        "sync_title": "Kein Git-Repository verknüpft",
        "sync_detail": "Die App läuft ohne lokale Git-Historie.",
        "history": [],
    }

    if not info["is_git"]:
        cfg = load_config()
        remote_url = (cfg.get("github_remote_url") or DEFAULT_GITHUB_REMOTE_URL).strip()
        branch = "main"
        rel = _fetch_remote_release_info(remote_url, branch, timeout=5)
        urls = rel.get("urls") or _derive_github_urls(remote_url, branch)
        info["remote_url"] = remote_url
        info["branch"] = branch
        info["raw_exe_url"] = urls.get("raw_exe_url", "")
        info["can_self_update"] = getattr(sys, "frozen", False)
        if rel.get("remote_last_commit"):
            info["remote_last_commit"] = rel["remote_last_commit"]
        if rel.get("remote_last_date"):
            info["remote_last_date"] = rel["remote_last_date"]
        if rel.get("remote_commits"):
            info["remote_commits"] = rel["remote_commits"]
        rv = rel.get("remote_version") or ""
        info["remote_version"] = rv
        if not rel.get("online"):
            info["sync_state"] = "offline"
            info["sync_title"] = f"Offline / GitHub nicht erreichbar ({APP_VERSION})"
            info["sync_detail"] = "Standalone-/USB-Modus (ohne Git). Online-Prüfung fehlgeschlagen – Internet/Firewall prüfen."
        elif rv and _parse_version_tuple(rv) > _parse_version_tuple(APP_VERSION):
            info["sync_state"] = "remote_newer"
            info["sync_title"] = f"Neue Version auf GitHub verfügbar: {rv} (Lokal: {APP_VERSION})"
            info["sync_detail"] = "Standalone-/USB-Modus (ohne Git): Klick auf 'Jetzt von GitHub aktualisieren' lädt die neue .exe direkt, prüft sie und startet neu (config.json bleibt erhalten)."
        elif rv and _parse_version_tuple(APP_VERSION) > _parse_version_tuple(rv):
            info["sync_state"] = "local_newer"
            info["sync_title"] = f"Lokale Version ({APP_VERSION}) neuer als GitHub ({rv})"
            info["sync_detail"] = "Standalone-/USB-Modus: Diese .exe ist neuer als der Online-Stand auf GitHub."
        else:
            info["sync_state"] = "in_sync"
            shown_rv = rv or APP_VERSION
            info["sync_title"] = f"Auf dem neuesten Stand mit GitHub ({shown_rv})"
            info["sync_detail"] = "Standalone-/USB-Modus (ohne Git): Diese .exe entspricht der neuesten GitHub-Version."
        return info

    try:
        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0:
            info["remote_url"] = res.stdout.strip()

        res = subprocess.run(["git", "branch", "--show-current"], cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            info["branch"] = res.stdout.strip()
        branch_name = info["branch"] or "main"

        res = subprocess.run(
            ["git", "log", "-1", "--format=%h - %s • %ad", "--date=format:%d.%m.%y %H:%M"],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if res.returncode == 0:
            info["last_commit"] = res.stdout.strip()

        res_sub = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if res_sub.returncode == 0:
            info["git_version"] = _extract_version_tag(res_sub.stdout.strip())

        remote_ref = f"origin/{branch_name}"
        res_rem = subprocess.run(
            ["git", "log", "-1", remote_ref, "--format=%h - %s • %ad", "--date=format:%d.%m.%y %H:%M"],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if res_rem.returncode == 0 and res_rem.stdout.strip():
            info["remote_commit"] = res_rem.stdout.strip()
            info["remote_version"] = _extract_version_tag(res_rem.stdout.strip())
        else:
            info["remote_commit"] = info["last_commit"]
            info["remote_version"] = info["git_version"]

        res_lr = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", f"HEAD...{remote_ref}"],
            cwd=repo_dir, capture_output=True, text=True
        )
        if res_lr.returncode == 0:
            parts = res_lr.stdout.strip().split()
            if len(parts) == 2:
                info["ahead"] = int(parts[0])
                info["behind"] = int(parts[1])

        res_st = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        dirty_files = _filter_meaningful_git_dirty_lines(res_st.stdout)
        info["dirty_files"] = dirty_files
        info["dirty"] = bool(dirty_files)

        res_hist = subprocess.run(
            ["git", "log", "-n", "10", "--format=%H|%h|%s|%ad", "--date=format:%d.%m.%y %H:%M"],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if res_hist.returncode == 0:
            hist = []
            for line in res_hist.stdout.splitlines():
                cols = line.split("|", 3)
                if len(cols) == 4:
                    hist.append({
                        "hash": cols[0].strip(),
                        "short": cols[1].strip(),
                        "subject": cols[2].strip(),
                        "date": cols[3].strip(),
                        "version": _extract_version_tag(cols[2]) or cols[1].strip(),
                    })
            info["history"] = hist

        local_tuple = _parse_version_tuple(APP_VERSION)
        ref_ver = info["remote_version"] or info["git_version"]
        remote_tuple = _parse_version_tuple(ref_ver)
        has_local_changes = bool(dirty_files) or info["ahead"] > 0

        if local_tuple > remote_tuple:
            info["local_is_newer"] = True
            info["sync_state"] = "local_newer"
            ref_label = ref_ver or "älterer Stand"
            info["sync_title"] = f"Lokale App-Version ({APP_VERSION}) ist höher als auf GitHub ({ref_label})"
            info["sync_detail"] = (
                f"{len(dirty_files)} geänderte Datei(en) bzw. noch nicht auf GitHub hochgeladen. "
                "Klicke auf „Stand nach GitHub hochladen“, um Code & EXE auf GitHub zu aktualisieren."
            )
        elif has_local_changes:
            info["local_is_newer"] = True
            info["sync_state"] = "local_ahead"
            info["sync_title"] = f"Lokale Änderungen noch nicht auf GitHub hochgeladen ({APP_VERSION})"
            details = []
            if dirty_files:
                details.append(f"{len(dirty_files)} lokal geänderte Datei(en)")
            if info["ahead"] > 0:
                details.append(f"{info['ahead']} ungesicherte Commit(s)")
            info["sync_detail"] = " • ".join(details) + ". Mit „Stand nach GitHub hochladen“ auf GitHub sichern."
        elif info["behind"] > 0:
            info["sync_state"] = "remote_newer"
            info["sync_title"] = f"Neuerer Stand auf GitHub verfügbar ({info['remote_version'] or str(info['behind']) + ' Commit(s)'})"
            info["sync_detail"] = (
                f"GitHub ist {info['behind']} Commit(s) voraus. "
                "Klicke auf „Jetzt von GitHub aktualisieren“, um den Stand zu laden."
            )
        else:
            info["sync_state"] = "in_sync"
            info["sync_title"] = f"Auf dem neuesten Stand mit GitHub ({APP_VERSION})"
            info["sync_detail"] = "Lokale Version und GitHub-Repository sind synchron."
    except Exception as e:
        info["error"] = str(e)

    return info


def _self_update_exe_from_github(remote_url=None, branch="main"):
    """Dubeli-sicheres Direkt-Update der laufenden .exe von GitHub (USB-/Standalone-Modus ohne Git)."""
    import urllib.request
    import tempfile

    if not getattr(sys, "frozen", False):
        return {
            "success": False,
            "error": "Kein Git-Repository gefunden. Das automatische .exe-Direktupdate funktioniert im kompilierten Programm (.exe) oder im Git-Ordner.",
        }

    exe_path = os.path.abspath(sys.executable)
    exe_dir = os.path.dirname(exe_path)

    # 1. Schreibrechte im Programmordner prüfen BEVOR heruntergeladen wird
    probe_path = os.path.join(exe_dir, f".update_writecheck_{os.getpid()}.tmp")
    try:
        with open(probe_path, "wb") as pf:
            pf.write(b"ok")
        os.remove(probe_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Keine Schreibrechte im Programmordner ({exe_dir}): {e}. Bitte als Administrator ausführen oder auf einen beschreibbaren Ordner/USB-Stick kopieren.",
        }

    cfg = load_config()
    remote = (remote_url or cfg.get("github_remote_url") or DEFAULT_GITHUB_REMOTE_URL).strip()
    rel = _fetch_remote_release_info(remote, branch, timeout=6)
    if not rel.get("online"):
        return {
            "success": False,
            "error": f"GitHub ist aktuell nicht erreichbar ({rel.get('error') or 'Offline'}). Bitte Internetverbindung prüfen.",
            "git_info": get_git_info(),
        }

    rv = rel.get("remote_version") or ""
    if rv and _parse_version_tuple(rv) <= _parse_version_tuple(APP_VERSION):
        return {
            "success": True,
            "already_up_to_date": True,
            "message": f"Bereits aktuell ({APP_VERSION})! Auf GitHub liegt aktuell {rv}.",
            "output": f"Already up to date ({APP_VERSION} >= {rv}). Kein Download nötig.",
            "git_info": get_git_info(),
        }

    urls = rel.get("urls") or _derive_github_urls(remote, branch)
    raw_exe_url = urls.get("raw_exe_url") or ""
    if not raw_exe_url:
        return {"success": False, "error": "Keine gültige Download-URL für die .exe ermittelt."}

    tmp_path = exe_path + ".update.tmp"
    bak_path = exe_path + ".bak"
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass

    downloaded = 0
    expected_len = None
    try:
        req = urllib.request.Request(
            raw_exe_url,
            headers={"User-Agent": "Datei-Suchmaschine-Pro-Updater/1.0", "Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            cl_hdr = resp.headers.get("Content-Length")
            if cl_hdr and cl_hdr.isdigit():
                expected_len = int(cl_hdr)
            with open(tmp_path, "wb") as out_f:
                while True:
                    buf = resp.read(65536)
                    if not buf:
                        break
                    out_f.write(buf)
                    downloaded += len(buf)

        min_bytes = 5 * 1024 * 1024
        if expected_len is not None and downloaded != expected_len:
            raise ValueError(f"Unvollständiger Download ({downloaded} von {expected_len} Bytes).")
        if downloaded < min_bytes:
            raise ValueError(f"Heruntergeladene Datei ist zu klein ({downloaded} Bytes) – vermutlich keine gültige .exe.")
        with open(tmp_path, "rb") as vf:
            magic = vf.read(2)
        if magic != b"MZ":
            raise ValueError("Heruntergeladene Datei ist keine gültige Windows-EXE (MZ-Signatur fehlt).")
    except Exception as e:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return {
            "success": False,
            "error": f"Download/Prüfung fehlgeschlagen (alte Version bleibt unberührt): {e}",
            "git_info": get_git_info(),
        }

    try:
        cmd_fd, cmd_path = tempfile.mkstemp(prefix="suchmaschine_update_", suffix=".cmd")
        os.close(cmd_fd)
        cmd_lines = [
            "@echo off",
            "chcp 65001 >nul",
            "setlocal",
            f'set "TARGET={exe_path}"',
            f'set "NEWEXE={tmp_path}"',
            f'set "BAKEXE={bak_path}"',
            'if not exist "%NEWEXE%" goto :end',
            'copy /Y "%TARGET%" "%BAKEXE%" >nul 2>nul',
            "set /a tries=0",
            ":waitloop",
            "ping -n 2 127.0.0.1 >nul",
            'move /Y "%NEWEXE%" "%TARGET%" >nul 2>nul',
            "if errorlevel 1 (",
            "  set /a tries+=1",
            "  if %tries% LSS 30 goto :waitloop",
            "  goto :end",
            ")",
            'start "" "%TARGET%"',
            ":end",
            'del "%~f0" >nul 2>nul',
        ]
        with open(cmd_path, "w", encoding="utf-8", newline="\r\n") as cf:
            cf.write("\r\n".join(cmd_lines) + "\r\n")

        flags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
        subprocess.Popen(
            ["cmd.exe", "/c", cmd_path],
            cwd=tempfile.gettempdir(),
            creationflags=flags,
            close_fds=True,
        )
    except Exception as e:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return {"success": False, "error": f"Update-Starter konnte nicht gestartet werden: {e}"}

    size_mb = downloaded / (1024 * 1024)
    shown_rv = rv or "neu"
    return {
        "success": True,
        "self_updating": True,
        "remote_version": rv,
        "message": f"Update ({shown_rv}, {size_mb:.1f} MB) geladen – App wird ersetzt und startet gleich neu...",
        "output": f"Quelle: {raw_exe_url}\nGröße: {size_mb:.1f} MB (MZ-Prüfung OK)\nBackup: {bak_path}\nEinstellungen (config.json) bleiben erhalten.",
    }


def git_pull_update():
    """Führt git pull aus (im Git-Repo) oder lädt im USB-/Standalone-Modus die neueste .exe von GitHub."""
    repo_dir = _get_git_repo_dir()
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        return _self_update_exe_from_github()
    try:
        check_rem = subprocess.run(["git", "remote", "-v"], cwd=repo_dir, capture_output=True, text=True)
        if not check_rem.stdout.strip():
            return {
                "success": False,
                "error": "Kein GitHub-Remote konfiguriert."
            }

        res_branch = subprocess.run(["git", "branch", "--show-current"], cwd=repo_dir, capture_output=True, text=True)
        branch = (res_branch.stdout or "").strip() or "main"

        res = subprocess.run(["git", "pull", "origin", branch], cwd=repo_dir, capture_output=True, text=True, timeout=35)
        output = (res.stdout + "\n" + res.stderr).strip()
        success = res.returncode == 0

        if not success:
            res2 = subprocess.run(["git", "pull"], cwd=repo_dir, capture_output=True, text=True, timeout=35)
            output = (res2.stdout + "\n" + res2.stderr).strip()
            success = res2.returncode == 0

        already_up_to_date = ("Already up to date" in output or "Already up-to-date" in output or "Bereits aktuell" in output)
        msg = "Update erfolgreich eingespielt!"
        if already_up_to_date:
            msg = "Bereits auf dem neuesten Stand! Keine neuen Änderungen auf GitHub vorhanden."

        return {
            "success": success,
            "already_up_to_date": already_up_to_date,
            "output": output,
            "message": msg,
            "git_info": get_git_info(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_push_upload():
    """Erstellt bei Bedarf einen Commit (ohne config.json/__pycache__) und überträgt ihn nach GitHub."""
    repo_dir = _get_git_repo_dir()
    logs = []
    try:
        res_branch = subprocess.run(["git", "branch", "--show-current"], cwd=repo_dir, capture_output=True, text=True)
        branch = (res_branch.stdout or "").strip() or "main"

        # Versehentlich getrackte Cache-Dateien einmalig aus dem Index entfernen
        subprocess.run(["git", "rm", "-r", "--cached", "--ignore-unmatch", "__pycache__"], cwd=repo_dir, capture_output=True, text=True)

        # Änderungen stagen; persönliche config.json & ignorierte Cache-Dateien außen vor lassen
        add_res = subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if add_res.returncode != 0:
            return {
                "success": False,
                "output": (add_res.stdout + "\n" + add_res.stderr).strip(),
                "message": "Staging (git add) fehlgeschlagen: " + (add_res.stderr.strip() or add_res.stdout.strip()),
                "git_info": get_git_info(),
            }
        if add_res.stdout.strip():
            logs.append(add_res.stdout.strip())
        # config.json bewusst nicht mit committen (lokale Nutzer-Einstellungen/History)
        subprocess.run(["git", "reset", "-q", "HEAD", "--", "config.json"], cwd=repo_dir, capture_output=True)

        diff_res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_dir, capture_output=True)
        if diff_res.returncode != 0:
            head_res = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
            head_ver = _extract_version_tag(head_res.stdout or "")
            if head_ver and _parse_version_tuple(APP_VERSION) <= _parse_version_tuple(head_ver):
                new_ver, bumped_files = _auto_bump_version_in_repo(repo_dir, APP_VERSION)
                if bumped_files:
                    subprocess.run(["git", "add", "--"] + bumped_files, cwd=repo_dir, capture_output=True, text=True)
                    logs.append(f"Version automatisch erhöht: {new_ver}")
            commit_msg = f"{APP_VERSION}: Sync & Build nach GitHub ({datetime.now().strftime('%d.%m.%Y %H:%M')})"
            c_res = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            c_out = (c_res.stdout + "\n" + c_res.stderr).strip()
            if c_out:
                logs.append(c_out)
            if c_res.returncode != 0:
                return {
                    "success": False,
                    "output": "\n".join(logs),
                    "message": "Commit fehlgeschlagen: " + (c_res.stderr.strip() or c_res.stdout.strip()),
                    "git_info": get_git_info(),
                }

        res = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90
        )
        p_out = (res.stdout + "\n" + res.stderr).strip()
        if p_out:
            logs.append(p_out)

        return {
            "success": res.returncode == 0,
            "output": "\n\n".join([x for x in logs if x]).strip() or "Erfolgreich hochgeladen.",
            "message": f"Stand ({APP_VERSION}) erfolgreich nach GitHub hochgeladen!" if res.returncode == 0 else p_out,
            "git_info": get_git_info(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_rollback_version(commit_hash):
    """Setzt die Arbeitskopie sicher auf einen früheren Commit zurück (mit config.json-Erhalt & Sicherheits-Stash)."""
    repo_dir = _get_git_repo_dir()
    commit_hash = (commit_hash or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit_hash):
        return {"success": False, "error": "Ungültige Commit-ID."}
    try:
        chk = subprocess.run(["git", "cat-file", "-t", commit_hash], cwd=repo_dir, capture_output=True, text=True)
        if chk.returncode != 0 or chk.stdout.strip() != "commit":
            return {"success": False, "error": f"Commit {commit_hash} nicht gefunden."}

        # Persönliche config.json im Speicher sichern, damit beim Reset nichts verloren geht
        cfg_path = os.path.join(repo_dir, "config.json")
        saved_cfg = None
        if os.path.exists(cfg_path):
            with open(cfg_path, "rb") as f:
                saved_cfg = f.read()

        logs = []
        dirty = _filter_meaningful_git_dirty_lines(
            subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, capture_output=True, text=True).stdout
        )
        if dirty:
            st_msg = f"Sicherheitskopie vor Retour ({datetime.now().strftime('%d.%m.%Y %H:%M:%S')})"
            st_res = subprocess.run(
                ["git", "stash", "push", "-u", "-m", st_msg],
                cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if st_res.stdout.strip() or st_res.stderr.strip():
                logs.append("Backup erstellt: " + (st_res.stdout + "\n" + st_res.stderr).strip())

        rst_res = subprocess.run(
            ["git", "reset", "--hard", commit_hash],
            cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        logs.append((rst_res.stdout + "\n" + rst_res.stderr).strip())

        if saved_cfg is not None:
            with open(cfg_path, "wb") as f:
                f.write(saved_cfg)

        if rst_res.returncode != 0:
            return {"success": False, "output": "\n".join(logs), "error": "Zurücksetzen fehlgeschlagen."}

        return {
            "success": True,
            "output": "\n".join([x for x in logs if x]).strip(),
            "message": f"Erfolgreich auf Version {commit_hash[:7]} zurückgesetzt (Einstellungen behalten).",
            "git_info": get_git_info(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_set_remote(remote_url):
    """Setzt oder ändert die GitHub Remote URL (oder speichert sie im Standalone-Modus in config.json)."""
    repo_dir = _get_git_repo_dir()
    clean_url = (remote_url or "").strip()
    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        cfg = load_config()
        cfg["github_remote_url"] = clean_url or DEFAULT_GITHUB_REMOTE_URL
        save_config(cfg)
        return {"success": True, "remote_url": cfg["github_remote_url"]}
    try:
        # Remove existing if any
        subprocess.run(["git", "remote", "remove", "origin"], cwd=repo_dir, capture_output=True)
        res = subprocess.run(["git", "remote", "add", "origin", clean_url], cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0:
            return {"success": True, "remote_url": clean_url}
        else:
            return {"success": False, "error": res.stderr.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_usb_drives(app_folder_name: str = "Datei-Suchmaschine", exe_name: str = "Datei-Suchmaschine-Pro.exe") -> list[dict]:
    """Erkennt eingesteckte USB-Wechseldatenträger (DRIVE_REMOVABLE) inklusive Namen & Zielpfad."""
    drives = []
    if os.name != "nt":
        return drives
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        mask = k32.GetLogicalDrives()
        for idx in range(26):
            if not (mask & (1 << idx)):
                continue
            letter = chr(ord("A") + idx)
            root = f"{letter}:\\"
            if k32.GetDriveTypeW(root) != 2:  # DRIVE_REMOVABLE
                continue
            vol_buf = ctypes.create_unicode_buffer(261)
            ok_vol = k32.GetVolumeInformationW(root, vol_buf, 260, None, None, None, None, 0)
            label = vol_buf.value.strip() if ok_vol and vol_buf.value else "USB-Stick"
            free_gb = 0.0
            try:
                usage = shutil.disk_usage(root)
                free_gb = round(usage.free / (1024 ** 3), 1)
            except OSError:
                pass
            default_dir = os.path.join(root, "Tools", app_folder_name)
            has_exe = os.path.isfile(os.path.join(default_dir, exe_name))
            usb_data_dir = os.path.join(root, "USB_Stick")
            drives.append({
                "drive": root,
                "letter": letter,
                "label": label,
                "display": f"{label} ({letter}:)",
                "free_gb": free_gb,
                "default_dir": default_dir,
                "has_exe": has_exe,
                "usb_data_dir": usb_data_dir if os.path.isdir(usb_data_dir) else "",
            })
    except Exception as exc:
        logger.debug("USB-Laufwerkssuche fehlgeschlagen: %s", exc)
    return drives


def find_usb_stick_data_dir() -> str:
    """Findet automatisch den Ordner 'USB_Stick' auf jedem eingesteckten USB-Stick (unabhängig vom Laufwerksbuchstaben)."""
    if os.name != "nt":
        return ""
    if getattr(sys, "frozen", False):
        exe_drive, _ = os.path.splitdrive(os.path.abspath(sys.executable))
        if exe_drive:
            cand = os.path.join(exe_drive + "\\", "USB_Stick")
            if os.path.isdir(cand):
                return cand
    for d in list_usb_drives():
        cand = d.get("usb_data_dir") or os.path.join(d["drive"], "USB_Stick")
        if os.path.isdir(cand):
            return cand
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        mask = k32.GetLogicalDrives()
        for idx in range(2, 26):
            if not (mask & (1 << idx)):
                continue
            cand = f"{chr(ord('A') + idx)}:\\USB_Stick"
            if os.path.isdir(cand):
                return cand
    except Exception:
        pass
    return ""


def _is_ntfs_volume(path: str) -> bool:
    if os.name != "nt" or not path:
        return False
    drive, _ = os.path.splitdrive(os.path.abspath(path))
    if not drive:
        return False
    try:
        import ctypes
        fs_buf = ctypes.create_unicode_buffer(64)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(drive + "\\", None, 0, None, None, None, fs_buf, 64)
        return bool(ok and fs_buf.value.upper() == "NTFS")
    except Exception:
        return False


def _run_icacls(args: list[str]) -> bool:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        res = subprocess.run(["icacls"] + args, capture_output=True, text=True, timeout=15, creationflags=flags)
        return res.returncode == 0
    except Exception:
        return False


def unprotect_usb_tools_dir(target_dir: str) -> None:
    """Entfernt temporär den NTFS-Löschschutz für Updates auf Tools\\..."""
    if not _is_ntfs_volume(target_dir):
        return
    norm = os.path.abspath(target_dir)
    parent = os.path.dirname(norm)
    paths = [norm]
    if os.path.basename(parent).lower() == "tools":
        paths.insert(0, parent)
    for p in paths:
        if os.path.exists(p):
            _run_icacls([p, "/remove:d", "*S-1-1-0", "/T", "/Q"])
            _run_icacls([p, "/grant", "*S-1-1-0:(OI)(CI)F", "/T", "/Q"])


def protect_usb_tools_tree(target_dir: str) -> bool:
    """Aktiviert echten NTFS-Löschschutz auf Tools (+EXEs), hält JSON-Configs beschreibbar und schützt USB_Stick-Wurzel."""
    if not _is_ntfs_volume(target_dir):
        return False
    norm = os.path.abspath(target_dir)
    drive, _ = os.path.splitdrive(norm)
    drive_root = drive + "\\" if drive else ""
    parent = os.path.dirname(norm)
    tools_root = parent if os.path.basename(parent).lower() == "tools" else norm

    ok = True
    if drive_root and os.path.isdir(drive_root):
        _run_icacls([drive_root, "/deny", "*S-1-1-0:(DC)"])

    if os.path.isdir(tools_root):
        ok = _run_icacls([tools_root, "/inheritance:r", "/Q"]) and ok
        ok = _run_icacls([tools_root, "/grant", "*S-1-1-0:(OI)(CI)RX", "*S-1-5-32-544:(OI)(CI)F", "/Q"]) and ok
        for rdir, dirs, fnames in os.walk(tools_root):
            for dn in dirs:
                _run_icacls([os.path.join(rdir, dn), "/reset", "/Q"])
            for fn in fnames:
                fp = os.path.join(rdir, fn)
                if fn.lower().endswith(".json"):
                    _run_icacls([fp, "/inheritance:r", "/Q"])
                    _run_icacls([fp, "/grant", "*S-1-1-0:(R,W)", "*S-1-5-32-544:F", "/Q"])
                    _run_icacls([fp, "/deny", "*S-1-1-0:(DE)", "/Q"])
                else:
                    _run_icacls([fp, "/reset", "/Q"])
        ok = _run_icacls([tools_root, "/deny", "*S-1-1-0:(OI)(CI)(DE,DC,WD,AD)", "/Q"]) and ok

    if drive_root:
        usb_stick_dir = os.path.join(drive_root, "USB_Stick")
        if os.path.isdir(usb_stick_dir):
            _run_icacls([usb_stick_dir, "/inheritance:r", "/Q"])
            _run_icacls([usb_stick_dir, "/grant", "*S-1-1-0:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F", "/Q"])
            _run_icacls([usb_stick_dir, "/deny", "*S-1-1-0:(DE)", "/Q"])
    return ok


def _resolve_usb_app_dir(target_root: str, app_folder: str, exe_name: str) -> str:
    raw = os.path.normpath(str(target_root or "").strip())
    if re.fullmatch(r"[A-Za-z]:\\?", raw):
        drive = raw[:2] + "\\"
        return os.path.join(drive, "Tools", app_folder)
    base_low = os.path.basename(raw).lower()
    if base_low in {app_folder.lower(), "suchmaschine", "7-ordner-pro", "7_ordner_pro", "ordner-struktur"}:
        return raw
    if os.path.isfile(os.path.join(raw, exe_name)):
        return raw
    return os.path.join(raw, app_folder)


def deploy_exe_to_usb(target_root: str = "") -> dict:
    """Erstellt den USB-Stick-Ordner und kopiert Datei-Suchmaschine-Pro.exe direkt hinein (ohne config.json anzutasten)."""
    exe_name = "Datei-Suchmaschine-Pro.exe"
    app_folder = "Datei-Suchmaschine"

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(sys.executable)
    base_dir = _get_base_dir()
    repo_dir = _get_git_repo_dir()
    candidates.extend([
        os.path.join(base_dir, exe_name),
        os.path.join(base_dir, "dist", exe_name),
        os.path.join(repo_dir, exe_name),
    ])
    src_exe = next((p for p in candidates if p and os.path.isfile(p)), "")
    if not src_exe:
        return {"success": False, "error": f"Keine fertige {exe_name} gefunden."}

    clean_target = (target_root or "").strip()
    if not clean_target:
        usb_list = list_usb_drives(app_folder, exe_name)
        if not usb_list:
            return {"success": False, "error": "Kein USB-Stick erkannt. Bitte USB-Stick einstecken oder einen Zielpfad angeben."}
        target_dir = usb_list[0]["default_dir"]
    else:
        target_dir = _resolve_usb_app_dir(clean_target, app_folder, exe_name)

    dest_exe = os.path.join(target_dir, exe_name)
    is_tools_target = os.path.basename(os.path.dirname(os.path.abspath(target_dir))).lower() == "tools"
    try:
        if os.path.abspath(src_exe).lower() == os.path.abspath(dest_exe).lower():
            return {
                "success": True,
                "already_there": True,
                "target_dir": target_dir,
                "target_exe": dest_exe,
                "message": f"Die App läuft bereits direkt unter {dest_exe}.",
            }
        if is_tools_target:
            unprotect_usb_tools_dir(target_dir)
        os.makedirs(target_dir, exist_ok=True)
        existed_before = os.path.isfile(dest_exe)
        tmp_exe = os.path.join(target_dir, f".{exe_name}.{os.getpid()}.tmp")
        shutil.copy2(src_exe, tmp_exe)
        os.replace(tmp_exe, dest_exe)
        size_mb = f"{os.path.getsize(dest_exe) / (1024 * 1024):.1f} MB"
        verb = "aktualisiert" if existed_before else "neu angelegt & abgelegt"
        prot_note = ""
        if is_tools_target and protect_usb_tools_tree(target_dir):
            prot_note = " (Tools-Ordner ist löschgeschützt)"
        return {
            "success": True,
            "already_there": False,
            "existed_before": existed_before,
            "target_dir": target_dir,
            "target_exe": dest_exe,
            "size_mb": size_mb,
            "message": f"{exe_name} ({size_mb}) erfolgreich in {target_dir} {verb}{prot_note}!",
        }
    except Exception as exc:
        if is_tools_target:
            protect_usb_tools_tree(target_dir)
        return {"success": False, "error": f"Kopieren auf USB-Stick fehlgeschlagen: {exc}"}

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

import ctypes
from ctypes import wintypes

class MapiFileDesc(ctypes.Structure):
    _fields_ = [
        ("ulReserved", wintypes.ULONG),
        ("ulFlags", wintypes.ULONG),
        ("nPosition", wintypes.ULONG),
        ("lpszPathName", wintypes.LPSTR),
        ("lpszFileName", wintypes.LPSTR),
        ("lpFileType", ctypes.c_void_p),
    ]

class MapiRecipDesc(ctypes.Structure):
    _fields_ = [
        ("ulReserved", wintypes.ULONG),
        ("ulRecipClass", wintypes.ULONG),
        ("lpszName", wintypes.LPSTR),
        ("lpszAddress", wintypes.LPSTR),
        ("ulEIDSize", wintypes.ULONG),
        ("lpEntryID", ctypes.c_void_p),
    ]

class MapiMessage(ctypes.Structure):
    _fields_ = [
        ("ulReserved", wintypes.ULONG),
        ("lpszSubject", wintypes.LPSTR),
        ("lpszNoteText", wintypes.LPSTR),
        ("lpszMessageType", wintypes.LPSTR),
        ("lpszDateReceived", wintypes.LPSTR),
        ("lpszConversationID", wintypes.LPSTR),
        ("flFlags", wintypes.ULONG),
        ("lpOriginator", ctypes.c_void_p),
        ("nRecipCount", wintypes.ULONG),
        ("lpRecips", ctypes.POINTER(MapiRecipDesc)),
        ("nFileCount", wintypes.ULONG),
        ("lpFiles", ctypes.POINTER(MapiFileDesc)),
    ]

def send_via_mapi_threaded(filepath, subject="", body="", recipient=""):
    """
    Sendet Datei über Windows Simple MAPI (direkt an Thunderbird / registrierten MAPI-Client).
    Läuft in einem separaten Thread, damit MAPISendMail den Server nicht blockiert.
    """
    def _worker():
        try:
            file_desc = MapiFileDesc(
                0, 0, 0xFFFFFFFF,
                filepath.encode('mbcs'),
                os.path.basename(filepath).encode('mbcs'),
                None
            )
            msg = MapiMessage()
            msg.ulReserved = 0
            msg.lpszSubject = subject.encode('mbcs')
            msg.lpszNoteText = body.encode('mbcs')
            msg.nFileCount = 1
            msg.lpFiles = ctypes.pointer(file_desc)
            if recipient:
                recip = MapiRecipDesc(0, 1, recipient.encode('mbcs'), f"SMTP:{recipient}".encode('mbcs'), 0, None)
                msg.nRecipCount = 1
                msg.lpRecips = ctypes.pointer(recip)
            MAPI_DIALOG = 0x00000008
            MAPI_LOGON_UI = 0x00000001
            ctypes.windll.mapi32.MAPISendMail(0, 0, ctypes.pointer(msg), MAPI_DIALOG | MAPI_LOGON_UI, 0)
        except Exception as e:
            logger.warning(f"MAPI worker error: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True

def get_thunderbird_profile_dir():
    """Findet den aktiven Thunderbird-Profilordner (%APPDATA%\\Thunderbird\\Profiles\\*.default*)"""
    appdata = os.environ.get("APPDATA", "")
    profiles_dir = os.path.join(appdata, "Thunderbird", "Profiles")
    if os.path.exists(profiles_dir):
        candidates = [os.path.join(profiles_dir, d) for d in os.listdir(profiles_dir) if os.path.isdir(os.path.join(profiles_dir, d))]
        rel = [c for c in candidates if "default-release" in os.path.basename(c).lower()]
        if rel:
            return rel[0]
        def_p = [c for c in candidates if "default" in os.path.basename(c).lower()]
        if def_p:
            return def_p[0]
        if candidates:
            return candidates[0]
    return None

def _cleanup_stale_thunderbird_locks():
    """Löscht verwaiste parent.lock und .startup-incomplete Dateien, falls kein Thunderbird-Prozess läuft"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Process thunderbird -ErrorAction SilentlyContinue"],
            capture_output=True, text=True, timeout=3
        )
        if "thunderbird" not in out.stdout.lower():
            import glob
            appdata = os.environ.get("APPDATA", "")
            localappdata = os.environ.get("LOCALAPPDATA", "")
            for lock_f in glob.glob(os.path.join(appdata, "Thunderbird", "Profiles", "*", "parent.lock")):
                try:
                    os.remove(lock_f)
                except Exception:
                    pass
            for inc_f in glob.glob(os.path.join(localappdata, "Thunderbird", "Profiles", "*", ".startup-incomplete")):
                try:
                    os.remove(inc_f)
                except Exception:
                    pass
    except Exception:
        pass

def send_file_via_email(filepath, recipient="", client=None):
    """
    Erstellt E-Mail Entwurf mit Anhang für das gewählte E-Mail-Programm:
    - icloud: Apple iCloud Mail (https://www.icloud.com/mail/) im Browser + Strg+V
    - gmail: Google Mail Web-Compose im Browser + Strg+V
    - thunderbird: Mozilla Thunderbird + Strg+V Backup
    - outlook: Microsoft Outlook + Strg+V
    - default: Windows Standard mailto: + Strg+V
    """
    if not os.path.exists(filepath):
        return {"success": False, "error": "Datei nicht gefunden"}
    
    if not client:
        client = get_email_client()
        
    abs_p = os.path.abspath(filepath)
    abs_p_win = abs_p.replace("/", "\\")
    filename = os.path.basename(filepath)
    clean_filename = filename.replace("'", "")

    # Grundsätzlich: Datei IMMER in die Windows-Zwischenablage legen!
    # Damit funktioniert Strg+V in JEDEM Mail-Programm und jedem Browser zuverlässig!
    copy_file_for_teams(filepath)

    # 1. APPLE ICLOUD MAIL
    if client == "icloud":
        try:
            import webbrowser
            # Windows Explorer mit markierter Datei im Hintergrund öffnen für Drag & Drop
            try:
                subprocess.Popen(['explorer.exe', f'/select,{abs_p_win}'])
            except Exception:
                pass
                
            icloud_url = "https://www.icloud.com/mail/"
            try:
                webbrowser.open(icloud_url)
            except Exception:
                pass
                
            return {
                "success": True,
                "method": "icloud",
                "web_url": icloud_url,
                "message": f"iCloud Mail im Browser geöffnet & '{filename}' in Zwischenablage kopiert! Im Mail-Fenster einfach [Strg + V] drücken."
            }
        except Exception as e:
            return {"success": False, "error": f"Fehler beim Öffnen von iCloud Mail: {str(e)}"}

    # 2. GOOGLE MAIL (GMAIL)
    elif client == "gmail":
        try:
            import urllib.parse
            import webbrowser
            # Windows Explorer mit markierter Datei im Hintergrund öffnen für Drag & Drop
            try:
                subprocess.Popen(['explorer.exe', f'/select,{abs_p_win}'])
            except Exception:
                pass
                
            subject = urllib.parse.quote(f"Datei: {filename}")
            body = urllib.parse.quote(
                f"Hier ist die Datei: {filename}\n\n"
                f"Lokaler Pfad: {abs_p_win}\n\n"
                f"💡 Die Datei ist bereits in der Zwischenablage kopiert!\n"
                f"Einfach [Strg + V] drücken zum Einfügen."
            )
            gmail_url = f"https://mail.google.com/mail/u/0/?view=cm&fs=1&to={urllib.parse.quote(recipient)}&su={subject}&body={body}"
            
            try:
                webbrowser.open(gmail_url)
            except Exception:
                pass
                
            return {
                "success": True,
                "method": "gmail",
                "web_url": gmail_url,
                "message": f"Google Mail geöffnet & '{filename}' in Zwischenablage kopiert! Im Mail-Fenster einfach [Strg + V] drücken."
            }
        except Exception as e:
            return {"success": False, "error": f"Fehler beim Öffnen von Google Mail: {str(e)}"}

    # 3. MOZILLA THUNDERBIRD
    elif client == "thunderbird":
        # Verwaiste Locks aufräumen
        _cleanup_stale_thunderbird_locks()
        
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
                prof_dir = get_thunderbird_profile_dir()
                file_uri = Path(abs_p).as_uri()
                compose_arg = f"attachment='{file_uri}',subject='Datei: {clean_filename}'"
                if recipient:
                    compose_arg = f"to='{recipient}'," + compose_arg
                cmd = [tb_exe]
                if prof_dir and os.path.exists(prof_dir):
                    cmd.extend(["-profile", prof_dir])
                cmd.extend(["-compose", compose_arg])
                subprocess.Popen(cmd)
                return {
                    "success": True,
                    "method": "thunderbird",
                    "message": f"Thunderbird geöffnet & '{filename}' angehängt (sowie in Zwischenablage für Strg+V)!"
                }
            except Exception as e_tb:
                logger.warning(f"Thunderbird start failed: {e_tb}")

        # Fallback auf mailto
        import urllib.parse
        subject = urllib.parse.quote(f"Datei: {filename}")
        body = urllib.parse.quote(f"Hier ist die Datei: {filename}\n(Datei in Zwischenablage, einfach Strg+V drücken)")
        try:
            os.startfile(f"mailto:{recipient}?subject={subject}&body={body}")
        except Exception:
            pass
        return {
            "success": True,
            "method": "thunderbird_fallback",
            "message": f"E-Mail-Programm aufgerufen & '{filename}' in Zwischenablage kopiert (einfach [Strg + V] drücken)!"
        }

    # 4a. NEUES OUTLOOK (Store-App) - kennt keine Anhang-Schalter, daher Strg+V
    elif client == "outlook_new":
        import urllib.parse
        subject = urllib.parse.quote(f"Datei: {filename}")
        body = urllib.parse.quote(f"Hier ist die Datei: {filename}\n(Datei in Zwischenablage, einfach Strg+V drücken)")
        try:
            # Direkt die Store-App ansprechen (nicht das Standard-Mailprogramm)
            subprocess.Popen(["explorer.exe", "shell:AppsFolder\\Microsoft.OutlookForWindows_8wekyb3d8bbwe!Microsoft.OutlookforWindows"])
            time.sleep(1.5)
            os.startfile(f"mailto:{recipient}?subject={subject}&body={body}")
        except Exception as e_new:
            logger.warning(f"Neues Outlook start failed: {e_new}")
        return {
            "success": True,
            "method": "outlook_new",
            "message": f"Neues Outlook geöffnet & '{filename}' in Zwischenablage kopiert – im Nachrichtenfenster einfach [Strg + V] drücken!"
        }

    # 4b. MICROSOFT OUTLOOK (klassisch)
    elif client == "outlook":
        outlook_paths = [
            r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"C:\Program Files\Microsoft Office\Office16\OUTLOOK.EXE",
            r"C:\Program Files (x86)\Microsoft Office\Office16\OUTLOOK.EXE",
            r"C:\Program Files\Microsoft Office\Office15\OUTLOOK.EXE",
        ]
        ol_exe = next((p for p in outlook_paths if os.path.exists(p)), None)
        if not ol_exe:
            import shutil
            ol_exe = shutil.which("OUTLOOK.EXE") or shutil.which("outlook.exe")

        if ol_exe:
            try:
                # Direkter nativer Microsoft Outlook Befehl: OUTLOOK.EXE /c ipm.note /a "Pfad"
                cmd = [ol_exe, "/c", "ipm.note", "/a", abs_p_win]
                if recipient:
                    cmd.extend(["/m", recipient])
                subprocess.Popen(cmd)
                return {
                    "success": True,
                    "method": "outlook",
                    "message": f"Microsoft Outlook mit Anhang '{filename}' geöffnet!"
                }
            except Exception as e_ol:
                logger.warning(f"Direct Outlook command failed: {e_ol}")

        # Fallback auf COM Automation
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

    # 5. WINDOWS STANDARD (MAILTO:) FALLBACK
    import urllib.parse
    subject = urllib.parse.quote(f"Datei: {filename}")
    body = urllib.parse.quote(f"Hier ist die Datei: {filename}\n\nPfad: {filepath}\n(Datei in Zwischenablage, einfach Strg+V drücken)")
    mailto_url = f"mailto:{recipient}?subject={subject}&body={body}"
    try:
        os.startfile(mailto_url)
    except Exception:
        pass
    return {
        "success": True,
        "method": "clipboard_mailto",
        "message": f"E-Mail geöffnet & '{filename}' in Zwischenablage kopiert (in E-Mail einfach [Strg + V] drücken)!"
    }


# ============================================================
# BRÜCKE ZU 7-ORDNER-PRO (App-Discovery & Datei-/Ordner-Übergabe)
# ============================================================

def get_shared_bridge_dir() -> str:
    """Gemeinsames Austauschverzeichnis unter %APPDATA%\\7-Ordner-Pro für beide Apps."""
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    bridge_dir = os.path.join(appdata, "7-Ordner-Pro")
    try:
        os.makedirs(bridge_dir, exist_ok=True)
    except Exception:
        pass
    return bridge_dir


def get_shared_bridge_file() -> str:
    return os.path.join(get_shared_bridge_dir(), "app_bridge.json")


def _load_bridge_registry() -> dict:
    path = get_shared_bridge_file()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def register_suchmaschine_bridge(port: int = 5005) -> str:
    """Registriert Installationspfade von Datei-Suchmaschine Pro für 7-Ordner-Pro."""
    base_dir = _get_base_dir()
    data = _load_bridge_registry()
    entry = {
        "version": APP_VERSION,
        "dir": base_dir,
        "config_file": CONFIG_FILE,
        "port": int(port),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if getattr(sys, "frozen", False):
        entry["exe"] = sys.executable
    else:
        exe_candidate = os.path.join(base_dir, "Datei-Suchmaschine-Pro.exe")
        if os.path.isfile(exe_candidate):
            entry["exe"] = exe_candidate
        script_candidate = os.path.join(base_dir, "app.py")
        if os.path.isfile(script_candidate):
            entry["script"] = script_candidate
    vbs_candidate = os.path.join(base_dir, "Start_Hintergrund.vbs")
    if os.path.isfile(vbs_candidate):
        entry["vbs"] = vbs_candidate
    data["suchmaschine"] = entry

    bridge_path = get_shared_bridge_file()
    try:
        with open(bridge_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.debug("Bridge-Registrierung fehlgeschlagen: %s", exc)
    return bridge_path


def _iter_shallow_subdirs(root_dir: str, limit: int = 80) -> list[str]:
    """Listet direkte (nicht versteckte) Unterordner für ordnernamen-unabhängige USB-Suche."""
    if not root_dir or not os.path.isdir(root_dir):
        return []
    out = []
    skip = {"windows", "system volume information", "__pycache__", "node_modules", "appdata", "programdata"}
    try:
        with os.scandir(root_dir) as it:
            for entry in it:
                if len(out) >= limit:
                    break
                name_low = entry.name.lower()
                if name_low.startswith((".", "$")) or name_low in skip:
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        out.append(entry.path)
                except OSError:
                    continue
    except OSError:
        pass
    return out


def find_seven_folder_app() -> list | None:
    """Sucht 7-Ordner-Pro (EXE oder Python-Skript) unabhängig vom Ordnernamen lokal/USB-relativ, über Bridge oder Standardpfade."""
    reg = _load_bridge_registry()
    sf = reg.get("seven_folder", {}) if isinstance(reg.get("seven_folder"), dict) else {}

    base_dir = _get_base_dir()
    parent_dir = os.path.dirname(base_dir)
    user_home = os.path.expanduser("~")
    desktop_dir = os.path.join(user_home, "Desktop")

    # Zuerst direkt am aktuellen App-/USB-Speicherort suchen (ordnernamen-unabhängig, ohne Vorab-Start)
    exe_candidates = [
        os.path.join(base_dir, "7-Ordner-Pro.exe"),
        os.path.join(base_dir, "7-Ordner-Pro", "7-Ordner-Pro.exe"),
        os.path.join(parent_dir, "7-Ordner-Pro", "7-Ordner-Pro.exe"),
        os.path.join(parent_dir, "Ordner-Struktur", "7-Ordner-Pro.exe"),
        os.path.join(parent_dir, "7-Ordner-Pro.exe"),
    ]
    for sub in _iter_shallow_subdirs(base_dir):
        exe_candidates.append(os.path.join(sub, "7-Ordner-Pro.exe"))
    for sub in _iter_shallow_subdirs(parent_dir):
        exe_candidates.append(os.path.join(sub, "7-Ordner-Pro.exe"))

    if sf.get("exe"):
        exe_candidates.append(sf["exe"])
    if sf.get("dir"):
        exe_candidates.append(os.path.join(sf["dir"], "7-Ordner-Pro.exe"))
    exe_candidates.extend([
        os.path.join(desktop_dir, "7-Ordner-Pro.exe"),
        os.path.join(user_home, ".gemini", "antigravity", "scratch", "Ordner-Struktur", "7-Ordner-Pro.exe"),
    ])

    for cand in exe_candidates:
        if cand and os.path.isfile(cand):
            return [cand]

    script_candidates = [
        os.path.join(base_dir, "app.pyw"),
        os.path.join(parent_dir, "Ordner-Struktur", "app.pyw"),
        os.path.join(parent_dir, "7-Ordner-Pro", "app.pyw"),
    ]
    for sub in _iter_shallow_subdirs(parent_dir):
        script_candidates.append(os.path.join(sub, "app.pyw"))
    if sf.get("script"):
        script_candidates.append(sf["script"])
    script_candidates.append(
        os.path.join(user_home, ".gemini", "antigravity", "scratch", "Ordner-Struktur", "app.pyw")
    )
    for script in script_candidates:
        if script and os.path.isfile(script):
            py_exe = sys.executable if not getattr(sys, "frozen", False) else "python"
            py_dir = os.path.dirname(py_exe)
            pyw = os.path.join(py_dir, "pythonw.exe")
            runner = pyw if os.path.isfile(pyw) else py_exe
            return [runner, script]
    return None


def _save_bridge_registry(data: dict) -> str:
    bridge_path = get_shared_bridge_file()
    try:
        os.makedirs(os.path.dirname(bridge_path), exist_ok=True)
        with open(bridge_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.debug("Bridge-Speichern fehlgeschlagen: %s", exc)
    return bridge_path


def get_shared_theme() -> str:
    reg = _load_bridge_registry()
    val = str(reg.get("theme") or "").strip().lower()
    return val if val in ("light", "dark") else "light"


def set_shared_theme(theme: str) -> str:
    clean = "dark" if str(theme or "").strip().lower() == "dark" else "light"
    reg = _load_bridge_registry()
    reg["theme"] = clean
    reg["theme_updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_bridge_registry(reg)
    return clean


def send_to_seven_folder(paths=None, folder_path: str | None = None, target_dir: str | None = None, theme: str | None = None) -> dict:
    """Übergibt markierte Dateien oder einen Ordner an 7-Ordner-Pro und startet es bei Bedarf automatisch."""
    register_suchmaschine_bridge()
    resolved_theme = set_shared_theme(theme) if theme in ("light", "dark") else get_shared_theme()
    base_cmd = find_seven_folder_app()
    if not base_cmd:
        return {
            "success": False,
            "error": "7-Ordner-Pro wurde nicht gefunden (weder EXE noch app.pyw). Bitte 7-Ordner-Pro einmalig starten."
        }

    clean_paths = []
    seen = set()
    for raw in (paths or []):
        p_str = str(raw or "").strip()
        if not p_str:
            continue
        norm = os.path.normpath(p_str)
        low = norm.lower()
        if low in seen:
            continue
        if os.path.exists(norm):
            seen.add(low)
            clean_paths.append(norm)

    cmd = list(base_cmd)
    handoff_file = ""
    mode = "launch"

    if clean_paths:
        parents = [os.path.dirname(p) for p in clean_paths if os.path.dirname(p)]
        common_src = ""
        if parents:
            try:
                cand = os.path.commonpath(parents)
                if os.path.isdir(cand):
                    common_src = cand
            except Exception:
                common_src = ""
        if not common_src and parents:
            common_src = parents[0]

        bridge_dir = get_shared_bridge_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        handoff_file = os.path.join(bridge_dir, f"handoff_queue_{ts}.json")
        payload = {
            "version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_app": "Datei-Suchmaschine",
            "source_dir": common_src,
            "target_dir": os.path.normpath(target_dir) if target_dir else "",
            "theme": resolved_theme,
            "paths": clean_paths,
        }
        try:
            with open(handoff_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            return {"success": False, "error": f"Übergabedatei konnte nicht geschrieben werden: {exc}"}

        cmd.extend(["--handoff", handoff_file])
        mode = "handoff"
    elif folder_path and str(folder_path).strip():
        clean_folder = os.path.normpath(str(folder_path).strip())
        if not os.path.isdir(clean_folder):
            return {"success": False, "error": f"Ordner nicht gefunden: {clean_folder}"}
        cmd.extend(["--source", clean_folder])
        if target_dir and str(target_dir).strip():
            cmd.extend(["--target", os.path.normpath(str(target_dir).strip())])
        mode = "source"

    cmd.extend(["--theme", resolved_theme])

    creation_flags = 0
    if os.name == "nt":
        creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    try:
        app_cwd = os.path.dirname(base_cmd[-1]) or None
        proc = subprocess.Popen(cmd, cwd=app_cwd, creationflags=creation_flags)
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(int(proc.pid))
            except Exception:
                pass
    except Exception as exc:
        return {"success": False, "error": f"7-Ordner-Pro konnte nicht gestartet werden: {exc}"}

    return {
        "success": True,
        "mode": mode,
        "count": len(clean_paths),
        "folder": os.path.normpath(str(folder_path).strip()) if folder_path else "",
        "handoff_file": handoff_file,
        "app_cmd": base_cmd[0],
        "launched": True,
    }


def _unique_dest_path(dest_dir: str, filename: str) -> str:
    """Erzeugt einen kollisionsfreien Zielpfad ('Datei (1).ext'), falls Zieldatei existiert."""
    candidate = os.path.join(dest_dir, filename)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(filename)
    idx = 1
    while idx < 10000:
        cand = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
        if not os.path.exists(cand):
            return cand
        idx += 1
    return candidate


def _check_dir_writable(target_dir: str) -> tuple:
    """Prüft Schreibrechte im Zielordner ohne Dateien zu hinterlassen."""
    try:
        os.makedirs(target_dir, exist_ok=True)
        probe = os.path.join(target_dir, f".__write_test_{os.getpid()}_{int(time.time() * 1000)}.tmp")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def browse_folder_dialog(initial_dir: str = "") -> str:
    """Öffnet den nativen Windows-Ordnerauswahl-Dialog sauber ohne Konsole."""
    if os.name != "nt":
        return ""
    init_dir = resolve_german_alias_path(initial_dir or "")
    if not init_dir or not os.path.isdir(init_dir):
        init_dir = find_usb_stick_data_dir() or os.path.expanduser("~")
    init_escaped = init_dir.replace("'", "''")
    ps_script = (
        "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
        "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$f.Description = 'Speicher-Ordner für ausgewählte Dateien wählen'; "
        "$f.UseDescriptionForTitle = $true; "
        "$f.ShowNewFolderButton = $true; "
        f"if (Test-Path '{init_escaped}') {{ $f.SelectedPath = '{init_escaped}' }}; "
        "$owner = New-Object System.Windows.Forms.Form; "
        "$owner.TopMost = $true; $owner.StartPosition = 'Manual'; $owner.Location = New-Object System.Drawing.Point(-32000,-32000); "
        "if ($f.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($f.SelectedPath) }; "
        "$owner.Dispose()"
    )
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        res = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            timeout=180,
        )
        chosen = (res.stdout or "").strip()
        if chosen and os.path.isdir(chosen):
            return os.path.normpath(chosen)
    except Exception as exc:
        logger.warning("Ordnerauswahl fehlgeschlagen: %s", exc)
    return ""


def copy_or_move_files(
    items: list,
    target_base_dir: str,
    mode: str = "copy",
    use_category_subfolder: bool = False,
) -> dict:
    """Kopiert oder verschiebt ausgewählte Dateien/Ordner sicher in den gewählten Speicher-Ordner."""
    base_dir = resolve_german_alias_path((target_base_dir or "").strip())
    if not base_dir:
        return {"success": False, "error": "Kein Zielordner angegeben.", "processed": [], "errors": []}

    abs_base = os.path.abspath(base_dir)
    ok_write, err_write = _check_dir_writable(abs_base)
    if not ok_write:
        return {
            "success": False,
            "error": f"Keine Schreibrechte im Zielordner '{abs_base}': {err_write}",
            "processed": [],
            "errors": [],
        }

    op_mode = "move" if str(mode).lower() == "move" else "copy"
    processed = []
    errors = []

    for entry in (items or []):
        if isinstance(entry, str):
            src_path = entry
            target_sub = ""
        elif isinstance(entry, dict):
            src_path = entry.get("path") or ""
            target_sub = (entry.get("target_sub") or "").strip().strip("\\/")
        else:
            continue

        if not src_path or not os.path.exists(src_path):
            errors.append({"path": src_path, "error": "Quelldatei nicht gefunden"})
            continue

        try:
            src_abs = os.path.abspath(src_path)
            # Wenn target_sub selbst ein absoluter Pfad ist (benutzerdefinierter Ordner pro Zeile), diesen nutzen
            if target_sub and os.path.isabs(target_sub):
                dest_dir = target_sub
            elif use_category_subfolder and target_sub:
                dest_dir = os.path.join(abs_base, target_sub.replace("/", os.sep))
            else:
                dest_dir = abs_base

            os.makedirs(dest_dir, exist_ok=True)
            base_name = os.path.basename(src_abs.rstrip("\\/"))
            dest_path = _unique_dest_path(dest_dir, base_name)

            if os.path.normcase(os.path.dirname(src_abs)) == os.path.normcase(os.path.abspath(dest_dir)) and op_mode == "move":
                # Bereits genau in diesem Zielordner
                processed.append({"src": src_abs, "dest": src_abs, "unchanged": True})
                continue

            if os.path.isdir(src_abs):
                if op_mode == "move":
                    shutil.move(src_abs, dest_path)
                else:
                    shutil.copytree(src_abs, dest_path, dirs_exist_ok=False)
            else:
                if op_mode == "move":
                    shutil.move(src_abs, dest_path)
                else:
                    shutil.copy2(src_abs, dest_path)

            processed.append({"src": src_abs, "dest": dest_path})
        except Exception as exc:
            errors.append({"path": src_path, "error": str(exc)})

    return {
        "success": len(processed) > 0 or len(errors) == 0,
        "mode": op_mode,
        "target_dir": abs_base,
        "processed_count": len(processed),
        "error_count": len(errors),
        "processed": processed,
        "errors": errors,
    }


# ============================================================================
# ASYNCHRONER TRANSFER-MANAGER (Live-Fortschritt, Restzeit, Abbrechen, Zurück)
# ============================================================================
_TRANSFER_JOBS: dict[str, dict] = {}
_TRANSFER_LOCK = threading.Lock()
_TRANSFER_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB Fallback-Chunks (Windows nutzt primär natives CopyFileExW)


def _calc_path_size_bytes(path: str) -> int:
    try:
        if os.path.isfile(path):
            return max(0, os.path.getsize(path))
        if os.path.isdir(path):
            total = 0
            for root, _, files in os.walk(path):
                for fn in files:
                    try:
                        total += max(0, os.path.getsize(os.path.join(root, fn)))
                    except Exception:
                        pass
            return total
    except Exception:
        pass
    return 0


def _copy_file_windows_native(
    src: str,
    dest: str,
    cancel_event: threading.Event,
    on_chunk=None,
) -> bool:
    """Nutzt Windows' natives kernel32.CopyFileExW (Explorer-Kopier-Engine) mit Live-Fortschritt & Abbruch."""
    import ctypes
    from ctypes import wintypes

    PROGRESS_CONTINUE = 0
    PROGRESS_CANCEL = 1

    LPPROGRESS_ROUTINE = ctypes.WINFUNCTYPE(
        wintypes.DWORD,
        ctypes.c_int64,   # TotalFileSize
        ctypes.c_int64,   # TotalBytesTransferred
        ctypes.c_int64,   # StreamSize
        ctypes.c_int64,   # StreamBytesTransferred
        wintypes.DWORD,   # dwStreamNumber
        wintypes.DWORD,   # dwCallbackReason
        wintypes.HANDLE,  # hSourceFile
        wintypes.HANDLE,  # hDestinationFile
        wintypes.LPVOID,  # lpData
    )

    last_transferred = 0
    cancel_flag = ctypes.c_int(0)

    def _progress_cb(total_size, total_transferred, _ss, _st, _sn, _reason, _hs, _hd, _data):
        nonlocal last_transferred
        if cancel_event.is_set():
            cancel_flag.value = 1
            return PROGRESS_CANCEL
        delta = max(0, int(total_transferred) - last_transferred)
        last_transferred = int(total_transferred)
        if delta > 0 and on_chunk:
            on_chunk(delta, last_transferred, max(0, int(total_size)))
        return PROGRESS_CONTINUE

    cb = LPPROGRESS_ROUTINE(_progress_cb)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CopyFileExW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        LPPROGRESS_ROUTINE,
        wintypes.LPVOID,
        ctypes.POINTER(ctypes.c_int),
        wintypes.DWORD,
    ]
    kernel32.CopyFileExW.restype = wintypes.BOOL

    ok = bool(kernel32.CopyFileExW(src, dest, cb, None, ctypes.byref(cancel_flag), 0))
    if not ok:
        err_code = ctypes.get_last_error()
        if cancel_event.is_set() or err_code == 1235:  # ERROR_REQUEST_ABORTED
            try:
                if os.path.exists(dest):
                    os.remove(dest)
            except Exception:
                pass
            return False
        raise OSError(err_code, f"CopyFileExW Fehler (Code {err_code})")
    return True


def _copy_file_chunked(
    src: str,
    dest: str,
    cancel_event: threading.Event,
    on_chunk=None,
) -> bool:
    """Kopiert eine Datei maximal schnell (Windows-natives CopyFileExW, Fallback 8-MB-Chunks). Bei Abbruch wird die Teil-Datei gelöscht."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.name == "nt":
        try:
            return _copy_file_windows_native(src, dest, cancel_event, on_chunk=on_chunk)
        except Exception:
            if cancel_event.is_set():
                return False
            # Fallback auf 8-MB-Python-Chunk-Kopie
            pass

    file_total = 0
    try:
        file_total = max(0, os.path.getsize(src))
    except Exception:
        pass
    file_copied = 0
    try:
        with open(src, "rb", buffering=_TRANSFER_CHUNK_SIZE) as fsrc, open(dest, "wb", buffering=_TRANSFER_CHUNK_SIZE) as fdst:
            while True:
                if cancel_event.is_set():
                    break
                buf = fsrc.read(_TRANSFER_CHUNK_SIZE)
                if not buf:
                    break
                fdst.write(buf)
                n = len(buf)
                file_copied += n
                if on_chunk:
                    on_chunk(n, file_copied, file_total)
        if cancel_event.is_set():
            try:
                if os.path.exists(dest):
                    os.remove(dest)
            except Exception:
                pass
            return False
        try:
            shutil.copystat(src, dest)
        except Exception:
            pass
        return True
    except Exception:
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception:
            pass
        raise


def _copy_dir_chunked(
    src_dir: str,
    dest_dir: str,
    cancel_event: threading.Event,
    on_chunk=None,
    on_file=None,
) -> bool:
    os.makedirs(dest_dir, exist_ok=True)
    for root, dirs, files in os.walk(src_dir):
        if cancel_event.is_set():
            return False
        rel = os.path.relpath(root, src_dir)
        target_root = dest_dir if rel == "." else os.path.join(dest_dir, rel)
        os.makedirs(target_root, exist_ok=True)
        for fn in files:
            if cancel_event.is_set():
                return False
            s_file = os.path.join(root, fn)
            d_file = os.path.join(target_root, fn)
            if on_file:
                on_file(fn, _calc_path_size_bytes(s_file))
            ok = _copy_file_chunked(s_file, d_file, cancel_event, on_chunk=on_chunk)
            if not ok:
                return False
    return True


def _run_undo_for_job(job: dict):
    """Macht alle bereits abgeschlossenen Kopier-/Verschiebe-Schritte eines Jobs rückgängig."""
    processed = list(job.get("processed") or [])
    reversible = [p for p in reversed(processed) if not p.get("unchanged")]
    total_undo_bytes = sum(_calc_path_size_bytes(p["dest"]) for p in reversible if os.path.exists(p["dest"]))

    undo_cancel = threading.Event()
    start_t = time.monotonic()
    last_speed_t = start_t
    last_speed_b = 0

    with _TRANSFER_LOCK:
        job["status"] = "rolling_back"
        job["undo_total"] = len(reversible)
        job["undo_done"] = 0
        job["undo_errors"] = []
        job["total_bytes"] = total_undo_bytes
        job["copied_bytes"] = 0
        job["file_total_bytes"] = 0
        job["file_copied_bytes"] = 0
        job["speed_mb_s"] = 0.0
        job["eta_seconds"] = None
        job["current_index"] = 0
        job["total_items"] = len(reversible)
        job["current_file"] = ""

    def _on_undo_chunk(n_bytes, f_copied, f_total):
        nonlocal last_speed_t, last_speed_b
        now = time.monotonic()
        with _TRANSFER_LOCK:
            job["copied_bytes"] += n_bytes
            job["file_copied_bytes"] = f_copied
            job["file_total_bytes"] = f_total
            dt = now - last_speed_t
            if dt >= 0.35:
                diff = job["copied_bytes"] - last_speed_b
                inst = max(0.0, (diff / (1024 * 1024)) / max(0.01, dt))
                prev = job["speed_mb_s"]
                job["speed_mb_s"] = inst if prev <= 0 else (prev * 0.65 + inst * 0.35)
                last_speed_t = now
                last_speed_b = job["copied_bytes"]
                rem = max(0, job["total_bytes"] - job["copied_bytes"])
                if job["speed_mb_s"] > 0.05:
                    job["eta_seconds"] = rem / (job["speed_mb_s"] * 1024 * 1024)
            job["elapsed_seconds"] = now - start_t

    done_cnt = 0
    undo_errors = []
    for idx, rec in enumerate(reversible, start=1):
        src = rec["src"]
        dest = rec["dest"]
        op_mode = rec.get("mode") or job.get("mode", "copy")
        is_dir = bool(rec.get("is_dir"))
        fname = os.path.basename(dest.rstrip("\\/")) or dest
        fsize = _calc_path_size_bytes(dest) if os.path.exists(dest) else 0

        with _TRANSFER_LOCK:
            job["current_index"] = idx
            job["current_file"] = fname
            job["file_copied_bytes"] = 0
            job["file_total_bytes"] = fsize

        try:
            if not os.path.exists(dest):
                continue
            if op_mode == "copy":
                if is_dir or os.path.isdir(dest):
                    shutil.rmtree(dest, ignore_errors=False)
                else:
                    os.remove(dest)
                with _TRANSFER_LOCK:
                    job["copied_bytes"] += fsize
                done_cnt += 1
            else:
                # Verschieben rückgängig: dest zurück nach src
                os.makedirs(os.path.dirname(src), exist_ok=True)
                restore_target = src if not os.path.exists(src) else _unique_dest_path(os.path.dirname(src), os.path.basename(src))
                moved_fast = False
                try:
                    os.rename(dest, restore_target)
                    moved_fast = True
                    with _TRANSFER_LOCK:
                        job["copied_bytes"] += fsize
                except OSError:
                    pass
                if not moved_fast:
                    if is_dir or os.path.isdir(dest):
                        _copy_dir_chunked(dest, restore_target, undo_cancel, on_chunk=_on_undo_chunk)
                        shutil.rmtree(dest, ignore_errors=False)
                    else:
                        _copy_file_chunked(dest, restore_target, undo_cancel, on_chunk=_on_undo_chunk)
                        os.remove(dest)
                done_cnt += 1
        except Exception as exc:
            undo_errors.append({"path": dest, "error": str(exc)})

        with _TRANSFER_LOCK:
            job["undo_done"] = done_cnt
            job["undo_errors"] = list(undo_errors)

    with _TRANSFER_LOCK:
        job["status"] = "rolled_back"
        job["undo_done"] = done_cnt
        job["undo_errors"] = undo_errors
        job["eta_seconds"] = 0.0
        job["elapsed_seconds"] = time.monotonic() - start_t
        job["can_undo"] = False


def start_transfer_job(
    items: list,
    target_base_dir: str,
    mode: str = "copy",
    use_category_subfolder: bool = False,
) -> dict:
    """Startet einen asynchronen Kopier-/Verschiebe-Job mit Byte-Fortschritt, Restzeit, Abbrechen & Zurück."""
    base_dir = resolve_german_alias_path((target_base_dir or "").strip())
    if not base_dir:
        return {"success": False, "error": "Kein Zielordner angegeben."}

    abs_base = os.path.abspath(base_dir)
    ok_write, err_write = _check_dir_writable(abs_base)
    if not ok_write:
        return {"success": False, "error": f"Keine Schreibrechte im Zielordner '{abs_base}': {err_write}"}

    op_mode = "move" if str(mode).lower() == "move" else "copy"
    prepared = []
    pre_errors = []
    total_bytes = 0

    for entry in (items or []):
        if isinstance(entry, str):
            src_path = entry
            target_sub = ""
        elif isinstance(entry, dict):
            src_path = entry.get("path") or ""
            target_sub = (entry.get("target_sub") or "").strip().strip("\\/")
        else:
            continue
        if not src_path or not os.path.exists(src_path):
            pre_errors.append({"path": src_path, "error": "Quelldatei nicht gefunden"})
            continue
        src_abs = os.path.abspath(src_path)
        is_dir = os.path.isdir(src_abs)
        sz = _calc_path_size_bytes(src_abs)
        total_bytes += sz
        prepared.append({
            "src": src_abs,
            "target_sub": target_sub,
            "is_dir": is_dir,
            "size": sz,
            "name": os.path.basename(src_abs.rstrip("\\/")) or src_abs,
        })

    if not prepared:
        return {
            "success": False,
            "error": pre_errors[0]["error"] if pre_errors else "Keine gültigen Quelldateien gefunden.",
        }

    job_id = f"tr_{int(time.time() * 1000)}_{hashlib.md5(f'{abs_base}{time.monotonic()}'.encode()).hexdigest()[:6]}"
    cancel_ev = threading.Event()
    job = {
        "job_id": job_id,
        "status": "running",
        "mode": op_mode,
        "target_dir": abs_base,
        "use_category_subfolder": bool(use_category_subfolder),
        "total_items": len(prepared),
        "current_index": 0,
        "current_file": prepared[0]["name"],
        "total_bytes": total_bytes,
        "copied_bytes": 0,
        "file_total_bytes": prepared[0]["size"],
        "file_copied_bytes": 0,
        "speed_mb_s": 0.0,
        "eta_seconds": None,
        "elapsed_seconds": 0.0,
        "processed": [],
        "errors": list(pre_errors),
        "cancel_event": cancel_ev,
        "auto_undo": False,
        "can_undo": False,
        "undo_total": 0,
        "undo_done": 0,
        "undo_errors": [],
        "created_at": time.monotonic(),
    }

    with _TRANSFER_LOCK:
        # Alte abgeschlossene Jobs aufräumen (max 25 behalten)
        if len(_TRANSFER_JOBS) > 25:
            old_ids = sorted(_TRANSFER_JOBS.keys(), key=lambda k: _TRANSFER_JOBS[k].get("created_at", 0))
            for oid in old_ids[:-20]:
                if _TRANSFER_JOBS[oid].get("status") not in ("running", "rolling_back"):
                    _TRANSFER_JOBS.pop(oid, None)
        _TRANSFER_JOBS[job_id] = job

    def _worker():
        start_t = time.monotonic()
        last_speed_t = start_t
        last_speed_b = 0

        def _on_chunk(n_bytes, f_copied, f_total):
            nonlocal last_speed_t, last_speed_b
            now = time.monotonic()
            with _TRANSFER_LOCK:
                job["copied_bytes"] += n_bytes
                job["file_copied_bytes"] = f_copied
                job["file_total_bytes"] = f_total
                job["elapsed_seconds"] = now - start_t
                dt = now - last_speed_t
                if dt >= 0.35:
                    diff = job["copied_bytes"] - last_speed_b
                    inst = max(0.0, (diff / (1024 * 1024)) / max(0.01, dt))
                    prev = job["speed_mb_s"]
                    job["speed_mb_s"] = inst if prev <= 0 else (prev * 0.65 + inst * 0.35)
                    last_speed_t = now
                    last_speed_b = job["copied_bytes"]
                    rem = max(0, job["total_bytes"] - job["copied_bytes"])
                    if job["speed_mb_s"] > 0.05:
                        job["eta_seconds"] = rem / (job["speed_mb_s"] * 1024 * 1024)

        def _on_subfile(fn, fsz):
            with _TRANSFER_LOCK:
                job["current_file"] = fn
                job["file_copied_bytes"] = 0
                job["file_total_bytes"] = fsz

        for idx, it in enumerate(prepared, start=1):
            if cancel_ev.is_set():
                break
            src_abs = it["src"]
            target_sub = it["target_sub"]
            is_dir = it["is_dir"]
            fsize = it["size"]

            with _TRANSFER_LOCK:
                job["current_index"] = idx
                job["current_file"] = it["name"]
                job["file_copied_bytes"] = 0
                job["file_total_bytes"] = fsize
                job["elapsed_seconds"] = time.monotonic() - start_t

            try:
                if target_sub and os.path.isabs(target_sub):
                    dest_dir = target_sub
                elif use_category_subfolder and target_sub:
                    dest_dir = os.path.join(abs_base, target_sub.replace("/", os.sep))
                else:
                    dest_dir = abs_base

                os.makedirs(dest_dir, exist_ok=True)
                dest_path = _unique_dest_path(dest_dir, it["name"])

                if os.path.normcase(os.path.dirname(src_abs)) == os.path.normcase(os.path.abspath(dest_dir)) and op_mode == "move":
                    with _TRANSFER_LOCK:
                        job["processed"].append({"src": src_abs, "dest": src_abs, "is_dir": is_dir, "mode": op_mode, "unchanged": True})
                        job["copied_bytes"] += fsize
                    continue

                if op_mode == "copy":
                    if is_dir:
                        ok = _copy_dir_chunked(src_abs, dest_path, cancel_ev, on_chunk=_on_chunk, on_file=_on_subfile)
                    else:
                        ok = _copy_file_chunked(src_abs, dest_path, cancel_ev, on_chunk=_on_chunk)
                    if not ok and cancel_ev.is_set():
                        break
                else:
                    moved_fast = False
                    try:
                        os.rename(src_abs, dest_path)
                        moved_fast = True
                        with _TRANSFER_LOCK:
                            job["copied_bytes"] += fsize
                            job["file_copied_bytes"] = fsize
                    except OSError:
                        pass
                    if not moved_fast:
                        if is_dir:
                            ok = _copy_dir_chunked(src_abs, dest_path, cancel_ev, on_chunk=_on_chunk, on_file=_on_subfile)
                            if not ok and cancel_ev.is_set():
                                try:
                                    if os.path.exists(dest_path):
                                        shutil.rmtree(dest_path, ignore_errors=True)
                                except Exception:
                                    pass
                                break
                            shutil.rmtree(src_abs, ignore_errors=False)
                        else:
                            ok = _copy_file_chunked(src_abs, dest_path, cancel_ev, on_chunk=_on_chunk)
                            if not ok and cancel_ev.is_set():
                                break
                            os.remove(src_abs)

                with _TRANSFER_LOCK:
                    job["processed"].append({"src": src_abs, "dest": dest_path, "is_dir": is_dir, "mode": op_mode, "unchanged": False})
                    job["can_undo"] = True
            except Exception as exc:
                with _TRANSFER_LOCK:
                    job["errors"].append({"path": src_abs, "error": str(exc)})

        with _TRANSFER_LOCK:
            was_cancelled = cancel_ev.is_set()
            do_auto_undo = bool(job.get("auto_undo")) and len([p for p in job["processed"] if not p.get("unchanged")]) > 0
            job["elapsed_seconds"] = time.monotonic() - start_t
            job["eta_seconds"] = 0.0
            if not do_auto_undo:
                job["status"] = "cancelled" if was_cancelled else ("done" if (len(job["processed"]) > 0 or len(job["errors"]) == 0) else "error")

        if do_auto_undo:
            _run_undo_for_job(job)

    threading.Thread(target=_worker, daemon=True).start()
    return {"success": True, "job_id": job_id}


def get_transfer_job_status(job_id: str) -> dict:
    with _TRANSFER_LOCK:
        job = _TRANSFER_JOBS.get(job_id)
        if not job:
            return {"success": False, "error": "Transfer-Job nicht gefunden"}
        total_b = max(0, job["total_bytes"])
        copied_b = min(total_b, max(0, job["copied_bytes"])) if total_b > 0 else max(0, job["copied_bytes"])
        pct = (copied_b / total_b * 100.0) if total_b > 0 else (
            (job["current_index"] / max(1, job["total_items"])) * 100.0 if job["status"] == "running" else 100.0
        )
        f_total = max(0, job["file_total_bytes"])
        f_copied = min(f_total, max(0, job["file_copied_bytes"])) if f_total > 0 else 0
        f_pct = (f_copied / f_total * 100.0) if f_total > 0 else 0.0
        return {
            "success": True,
            "job_id": job_id,
            "status": job["status"],
            "mode": job["mode"],
            "target_dir": job["target_dir"],
            "total_items": job["total_items"],
            "current_index": job["current_index"],
            "current_file": job["current_file"],
            "total_bytes": total_b,
            "copied_bytes": copied_b,
            "percent": round(min(100.0, max(0.0, pct)), 1),
            "file_total_bytes": f_total,
            "file_copied_bytes": f_copied,
            "file_percent": round(min(100.0, max(0.0, f_pct)), 1),
            "speed_mb_s": round(job["speed_mb_s"], 1),
            "eta_seconds": None if job["eta_seconds"] is None else max(0, int(round(job["eta_seconds"]))),
            "elapsed_seconds": max(0, int(round(job["elapsed_seconds"]))),
            "processed_count": len(job["processed"]),
            "error_count": len(job["errors"]),
            "processed": list(job["processed"]),
            "errors": list(job["errors"]),
            "can_undo": bool(job.get("can_undo")) and len([p for p in job["processed"] if not p.get("unchanged")]) > 0,
            "undo_total": job.get("undo_total", 0),
            "undo_done": job.get("undo_done", 0),
            "undo_errors": list(job.get("undo_errors") or []),
        }


def cancel_transfer_job(job_id: str, auto_undo: bool = False) -> dict:
    with _TRANSFER_LOCK:
        job = _TRANSFER_JOBS.get(job_id)
        if not job:
            return {"success": False, "error": "Transfer-Job nicht gefunden"}
        if auto_undo:
            job["auto_undo"] = True
        ev = job.get("cancel_event")
        if ev:
            ev.set()
        return {"success": True, "auto_undo": bool(auto_undo)}


def undo_transfer_job(job_id: str) -> dict:
    with _TRANSFER_LOCK:
        job = _TRANSFER_JOBS.get(job_id)
        if not job:
            return {"success": False, "error": "Transfer-Job nicht gefunden"}
        if job["status"] in ("running", "rolling_back"):
            return {"success": False, "error": "Vorgang läuft noch."}
        if not job.get("can_undo"):
            return {"success": False, "error": "Keine rückgängig machbaren Dateien vorhanden."}
        job["status"] = "rolling_back"
    threading.Thread(target=_run_undo_for_job, args=(job,), daemon=True).start()
    return {"success": True}


def get_rich_file_preview_info(path: str) -> dict:
    """Liefert schnelle, strukturierte Metadaten & Vorschau-Inhalte für die Seiten-Vorschau."""
    if not path or not os.path.exists(path):
        return {"success": False, "error": "Datei nicht gefunden"}

    is_dir = os.path.isdir(path)
    name = os.path.basename(path.rstrip("\\/")) or path
    _, ext = os.path.splitext(name.lower())
    target_sub, cat_label = classify_for_seven_folder(name, ext, is_dir=is_dir)
    try:
        st = os.stat(path, follow_symlinks=False)
        size_fmt = "Ordner" if is_dir else format_size(st.st_size)
        mod_fmt = datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M")
    except Exception:
        size_fmt = "—"
        mod_fmt = "—"

    info = {
        "success": True,
        "name": name,
        "path": path,
        "folder": to_german_display_path(os.path.dirname(path)),
        "ext": "ORDNER" if is_dir else (ext.lstrip(".").upper() or "DATEI"),
        "size_formatted": size_fmt,
        "modified_formatted": mod_fmt,
        "category_label": cat_label,
        "target_sub": target_sub,
        "kind": "info",
        "badge": "Ordner" if is_dir else (ext.lstrip(".").upper() or "DATEI"),
        "text": "",
        "dimensions": "",
    }

    if is_dir:
        try:
            entries = sorted(os.listdir(path))[:40]
            info["kind"] = "text"
            info["badge"] = f"Ordner ({len(entries)}+ Einträge)"
            info["text"] = "\n".join(f"• {e}" for e in entries) or "Leerer Ordner."
        except Exception:
            info["text"] = "Ordnerinhalt konnte nicht gelesen werden."
        return info

    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".ico", ".svg"}:
        info["kind"] = "image"
        try:
            if ext != ".svg":
                from PIL import Image
                with Image.open(path) as im:
                    w, h = im.size
                    info["dimensions"] = f"{w} × {h} px"
                    info["badge"] = f"{w} × {h} px"
        except Exception:
            pass
        return info

    if ext == ".pdf":
        info["kind"] = "pdf"
        info["badge"] = "PDF-Dokument"
        return info

    if ext in {".txt", ".log", ".py", ".js", ".ts", ".json", ".html", ".css", ".md", ".csv", ".xml", ".yaml", ".yml", ".bat", ".ps1", ".ini", ".cfg"}:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                info["text"] = f.read(16000)
            info["kind"] = "text"
            info["badge"] = f"Text ({ext.lstrip('.').upper()})"
        except Exception as exc:
            info["text"] = f"Vorschau nicht lesbar: {exc}"
        return info

    if ext in {".docx", ".xlsx", ".pptx", ".zip"}:
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            if ext == ".zip":
                with zipfile.ZipFile(path, "r") as zf:
                    names = zf.namelist()
                info["kind"] = "text"
                info["badge"] = f"ZIP ({len(names)} Einträge)"
                info["text"] = "\n".join(f"• {n}" for n in names[:35])
                return info
            if ext == ".docx":
                with zipfile.ZipFile(path, "r") as zf:
                    if "word/document.xml" in zf.namelist():
                        root = ET.fromstring(zf.read("word/document.xml"))
                        paras = []
                        for p in root.iter():
                            if p.tag.endswith("}p"):
                                txt = "".join(t.text for t in p.iter() if t.tag.endswith("}t") and t.text)
                                if txt.strip():
                                    paras.append(txt.strip())
                                if len(paras) >= 45:
                                    break
                        info["kind"] = "text"
                        info["badge"] = "Word-Dokument (DOCX)"
                        info["text"] = "\n\n".join(paras)[:6000] or "Leeres Word-Dokument."
                        return info
        except Exception:
            pass

    info["text"] = f"Dateityp: {info['ext']}\nGröße: {size_fmt}\n\nUnten auf „Standard-App“ klicken, um die Datei vollständig zu öffnen."
    return info
