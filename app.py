import os
import sys
import mimetypes
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, abort

import file_service

app = Flask(__name__)
# Max upload/request size
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/system-info", methods=["GET"])
def system_info():
    locations = file_service.get_system_locations()
    od_info = file_service.detect_onedrive_paths()
    local_ip = file_service.get_local_ip()
    git_info = file_service.get_git_info()
    saved_paths = file_service.get_saved_paths()
    
    return jsonify({
        "app_version": file_service.APP_VERSION,
        "local_ip": local_ip,
        "network_url": f"http://{local_ip}:5005",
        "onedrive_info": od_info,
        "git_info": git_info,
        "saved_paths": saved_paths,
        "locations": locations
    })

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

@app.route("/api/save-onedrive-paths", methods=["POST"])
def save_onedrive_paths():
    data = request.get_json() or {}
    cfg = file_service.load_config()
    if "personal" in data:
        cfg["onedrive_personal"] = data["personal"]
    if "business" in data:
        cfg["onedrive_business"] = data["business"]
    file_service.save_config(cfg)
    return jsonify({"success": True, "onedrive_info": file_service.detect_onedrive_paths()})

@app.route("/api/git-info", methods=["GET"])
def git_info_route():
    return jsonify(file_service.get_git_info())

@app.route("/api/git-update", methods=["POST"])
def git_update_route():
    res = file_service.git_pull_update()
    return jsonify(res)

@app.route("/api/git-set-remote", methods=["POST"])
def git_set_remote_route():
    data = request.get_json() or {}
    remote_url = data.get("remote_url", "")
    if not remote_url:
        return jsonify({"error": "Remote URL fehlt"}), 400
    res = file_service.git_set_remote(remote_url)
    return jsonify(res)

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
    directory = data.get("directory", file_service.ONEDRIVE_PATH or "C:\\")
    query = data.get("query", "")
    category = data.get("category", "all")
    custom_exts = data.get("extensions", "")
    only_onedrive = data.get("only_onedrive", False)
    
    # Parse sizes
    min_size_mb = data.get("min_size_mb")
    max_size_mb = data.get("max_size_mb")
    min_bytes = int(float(min_size_mb) * 1024 * 1024) if min_size_mb not in (None, "") else None
    max_bytes = int(float(max_size_mb) * 1024 * 1024) if max_size_mb not in (None, "") else None

    # Date filter
    modified_after = data.get("modified_after")
    modified_before = data.get("modified_before")
    mod_after_ts = None
    mod_before_ts = None
    if modified_after:
        try:
            from datetime import datetime
            mod_after_ts = datetime.fromisoformat(modified_after).timestamp()
        except Exception:
            pass
    if modified_before:
        try:
            from datetime import datetime
            mod_before_ts = datetime.fromisoformat(modified_before).timestamp()
        except Exception:
            pass

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

    return jsonify({
        "count": len(results),
        "total_bytes": total_bytes,
        "total_size_formatted": file_service.format_size(total_bytes),
        "elapsed_seconds": elapsed,
        "results": results
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

@app.route("/api/send-email", methods=["POST"])
def send_email_route():
    data = request.get_json() or {}
    path = data.get("path")
    recipient = data.get("recipient", "")
    if not path:
        return jsonify({"error": "Pfad fehlt"}), 400
    res = file_service.send_file_via_email(path, recipient)
    return jsonify(res)

@app.route("/api/file-preview", methods=["GET"])
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

if __name__ == "__main__":
    import webbrowser
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    port = 5005
    local_ip = file_service.get_local_ip()
    print(f"Datei-Suchmaschine laeuft auf:")
    print(f"  - Lokal:        http://localhost:{port}")
    print(f"  - iPad / iPhone: http://{local_ip}:{port}")
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass
    # Auf 0.0.0.0 lauschen für Zugriff von iPad, iPhone & Heim/Geschäftsnetzwerk
    app.run(host="0.0.0.0", port=port, debug=False)
