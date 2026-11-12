import os
import sys
import json
import subprocess
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(BASE_DIR, "open_queue.json")

ACCESS_EXTS = {".accdb", ".mdb", ".accde", ".accdr"}
NOTEPAD_TEXT_EXTS = {
    ".srt", ".vtt", ".sub", ".nfo", ".cfg", ".ini", ".conf",
    ".log", ".env", ".yml", ".yaml", ".toml", ".sql", ".md", ".txt"
}

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
        # Prüfe ob gültiges UTF-8 oder druckbares Westeuropäisch (CP1252)
        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            pass
        # Zähle Steuerzeichen außerhalb von Tab/CR/LF
        non_printable = sum(1 for b in chunk if b < 32 and b not in (9, 10, 13))
        return (non_printable / len(chunk)) < 0.05
    except Exception:
        return False

def _is_pdf_header(filepath):
    try:
        with open(filepath, "rb") as f:
            return f.read(4) == b"%PDF"
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

def smart_open_on_desktop(abs_p):
    # 0. Ordner -> Direkt im Windows Explorer öffnen
    if os.path.isdir(abs_p):
        subprocess.Popen(f'explorer.exe "{abs_p}"')
        return

    ext = os.path.splitext(abs_p)[1].lower().strip()

    # 1. PDF (oder Datei ohne Endung mit %PDF Header) -> Direkt in PDF X
    if ext == ".pdf" or (not ext and _is_pdf_header(abs_p)):
        encoded = urllib.parse.quote(abs_p, safe="")
        os.startfile(f"pdflab-service-editor://open/?fpath={encoded}")
        return

    # 2. Microsoft Access (.accdb, .mdb, .accde, .accdr) -> Direkt in MSACCESS.EXE
    if ext in ACCESS_EXTS:
        msaccess = _find_msaccess_exe()
        if msaccess:
            subprocess.Popen([msaccess, abs_p])
            return
        try:
            os.startfile(abs_p)
            return
        except Exception:
            pass

    # 3. Untertitel (.srt, .vtt, .sub) & Text-/Konfigurationsdateien ohne feste App -> Windows Editor
    if ext in NOTEPAD_TEXT_EXTS:
        subprocess.Popen(["notepad.exe", abs_p])
        return

    # 4. Datei mit bekannter Windows-Zuordnung -> Standard-App starten
    if ext and _has_windows_association(ext):
        try:
            os.startfile(abs_p)
            return
        except OSError:
            pass

    # 5. Datei ohne Endung (wie z.B. 'Bucharest') oder unbekannte Endung:
    #    Inhaltsprüfung: Falls lesbarer Text -> im Windows-Editor öffnen, sonst 'Öffnen mit...' Dialog
    if _is_likely_text_file(abs_p):
        subprocess.Popen(["notepad.exe", abs_p])
    else:
        subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", abs_p])

def main():
    if len(sys.argv) < 2:
        return
    raw_uri = sys.argv[1].strip()
    # Format: suchmaschine://run/<ticket_id>
    ticket_id = raw_uri.rstrip("/").split("/")[-1]
    if not os.path.exists(QUEUE_FILE):
        return
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue = json.load(f)
    except Exception:
        return

    item = queue.pop(ticket_id, None)
    if not item:
        return

    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    action = item.get("action")
    target_path = item.get("path")
    if not target_path or not os.path.exists(target_path):
        return

    abs_p = os.path.abspath(target_path)
    if action == "select":
        subprocess.Popen(f'explorer.exe /select,"{abs_p}"')
    elif action == "open":
        smart_open_on_desktop(abs_p)
    elif action == "open_with":
        subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", abs_p])

if __name__ == "__main__":
    main()
