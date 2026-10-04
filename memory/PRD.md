# PRD — LoL Autopicker (Windows-Python, ausdrücklich keine mobile App)

## Problemstellung / Persona
Privater Windows-League-Spieler mit bestehendem externem Tkinter/Python-Autopicker. EXE verschwand nach unklarer Schutzmeldung. Client-Neustart verbindet nicht neu; Auto-Ready verzögert, Hotkey-Änderungen nicht wirksam und Shift+1 wird als ! erfasst; Lolalytics-Spam erzeugt viele Fenster, Item-/VS-URLs gehen verloren, Gegnerrolle aus Draft-Reihenfolge falsch. Transparentes Icon, strukturierter Code und deutsche README gewünscht.

Nutzerentscheidung: vorhandenes Python-Programm als verbesserten Download mit Startdatei liefern. Chromium-/Firefox-Erweiterung erlaubt, weitere Browser mit klaren Grenzen. Keine Garantie gegen Defender-Erkennung oder universelle Browserkompatibilität. Statistikvorhersage optional und bei fehlender verlässlicher Quelle weglassen.

## Statische Anforderungen
- Lokal/extern, keine Prozessinjektion, keine Anti-Cheat-/Antivirus-Umgehung.
- Wiederverbindung, ereignisbasiertes Ready, sichere eigene Pick-/Ban-Aktionen, Priorität/Bad-Matchups.
- Sofort wirksame persistente Kürzel, physische Windows-Zifferntasten, Konfliktbehandlung.
- Browserübergreifender gemeinsamer API-Weg: exakte URL-Deduplizierung, gleicher Champion, Query-/VS-Persistenz, ACK vor Close.
- Gegnerabgleich aus verfügbaren Live-Rollen; unbekannt statt geraten, ARAM/Arena ausgeschlossen.
- Transparenter PNG-/ICO-Rand; expliziter reversibler Benutzer-Autostart; kleine begrenzte Hintergrundlast.
- Deutsches Quellenpaket mit Einrichtung, Grenzen, Diagnose und Tests.

## Architektur
`/app/autopicker`: Python3.11+ Tkinter, aiohttp LCU WebSocket/HTTPS, psutil Lockfile-Discovery. Keine MongoDB oder Expo für das Produkt. JSON-Dateien atomar in LOCALAPPDATA, private Dateirechte. Dedizierter WindowsHotkeys-Thread (Tk darf WM_HOTKEY nicht vorher konsumieren), UI-Queue, SingleInstance-Mutex. Authentifizierte Loopback-Bridge an zufälligem Port; Native Messaging Python-Adapter; gemeinsame WebExtension-Logik Chromium MV3 / Firefox MV2. Browser-owned tab IDs in storage.session. All user settings local; cloud only for delivering requested public source/PNG/ICO/docs downloads.

Original unverändert `/app/original/autopicker.py`; Bilder `/app/original/icon.jpeg`.
Download-Paket `/app/downloads/LoL-Autopicker-2.0-Quellcode.zip`; `/app/tools/package_autopicker.py` synchronisiert gemeinsame JS-Datei in Browserordner. `/app/tools/upload_autopicker_artifacts.py` lädt freigegebene Dateien in Managed Object Storage. `/app/backend/autopicker_downloads.py` liefert ausschließlich Manifest-whitelist via `/api/autopicker/download/{filename}`. Frontend-Gerüst bleibt bewusst unverändert.

