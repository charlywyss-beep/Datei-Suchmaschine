using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.VisualBasic.FileIO;
using Microsoft.Win32;

namespace DokumentenSucheHelfer
{
    static class Program
    {
        const int PORT = 17654;
        const string HOST_URL = "http://127.0.0.1:17654/";
        const string GITHUB_APP_URL = "https://charlywyss-beep.github.io/Datei-Suchmaschine/";
        const string AUTOSTART_KEY = @"Software\Microsoft\Windows\CurrentVersion\Run";
        const string AUTOSTART_NAME = "DokumentenSucheProHelfer";
        const string VERSION = "1.0.0";

        static HttpListener _listener;
        static volatile bool _running = true;
        static NotifyIcon _trayIcon;
        static string _webRoot;
        static readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        static readonly HashSet<string> SKIP_ALWAYS = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "$recycle.bin", "system volume information", "$windows.~bt", "$windows.~ws",
            "node_modules", ".git", ".vs", "__pycache__", ".venv", "venv"
        };

        static readonly HashSet<string> SKIP_DRIVE_ROOT = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "windows", "windows.old", "program files", "program files (x86)", "programdata",
            "recovery", "perflogs", "config.msi", "msocache", "appdata", "intel", "amd",
            "drivers", "boot", "efi", "onedrivetemp", "found.000", "found.001", "found.002"
        };

        static readonly Dictionary<string, string> GERMAN_TO_EN = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "dokumente", "Documents" },
            { "bilder", "Pictures" },
            { "musik", "Music" },
            { "benutzer", "Users" },
            { "favoriten", "Favorites" },
            { "kontakte", "Contacts" },
            { "gespeicherte spiele", "Saved Games" },
            { "suchvorgänge", "Searches" }
        };

        [STAThread]
        static void Main(string[] args)
        {
            bool isAutostart = false;
            bool noBrowser = false;
            foreach (string a in args)
            {
                if (string.Equals(a, "--autostart", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(a, "--silent", StringComparison.OrdinalIgnoreCase))
                    isAutostart = true;
                if (string.Equals(a, "--no-browser", StringComparison.OrdinalIgnoreCase))
                    noBrowser = true;
            }

            bool createdNew;
            using (Mutex mutex = new Mutex(true, @"Local\DokumentenSuchePro_Helfer_v1", out createdNew))
            {
                if (!createdNew)
                {
                    if (!isAutostart && !noBrowser) OpenAppInBrowser();
                    return;
                }

                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);

                _webRoot = ResolveWebRoot();

                if (!StartHttpServer())
                {
                    MessageBox.Show(
                        "Der lokale Hilfsdienst konnte auf Port " + PORT + " nicht gestartet werden.\nMöglicherweise läuft er bereits oder der Port ist belegt.",
                        "Dokumenten-Suche Pro – Helfer",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                    return;
                }

                SetupTrayIcon();

                if (!isAutostart && !noBrowser)
                {
                    OpenAppInBrowser();
                }

                Application.Run();
                StopHttpServer();
            }
        }

        static string ResolveWebRoot()
        {
            try
            {
                string exeDir = AppDomain.CurrentDomain.BaseDirectory;
                string[] candidates = new[]
                {
                    Path.Combine(exeDir, "docs"),
                    exeDir,
                    Path.GetFullPath(Path.Combine(exeDir, "..", "docs")),
                    Path.GetFullPath(Path.Combine(exeDir, ".."))
                };
                foreach (string dir in candidates)
                {
                    if (Directory.Exists(dir) &&
                        (File.Exists(Path.Combine(dir, "index.html")) || File.Exists(Path.Combine(dir, "PDF-Suche-Web.html"))))
                    {
                        return dir;
                    }
                }
            }
            catch { }
            return null;
        }

        static void OpenAppInBrowser()
        {
            try
            {
                string url = !string.IsNullOrEmpty(_webRoot) ? HOST_URL : GITHUB_APP_URL;
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch { }
        }

        static Icon CreateFluentIcon()
        {
            using (Bitmap bmp = new Bitmap(32, 32))
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.Clear(Color.Transparent);
                using (GraphicsPath path = RoundedRect(new Rectangle(2, 2, 28, 28), 7))
                using (SolidBrush bg = new SolidBrush(Color.FromArgb(37, 99, 235)))
                {
                    g.FillPath(bg, path);
                }
                using (Pen p = new Pen(Color.White, 2.6f))
                {
                    p.StartCap = LineCap.Round;
                    p.EndCap = LineCap.Round;
                    g.DrawEllipse(p, 8, 8, 11, 11);
                    g.DrawLine(p, 17.5f, 17.5f, 23.5f, 23.5f);
                }
                IntPtr hIcon = bmp.GetHicon();
                return Icon.FromHandle(hIcon);
            }
        }

        static GraphicsPath RoundedRect(Rectangle bounds, int radius)
        {
            int d = radius * 2;
            GraphicsPath path = new GraphicsPath();
            path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
            path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
            path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
            path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        static bool IsAutostartEnabled()
        {
            try
            {
                using (RegistryKey key = Registry.CurrentUser.OpenSubKey(AUTOSTART_KEY, false))
                {
                    if (key == null) return false;
                    object val = key.GetValue(AUTOSTART_NAME);
                    return val != null && !string.IsNullOrEmpty(val.ToString());
                }
            }
            catch { return false; }
        }

        static void SetAutostart(bool enable)
        {
            try
            {
                using (RegistryKey key = Registry.CurrentUser.CreateSubKey(AUTOSTART_KEY))
                {
                    if (key == null) return;
                    if (enable)
                    {
                        string exe = Process.GetCurrentProcess().MainModule.FileName;
                        key.SetValue(AUTOSTART_NAME, "\"" + exe + "\" --autostart");
                    }
                    else
                    {
                        key.DeleteValue(AUTOSTART_NAME, false);
                    }
                }
            }
            catch { }
        }

        static void SetupTrayIcon()
        {
            ContextMenuStrip menu = new ContextMenuStrip();

            ToolStripMenuItem openItem = new ToolStripMenuItem("Dokumenten-Suche Pro öffnen");
            openItem.Font = new Font(openItem.Font, FontStyle.Bold);
            openItem.Click += (s, e) => OpenAppInBrowser();
            menu.Items.Add(openItem);

            ToolStripMenuItem autoItem = new ToolStripMenuItem("Mit Windows starten");
            autoItem.CheckOnClick = true;
            autoItem.Checked = IsAutostartEnabled();
            autoItem.Click += (s, e) => SetAutostart(autoItem.Checked);
            menu.Items.Add(autoItem);

            menu.Items.Add(new ToolStripSeparator());

            ToolStripMenuItem exitItem = new ToolStripMenuItem("Helfer beenden");
            exitItem.Click += (s, e) =>
            {
                if (_trayIcon != null) _trayIcon.Visible = false;
                Application.Exit();
            };
            menu.Items.Add(exitItem);

            _trayIcon = new NotifyIcon
            {
                Icon = CreateFluentIcon(),
                Text = "Dokumenten-Suche Pro – Windows-Helfer (aktiv)",
                ContextMenuStrip = menu,
                Visible = true
            };
            _trayIcon.DoubleClick += (s, e) => OpenAppInBrowser();
        }

        static bool StartHttpServer()
        {
            try
            {
                _listener = new HttpListener();
                _listener.Prefixes.Add(HOST_URL);
                _listener.Start();

                Thread worker = new Thread(ListenLoop) { IsBackground = true };
                worker.Start();
                return true;
            }
            catch
            {
                return false;
            }
        }

        static void StopHttpServer()
        {
            _running = false;
            try { if (_listener != null) _listener.Stop(); } catch { }
            try { if (_listener != null) _listener.Close(); } catch { }
            try { if (_trayIcon != null) _trayIcon.Dispose(); } catch { }
        }

        static void ListenLoop()
        {
            while (_running && _listener != null && _listener.IsListening)
            {
                try
                {
                    HttpListenerContext ctx = _listener.GetContext();
                    ThreadPool.QueueUserWorkItem(_ => HandleRequest(ctx));
                }
                catch
                {
                    if (!_running) break;
                }
            }
        }

        static bool IsAllowedOrigin(string origin)
        {
            if (string.IsNullOrEmpty(origin)) return true;
            if (origin == "null") return true;
            if (origin.Equals("https://charlywyss-beep.github.io", StringComparison.OrdinalIgnoreCase)) return true;
            if (origin.Equals("http://127.0.0.1:" + PORT, StringComparison.OrdinalIgnoreCase)) return true;
            if (origin.Equals("http://localhost:" + PORT, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        static void ApplyCors(HttpListenerRequest req, HttpListenerResponse res)
        {
            string origin = req.Headers["Origin"];
            if (!string.IsNullOrEmpty(origin) && IsAllowedOrigin(origin))
            {
                res.Headers["Access-Control-Allow-Origin"] = origin;
                res.Headers["Vary"] = "Origin";
            }
            res.Headers["Access-Control-Allow-Private-Network"] = "true";
            res.Headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS";
            res.Headers["Access-Control-Allow-Headers"] = "Content-Type";
        }

        static void HandleRequest(HttpListenerContext ctx)
        {
            HttpListenerRequest req = ctx.Request;
            HttpListenerResponse res = ctx.Response;
            try
            {
                string origin = req.Headers["Origin"];
                if (!IsAllowedOrigin(origin))
                {
                    res.StatusCode = 403;
                    res.Close();
                    return;
                }

                ApplyCors(req, res);

                if (req.HttpMethod == "OPTIONS")
                {
                    res.StatusCode = 204;
                    res.Close();
                    return;
                }

                string path = req.Url.AbsolutePath ?? "/";

                if (path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase))
                {
                    res.Headers["Cache-Control"] = "no-store";
                    RouteApi(path.ToLowerInvariant(), req, res);
                    return;
                }

                ServeStaticFile(path, res);
            }
            catch (Exception ex)
            {
                try
                {
                    WriteJson(res, 500, "{\"ok\":false,\"error\":" + JsonEscape(ex.Message) + "}");
                }
                catch { }
            }
            finally
            {
                try { res.OutputStream.Close(); } catch { }
            }
        }

        static void RouteApi(string path, HttpListenerRequest req, HttpListenerResponse res)
        {
            switch (path)
            {
                case "/api/ping":
                    HandlePing(res);
                    break;
                case "/api/pick-folder":
                    HandlePickFolder(req, res);
                    break;
                case "/api/scan":
                    HandleScan(req, res);
                    break;
                case "/api/file":
                    HandleStreamFile(req, res);
                    break;
                case "/api/rename":
                    HandleRename(req, res);
                    break;
                case "/api/delete":
                    HandleDelete(req, res);
                    break;
                case "/api/explorer":
                    HandleExplorer(req, res);
                    break;
                default:
                    WriteJson(res, 404, "{\"ok\":false,\"error\":\"Unbekannter Endpunkt\"}");
                    break;
            }
        }

        static void HandlePing(HttpListenerResponse res)
        {
            List<string> drives = new List<string>();
            try
            {
                foreach (DriveInfo d in DriveInfo.GetDrives())
                {
                    if (d.IsReady)
                    {
                        drives.Add(d.Name.TrimEnd('\\').ToUpperInvariant());
                    }
                }
            }
            catch { }

            string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            string docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string downloads = Path.Combine(userProfile, "Downloads");
            string pictures = Environment.GetFolderPath(Environment.SpecialFolder.MyPictures);

            StringBuilder sb = new StringBuilder(512);
            sb.Append("{\"ok\":true,\"version\":").Append(JsonEscape(VERSION));
            sb.Append(",\"hasLocalWeb\":").Append(!string.IsNullOrEmpty(_webRoot) ? "true" : "false");
            sb.Append(",\"drives\":[");
            for (int i = 0; i < drives.Count; i++)
            {
                if (i > 0) sb.Append(',');
                sb.Append(JsonEscape(drives[i]));
            }
            sb.Append("],\"specialFolders\":{");
            sb.Append("\"documents\":").Append(JsonEscape(docs));
            sb.Append(",\"desktop\":").Append(JsonEscape(desktop));
            sb.Append(",\"downloads\":").Append(JsonEscape(Directory.Exists(downloads) ? downloads : ""));
            sb.Append(",\"pictures\":").Append(JsonEscape(pictures));
            sb.Append("}}");

            WriteJson(res, 200, sb.ToString());
        }

        static void HandlePickFolder(HttpListenerRequest req, HttpListenerResponse res)
        {
            string initial = GetQueryParam(req.Url.Query, "initial") ?? "";
            string title = GetQueryParam(req.Url.Query, "title") ?? "Ordner für Dokumenten-Suche Pro auswählen";
            string selected = null;
            Exception err = null;

            Thread sta = new Thread(() =>
            {
                try
                {
                    selected = ShowModernFolderDialog(title, initial);
                }
                catch (Exception ex)
                {
                    err = ex;
                }
            });
            sta.SetApartmentState(ApartmentState.STA);
            sta.Start();
            sta.Join();

            if (err != null)
            {
                WriteJson(res, 500, "{\"ok\":false,\"error\":" + JsonEscape(err.Message) + "}");
                return;
            }
            if (string.IsNullOrEmpty(selected))
            {
                WriteJson(res, 200, "{\"ok\":false,\"cancelled\":true}");
                return;
            }
            WriteJson(res, 200, "{\"ok\":true,\"path\":" + JsonEscape(selected) + "}");
        }

        static string ShowModernFolderDialog(string title, string initialDir)
        {
            using (Form owner = new Form())
            {
                owner.TopMost = true;
                owner.ShowInTaskbar = false;
                owner.FormBorderStyle = FormBorderStyle.None;
                owner.StartPosition = FormStartPosition.Manual;
                owner.Location = new Point(-32000, -32000);
                owner.Size = new Size(1, 1);
                owner.Show();
                owner.Activate();

                try
                {
                    return VistaFolderPicker.ShowDialog(owner.Handle, title, initialDir);
                }
                catch
                {
                    using (FolderBrowserDialog fbd = new FolderBrowserDialog())
                    {
                        fbd.Description = title;
                        fbd.ShowNewFolderButton = false;
                        if (!string.IsNullOrEmpty(initialDir) && Directory.Exists(initialDir))
                            fbd.SelectedPath = initialDir;
                        if (fbd.ShowDialog(owner) == DialogResult.OK)
                            return fbd.SelectedPath;
                        return null;
                    }
                }
            }
        }

        static void HandleScan(HttpListenerRequest req, HttpListenerResponse res)
        {
            string rawPath = GetQueryParam(req.Url.Query, "path") ?? "";
            string target = ResolveWindowsPath(rawPath);
            if (string.IsNullOrEmpty(target) || !Directory.Exists(target))
            {
                WriteJson(res, 404, "{\"ok\":false,\"error\":\"Ordner nicht gefunden: " + rawPath.Replace("\"", "'") + "\"}");
                return;
            }

            // Normalize drive root e.g. "D:" -> "D:\"
            if (target.Length == 2 && target[1] == ':') target += "\\";
            bool isDriveRoot = (target.Length == 3 && target[1] == ':' && target[2] == '\\');
            string rootClean = isDriveRoot ? target : target.TrimEnd('\\');
            string rootName = isDriveRoot ? target.Substring(0, 2).ToUpperInvariant() : Path.GetFileName(rootClean);

            StringBuilder filesJson = new StringBuilder(65536);
            StringBuilder dirsJson = new StringBuilder(16384);
            filesJson.Append('[');
            dirsJson.Append('[');
            bool firstFile = true;
            bool firstDir = true;
            int fileCount = 0;

            Stack<KeyValuePair<string, string>> stack = new Stack<KeyValuePair<string, string>>();
            stack.Push(new KeyValuePair<string, string>(rootClean, ""));

            DateTime epoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);

            while (stack.Count > 0)
            {
                KeyValuePair<string, string> cur = stack.Pop();
                string curFull = cur.Key;
                string curRel = cur.Value;

                DirectoryInfo di;
                try { di = new DirectoryInfo(curFull); }
                catch { continue; }

                IEnumerable<FileSystemInfo> entries;
                try { entries = di.EnumerateFileSystemInfos(); }
                catch { continue; }

                foreach (FileSystemInfo fsi in entries)
                {
                    try
                    {
                        string name = fsi.Name;
                        if (string.IsNullOrEmpty(name)) continue;

                        if ((fsi.Attributes & FileAttributes.Directory) != 0)
                        {
                            // Skip junctions / symlinks to avoid infinite loops in C:\Users
                            if ((fsi.Attributes & FileAttributes.ReparsePoint) != 0) continue;
                            if (name.StartsWith("$")) continue;
                            if (SKIP_ALWAYS.Contains(name)) continue;
                            if (isDriveRoot && string.IsNullOrEmpty(curRel) && SKIP_DRIVE_ROOT.Contains(name)) continue;

                            string subRel = string.IsNullOrEmpty(curRel) ? name : (curRel + "\\" + name);
                            if (!firstDir) dirsJson.Append(',');
                            firstDir = false;
                            dirsJson.Append(JsonEscape(subRel));
                            stack.Push(new KeyValuePair<string, string>(fsi.FullName, subRel));
                        }
                        else
                        {
                            if (name.StartsWith("~$") || name.Equals("desktop.ini", StringComparison.OrdinalIgnoreCase) ||
                                name.Equals("thumbs.db", StringComparison.OrdinalIgnoreCase))
                                continue;

                            FileInfo fi = fsi as FileInfo;
                            long size = fi != null ? fi.Length : 0;
                            long mtime = 0;
                            try
                            {
                                mtime = (long)(fsi.LastWriteTimeUtc - epoch).TotalMilliseconds;
                                if (mtime < 0) mtime = 0;
                            }
                            catch { }

                            if (!firstFile) filesJson.Append(',');
                            firstFile = false;
                            filesJson.Append("{\"name\":").Append(JsonEscape(name))
                                     .Append(",\"dir\":").Append(JsonEscape(curRel))
                                     .Append(",\"fullPath\":").Append(JsonEscape(fsi.FullName))
                                     .Append(",\"size\":").Append(size)
                                     .Append(",\"mtime\":").Append(mtime)
                                     .Append('}');
                            fileCount++;
                        }
                    }
                    catch { }
                }
            }

            filesJson.Append(']');
            dirsJson.Append(']');

            StringBuilder outJson = new StringBuilder(filesJson.Length + dirsJson.Length + 256);
            outJson.Append("{\"ok\":true,\"rootPath\":").Append(JsonEscape(rootClean))
                   .Append(",\"rootName\":").Append(JsonEscape(rootName))
                   .Append(",\"count\":").Append(fileCount)
                   .Append(",\"files\":").Append(filesJson)
                   .Append(",\"dirs\":").Append(dirsJson)
                   .Append('}');

            WriteJson(res, 200, outJson.ToString());
        }

        static void HandleStreamFile(HttpListenerRequest req, HttpListenerResponse res)
        {
            string rawPath = GetQueryParam(req.Url.Query, "path") ?? "";
            string target = ResolveWindowsPath(rawPath);
            if (string.IsNullOrEmpty(target) || !File.Exists(target))
            {
                res.StatusCode = 404;
                return;
            }

            string mime = GetMimeType(Path.GetExtension(target));
            res.ContentType = mime;
            res.Headers["Accept-Ranges"] = "bytes";

            using (FileStream fs = new FileStream(target, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                long total = fs.Length;
                long start = 0;
                long end = total - 1;
                bool isRange = false;

                string rangeHeader = req.Headers["Range"];
                if (!string.IsNullOrEmpty(rangeHeader) && rangeHeader.StartsWith("bytes=", StringComparison.OrdinalIgnoreCase) && total > 0)
                {
                    string[] parts = rangeHeader.Substring(6).Split('-');
                    long parsedStart;
                    if (long.TryParse(parts[0], out parsedStart))
                    {
                        start = Math.Max(0, Math.Min(parsedStart, total - 1));
                        long parsedEnd;
                        if (parts.Length > 1 && long.TryParse(parts[1], out parsedEnd))
                            end = Math.Max(start, Math.Min(parsedEnd, total - 1));
                        isRange = true;
                    }
                }

                long length = total == 0 ? 0 : (end - start + 1);
                if (isRange)
                {
                    res.StatusCode = 206;
                    res.Headers["Content-Range"] = "bytes " + start + "-" + end + "/" + total;
                }
                else
                {
                    res.StatusCode = 200;
                }
                res.ContentLength64 = length;

                if (length > 0)
                {
                    fs.Seek(start, SeekOrigin.Begin);
                    byte[] buffer = new byte[65536];
                    long remaining = length;
                    while (remaining > 0)
                    {
                        int toRead = (int)Math.Min(buffer.Length, remaining);
                        int read = fs.Read(buffer, 0, toRead);
                        if (read <= 0) break;
                        res.OutputStream.Write(buffer, 0, read);
                        remaining -= read;
                    }
                }
            }
        }

        static void HandleRename(HttpListenerRequest req, HttpListenerResponse res)
        {
            Dictionary<string, object> body = ReadJsonBody(req);
            string oldPath = ResolveWindowsPath(GetDictString(body, "path"));
            string newName = (GetDictString(body, "newName") ?? "").Trim();

            if (string.IsNullOrEmpty(oldPath) || string.IsNullOrEmpty(newName))
            {
                WriteJson(res, 400, "{\"ok\":false,\"error\":\"Pfad oder neuer Name fehlt\"}");
                return;
            }
            if (newName.IndexOfAny(new[] { '\\', '/', ':', '*', '?', '"', '<', '>', '|' }) >= 0)
            {
                WriteJson(res, 400, "{\"ok\":false,\"error\":\"Ungültige Zeichen im Dateinamen\"}");
                return;
            }

            string dir = Path.GetDirectoryName(oldPath);
            string newPath = Path.Combine(dir, newName);

            if (string.Equals(oldPath, newPath, StringComparison.OrdinalIgnoreCase))
            {
                if (oldPath != newPath)
                {
                    string tmp = oldPath + ".__tmp_case_" + Guid.NewGuid().ToString("N").Substring(0, 6);
                    if (File.Exists(oldPath)) { File.Move(oldPath, tmp); File.Move(tmp, newPath); }
                    else if (Directory.Exists(oldPath)) { Directory.Move(oldPath, tmp); Directory.Move(tmp, newPath); }
                }
                WriteJson(res, 200, "{\"ok\":true,\"newPath\":" + JsonEscape(newPath) + "}");
                return;
            }

            if (File.Exists(newPath) || Directory.Exists(newPath))
            {
                WriteJson(res, 409, "{\"ok\":false,\"error\":\"Eine Datei mit diesem Namen existiert bereits\"}");
                return;
            }

            if (File.Exists(oldPath))
            {
                File.Move(oldPath, newPath);
            }
            else if (Directory.Exists(oldPath))
            {
                Directory.Move(oldPath, newPath);
            }
            else
            {
                WriteJson(res, 404, "{\"ok\":false,\"error\":\"Datei nicht gefunden\"}");
                return;
            }

            WriteJson(res, 200, "{\"ok\":true,\"newPath\":" + JsonEscape(newPath) + "}");
        }

        static void HandleDelete(HttpListenerRequest req, HttpListenerResponse res)
        {
            Dictionary<string, object> body = ReadJsonBody(req);
            string target = ResolveWindowsPath(GetDictString(body, "path"));
            if (string.IsNullOrEmpty(target))
            {
                WriteJson(res, 400, "{\"ok\":false,\"error\":\"Pfad fehlt\"}");
                return;
            }

            if (File.Exists(target))
            {
                FileSystem.DeleteFile(target, UIOption.OnlyErrorDialogs, RecycleOption.SendToRecycleBin);
                WriteJson(res, 200, "{\"ok\":true,\"recycled\":true}");
            }
            else if (Directory.Exists(target))
            {
                FileSystem.DeleteDirectory(target, UIOption.OnlyErrorDialogs, RecycleOption.SendToRecycleBin);
                WriteJson(res, 200, "{\"ok\":true,\"recycled\":true}");
            }
            else
            {
                WriteJson(res, 404, "{\"ok\":false,\"error\":\"Datei oder Ordner nicht gefunden\"}");
            }
        }

        static void HandleExplorer(HttpListenerRequest req, HttpListenerResponse res)
        {
            Dictionary<string, object> body = ReadJsonBody(req);
            string rawPath = GetDictString(body, "path");
            string target = ResolveWindowsPath(rawPath);

            if (string.IsNullOrEmpty(target))
            {
                WriteJson(res, 400, "{\"ok\":false,\"error\":\"Pfad fehlt\"}");
                return;
            }

            if (File.Exists(target))
            {
                Process.Start("explorer.exe", "/select,\"" + target + "\"");
                WriteJson(res, 200, "{\"ok\":true,\"opened\":" + JsonEscape(target) + "}");
                return;
            }
            if (Directory.Exists(target))
            {
                Process.Start("explorer.exe", "\"" + target + "\"");
                WriteJson(res, 200, "{\"ok\":true,\"opened\":" + JsonEscape(target) + "}");
                return;
            }

            // Fallback: open nearest existing parent folder
            string parent = target;
            while (!string.IsNullOrEmpty(parent))
            {
                parent = Path.GetDirectoryName(parent);
                if (!string.IsNullOrEmpty(parent) && Directory.Exists(parent))
                {
                    Process.Start("explorer.exe", "\"" + parent + "\"");
                    WriteJson(res, 200, "{\"ok\":true,\"opened\":" + JsonEscape(parent) + "}");
                    return;
                }
            }

            WriteJson(res, 404, "{\"ok\":false,\"error\":\"Pfad nicht gefunden\"}");
        }

        static void ServeStaticFile(string reqPath, HttpListenerResponse res)
        {
            if (string.IsNullOrEmpty(_webRoot))
            {
                res.StatusCode = 302;
                res.RedirectLocation = GITHUB_APP_URL;
                return;
            }

            string rel = Uri.UnescapeDataString((reqPath ?? "/").TrimStart('/')).Replace('/', '\\');
            if (string.IsNullOrEmpty(rel))
            {
                rel = File.Exists(Path.Combine(_webRoot, "index.html")) ? "index.html" : "PDF-Suche-Web.html";
            }

            string full = Path.GetFullPath(Path.Combine(_webRoot, rel));
            string rootFull = Path.GetFullPath(_webRoot);
            if (!full.StartsWith(rootFull, StringComparison.OrdinalIgnoreCase) || !File.Exists(full))
            {
                res.StatusCode = 404;
                return;
            }

            byte[] data = File.ReadAllBytes(full);
            res.ContentType = GetMimeType(Path.GetExtension(full));
            res.ContentLength64 = data.Length;
            res.OutputStream.Write(data, 0, data.Length);
        }

        static string ResolveWindowsPath(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw)) return "";
            string p = raw.Trim().Trim('"').Replace('/', '\\');
            if (p.Length == 2 && p[1] == ':') p += "\\";
            if (File.Exists(p) || Directory.Exists(p)) return p;

            // Translate German Explorer labels (Dokumente -> Documents, Benutzer -> Users, ...)
            string[] segs = p.Split('\\');
            bool changed = false;
            for (int i = 0; i < segs.Length; i++)
            {
                string mapped;
                if (GERMAN_TO_EN.TryGetValue(segs[i], out mapped))
                {
                    segs[i] = mapped;
                    changed = true;
                }
            }
            if (changed)
            {
                string alt = string.Join("\\", segs);
                if (File.Exists(alt) || Directory.Exists(alt)) return alt;
            }
            return p;
        }

        static Dictionary<string, object> ReadJsonBody(HttpListenerRequest req)
        {
            using (StreamReader sr = new StreamReader(req.InputStream, req.ContentEncoding ?? Encoding.UTF8))
            {
                string raw = sr.ReadToEnd();
                if (string.IsNullOrWhiteSpace(raw)) return new Dictionary<string, object>();
                return _json.Deserialize<Dictionary<string, object>>(raw) ?? new Dictionary<string, object>();
            }
        }

        static string GetDictString(Dictionary<string, object> dict, string key)
        {
            object v;
            if (dict != null && dict.TryGetValue(key, out v) && v != null) return v.ToString();
            return "";
        }

        static string GetQueryParam(string query, string key)
        {
            if (string.IsNullOrEmpty(query)) return null;
            string q = query.TrimStart('?');
            foreach (string pair in q.Split('&'))
            {
                int eq = pair.IndexOf('=');
                if (eq < 0) continue;
                string k = Uri.UnescapeDataString(pair.Substring(0, eq).Replace('+', ' '));
                if (string.Equals(k, key, StringComparison.OrdinalIgnoreCase))
                {
                    return Uri.UnescapeDataString(pair.Substring(eq + 1).Replace('+', ' '));
                }
            }
            return null;
        }

        static void WriteJson(HttpListenerResponse res, int status, string json)
        {
            byte[] buf = Encoding.UTF8.GetBytes(json);
            res.StatusCode = status;
            res.ContentType = "application/json; charset=utf-8";
            res.ContentLength64 = buf.Length;
            res.OutputStream.Write(buf, 0, buf.Length);
        }

        static string JsonEscape(string s)
        {
            if (s == null) return "\"\"";
            StringBuilder sb = new StringBuilder(s.Length + 4);
            sb.Append('"');
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 32) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
            return sb.ToString();
        }

        static string GetMimeType(string ext)
        {
            switch ((ext ?? "").ToLowerInvariant())
            {
                case ".html": case ".htm": return "text/html; charset=utf-8";
                case ".js": case ".mjs": return "application/javascript; charset=utf-8";
                case ".css": return "text/css; charset=utf-8";
                case ".json": return "application/json; charset=utf-8";
                case ".pdf": return "application/pdf";
                case ".png": return "image/png";
                case ".jpg": case ".jpeg": return "image/jpeg";
                case ".gif": return "image/gif";
                case ".webp": return "image/webp";
                case ".svg": return "image/svg+xml";
                case ".bmp": return "image/bmp";
                case ".ico": return "image/x-icon";
                case ".mp4": case ".m4v": return "video/mp4";
                case ".webm": return "video/webm";
                case ".mkv": return "video/x-matroska";
                case ".mov": return "video/quicktime";
                case ".avi": return "video/x-msvideo";
                case ".txt": case ".log": case ".md": case ".csv": case ".ini": return "text/plain; charset=utf-8";
                case ".xml": return "application/xml; charset=utf-8";
                case ".docx": return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
                case ".xlsx": return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
                case ".pptx": return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
                default: return "application/octet-stream";
            }
        }
    }

    // Modern Windows 10/11 IFileOpenDialog Folder Picker (no external NuGet needed)
    static class VistaFolderPicker
    {
        const uint FOS_PICKFOLDERS = 0x00000020;
        const uint FOS_FORCEFILESYSTEM = 0x00000040;
        const uint FOS_PATHMUSTEXIST = 0x00000800;
        const uint SIGDN_FILESYSPATH = 0x80058000;

        public static string ShowDialog(IntPtr hwndOwner, string title, string initialDir)
        {
            IFileOpenDialog dialog = (IFileOpenDialog)new FileOpenDialogRCW();
            try
            {
                uint opts;
                dialog.GetOptions(out opts);
                dialog.SetOptions(opts | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
                if (!string.IsNullOrEmpty(title)) dialog.SetTitle(title);

                if (!string.IsNullOrEmpty(initialDir) && Directory.Exists(initialDir))
                {
                    IShellItem item;
                    Guid riid = typeof(IShellItem).GUID;
                    if (SHCreateItemFromParsingName(initialDir, IntPtr.Zero, ref riid, out item) == 0 && item != null)
                    {
                        dialog.SetFolder(item);
                        Marshal.ReleaseComObject(item);
                    }
                }

                int hr = dialog.Show(hwndOwner);
                if (hr != 0) return null;

                IShellItem result;
                dialog.GetResult(out result);
                if (result == null) return null;
                try
                {
                    string path;
                    result.GetDisplayName(SIGDN_FILESYSPATH, out path);
                    return path;
                }
                finally
                {
                    Marshal.ReleaseComObject(result);
                }
            }
            finally
            {
                Marshal.ReleaseComObject(dialog);
            }
        }

        [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = true)]
        static extern int SHCreateItemFromParsingName(
            [MarshalAs(UnmanagedType.LPWStr)] string pszPath,
            IntPtr pbc,
            ref Guid riid,
            [MarshalAs(UnmanagedType.Interface)] out IShellItem ppv);

        [ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")]
        class FileOpenDialogRCW { }

        [ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IFileOpenDialog
        {
            [PreserveSig] int Show(IntPtr parent);
            void SetFileTypes(uint cFileTypes, IntPtr rgFilterSpec);
            void SetFileTypeIndex(uint iFileType);
            void GetFileTypeIndex(out uint piFileType);
            void Advise(IntPtr pfde, out uint pdwCookie);
            void Unadvise(uint dwCookie);
            void SetOptions(uint fos);
            void GetOptions(out uint pfos);
            void SetDefaultFolder(IShellItem psi);
            void SetFolder(IShellItem psi);
            void GetFolder(out IShellItem ppsi);
            void GetCurrentSelection(out IShellItem ppsi);
            void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
            void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
            void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
            void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
            void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
            void GetResult(out IShellItem ppsi);
            void AddPlace(IShellItem psi, int alignment);
            void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string pszDefaultExtension);
            void Close(int hr);
            void SetClientGuid(ref Guid guid);
            void ClearClientData();
            void SetFilter(IntPtr pFilter);
            void GetResults(out IntPtr ppenum);
            void GetSelectedItems(out IntPtr ppsai);
        }

        [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        interface IShellItem
        {
            void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
            void GetParent(out IShellItem ppsi);
            void GetDisplayName(uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
            void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
            void Compare(IShellItem psi, uint hint, out int piOrder);
        }
    }
}
