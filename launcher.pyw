import os
import sys
import json
import subprocess
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(BASE_DIR, "open_queue.json")

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
        # Windows Explorer mit markierter Datei im Vordergrund öffnen
        subprocess.Popen(f'explorer.exe /select,"{abs_p}"')
    elif action == "open":
        ext = os.path.splitext(abs_p)[1].lower()
        if ext == ".pdf":
            encoded = urllib.parse.quote(abs_p, safe="")
            os.startfile(f"pdflab-service-editor://open/?fpath={encoded}")
        else:
            os.startfile(abs_p)

if __name__ == "__main__":
    main()
