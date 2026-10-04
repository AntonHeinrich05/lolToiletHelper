# PLAN.md — Offene Aufgaben für LoL Autopicker (Stand 2.3.1)

Dieses Dokument ist die Übergabe an die nächste Session/den nächsten Account. Alles Nötige steht hier, der Nutzer muss nichts erneut erklären.

## Kontext in 60 Sekunden

- Windows-Desktop-Tool (Python 3.11+, Tkinter) in `autopicker/`, Paket `lolpicker/`. Overlay liegt über dem League-Client. **Design darf nicht verändert werden** – nur ergänzen, Farben/Fonts/Abstände aus `ui_layout.py`/`ui_widgets.py` übernehmen.
- Verbindung zum League-Client (LCU) in `lolpicker/lcu.py`; Pick/Ban/Ready/Intent funktionieren seit 2.3.1 (Nutzer hat Verbindung, Ban, Pick bestätigt; Intent-Fix 2.3.1 noch vom Nutzer zu bestätigen – falls nicht, `%LOCALAPPDATA%\LoLAutopicker\autopicker.log` anfordern, dort steht pro Versuch Timer-Phase + HTTP-Status).
- Browser-Steuerung (Lolalytics-Tabs in Opera) läuft über eine Browser-Erweiterung + Native Messaging: `extension/`, `lolpicker/bridge.py`, `lolpicker/browser_windows.py`, `lolpicker/platform_win.py`. Hotkeys in `lolpicker/hotkeys.py`, Defaults in `storage.py` (`<alt>+<shift>+1` Lolalytics, `+2` VS, `+3` Tab schließen, Overlay ein/aus).
- Einstellungen: `storage.py` (DEFAULTS + Validierung) → `settings_layout.py`/`settings_ui.py` (Fenster) → `ui.py` (`SETTINGS`-Liste, `load_config/save_config`).
- Tests: `cd autopicker && python -m pytest -q` (45 Tests; `tests/mock_lcu.py` simuliert den League-Client, Tk-Tests brauchen Display). Paket bauen: `python tools/package_autopicker.py` → `downloads/LoL-Autopicker-<version>.zip`, Download über Backend `/api/autopicker/download/<datei>`.
- League kann in der Entwicklungsumgebung nicht laufen; Windows-/Browser-Verhalten muss der Nutzer testen. Deshalb: jede Änderung mit INFO-Logs versehen.

## Aufgaben (Priorität von oben nach unten)

### 1. Rahmen bei Auto-Bans fehlt, solange noch nichts gebannt wurde
- Symptom: Die Ban-Zeilen haben zu Beginn der Champion-Auswahl keinen Rand; Pick-Zeilen sind grau umrandet.
- Vermutung: `pick_status` setzt nur `pick_rows` (`ui.py`, Zweig `kind == 'pick_status'`); Ban-Zeilen bekommen erst nach dem Ban eine Farbe bzw. der Default-Rand (`PICK_BORDER`) wird für `ban_rows` nicht gesetzt. Prüfen in `ui_layout.py` (Erzeugung der Ban-Zeilen) und beim Phasenwechsel in `ui.py` (`kind == 'phase'`).
- Ziel: Ban-Zeilen immer mit Standardrand (grau), gebannter Champion blau wie beim Pick.

### 2. Deckkraft (Transparenz) einstellbar – getrennt für „im Spiel“ und „sonst“
- Aktuell fest: `ui_layout.py` Zeile ~11 `self.root.attributes('-alpha', 0.75)`.
- Neu: zwei Einstellungen `opacity_default` (z. B. 0.75) und `opacity_ingame` (z. B. 0.5) in `storage.DEFAULTS` + Validierung (0.2–1.0), Schieberegler oder Eingabe im Einstellungsfenster (`settings_layout.py`), Aufnahme in `ui.SETTINGS`.
- Umschalten: bei `phase`-Event in `ui.py` – Phasen `InProgress`/`GameStart`/`Reconnect` → `opacity_ingame`, sonst `opacity_default`. Auch sofort anwenden, wenn der Regler bewegt wird.

### 3. Schwacher-PC-Modus repariert und präzisiert
- Soll: Wenn das Spiel in den Vordergrund kommt, **nur Lolalytics-Tabs** schließen (nicht alle Browserfenster/Tabs). Muss sowohl für den Hotkey-Pfad als auch für den automatischen Pfad funktionieren.
- Ist: funktioniert laut Nutzer gar nicht. Einstieg: `controller.py` Zeile ~86 (`kind == "game_foreground"` → nur wenn `weak_pc_mode`), `browser_windows.py` Zeile ~67, `platform_win.py` (Vordergrund-Erkennung des Spiels, Prozessname `League of Legends.exe`), Erweiterung `extension/shared/background.js` (Befehl zum Schließen; nur Tabs mit URL auf `lolalytics.com` schließen).
- Debuggen: INFO-Logs in jedem Schritt (Vordergrund erkannt → Befehl an Bridge → Antwort der Erweiterung). Diagnose.bat zeigt die Konsole.

### 4. Lolalytics-Tabs schließen, auch nach Champion-Wechsel im Tab
- Symptom: `Alt+Shift+1` öffnet Lolalytics; wählt der Nutzer in Lolalytics einen anderen Champion, lässt sich der Tab mit `Alt+Shift+3` nicht mehr schließen.
- Ursache sehr wahrscheinlich: Tabs werden über die exakte geöffnete URL/Tab-ID gemerkt; nach Navigation stimmt die URL nicht mehr. Fix: in `extension/shared/background.js` alle Tabs schließen, deren URL-Host `lolalytics.com` ist (unabhängig von der gemerkten URL), zusätzlich gemerkte Tab-IDs. Betroffene Stellen: `bridge.py`/`controller.py` (Befehl `close_tab`/`close_all`), `tests/test_extension_background.js`.
- Gilt für alle Lolalytics-Tabs, nicht nur den zuletzt geöffneten.