## Implementiert — 2026-10-04
- Refaktorierter lokaler Desktop-Autopicker inkl. Pick-/Ban-Prioritäten, Bad-Matchup-Auswahl, deutscher Einstellungen.
- LCU Rediscovery/Backoff, WebSocket-Ready mit begrenztem Fallback, Fresh-Session-Check vor Lock-in, verfügbare Champions und Team-Hover geschützt.
- Windows RegisterHotKey auf eigener Nachrichtenthread, UI-dispatch, atomarer Rebind/Rollback, Shift+1-Keycode, Dubletten-F12-Konfliktmeldung.
- Browser-Bridge, begrenzte Queues, Native-Host-Installer/Uninstaller HKCU, zwei Browsermanifeste.
- Serielle Tabs-Operationen, URL-Normalisierung, Speicherung Items/VS/SPA pro Champion, ACK vor Close, keine fremden Tabs/Browserprozesse beendet.
- Live-Gegnerabgleich anhand Identität/Team/Rolle, vorhandene verwaltete VS-Tabs ohne Fokusdiebstahl korrigiert; keine cellId-Index-Heuristik.
- Setup/Start/Diagnose/Autostart-Batches, Migration alter Konfiguration, transparente PNG/ICO-Assets, README/TESTPLAN/TESTERGEBNIS.
- Tests iteration_1: 26 Python +5 JS. Nach zusätzlicher Windows-Message-Thread-Korrektur iteration_2: **33 Python +5 JS bestanden**, Tk-Screenshot geprüft. Simulierte Win32/LCU/WebExtension-Transporte klar von echten lokalen Socket-/Framing-/Tk-Tests getrennt. Kein realer Windows-/League-Test möglich in Linux.

## Implementiert — 2026-10-04 (Session 2.2, Verbindungsfix)
- Problem: Overlay flackerte „Verbunden/Getrennt“, keine Neuverbindung nach League-Neustart.
- Ursache: jede einzelne fehlgeschlagene/langsame LCU-Anfrage (3s-Total-Timeout, Keep-Alive-Abbruch, 401/403, WS-Heartbeat ohne Pong) riss die gesamte Verbindung ab; unerwartete Exceptions beendeten den Thread.
- Fix `/app/autopicker/lolpicker/lcu.py`: Anfragefehler werden toleriert (Reconnect erst nach 4 Fehlschlägen in Folge oder WS-Schließung), kein WS-Heartbeat, force_close-Connector, 8s-Request-Timeout, Status-Debounce, Phase-Reset bei Trennung, Discovery alle 1,5s über `LeagueClientUx.exe`-Cmdline (wie lcu-driver) → Lockfile → Standardpfad. Pick-Intent (Pre-Hover) aus Originalversion ergänzt.
- Tests: `tests/mock_lcu.py` (simulierter LCU HTTPS+WS), `test_lcu_mock_server.py`, `test_lcu_discovery.py`; 43 Python-Tests bestanden (iteration_4), Backend-Download-Routen geprüft.
- Download: `/app/downloads/LoL-Autopicker-2.2-Verbindungsfix.zip`, Backend liefert direkt aus `/app/downloads` (`/api/autopicker/download/{filename}`, `/api/autopicker/downloads`); Object-Storage-Manifest entfernt.

## Backlog / nächste Schritte
### P0 — manuelle Abnahme
- Nutzer prüft 2.2 auf Windows: Verbinden, League schließen/neu starten, Ready, Hover/Ban/Pick (Linux kann League nicht ausführen).
- Auf Nutzer-Windows echte Hotkeys, Registry Native Messaging, Autostart und League-Neustarts/Ready/Pick/Ban prüfen (TESTPLAN).
- Exakten Defender-/SmartScreen-/AV-Befund aus Schutzverlauf ermitteln. Keine unprüfbaren Bypass-/Erkennungsgarantien.
- Reale Browserprofile Chrome/Edge/Firefox end-to-end; Herstellerderivate erst nach Test als abgenommen bezeichnen.
### P1
- Mozilla-Signierung für dauerhaft installierbare Firefox-Erweiterung (aktuell temporär entwicklerladbar).
- Ressourcenmessung auf Ziel-Laptop, Windows-Display-Skalierung prüfen.
- Eventuell kompaktes Diagnoseexportpaket ohne Tokens; Champion-Datenaktualisierung.
### P2
- Statistische Rollenprognose erst mit verlässlicher erlaubter Datenquelle, derzeit ausdrücklich nicht implementiert.
- Optional signierter Windows-Release nach echten Integrationstests. Keine EXE im gelieferten Quellenpaket.

## Nicht zugesagt
Null-Latenz, garantierte AV-Warnungsfreiheit, alle Browser, tatsächliche Lane-Swaps ohne Daten, Wiederherstellung letzter Änderung bei abruptem Browser-/Systemabsturz.

