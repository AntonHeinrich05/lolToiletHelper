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

## Implementiert — 2026-10-04 (Session 2.2.1, Pick/Ban wie Original)
- Nutzer-Log bestätigt: Verbindung + Reconnect nach League-Neustart funktionieren. Pick/Ban wurde nicht bestätigt, Pick-Intent fehlte.
- `automate()` folgt jetzt exakt der Original-Datei: PATCH {championId, completed:true} → 0,12s → POST /complete; Wiederholung jede Sekunde solange die Aktion offen ist; `pickable-champion-ids`-Gate und GET-Verifikation entfernt; INFO-Logs mit HTTP-Status pro Schritt.
- `prehover()`: Pick-Intent jede Sekunde solange nichts gehovert ist (manuelles Hovern bleibt). `available()` schließt auch Champions aus, die andere Spieler gewählt haben.
- 44 Tests grün; ZIP LoL-Autopicker-2.2.1-Verbindungsfix.zip.

## Implementiert — 2026-10-04 (Session 2.3)
- Nutzer bestätigt: Verbindung, Ban und Pick funktionieren. Offen waren: Pick-Intent in der Vorauswahl, Rahmenfarbe nach Lock-in (Diana grün), Python-Installation für Nutzer ohne Python.
- `prehover()`: PATCH {championId} (ohne completed) auf alle eigenen Pick-Aktionen, jede Sekunde bis Intent sichtbar; Logging mit Timer-Phase + HTTP-Status + Fehlerbody.
- `pick_status`: nach eigenem Lock-in nur gewählter Champion „hovered“ (blau), Rest „ok“ (grau).
- `Setup.bat`: findet py/python 3.11+, sonst Download python-3.12.10-amd64.exe (/passive, PrependPath) → Fallback winget → venv.
- 44 Tests grün; ZIP LoL-Autopicker-2.3.zip.

## Implementiert — 2026-10-04 (Session 2.3.1)
- Screenshot: in PLANNING („Absicht verkünden“) kein Hover. Hypothese (konsistent mit allen Beobachtungen): LCU meldet eigene Pick-Aktion in PLANNING als isInProgress → automate() versuchte Lock-in (abgelehnt) statt Intent.
- Fix: bei timer.phase == PLANNING immer prehover (PATCH championId, completed=false); bei abgelehntem Lock-in zusätzlich Hover-PATCH als Fallback. Test ergänzt. 45 Tests grün. ZIP LoL-Autopicker-2.3.1.zip.

## Übergabe — 2026-10-04
- Nutzer-Account fast leer. Vollständiger Aufgabenplan für die nächste Session steht in `/app/autopicker/PLAN.md` (auch im ZIP): Ban-Rahmen, Deckkraft (Spiel/sonst), Schwacher-PC-Modus nur Lolalytics-Tabs, Lolalytics-Tabs nach Champion-Wechsel schließen, roter VS-Button, Runen+Beschwörerzauber pro Champion (Runenwahl wie im Client, Hover-Namen, gespeichert), Browser in den Vordergrund bei Alt+Shift+1/2, Alt+Shift+3 auch wenn LoL im Vordergrund.

## Implementiert — 2026-10-04 (Session 2.4.0, alle 8 PLAN-Aufgaben)
- Ban-Zeilen: neutraler grauer Rahmen ab ChampSelect, eigener Ban blau, nicht bannbar grün (`lcu.py` emittiert `ban_status`, `ui.py`).
- Deckkraft: `opacity_default`/`opacity_ingame` (0.2–1.0) in `storage.py`, zwei Regler mit Live-Vorschau in `settings_layout.py`, Umschalten bei Phase InProgress/GameStart/Reconnect.
- Schwacher-PC-Modus: Spielfenster-Erkennung über `RiotWindowClass`/Titel (nicht nur Prozessname), schließt nur Lolalytics-Tabs in allen Browsern (`close_lolalytics`); Alt+Shift+4 gleiche Aktion. `close_browser_windows` entfernt.
- Erweiterung: `closeLolalytics()` schließt jeden Lolalytics-Tab (host-basiert, auch nach Champion-Wechsel), Save vor Close, Fehler blockiert nicht; Fenster-Fokus beim Öffnen; Befehle ohne Verbindung ignoriert.
- Browser nach vorn: `focus_browser_window` (AttachThreadInput + SetForegroundWindow, Titel-Hinweis „lolalytics“) nach jedem `open`.
- Runen & Zauber: `runes.py` (Data Dragon de_DE, Cache, STAT_SHARDS, Validierung), `loadout_ui.py` (Client-Layout, gold = gewählt, Tooltip), `✦` in Pick-Zeile, `loadouts` in settings, `lcu.apply_loadout` nach Lock-in (Seite anlegen/ersetzen, currentpage, my-selection Spells) genau einmal pro ChampSelect.
- Hotkeys: INFO-Log „Hotkey empfangen“. VS-Button-Logik unverändert (erscheint bei bekanntem Gegner aus Draft-Rolle oder Live-Daten).
- Tests: 49 Python + 7 JS grün (iteration_5), ZIP LoL-Autopicker-2.4.0.zip, Erweiterungs-Manifest 2.4.0 (Neu laden nötig).

