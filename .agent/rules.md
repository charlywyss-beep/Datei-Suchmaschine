# Datei-Suchmaschine UI & Development Rules

To ensure a high-quality and accessible user experience, follow these rules for all developments:

## Typography & Contrast
1. **Proper White**: Never use muted colors (`text-muted-foreground`) or low opacity (`opacity-60/70/80`) for critical data labels against dark or colored backgrounds (e.g., blue banners, dark mode cards). Always use full-brightness white (`text-white` or `text-foreground`).
2. **High Contrast on Colored Banners**: Never use gray, muted colors or low opacity on blue/colored cards (poor readability). Labels and values on colored background must always be solid black (`text-slate-950` / `text-black`) or high-contrast white, clear and crisp.
3. **Mobile Readability**: Ensure font sizes for secondary data (dates, times, file paths) are at least `11px` (`text-[11px]`) to remain legible on mobile devices like iPhone and iPad.

## Formatting
1. **No Parentheses**: Avoid using parentheses `(...)` around dates, times or counts in the UI. Use spacing or dividers (`•`) instead.
2. **Date Format**: Use `DD.MM.YY` or `DD.MM.` strictly as per user preference (German/Swiss style, e.g. `11.11.26 19:30`).

## Header & Layout Integrity (STRIKT VERBINDLICH)
1. **Header-Höhen sind absolut tabu**: Es ist strikt verboten, an den Höhen, Paddings oder der Grundstruktur der Header etwas zu verändern. Alle Header müssen exakt einheitlich und unverändert in ihrer Höhe und Struktur bestehen bleiben.

## Responsive & Viewport Ausnutzung (STRIKT VERBINDLICH)
1. **Desktop & iPad (Quer- und Hochformat)**:
   - **Volle Ausnutzung des Bildschirms**: Das Display soll voll ausgenutzt werden – am unteren Rand darf kein ungenutzter Platz verschenkt werden.
   - **Alles auf einmal sichtbar (No-Scroll)**: Bei 100% Zoom müssen sämtliche Kacheln, Eingabefelder und Auswertungen vollständig auf einen Blick sichtbar sein, ohne dass der Nutzer scrollen muss oder Kanten abgeschnitten werden.
2. **iPhone & Smartphones**:
   - Da auf kleinen Smartphone-Displays nicht alles auf einmal sichtbar sein kann, müssen stets **ganze Kacheln** auf dem Display stehen (keine unvollständig abgeschnittenen Felder).
   - Beim Scrollen geht es sauber und blockweise mit den nächsten Feldern bzw. Kacheln weiter.

## Version Bump & Deployment Workflow (STRIKT VERBINDLICH)
1. **Bei JEDEM Code-Update / Deployment**:
   - Die Version MUSS in `file_service.py` (`APP_VERSION`), `templates/index.html` und in der UI inkrementiert werden.
   - Git Commit im Format: `vX.X.XXX: [Beschreibung der Änderung]`.
   - Versionsnummer dem Nutzer in der Antwort mitteilen!
   - ❌ **NIEMALS ohne Version-Bump deployen!**