### 5. VS-Button rot anzeigen, sobald der Gegner bekannt ist
- Soll: Sobald der Lane-Gegner feststeht (`draft`-Event mit `opponent` aus `lcu.py` oder `live`-Event aus `live.py`), erscheint rechts neben dem „LoLalytics“-Button ein roter Button „VS“ (gleiche Höhe/Font wie `lolalytics_btn` in `ui_layout.py` ~Zeile 104). Klick = `open_vs` (`ui.py`). Ohne bekannten Gegner ausblenden.
- Einstieg: `ui.py` `_update_match()` und `_refresh_vs_button_visibility`-ähnliche Logik aus der Originaldatei (`original/autopicker_latest.py`, Suche nach `_refresh_vs_button_visibility`).

### 6. Standard-Runen und Beschwörerzauber pro Auto-Pick-Champion
- Soll: Für jeden Champion in der Auto-Pick-Liste eigene Runenseite + zwei Beschwörerzauber festlegen; beim Lock-in automatisch im Client setzen; Auswahl wird gespeichert.
- UI: Pro Pick-Zeile ein zusätzlicher Eintrag im „…“-Menü (`ui_layout.py`, Zeile mit `...`), öffnet ein Fenster im bestehenden Stil. Runen wie im League-Client wählbar: Hauptpfad (5) → Schlüsselstein + 3 Reihen, Nebenpfad → 2 Reihen, 3 Statusrunen. Gewählte Runen eindeutig hervorheben (heller Rahmen + volle Deckkraft, nicht gewählte abgedunkelt), Tooltip mit Runenname beim Hovern (`ui_widgets.py` hat vermutlich schon eine Tooltip-/Hover-Hilfe).
- Daten: Runen-/Zauber-IDs und Icons von Data Dragon (`https://ddragon.leagueoflegends.com/cdn/<version>/data/de_DE/runesReforged.json`, `summoner.json`, Icons unter `/cdn/img/`), einmalig herunterladen und in `%LOCALAPPDATA%\LoLAutopicker\cache` ablegen. Speicherung in `storage.py` unter z. B. `loadouts: {"<championId>": {"primary": id, "sub": id, "perks": [6 ids], "spells": [id, id]}}` mit Validierung.
- LCU-Aufrufe (nach erfolgreichem Lock-in in `lcu.automate`, nur bei konfiguriertem Champion):
  - Runen: `GET /lol-perks/v1/pages` → eigene editierbare Seite finden oder `POST /lol-perks/v1/pages` anlegen (bei voller Seitenzahl älteste eigene Seite per `DELETE /lol-perks/v1/pages/{id}` ersetzen), Body `{"name": "Autopicker <Champion>", "primaryStyleId", "subStyleId", "selectedPerkIds": [...], "current": true}`; danach `PUT /lol-perks/v1/currentpage` mit der Seiten-ID.
  - Zauber: `PATCH /lol-champ-select/v1/session/my-selection` mit `{"spell1Id": …, "spell2Id": …}`.
  - Alles mit INFO-Logs und Mock-Endpunkten in `tests/mock_lcu.py` abdecken.

### 7. Hotkeys Alt+Shift+1 / Alt+Shift+2: Browser in den Vordergrund holen
- Symptom: Nach Öffnen von Lolalytics/VS bleibt der Browser hinter League.
- Einstieg: `browser_windows.py` / `platform_win.py` (`SetForegroundWindow` scheitert, wenn ein anderer Prozess den Vordergrund hält). Bewährter Weg: `AllowSetForegroundWindow`, `AttachThreadInput` auf den Vordergrund-Thread, dann `ShowWindow(SW_RESTORE)` + `SetForegroundWindow`; alternativ `keybd_event(VK_MENU)`-Trick vor `SetForegroundWindow`. Zusätzlich die Erweiterung `chrome.windows.update(windowId, {focused: true})` + `chrome.tabs.update(tabId, {active: true})` aufrufen lassen.

### 8. Alt+Shift+3 (Tabs schließen) auch wenn League im Vordergrund ist
- Symptom: Hotkey wirkt nicht, solange das Spiel fokussiert ist.
- Prüfen in `hotkeys.py`: Werden globale Hotkeys über `pynput`/`keyboard` registriert und von League (Vollbild, evtl. höhere Integrität) geschluckt? Optionen: `RegisterHotKey` (WinAPI) im Tk-Mainloop-Thread, Low-Level-Hook mit `ctypes`, oder das Spiel im Fenstermodus/randlos testen. Mit INFO-Log „Hotkey empfangen“ verifizieren, ob der Hotkey ankommt oder erst das Schließen scheitert (dann siehe Aufgabe 4).

## Arbeitsweise

1. Vor Änderungen `python -m pytest -q` grün halten; für jedes Feature Tests ergänzen (Mock-LCU für Client-Aufrufe, Node-Tests für `background.js`).
2. Version in `pyproject.toml`, `README.md`, `TESTERGEBNIS.md` und `tools/package_autopicker.py` erhöhen, ZIP bauen, Download-Link testen.
3. Nutzer testet unter Windows; bei Problemen Log anfordern (`%LOCALAPPDATA%\LoLAutopicker\autopicker.log`).
