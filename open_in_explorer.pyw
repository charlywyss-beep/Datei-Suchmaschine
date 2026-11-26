import os
import re
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlparse

GERMAN_TO_WIN = {
    'benutzer': 'Users',
    'dokumente': 'Documents',
    'bilder': 'Pictures',
    'musik': 'Music',
    'öffentlich': 'Public',
    'oeffentlich': 'Public',
    'favoriten': 'Favorites',
    'kontakte': 'Contacts',
}

WIN_TO_GERMAN = {v.lower(): k.capitalize() for k, v in GERMAN_TO_WIN.items() if k != 'oeffentlich'}


def resolve_windows_path(raw_path: str) -> str:
    p = os.path.normpath((raw_path or '').strip().strip('"'))
    if not p:
        return ''
    if not re.match(r'^[a-zA-Z]:\\|^\\\\', p):
        return ''
    if os.path.exists(p):
        return p

    # Segmentweise aufloesen (z. B. Dokumente <-> Documents, Benutzer <-> Users)
    m = re.match(r'^([a-zA-Z]:\\)(.*)$', p)
    if not m:
        return p
    cur = m.group(1)
    rest = [s for s in m.group(2).split('\\') if s]
    for seg in rest:
        cand = os.path.join(cur, seg)
        if os.path.exists(cand):
            cur = cand
            continue
        low = seg.lower()
        alt = GERMAN_TO_WIN.get(low) or WIN_TO_GERMAN.get(low)
        if alt:
            alt_cand = os.path.join(cur, alt)
            if os.path.exists(alt_cand):
                cur = alt_cand
                continue
        cur = cand
    return cur


def extract_target_path(uri_arg: str) -> str:
    raw = (uri_arg or '').strip()
    if not raw:
        return ''
    if raw.lower().startswith('suchmaschine-explorer:'):
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        if 'path' in qs and qs['path']:
            return qs['path'][0]
        # Fallback: Pfad direkt nach Protokoll
        tail = raw.split(':', 1)[1].lstrip('/')
        return unquote(tail)
    return raw


def main():
    if len(sys.argv) < 2:
        return
    raw_target = extract_target_path(sys.argv[1])
    resolved = resolve_windows_path(raw_target)
    if not resolved:
        return

    if os.path.isfile(resolved):
        subprocess.Popen(['explorer.exe', '/select,', resolved], shell=False)
    elif os.path.isdir(resolved):
        subprocess.Popen(['explorer.exe', resolved], shell=False)
    else:
        parent = os.path.dirname(resolved)
        if parent and os.path.isdir(parent):
            subprocess.Popen(['explorer.exe', parent], shell=False)


if __name__ == '__main__':
    main()
