# LoL Autopicker 2.1 — Originaldesign

Windows-Python-Programm mit deiner ursprünglichen Oberfläche. Kein Expo, keine Handy-App, kein Konto.

## Update von 2.0 — Opera ist schon eingerichtet

1. Autopicker vollständig beenden.
2. ZIP entpacken und **den Inhalt** des enthaltenen Programmordners in deinen **bisherigen Autopicker-Ordner** kopieren; Dateien ersetzen. `.venv` und `native_manifests` dort behalten. Den bisherigen Ordner nicht verschieben oder umbenennen.
3. In Opera `opera://extensions` öffnen und bei der Autopicker-Erweiterung **Neu laden** anklicken. Version: **2.1.0**. Kein erneutes ID-Kopieren nötig, solange Ordner und Browserprofil unverändert bleiben.
4. `Start.bat` starten. Einstellungen und gespeicherte URLs bleiben in `%LOCALAPPDATA%\LoLAutopicker` erhalten.

Die Abhängigkeiten haben sich nicht geändert: bei funktionierender 2.0-Installation ist `Setup.bat` nicht erneut nötig. Wer einen anderen Installationsordner verwendet, muss Erweiterung, Native Host und gegebenenfalls Autostart auf den neuen Pfad einrichten.

## Was wieder wie vorher ist

- Kleines rahmenloses Overlay: Originalfarben, Originalabstände, 75 % Deckkraft, keine große Überschrift und keine zusätzliche Browser-Statuszeile.
- Original-Einstellungen mit Gold-/Dunkelblau-Tönen, 96 % Deckkraft, kleinen Hotkey-Feldern und AN/AUS-Schaltern.
- Suche mit bis zu **fünf Vorschlägen**. `a` → Enter nimmt den ersten Treffer. Pfeiltasten oder Maus wählen einen anderen Treffer.
- Drag-and-drop für Pick-/Ban-Reihenfolge und Bad-Matchups; Doppelklick zum direkten Bearbeiten; × zum Entfernen.
- `…` am Pick öffnet das kompakte Bad-Matchup-Feld: drei pro Reihe, maximal sechs. Plus/Minus klappt die Listen wie früher ein und aus.
- „Schwacher PC Modus“ und „Alle Browser schließen“ haben wieder die ursprüngliche Bedeutung (siehe unten).

Die technischen Verbesserungen bleiben: League-Neuverbindung, ereignisbasiertes Auto-Ready, funktionierende Hotkey-Änderungen einschließlich Alt+Shift+1, sichere Pick-/Ban-Prüfungen, Tab-Deduplizierung, Item-/VS-Speicherung und Gegnerabgleich nach Spielstart.

## Schnellere Browser-Verbindung

Die Erweiterung hält einen kleinen lokalen Native-Host-Prozess bereit, auch wenn der Autopicker noch nicht läuft. Startet der Autopicker, bemerkt dieser Prozess die neue Sitzung normalerweise innerhalb eines **250-ms-Prüftakts** und verbindet sich. Die alte Wartezeit von bis zu 30 Sekunden zwischen Versuchen entfällt im normalen Start-/Neustartpfad. Das ist ein technischer Takt, keine garantierte End-to-End-Latenz auf jedem PC.

- Die Browser-Verbindung wartet **nicht erst auf League**: bei offenem Opera kann sie schon vorher bereit sein.
- Nach einem Autopicker-Neustart bleibt die Erweiterungsverbindung zum Native Host bestehen; Token und Port werden neu eingelesen.
- `…` am Erweiterungssymbol: lokale Brücke bereit, wartet auf Autopicker. `ON`: verbunden. Klicken wählt diesen Browser als Ziel.
- Ein **geschlossener** Browser muss zuerst geöffnet werden. Browser- oder Unternehmensrichtlinien können Hintergrundaktivität verzögern.
- In den Einstellungen zeigt Live-URL-Tracking `AKTIV`, `WARTE` oder `AUS`. Rechtsklick darauf oder auf „Verbunden/Getrennt“ zeigt den Verbindungsstatus, ohne das Overlay dauerhaft zu vergrößern.

## Schwacher PC Modus — wieder Originalverhalten

Standard: **AUS**. Bei **AN** werden Browserfenster geschlossen, sobald das eigentliche Spiel (`League of Legends.exe`) in den Vordergrund kommt, also auch beim erneuten Reintabben. Im Launcher/Client passiert nichts.

**Achtung: Das betrifft alle erkannten Browserfenster einschließlich anderer Tabs.** Vorher werden passende Lolalytics-URLs über verbundene Erweiterungen gespeichert. Scheitert diese Bestätigung, wird das Schließen abgebrochen. Anschließend werden normale Windows-Schließnachrichten gesendet, ohne Fokuswechsel, ohne `taskkill` und ohne erzwungene Prozessbeendigung. Browser dürfen Rückfragen wegen ungespeicherter Daten anzeigen; Hintergrundprozesse können je nach Browsereinstellung weiterlaufen.

