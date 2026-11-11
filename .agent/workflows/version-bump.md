---
description: Version erhöhen bei jedem Deployment
---

# Version Bump Workflow

**KRITISCH:** Dieser Workflow MUSS bei JEDEM Code-Deployment ausgeführt werden!

## Schritte

1. **Inkrementiere die Version in `file_service.py`**
   - z. B. `APP_VERSION = "v1.2.1"` -> `"v1.2.2"`

2. **Update die Version im Header in `templates/index.html`**
   - `<span id="header-version-tag">vX.X.XXX</span>`

3. **Commit mit Versionsnummer**
   ```bash
   git commit -m "vX.X.XXX: [Beschreibung der Änderung]"
   ```

4. **Automatische Erinnerung**
   - Habe ich die Version überall erhöht?
   - Habe ich die neue Version dem User mitgeteilt?
   - ❌ **NIEMALS ohne Version-Bump deployen!**