## Implementiert — 2026-10-06 (Session 2.5.0)
- Nutzer-Feedback wörtlich oben in README. Beschwörerzauber: PATCH my-selection + Verifikation in der Session, bis 4 Versuche (`lcu.set_spells`).
- `flash_side` (D/F) Einstellung; Jungle-Fallback Flash+Smite bzw. optionale `jungle_spells` pro Loadout (eingeklappt im Runen-Fenster) – `lolalytics.spells_for_role`.
- Rollen-Picklisten: `role_lists`/`list_role` in storage, Dropdown „Liste für“ im Overlay, `selection.effective_lists` (zugewiesene Rolle → Rollenliste, sonst Allgemein) in choose() und pick_status.
- Lolalytics-Import: `lolalytics.py` parst Qwik-State der Build-Seite (summary.pick/win → runes.set + sums.ids); Einstellungen Rang/Zeitraum-Patch/Build (Default all/30/pick), Auto-Import beim Lock-in ohne eigenes Loadout (`lcu.import_loadout`), Buttons „⤓ Lolalytics“ (Liste) und „⤓ Von Lolalytics“ (Fenster). Veraltete Runen nach Patch werden erkannt (validate) und nicht gesetzt.
- 55 Python + 7 JS Tests grün; ZIP 2.5.0.

## Implementiert — 2026-10-06 (Session 2.5.1, Prüfung + Ergänzung nach Account-Wechsel)
- Repo-Branch `autoimport-runes-angefangen` übernommen, 55 Tests grün, Lolalytics-Parser live gegen echte Seite verifiziert (mehrere Lanes/Ränge/Patches/Builds).
- `lcu.set_spells`: PATCH my-selection trägt `selectedSkinId` (LCU-Schema); Mock lehnt PATCH ohne Feld ab.
- `lcu.apply_loadout`: veraltete Runen → Lolalytics-Import für die Lane (wenn aktiviert), eigene Zauber bleiben.
- `ui._follow_assigned_role`: Overlay-Dropdown folgt in ChampSelect der zugewiesenen Rolle, Rückkehr zur manuellen Wahl in Lobby/None.
- README oben: Nutzer-Feedback (unverändert) + Abschnitt „Prüfung und Ergänzungen in 2.5.1“. 56 Python + 7 JS + 7 Backend-Tests grün; ZIP `LoL-Autopicker-2.5.1.zip`.

## Implementiert — 2026-10-06 (Session 2.6.0, Rückmeldung 2)
- `selection.effective_lists`: gewählte Liste (`list_role`) ist Standard, Rollenliste nur bei zugewiesener Rolle mit Einträgen, „Alle Rollen“ letzte Reserve; `controller.current_champion()` + `lcu.prehover` folgen dem (Alt+Shift+1 öffnet den ersten Champ der gewählten Liste).
- `ui._follow_assigned_role` springt nur noch bei eigener Rollenliste um; Rückkehr zur manuellen Wahl.
- Champion-spezifische Lolalytics-Einstellungen: `loadout.lolalytics` (nur Abweichungen), `lolalytics.import_settings/patch_options`, eingeklappte Sektion „▸ Einstellungen“ im Runen-Fenster, Import (Fenster, Liste, LCU-Fallback) nutzt sie.
- `close_scope` („lolalytics“/„browser“) in Einstellungen; `controller.close_browsers` mit Win32 `close_browser_windows` (WM_CLOSE) + Erweiterung `close_windows`; immer Rückmeldung im Overlay.
- Default `lolalytics_import.enabled=False`, Migration schema 2→3. Erweiterung 2.6.0 (Neu laden). 58 Python + 8 JS + 7 Backend-Tests grün; ZIP `LoL-Autopicker-2.6.0.zip`.

## Backlog / nächste Schritte
- Windows-Abnahme durch Nutzer: Spielfenster-Erkennung, Browser-Fokus im Spiel, Hotkeys bei fokussiertem Spiel, echte LCU-Runen-Endpunkte.
- Optional: Runenseiten-Import aus Lolalytics, Rollen-Picklisten, Dodge-Warnung.
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