Alt+Shift+4 löst denselben Ablauf manuell aus. Alt+Shift+3 speichert und schließt dagegen nur einen verwalteten Lolalytics-Tab.

## Neueinrichtung

1. Python 3.11+ mit Tkinter und Python-Launcher (`py`) von https://www.python.org installieren.
2. ZIP dauerhaft entpacken, dann `Setup.bat` ausführen. Keine Administratorrechte nötig.
3. Chromium/Opera/Edge/Brave/Vivaldi: Erweiterungsverwaltung → Entwicklermodus → **Entpackte Erweiterung laden** → `extension\chromium`.
4. Erweiterungs-ID kopieren, `Browser_Bridge_installieren.bat` → `1` → ID einfügen. Danach Erweiterung neu laden.
5. `Start.bat`. Bei Fehlern `Diagnose.bat` benutzen.

Firefox: `about:debugging#/runtime/this-firefox` → temporäres Add-on laden → `extension\firefox\manifest.json`; Browser-Installer → `2`. **Temporäre Firefox-Add-ons müssen nach Browser-Neustart erneut geladen werden.** Für Dauerbetrieb ist Mozilla-Signierung erforderlich; das Paket enthält kein signiertes Add-on.

Mehrere Browserprofile: im gewünschten Browser auf das Erweiterungssymbol klicken. Ohne Auswahl wird nur bei genau einer verbundenen Erweiterung automatisch entschieden. Browser ohne Native Messaging sind nicht unterstützt. Die vollständige Kompatibilität jedes Browsers ist nicht garantiert; Opera funktioniert laut deinem bisherigen Praxistest.

## Kürzel

| Standard | Funktion |
|---|---|
| Alt+Q | Overlay ein/aus |
| Alt+Shift+1 | Lolalytics öffnen / gleichen vorhandenen Tab aktivieren |
| Alt+Shift+2 | VS-Matchup öffnen |
| Alt+Shift+3 | Verwalteten Tab speichern und schließen |
| Alt+Shift+4 | Alle erkannten Browserfenster schließen |

In Einstellungen Kürzel anklicken und neue Kombination drücken. ESC bricht die Aufnahme ab. Konflikte werden angezeigt, statt nur die Anzeige zu ändern. Physische Zifferntasten bleiben mit Shift Zifferntasten. Windows kann Alt+Shift selbst zum Sprachwechsel verwenden; bei Konflikten andere Kombination wählen.

## Daten und Grenzen

- `%LOCALAPPDATA%\LoLAutopicker`: `settings.json`, `urls.json`, rotierendes `autopicker.log`. `bridge-session.json` enthält einen kurzlebigen lokalen Token und darf nicht weitergegeben werden.
- Alte `lolhelper_config.json`/`lol_tool_state.json` können vor dem allerersten Start in den Programmordner gelegt werden. Vorhandene neue Einstellungen werden nicht überschrieben.
- Live-Tracking speichert Änderungen für denselben Champion einschließlich Item-, Gegner- und Lane-Parametern. Ein anderer Champion überschreibt diese Auswahl nicht.
- VS wird nur anhand eindeutiger Rolleninformationen korrigiert, nie anhand der Pick-Reihenfolge. Fehlende Rollen und echte Lane-Swaps lassen sich nicht sicher erraten. Statistikvorhersage bleibt wie vereinbart weggelassen.
- Abrupter Browserabsturz/Stromausfall kann die allerletzte URL-Änderung verlieren. Der Autopicker-Schließen-Hotkey wartet auf Speicherbestätigung.
- Autostart freiwillig: `Autostart_aktivieren.bat`, rückgängig mit `Autostart_entfernen.bat`. Alten Batch-Autostart separat entfernen, damit nicht zwei Versionen starten.
- **Keine Garantie gegen Defender-/SmartScreen-Warnungen oder Löschungen.** Keine Schutzfunktion wird abgeschaltet. Bei erneuter Meldung den genauen Befund im Windows-Schutzverlauf nachsehen. Paket enthält Quellcode, keine als getestet ausgegebene EXE.
- LCU kann sich durch Riot-Updates ändern; aktuelle Riot-Regeln zu Drittanbieter-Tools beachten. Keine Anti-Cheat-Umgehung.
- Windows-/League-Praxistests bleiben erforderlich. Siehe `TESTPLAN.md` und `TESTERGEBNIS.md`.

Entfernen: Autopicker beenden, Autostart entfernen, `Browser_Bridge_entfernen.bat`, Erweiterung im Browser entfernen, Programmordner löschen. Den Datenordner nur löschen, wenn auch deine Einstellungen weg sollen.

Entwicklungstests: `.venv\Scripts\python.exe -m pip install ".[test]"`, danach `.venv\Scripts\python.exe -m pytest -q`. Optional mit Node.js: `node --test tests\test_extension_background.js`.