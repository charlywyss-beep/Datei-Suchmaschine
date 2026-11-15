import os
import sys
import time
import threading
import mimetypes
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, abort

# Wenn von PyInstaller kompiliert: Vorlagen und Static aus dem Bundle laden
if getattr(sys, 'frozen', False):
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    template_folder = os.path.join(base_dir, 'templates')
    static_folder = os.path.join(base_dir, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

import file_service
# Max upload/request size
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _get_asset_version():
    static_root = app.static_folder or os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    mtimes = []
    for rel in ("css/style.css", "js/app.js"):
        p = os.path.join(static_root, rel)
        if os.path.exists(p):
            try:
                mtimes.append(int(os.path.getmtime(p)))
            except Exception:
                pass
    return f"{file_service.APP_VERSION}_{max(mtimes) if mtimes else 0}"


@app.route("/")
def index():
    return render_template("index.html", version=file_service.APP_VERSION, asset_v=_get_asset_version())

@app.route("/api/system-info", methods=["GET"])
def system_info():
    locations = file_service.get_system_locations()
    od_info = file_service.detect_onedrive_paths()
    local_ip = file_service.get_local_ip()
    git_info = file_service.get_git_info()
    saved_paths = file_service.get_saved_paths()
    all_drives = file_service.get_all_local_drives()
    network_paths = file_service.get_network_paths()
    search_history = file_service.get_search_history()
    saved_searches = file_service.get_saved_searches()
    
    return jsonify({
        "app_version": file_service.APP_VERSION,
        "local_ip": local_ip,
        "network_url": f"http://{local_ip}:5005",
        "onedrive_info": od_info,
        "git_info": git_info,
        "saved_paths": saved_paths,
        "all_drives": all_drives,
        "network_paths": network_paths,
        "locations": locations,
        "search_history": search_history,
        "saved_searches": saved_searches,
        "email_client": file_service.get_email_client(),
        "usb_stick_dir": file_service.find_usb_stick_data_dir(),
        "usb_drives": file_service.list_usb_drives(),
        "seven_folder_options": file_service.get_seven_folder_options(),
    })

@app.route("/api/network-paths", methods=["GET"])
def get_network_paths_route():
    return jsonify({"network_paths": file_service.get_network_paths()})

@app.route("/api/add-network-path", methods=["POST"])
def add_network_path_route():
    data = request.get_json() or {}
    path = data.get("path", "")
    name = data.get("name", "")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.add_network_path(path, name)
    return jsonify(res)

@app.route("/api/delete-network-path", methods=["POST"])
def delete_network_path_route():
    data = request.get_json() or {}
    path_id = data.get("id") or data.get("path")
    if not path_id:
        return jsonify({"error": "ID fehlt"}), 400
    res = file_service.remove_network_path(path_id)
    return jsonify(res)

@app.route("/api/saved-paths", methods=["GET"])
def get_saved_paths_route():
    return jsonify({"saved_paths": file_service.get_saved_paths()})

@app.route("/api/save-path", methods=["POST"])
def save_path_route():
    data = request.get_json() or {}
    name = data.get("name", "")
    path = data.get("path", "")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.add_saved_path(name, path)
    return jsonify(res)

@app.route("/api/delete-saved-path", methods=["POST"])
def delete_saved_path_route():
    data = request.get_json() or {}
    path_id = data.get("id") or data.get("path")
    if not path_id:
        return jsonify({"error": "ID fehlt"}), 400
    res = file_service.remove_saved_path(path_id)
    return jsonify(res)

@app.route("/api/search-history", methods=["GET"])
def get_search_history_route():
    return jsonify({
        "search_history": file_service.get_search_history(),
        "saved_searches": file_service.get_saved_searches()
    })

@app.route("/api/delete-search-history", methods=["POST"])
def delete_search_history_route():
    data = request.get_json() or {}
    item_id = data.get("id")
    clear_all = bool(data.get("clear_all", False))
    res = file_service.remove_search_history(item_id=item_id, clear_all=clear_all)
    return jsonify(res)

@app.route("/api/save-search", methods=["POST"])
def save_search_route():
    data = request.get_json() or {}
    query = data.get("query", "")
    category = data.get("category", "all")
    name = data.get("name", "")
    res = file_service.add_saved_search(query=query, category=category, name=name)
    return jsonify(res)

@app.route("/api/delete-saved-search", methods=["POST"])
def delete_saved_search_route():
    data = request.get_json() or {}
    search_id = data.get("id") or data.get("query")
    if not search_id:
        return jsonify({"error": "ID fehlt"}), 400
    res = file_service.remove_saved_search(search_id)
    return jsonify(res)

@app.route("/api/save-onedrive-paths", methods=["POST"])
def save_onedrive_paths():
    data = request.get_json() or {}
    cfg = file_service.load_config()
    if "personal" in data:
        cfg["onedrive_personal"] = data["personal"]
    if "business" in data:
        cfg["onedrive_business"] = data["business"]
    if "icloud" in data:
        cfg["icloud_drive"] = data["icloud"]
    if "gdrive" in data or "google_drive" in data:
        cfg["google_drive"] = data.get("gdrive") or data.get("google_drive")
    file_service.save_config(cfg)
    return jsonify({"success": True, "onedrive_info": file_service.detect_onedrive_paths()})

@app.route("/api/save-gdrive-path", methods=["POST"])
def save_gdrive_path_route():
    data = request.get_json() or {}
    path = (data.get("path") or "").strip()
    cfg = file_service.load_config()
    cfg["google_drive"] = path
    file_service.save_config(cfg)
    return jsonify({"success": True, "onedrive_info": file_service.detect_onedrive_paths()})

@app.route("/api/git-info", methods=["GET"])
def git_info_route():
    return jsonify(file_service.get_git_info())

def _schedule_server_restart():
    import threading
    def _restart():
        import time
        time.sleep(1.2)
        if getattr(sys, 'frozen', False):
            subprocess.Popen([sys.executable, "--no-browser"], cwd=os.path.dirname(sys.executable))
        else:
            python_exe = sys.executable
            app_script = os.path.abspath(__file__)
            subprocess.Popen([python_exe, app_script, "--no-browser"], cwd=os.path.dirname(app_script))
        os._exit(0)
    threading.Thread(target=_restart, daemon=True).start()


def _schedule_clean_exit(delay_sec=0.8):
    import threading
    def _exit_soon():
        import time
        time.sleep(delay_sec)
        os._exit(0)
    threading.Thread(target=_exit_soon, daemon=True).start()


@app.route("/api/git-update", methods=["POST"])
def git_update_route():
    res = file_service.git_pull_update()
    if res.get("success"):
        if res.get("already_up_to_date"):
            pass
        elif res.get("self_updating"):
            _schedule_clean_exit(0.8)
        else:
            _schedule_server_restart()
    return jsonify(res)


@app.route("/api/git-push", methods=["POST"])
def git_push_route():
    res = file_service.git_push_upload()
    return jsonify(res)


@app.route("/api/git-rollback", methods=["POST"])
def git_rollback_route():
    data = request.get_json() or {}
    commit_hash = (data.get("commit_hash") or "").strip()
    res = file_service.git_rollback_version(commit_hash)
    if res.get("success"):
        _schedule_server_restart()
    return jsonify(res)

@app.route("/api/git-set-remote", methods=["POST"])
def git_set_remote_route():
    data = request.get_json() or {}
    remote_url = data.get("remote_url", "")
    if not remote_url:
        return jsonify({"error": "Remote URL fehlt"}), 400
    res = file_service.git_set_remote(remote_url)
    return jsonify(res)

@app.route("/api/usb-drives", methods=["GET"])
def usb_drives_route():
    return jsonify({
        "drives": file_service.list_usb_drives(),
        "usb_stick_dir": file_service.find_usb_stick_data_dir(),
    })

@app.route("/api/usb-install", methods=["POST"])
def usb_install_route():
    data = request.get_json() or {}
    target_root = data.get("target_root", "")
    return jsonify(file_service.deploy_exe_to_usb(target_root))

@app.route("/api/upload-file", methods=["POST"])
def upload_file_route():
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei im Request"}), 400
    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return jsonify({"error": "Keine Datei ausgewählt"}), 400
    target_dir = request.form.get("target_dir")
    res = file_service.save_uploaded_file(uploaded_file, target_dir)
    return jsonify(res)

@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json() or {}
    directory = data.get("directory", "THIS_PC")
    query = data.get("query", "")
    category = data.get("category", "all")
    custom_exts = data.get("extensions", "")
    only_onedrive = data.get("only_onedrive", False)
    
    # Parse sizes (bytes, human text e.g. '500 KB' / '1 MB', or legacy MB numbers)
    min_bytes = file_service.parse_size_to_bytes(data.get("min_size_bytes"), default_unit="bytes")
    if min_bytes is None and data.get("min_size_text") not in (None, ""):
        min_bytes = file_service.parse_size_to_bytes(data.get("min_size_text"), default_unit="kb")
    if min_bytes is None and data.get("min_size_mb") not in (None, ""):
        min_bytes = file_service.parse_size_to_bytes(data.get("min_size_mb"), default_unit="mb")

    max_bytes = file_service.parse_size_to_bytes(data.get("max_size_bytes"), default_unit="bytes")
    if max_bytes is None and data.get("max_size_text") not in (None, ""):
        max_bytes = file_service.parse_size_to_bytes(data.get("max_size_text"), default_unit="mb")
    if max_bytes is None and data.get("max_size_mb") not in (None, ""):
        max_bytes = file_service.parse_size_to_bytes(data.get("max_size_mb"), default_unit="mb")

    # Date filter (ISO oder TT.MM.JJJJ)
    mod_after_ts = file_service.parse_filter_datetime(data.get("modified_after"), end_of_day=False)
    mod_before_ts = file_service.parse_filter_datetime(data.get("modified_before"), end_of_day=True)

    max_results = int(data.get("max_results", 3000))

    import time
    start_t = time.time()
    results = file_service.fast_search(
        root_dir=directory,
        query=query,
        category=category,
        custom_extensions=custom_exts,
        min_size_bytes=min_bytes,
        max_size_bytes=max_bytes,
        modified_after_ts=mod_after_ts,
        modified_before_ts=mod_before_ts,
        only_onedrive=only_onedrive,
        max_results=max_results
    )
    elapsed = round(time.time() - start_t, 3)

    total_bytes = sum(f["size"] for f in results)
    if query and query.strip():
        search_history = file_service.add_search_history(query.strip(), category)
    else:
        search_history = file_service.get_search_history()

    return jsonify({
        "count": len(results),
        "total_bytes": total_bytes,
        "total_size_formatted": file_service.format_size(total_bytes),
        "elapsed_seconds": elapsed,
        "results": results,
        "search_history": search_history,
        "saved_searches": file_service.get_saved_searches()
    })

@app.route("/api/find-duplicates", methods=["POST"])
def find_duplicates_route():
    data = request.get_json() or {}
    files = data.get("files")
    directory = data.get("directory")

    if files and isinstance(files, list) and len(files) > 0:
        target = files
    elif directory and os.path.exists(directory):
        target = directory
    else:
        return jsonify({"error": "Keine Dateien oder ungültiger Pfad angegeben"}), 400

    report = file_service.find_duplicates(target)
    return jsonify(report)

@app.route("/api/delete-files", methods=["POST"])
def delete_files_route():
    data = request.get_json() or {}
    paths = data.get("paths", [])
    if not paths:
        return jsonify({"error": "Keine Pfade angegeben"}), 400
    res = file_service.delete_to_trash(paths)
    return jsonify(res)

@app.route("/api/rename-file", methods=["POST"])
def rename_file_route():
    data = request.get_json() or {}
    old_path = data.get("path")
    new_name = data.get("new_name")
    if not old_path or not new_name:
        return jsonify({"error": "Pfad oder neuer Name fehlt"}), 400
    res = file_service.rename_single_file(old_path, new_name)
    return jsonify(res)

@app.route("/api/batch-rename-preview", methods=["POST"])
def batch_rename_preview_route():
    data = request.get_json() or {}
    files = data.get("files", [])
    rule_type = data.get("rule_type", "replace")
    params = data.get("params", {})
    if not files:
        return jsonify({"error": "Keine Dateien ausgewählt"}), 400
    preview = file_service.batch_rename_preview(files, rule_type, params)
    return jsonify({"preview": preview})

@app.route("/api/batch-rename-execute", methods=["POST"])
def batch_rename_execute_route():
    data = request.get_json() or {}
    preview_items = data.get("preview", [])
    if not preview_items:
        return jsonify({"error": "Keine Vorschau übermittelt"}), 400
    res = file_service.execute_batch_rename(preview_items)
    return jsonify(res)

@app.route("/api/open-file", methods=["POST"])
def open_file_route():
    data = request.get_json() or {}
    path = data.get("path")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.open_file_in_system(path)
    return jsonify(res)

@app.route("/api/open-folder", methods=["POST"])
def open_folder_route():
    data = request.get_json() or {}
    path = data.get("path")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.open_folder_and_select(path)
    return jsonify(res)

@app.route("/api/open-with", methods=["POST"])
def open_with_route():
    data = request.get_json() or {}
    path = data.get("path")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.open_with_dialog(path)
    return jsonify(res)

@app.route("/api/edit-file", methods=["POST"])
def edit_file_route():
    data = request.get_json() or {}
    path = data.get("path")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.edit_file_in_system(path)
    return jsonify(res)

@app.route("/api/save-file", methods=["POST"])
def save_file_route():
    data = request.get_json() or {}
    path = data.get("path")
    content = data.get("content", "")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.save_text_file(path, content)
    return jsonify(res)

@app.route("/api/open-windows-settings", methods=["POST"])
def open_windows_settings_route():
    res = file_service.open_default_apps_settings()
    return jsonify(res)

@app.route("/api/print-file", methods=["POST"])
def print_file_route():
    data = request.get_json() or {}
    path = data.get("path")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.print_file_in_windows(path)
    return jsonify(res)

@app.route("/api/copy-teams", methods=["POST"])
def copy_teams_route():
    data = request.get_json() or {}
    path = data.get("path")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.copy_file_for_teams(path)
    return jsonify(res)

@app.route("/api/set-email-client", methods=["POST"])
def set_email_client_route():
    data = request.get_json() or {}
    client = data.get("client", "thunderbird")
    res = file_service.set_email_client(client)
    return jsonify(res)

@app.route("/api/send-email", methods=["POST"])
def send_email_route():
    try:
        data = request.get_json() or {}
        path = data.get("path")
        recipient = data.get("recipient", "")
        client = data.get("client")
        if not path:
            return jsonify({"success": False, "error": "Pfad fehlt"}), 400
        res = file_service.send_file_via_email(path, recipient, client=client)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": f"Interner Fehler beim E-Mail-Versand: {str(e)}"}), 500

@app.route("/api/download", methods=["GET"])
def download_file_route():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        return abort(404, "File not found")
    filename = os.path.basename(path)
    return send_file(path, as_attachment=True, download_name=filename)

@app.route("/api/file-preview", methods=["GET"])
@app.route("/api/preview", methods=["GET"])
def file_preview():
    path = request.args.get("path")
    if not path or not os.path.exists(path):
        return abort(404, "File not found")
    
    # Check mime type
    mime_type, _ = mimetypes.guess_type(path)
    ext = os.path.splitext(path)[1].lower()

    # Image preview
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"}:
        return send_file(path, mimetype=mime_type or "image/jpeg")

    # Text / Code preview
    if ext in {".txt", ".log", ".py", ".js", ".json", ".html", ".css", ".md", ".csv", ".xml", ".yaml", ".yml", ".bat", ".ps1"}:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(50000) # max 50KB for preview
            return jsonify({"type": "text", "content": content})
        except Exception as e:
            return jsonify({"type": "error", "error": str(e)})

    # PDF preview info
    if ext == ".pdf":
        return send_file(path, mimetype="application/pdf")

    # Binary/Other: return file stats
    stat = os.stat(path)
    return jsonify({
        "type": "binary",
        "name": os.path.basename(path),
        "size": file_service.format_size(stat.st_size),
        "mimetype": mime_type or "application/octet-stream"
    })


@app.route("/api/preview-info", methods=["GET"])
def api_preview_info():
    path = request.args.get("path") or ""
    return jsonify(file_service.get_rich_file_preview_info(path))


@app.route("/api/browse-folder", methods=["POST"])
def api_browse_folder():
    data = request.get_json(silent=True) or {}
    initial_dir = (data.get("initial_dir") or "").strip()
    chosen = ""
    try:
        import webview
        wins = getattr(webview, "windows", None) or []
        if wins:
            dlg_type = getattr(getattr(webview, "FileDialog", None), "FOLDER", getattr(webview, "FOLDER_DIALOG", 20))
            init_resolved = file_service.resolve_german_alias_path(initial_dir) if initial_dir else ""
            kwargs = {"directory": init_resolved} if init_resolved and os.path.isdir(init_resolved) else {}
            res = wins[0].create_file_dialog(dlg_type, **kwargs)
            if res and len(res) > 0:
                chosen = os.path.normpath(str(res[0]))
    except Exception:
        chosen = ""

    if not chosen:
        chosen = file_service.browse_folder_dialog(initial_dir)

    return jsonify({"success": bool(chosen), "path": chosen})


@app.route("/api/copy-or-move-files", methods=["POST"])
def api_copy_or_move_files():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or data.get("paths") or []
    target_dir = (data.get("target_dir") or "").strip()
    mode = data.get("mode", "copy")
    use_category_subfolder = bool(data.get("use_category_subfolder", False))
    res = file_service.copy_or_move_files(
        items=items,
        target_base_dir=target_dir,
        mode=mode,
        use_category_subfolder=use_category_subfolder,
    )
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code


@app.route("/api/handoff-seven-folder", methods=["POST"])
def api_handoff_seven_folder():
    """Übergibt markierte Dateien oder einen Ordner an 7-Ordner-Pro (startet es bei Bedarf automatisch)."""
    data = request.get_json(silent=True) or {}
    paths = data.get("paths") or []
    folder_path = data.get("folder_path")
    target_dir = data.get("target_dir")
    theme = data.get("theme")
    res = file_service.send_to_seven_folder(
        paths=paths if isinstance(paths, list) else [],
        folder_path=folder_path,
        target_dir=target_dir,
        theme=theme if theme in ("light", "dark") else None,
    )
    return jsonify(res), (200 if res.get("success") else 400)


@app.route("/api/bridge/theme", methods=["GET", "POST"])
def api_bridge_theme():
    """Liest oder setzt das gemeinsame Hell/Dunkel-Theme fuer beide Apps."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        t = file_service.set_shared_theme(data.get("theme") or "light")
        return jsonify({"success": True, "theme": t})
    return jsonify({"success": True, "theme": file_service.get_shared_theme()})


_BRIDGE_LOCK = threading.Lock()
_ACTIVE_CLIENTS: dict[str, float] = {}
_PENDING_OPEN_QUEUE: list[dict] = []


def _focus_existing_suchmaschine_window() -> bool:
    """Bringt ein bereits offenes Edge-App- oder Browser-Fenster von 'Datei-Suchmaschine Pro' in den Vordergrund."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def _enum_cb(hwnd, _lp):
            if not user32.IsWindowVisible(hwnd):
                return True
            ln = user32.GetWindowTextLengthW(hwnd)
            if ln <= 0:
                return True
            tbuf = ctypes.create_unicode_buffer(ln + 1)
            user32.GetWindowTextW(hwnd, tbuf, ln + 1)
            title = tbuf.value
            if "datei-suchmaschine" in title.lower():
                cbuf = ctypes.create_unicode_buffer(128)
                user32.GetClassNameW(hwnd, cbuf, 128)
                if cbuf.value not in ("CabinetWClass", "ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"):
                    found.append(hwnd)
                    return False
            return True

        user32.EnumWindows(_enum_cb, 0)
        if found:
            hwnd = found[0]
            user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
            user32.SetForegroundWindow(hwnd)
            return True
    except Exception:
        pass
    return False


def _find_msedge_exe() -> str:
    """Sucht Microsoft Edge (msedge.exe) fuer den tabfreien App-Modus."""
    import shutil
    found = shutil.which("msedge") or shutil.which("msedge.exe")
    if found and os.path.isfile(found):
        return found
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return ""


def _resolve_app_icon() -> str:
    """Findet das Embedded-/Projekt-Icon (.ico) fuer das Desktop-Fenster."""
    bases = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            bases.append(meipass)
        bases.append(os.path.dirname(sys.executable))
    bases.append(os.path.dirname(os.path.abspath(__file__)))
    for b in bases:
        for name in ("app_icon.ico", "Suchmaschine.ico"):
            p = os.path.join(b, name)
            if os.path.isfile(p):
                return p
    return ""


def _wait_for_port(port: int, timeout: float = 6.0) -> bool:
    import socket
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
        time.sleep(0.1)
    return False


def _launch_desktop_window(url: str) -> bool:
    """Oeffnet die Datei-Suchmaschine als echtes Windows-Desktop-Fenster (WebView2, 1 Taskleisten-Icon)."""
    if os.name == "nt" and not getattr(sys, "frozen", False):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DateiSuchmaschine.Pro.1")
        except Exception:
            pass
    try:
        import tempfile
        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        storage_dir = os.path.join(
            os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(),
            "DateiSuchmaschinePro",
            "WebView2",
        )
        os.makedirs(storage_dir, exist_ok=True)
        icon_path = _resolve_app_icon() or None
        win = webview.create_window(
            f"Datei-Suchmaschine Pro  {file_service.APP_VERSION}",
            url,
            width=1380,
            height=880,
            min_size=(960, 640),
            maximized=True,
            text_select=True,
            zoomable=True,
            background_color="#f8fafc",
        )

        def _maximize_window(w):
            import time as _time
            try:
                w.maximize()
                _time.sleep(0.15)
                w.maximize()
            except Exception:
                pass

        try:
            win.events.shown += (lambda *_: win.maximize())
        except Exception:
            pass
        webview.start(
            _maximize_window,
            win,
            gui="edgechromium" if os.name == "nt" else None,
            icon=icon_path,
            private_mode=False,
            storage_path=storage_dir,
        )
        return True
    except Exception:
        return False


def _open_suchmaschine_app_window(url: str):
    """Fallback-Fensterstart ueber Edge --app oder Standardbrowser, falls WebView2 nicht startet."""
    import subprocess
    import webbrowser
    edge = _find_msedge_exe() if os.name == "nt" else ""
    if edge:
        try:
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen([edge, f"--app={url}", "--start-maximized"], creationflags=flags)
            return
        except Exception:
            pass
    webbrowser.open(url)


def _activate_running_suchmaschine(port: int, open_path: str = "") -> bool:
    """Prueft ueber Bridge-API und Win32-Fenster, ob bereits ein Fenster offen ist und holt es nach vorn."""
    import json
    import urllib.request
    reused = False
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/bridge/open-in-active",
            data=json.dumps({"path": open_path, "focus": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            body = json.loads(resp.read().decode("utf-8") or "{}")
            reused = bool(body.get("reused_existing"))
    except Exception:
        reused = False
    focused = _focus_existing_suchmaschine_window()
    return reused or focused


@app.route("/api/bridge/poll", methods=["GET"])
def api_bridge_poll():
    """Herzschlag geöffneter Fenster (Edge-App/Browser) + Auslieferung ausstehender Ordner-Aufträge."""
    client_id = (request.args.get("client_id") or "").strip()[:80]
    now = time.monotonic()
    cmd = None
    with _BRIDGE_LOCK:
        for cid in [k for k, ts in _ACTIVE_CLIENTS.items() if now - ts > 8.0]:
            _ACTIVE_CLIENTS.pop(cid, None)
        if client_id:
            _ACTIVE_CLIENTS[client_id] = now
        if _PENDING_OPEN_QUEUE:
            cmd = _PENDING_OPEN_QUEUE.pop(0)
    return jsonify({
        "ok": True,
        "command": cmd,
    })


@app.route("/api/bridge/open-in-active", methods=["POST"])
def api_bridge_open_in_active():
    """Übergibt einen Pfad an eine bereits offene Edge-App-/Browser-Instanz ohne neues Fenster zu öffnen."""
    data = request.get_json(silent=True) or {}
    path = (data.get("path") or "").strip()
    now = time.monotonic()
    with _BRIDGE_LOCK:
        for cid in [k for k, ts in _ACTIVE_CLIENTS.items() if now - ts > 8.0]:
            _ACTIVE_CLIENTS.pop(cid, None)
        active_count = len(_ACTIVE_CLIENTS)
        if active_count > 0:
            _PENDING_OPEN_QUEUE.append({"open_path": path, "focus": True})
    focused = _focus_existing_suchmaschine_window() if active_count > 0 else False
    return jsonify({
        "success": True,
        "reused_existing": active_count > 0,
        "active_clients": active_count,
        "focused": focused,
    })


try:
    file_service.register_suchmaschine_bridge(port=5005)
except Exception:
    pass


if __name__ == "__main__":
    # 1. Behandle 'suchmaschine://' Protokoll-Aufrufe (für Standalone-EXE ohne Python)
    if len(sys.argv) > 1 and sys.argv[1].startswith("suchmaschine://"):
        try:
            import launcher
            launcher.handle_uri(sys.argv[1])
        except Exception:
            pass
        sys.exit(0)

    import socket
    import urllib.parse
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    port = 5005

    open_path_arg = ""
    if "--open-path" in sys.argv:
        p_idx = sys.argv.index("--open-path")
        if p_idx + 1 < len(sys.argv):
            open_path_arg = sys.argv[p_idx + 1].strip()
    start_url = f"http://localhost:{port}/"
    if open_path_arg:
        start_url = f"http://localhost:{port}/?open_path={urllib.parse.quote(open_path_arg)}"

    # 2. Prüfen, ob bereits eine Instanz auf Port 5005 läuft
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_already_running = False
    try:
        s.bind(("127.0.0.1", port))
        s.close()
    except OSError:
        server_already_running = True

    if server_already_running:
        # Server läuft bereits: Bestehende Instanz fokussieren (oder Desktop-Fenster oeffnen, falls Server headless lief)
        if "--no-browser" not in sys.argv:
            try:
                if not _activate_running_suchmaschine(port, open_path=open_path_arg):
                    if not _launch_desktop_window(start_url):
                        _open_suchmaschine_app_window(start_url)
            except Exception:
                pass
        sys.exit(0)

    local_ip = file_service.get_local_ip()
    print(f"Datei-Suchmaschine laeuft auf:")
    print(f"  - Lokal:        http://localhost:{port}")
    print(f"  - iPad / iPhone: http://{local_ip}:{port}")

    if "--no-browser" in sys.argv:
        # Reiner Hintergrundserver-Modus ohne eigenes Fenster
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        # Standard Desktop-App-Modus: Server im Daemon-Thread + eigenes WebView2-Fenster (genau 1 Taskleisten-Icon)
        server_thread = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
            daemon=True,
        )
        server_thread.start()
        _wait_for_port(port, timeout=6.0)
        if not _launch_desktop_window(start_url):
            _open_suchmaschine_app_window(start_url)
            server_thread.join()
