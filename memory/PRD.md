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

## Backlog / nächste Schritte
### P0 — manuelle Abnahme
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