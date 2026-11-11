# 🚀 Datei-Suchmaschine Pro

Eine moderne, blitzschnelle lokale Datei-Suchmaschine mit genialer Benutzeroberfläche für Windows. Entwickelt für schnelles Auffinden, Verwalten, Bereinigen und Teilen von Dateien auf dem PC und in OneDrive.

---

## 🌟 Hauptfunktionen

### 1. 🔍 Blitzschnelle Dateisuche & Intelligente Filter
- **Teilnamensuche**: Sucht nach Begriffen, Wörtern und Teilnamen im Dateinamen (Groß-/Kleinschreibung tolerant).
- **1-Klick-Schnellfilter für Dateitypen**:
  - 📄 **PDF-Dokumente** (`.pdf`)
  - 📝 **Word-Dokumente** (`.docx`, `.doc`, `.rtf`, `.odt`)
  - 📊 **Excel-Tabellen** (`.xlsx`, `.xls`, `.csv`, `.ods`)
  - 💼 **Alle Office-Dateien** (PDF, Word, Excel, PowerPoint)
  - 🖼️ **Bilder & Fotos** (`.jpg`, `.png`, `.webp`, `.gif`, `.svg`, etc.)
  - 📦 **Archive** (`.zip`, `.rar`, `.7z`)
  - 💻 **Text & Skripte** (`.txt`, `.md`, `.log`, `.py`, `.json`, etc.)
- **Erweiterte Filter**:
  - Dateigröße (Min/Max in MB)
  - Änderungsdatum (Geändert nach Datum)
  - Eigene benutzerdefinierte Dateiendungen

### 2. ☁️ Vollständige OneDrive-Einbindung (Privat & Geschäftlich)
- **OneDrive Privat**: Erkennt automatisch Ihren privaten Speicherort (`C:\Users\01\OneDrive`).
- **OneDrive Geschäftlich (Business / SharePoint)**: Eigener Schnellzugriff auf geschäftliche Microsoft 365 Konten (z.B. `OneDrive - Firma`), konfigurierbar mit 1 Klick.
- **Transfer-Hub (Sync)**: Automatischer Synchronisations-Ordner `Transfer_Zuhause_Geschaeft_iPad` für den nahtlosen Datenaustausch.
- **1-Klick-Filter**: Getrennt nach *Nur Privat* oder *Nur Geschäftlich* filtern.
- Farblich unterscheidbare Badges für private (blau) und geschäftliche (violett) Dateien.

### 2b. 🐙 GitHub Versions-Aktualisierung (wie im Portfolio-Manager)
- Integriertes GitHub-Update Studio direkt in der Maske (Button oben rechts).
- Zeigt aktuellen Branch, Git-Commit und Remote-Repository.
- **1-Klick-Update**: Führt im Hintergrund `git pull` aus, zeigt das Live-Update-Protokoll und lädt die Anwendung neu.
- Zusätzlich vorhanden: `Update_From_Github.bat` für den schnellen Windows-Doppelklick.

### 2c. 📱 Datenaustausch: PC Geschäft ⇄ PC Zuhause ⇄ iPad ⇄ iPhone
- **Drahtloser Live-Zugriff**: Server lauscht auf `0.0.0.0:5005` und ist im lokalen WLAN erreichbar.
- **Live QR-Code**: Im Header auf **[iPad & iPhone]** klicken – QR-Code mit der iPhone- oder iPad-Kamera scannen und die Suchmaschine öffnet sich sofort mobil.
- **Direkt-Dateitransfer (Mobile Upload & Download)**:
  - Fotos, Scans und Dateien vom iPhone / iPad direkt auf den PC hochladen.
  - Dokumente vom PC direkt auf das iPad / iPhone herunterladen.
- **Automatischer Cloud-Sync**: Über Microsoft OneDrive (Apps für iOS & Windows) sind alle Daten im Transfer-Hub ohne manuelles Zutun zwischen Heim-PC, Geschäfts-PC, iPad und iPhone synchron!

### 3. 👥 Doppel-Eliminierung (Intelligenter Duplikate-Finder)
- Findet exakte Kopien und Dubletten anhand des echten Dateiinhalts (**SHA-256 kryptografischer Hash**).
- Zeigt verschwendeten Festplattenspeicher an.
- **Intelligente Schnell-Auswahlhilfen**:
  - *Älteste Kopie behalten* (Neuere zum Löschen markieren)
  - *Neueste Kopie behalten* (Ältere zum Löschen markieren)
  - *OneDrive-Kopien bevorzugen*
  - *Dateien mit "(1)", "Kopie" etc. automatisch erkennen*
- **Sicheres Löschen**: Verschiebt Dateien sicher in den **Windows-Papierkorb** (kein versehentlicher Datenverlust, Wiederherstellung jederzeit möglich).

### 4. ✏️ Massen- & Einzel-Umbenennung (Batch Rename Studio)
- **Live-Vorschau**: Vorher-Nachher-Tabelle in Echtzeit *bevor* eine Datei umbenannt wird.
- **5 Umbenennungs-Regeln**:
  - 🔍 **Suchen & Ersetzen**: z.B. "_alt" durch "_neu" oder "Rechnung" durch "Invoice"
  - ➕ **Präfix / Suffix**: Text vorne oder hinten anfügen
  - 🔢 **Durchnummerieren**: z.B. `Foto_{01}`, `{name}_{index}` mit wählbarer Stellenanzahl
  - 📅 **Datumsstempel**: z.B. `2026-11-11_{name}`
  - 🔤 **Groß- / Kleinschreibung**: lowercase, UPPERCASE, Title Case
- Einzeldatei-Umbenennung direkt per Klick.

### 5. 🛠️ Bearbeitung der Dateien & "Öffnen mit..."
- **Öffnen mit...**: Startet den nativen Windows App-Auswahldialog zur freien Programmauswahl.
- **Im Standard-Editor bearbeiten**: Startet Word, Excel, Paint oder Notepad direkt mit der Datei.
- **Integrierter In-App Text-Editor**: Text-, Log-, Markdown- und Code-Dateien direkt in der Web-Maske bearbeiten und mit **1 Klick speichern**.

### 6. 💬 Teilen per MS Teams & ✉️ E-Mail
- **Microsoft Teams Integration**: Kopiert die Datei direkt als Dateiobjekt in die Windows-Zwischenablage. Wechseln Sie in MS Teams und drücken Sie einfach `Strg + V` – die Datei wird sofort angehängt!
- **E-Mail-Versand**: Erstellt automatisch einen Entwurf mit angehängter Datei in Microsoft Outlook oder Ihrem Standard-Mailprogramm.

### 7. 🖨️ Ausdruck-Möglichkeiten
- **Datei drucken**: Sendet die Datei direkt an Ihren Windows-Standarddrucker.
- **Ergebnisliste drucken**: Formatierte, übersichtliche A4-Druckansicht der gesamten Trefferliste.

---

## 🚀 Starten der Anwendung

1. **Über die Desktop-Verknüpfung**:
   - Doppelklick auf die Verknüpfung **Datei-Suchmaschine Pro** auf Ihrem Desktop.
2. **Über den Ordner**:
   - Starten Sie die Datei `Start_Suchmaschine.bat` im Ordner `Datei-Suchmaschine`.
   - Die Anwendung startet und öffnet automatisch Ihren Standardbrowser unter:
     `http://localhost:5005`