## Nutzerkorrektur / Version 2.1 — 2026-10-04
Der Nutzer verlangt ausdrücklich die ursprüngliche Tk-Oberfläche (Screenshot, Farben, 75%-Overlay/96%-Einstellungen, kompakte rahmenlose Fenster), Suchvorschläge/Enter/Drag-and-drop, ursprünglichen Schwacher-PC-Modus und keine Expo-Oberfläche. Er bestätigt, dass die Opera-Erweiterung funktioniert, möchte aber schnelleres Verbinden sobald League bereit ist. Keine neue Einrichtung oder Erweiterungs-ID einführen.

### Umgesetzt
- Originaldatei erneut geladen, SHA identisch mit erster Fassung. Reine Original-Tk-Widgets und Edit-/Drag-/Bad-Matchup-Methoden ohne alte fehlerhafte Netzwerk-/pynput-Schicht extrahiert; `ui_layout.py`, `ui_widgets.py`, `settings_layout.py`, Adapter in `ui.py`/`settings_ui.py`. Überflüssige Kommentare entfernt. Fünf statt vier Vorschläge entsprechend explizitem Wunsch.
- Ursprüngliche kleine Oberfläche/Settingsfarben und Transparenz wiederhergestellt; Settingshöhe mindestens400, bei Systemschriftbedarf automatisch ausreichend für Footer. Keine permanente Zusatz-Browserzeile/Großtitel.
- „Schwacher PC Modus“ wieder echte Spiel-Vordergrund-Auslösung (auch Reintabben), ausdrücklich **alle erkannten Browserfenster**, nicht nur verwaltete Tabs. Damit ersetzt der neue Nutzerwunsch die vorherige P0-Regel zum ausschließlichen Schließen verwalteter Tabs für diese Aktion. Vorher Erweiterungs-Snapshot/Save-ACK; danach normale WM_CLOSE-Nachrichten, niemals taskkill. Modus standardmäßig AUS. Alt+Shift+3 bleibt einzelner verwalteter Tab.
- Persistenter NativeRelay wartet auch bei beendetem Desktopprogramm auf neue Bridge-Sitzung. Nur Dateimetadaten alle250ms, Dateilesen erst bei Änderung, keine Prozess-Startschleife. Native Port hält Browserworker bereit. Crash-Fallback nun maximal2s statt30s. League-connected sendet frischen Kontext; Browserbereitschaft unabhängig von League bereits vorher möglich.
- Bestehende Opera-ID bleibt beim Ersetzen im selben Ordner erhalten; Erweiterung einmal in opera://extensions neu laden. Kein Setup erneut nötig. Im ZIP keine Expo-Dateien/-Abhängigkeiten.
- Testagent erster Lauf hing in veraltetem NativeHost-Fixture (accept vor hello), wurde beendet. Fixture handshake/Timeout korrigiert; zweiter Agent aktualisierte Classic-Tests. iteration_3:36 Python+7 Node bestanden. Hauptagent beseitigte danach aiohttp.BasicAuth-Deprecation mittels Authorization-Header und Footer-Clipping; erneuter vollständiger Lauf bestanden. Gemessene echte lokale Relay-Verbindung0.252s initial/0.251s reconnect (keine Windows-Garantie). Screenshot `/app/test_reports/classic_ui.png`.
- README stark gekürzt, Update-Anleitung für bestehende Opera-Installation. Version2.1.0. Neues Paket `/app/downloads/LoL-Autopicker-2.1-Originaldesign.zip`, öffentliche Download-Whitelist erhält alte2.0-Datei zusätzlich.

### Noch offen
- Nutzer prüft native Windows-Transparenz/Hotkeys, tatsächliche Opera-Verbindungszeit und WM_CLOSE mit ungespeicherten Tabs. Linux-/simulierte Schnittstellen ersetzen diese Abnahme nicht.
- Firefox-Signatur/Defender-Fehlalarmdiagnose bleiben unverändert offen. Keine Expo-App liefern oder Desktop-Design eigenmächtig wieder ändern.