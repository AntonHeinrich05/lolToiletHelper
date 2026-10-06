# Rückmeldung des Nutzers (Stand nach 2.4) — Grundlage für 2.5

> runen picken funktioniert sehr gut
> - beschwörer zauber funktioniert noch nicht so gut bzw garnicht, aber man muss auch bedenken wenn man jungler ist bzw zufällig bekommt passen die beschörer zauber unter umständen nicht, wenn das nicht passt soll flash und smite genommen werden bzw wär es auch cool wenn man einstellen kann ob wo man den flash hat auf welcher taste bzw links oder rechts und dazu dann auch einstellen kann wenn man jungler mit dem champ zufällig bekommt wie man dann die beschörer zauber hat, aber das mit dem zufällig jungler kommt sehr selten vor also muss diese einstellungsmöglichkeit nicht direkt ausgeklappt sein quasi, und wenn es neue runen gibt also nen update runen werden geändert passt sich der toilet helper da an? es sollte so sein
>
> Rollen Picklisten: Lass pro zugewiesener Rolle eigene Pick- und Ban-Champions festlegen, die automatisch greifen, vielleicht unter auto pick und bann also wenn man das öffnet das da ein dropdown menü hat wo man die rolle auswählen kann und wenn man jungle spielen will macht man sich da ne liste und wenn man dann zufällig doch toplane bekommt wird automatisch die toplane liste genutzt die man auch gemacht hat
>
> wenn man keine runen für den champ selbst gewählt hat soll man einstellen können ob automatisch die runen von lolalytics für den champ genommen werden und auch die einstellungsmöglichkeiten welche lolalytics rank man nimmt welchen patch bzw wie viel tage her wie im screenshot und ob man meistgespielt oder highest winrate will, und natürlich sollte es aber auch ne standard einstellung geben die ist bei rank all ranks letzten 30 tage und most common, die standard einstellung kann man abändern was standard ist quasi und dann soll es einen button geben auto import runes lolalytics für die rolle die ja dann logisch ist weil man die liste ja für eine bestimmte rolle macht und es soll auch auf die beschwörer zauber geguckt werden welche genommen werden und noch für die beschwörer zauber gibt es immer die preferenzen ob man flash auf d oder auf f hat also links oder rechts und die preferenz muss der spieler wo einstellen können damit wenn die beschwörerzauber importiert werden auch nicht das mit dem flash falschrum ist für manche weil lolalytics zeigt flash standardmäßig links also auf d an
> Runen Von Lolalytics: Lass die beliebteste Runenseite direkt aus Lolalytics für den Champion übernehmen statt alles von Hand zu klicken

## Umgesetzt in 2.5

- **Beschwörerzauber zuverlässig:** Nach dem Lock-in wird `PATCH /lol-champ-select/v1/session/my-selection` gesendet und anschließend in der Session **geprüft**, ob der Client die Zauber wirklich zeigt; falls nicht, bis zu 4 Versuche (der Client ignoriert sehr frühe PATCHes). Jeder Versuch steht mit HTTP-Status und Client-Anzeige im Protokoll.
- **Flash auf D oder F:** Einstellungen → „Flash auf“ `D (links)` / `F (rechts)`. Gilt für eigene und importierte Zauber (Lolalytics zeigt Flash standardmäßig links).
- **Zufällig Jungle:** Ist die zugewiesene Rolle Jungle und die gespeicherten Zauber enthalten kein Smite, werden automatisch **Flash + Smite** gesetzt. Im Runen-Fenster gibt es eingeklappt „▸ Zauber, falls zufällig Jungle“, um stattdessen eigene Jungle-Zauber festzulegen.
- **Neue Patches:** Die Runen-/Zauberdaten kommen von Data Dragon und werden täglich auf eine neue Version geprüft (Cache pro Version). Passt eine gespeicherte Runenseite nach einem Runen-Update nicht mehr zum aktuellen Baum, wird sie nicht gesetzt und du bekommst den Hinweis „Runen veraltet – bitte neu wählen“ (Zauber werden trotzdem gesetzt).
- **Rollen-Picklisten:** Unter „Auto-Pick&Ban“ gibt es das Dropdown „Liste für: Alle Rollen / Top / Jungle / Mid / Bot / Support“. Jede Rolle hat eigene Pick- und Ban-Listen; die Auswahl wird gespeichert. In der Champion-Auswahl greift automatisch die Liste der **zugewiesenen Rolle** (Picks und Bans getrennt); hat die Rolle keine Einträge, gilt die Liste „Alle Rollen“. Bad-Matchups bleiben pro Champion.
- **Lolalytics-Runen ohne eigene Wahl:** Einstellungen → „Lolalytics-Runen ohne eigene Wahl“ (Standard AN). Hat der gelockte Champion keine eigenen Runen, werden Runen, Statusrunen und Beschwörerzauber von der Lolalytics-Build-Seite für die zugewiesene Lane geholt. Einstellbar: **Rang** (All Ranks … Unranked wie auf Lolalytics), **Zeitraum/Patch** (7/14/30 Tage oder konkreter Patch), **Build** (Most Common / Highest Win). Standard: All Ranks, 30 Tage, Most Common.
- **Import-Buttons:** „⤓ Lolalytics“ neben dem Rollen-Dropdown importiert Runen + Zauber für alle Champions der angezeigten Liste (Lane = gewählte Rolle, bei „Alle Rollen“ die Standard-Lane des Champions). Im Runen-Fenster importiert „⤓ Von Lolalytics“ nur diesen Champion; danach kannst du anpassen und speichern. Eigene Jungle-Zauber bleiben beim Import erhalten.

# LoL Autopicker 2.5 — Rollen-Listen, Lolalytics-Import, Zauber-Fix (2.4: Runen & Zauber, Deckkraft, Lolalytics-Tabs)

Windows-Python-Programm mit deiner ursprünglichen Oberfläche. Kein Expo, keine Handy-App, kein Konto.

## Neu in 2.4

- **Runen & Beschwörerzauber pro Auto-Pick-Champion:** In jeder Pick-Zeile gibt es neben `…` das Symbol `✦`. Es öffnet ein Fenster im Overlay-Stil mit der Runenwahl wie im Client: Hauptpfad (Schlüsselrune + 3 Reihen), Nebenpfad (2 Runen aus verschiedenen Reihen), 3 Statusrunen und 2 Beschwörerzauber. Gewählte Einträge sind hell mit goldenem Rand, nicht gewählte abgedunkelt; beim Hovern erscheint der Name (plus Kurzbeschreibung). `SPEICHERN` merkt sich die Auswahl in `settings.json` (`loadouts`). Das `✦` leuchtet gold, sobald für den Champion etwas hinterlegt ist. Daten und Symbole kommen von Riot Data Dragon (aktuelle Version, deutsch) und werden einmalig in `%LOCALAPPDATA%\LoLAutopicker\cache` abgelegt – erster Start braucht dafür Internet.
- **Automatisch gesetzt beim Lock-in:** Sobald dein Pick im Client bestätigt ist (egal ob automatisch oder von Hand), legt der Autopicker eine eigene Runenseite „Autopicker <Champion>“ an (ältere Autopicker-Seiten werden ersetzt; sind alle Seiten belegt, wird die älteste eigene Seite ersetzt), aktiviert sie und setzt die beiden Beschwörerzauber (`/lol-perks/v1/pages`, `/lol-perks/v1/currentpage`, `/lol-champ-select/v1/session/my-selection`). Pro Champion-Auswahl passiert das genau einmal, mit HTTP-Status im Protokoll.
- **Deckkraft einstellbar:** In den Einstellungen zwei Regler „Deckkraft Client/Lobby“ (Standard 75 %) und „Deckkraft im Spiel“ (Standard 50 %), 20–100 %. Beim Ziehen siehst du die Wirkung sofort; im Spiel (`InProgress`/`GameStart`/`Reconnect`) gilt automatisch der zweite Wert.
- **Rahmen bei Auto-Bans:** Zu Beginn der Champion-Auswahl bekommen Pick- **und** Ban-Zeilen sofort den grauen Rahmen. Dein eigener bestätigter Ban wird blau, ein nicht mehr bannbarer Champion grün (wie bei den Picks).
- **Schwacher PC Modus repariert:** Das Spiel wird jetzt über das Spielfenster erkannt (`RiotWindowClass` / Titel „League of Legends (TM) Client“), nicht mehr nur über den Prozessnamen, der bei geschütztem Spielprozess nicht lesbar war. Sobald das Spiel in den Vordergrund kommt, werden **nur Lolalytics-Tabs** geschlossen – in allen verbundenen Browsern. Andere Tabs und Fenster bleiben unangetastet. Alt+Shift+4 löst dasselbe manuell aus.
- **Alle Lolalytics-Tabs schließen:** Alt+Shift+3 schließt jetzt jeden Lolalytics-Tab, auch wenn du im Tab einen anderen Champion ausgewählt hast oder den Tab selbst geöffnet hast. Vor dem Schließen wird die letzte URL noch gespeichert; schlägt das fehl, wird der Tab trotzdem geschlossen.
- **Browser nach vorn bei Alt+Shift+1/2:** Die Erweiterung fokussiert Tab und Fenster; zusätzlich holt der Autopicker das Browserfenster per Windows-API (`AttachThreadInput` + `SetForegroundWindow`) vor das Spiel. Im exklusiven Vollbild kann Windows das verhindern – „Randlos“ oder „Fenster“ im Spiel verwenden.
- **Hotkeys im Spiel:** Jeder empfangene Hotkey steht als „Hotkey empfangen: …“ im Protokoll. Kommt Alt+Shift+3 im Spiel nicht an, bitte prüfen, ob League als Administrator läuft (dann müsste der Autopicker ebenfalls als Administrator laufen) und den Logauszug schicken.

## Neu in 2.3

- **Setup.bat installiert Python selbst:** Fehlt Python 3.11+, lädt `Setup.bat` Python 3.12 von python.org herunter (Fallback: `winget`) und installiert es für den aktuellen Benutzer. Danach wird wie bisher die `.venv` angelegt. Eine EXE ist nicht nötig und würde von Virenscannern ohnehin oft gelöscht.
- **Pick-Intent in der Vorauswahl (2.3.1):** In der Phase „Absicht verkünden“ (Timer `PLANNING`) wird ausschließlich die Absicht gesetzt (`PATCH championId, completed=false`) – auch wenn der Client die eigene Pick-Aktion dort bereits als „in Bearbeitung“ meldet; vorher wurde in dieser Phase ein Lock-in versucht, den der Client ablehnt. Wiederholung jede Sekunde, bis die Absicht sichtbar ist. Manuelles Hovern wird nicht überschrieben. Jeder Versuch steht mit Timer-Phase und HTTP-Status im Protokoll.
- **Rahmenfarben nach dem Lock-in:** Ist der eigene Pick bestätigt, bleibt nur dieser blau; alle anderen Auto-Picks werden grau. Vor dem Lock-in zeigen die Rahmen weiterhin gebannt/vergriffen und Bad-Matchup an.

## Update von 2.1 auf 2.2/2.3 — nur Dateien ersetzen

1. Autopicker vollständig beenden.
2. ZIP entpacken und **den Inhalt** des enthaltenen Programmordners in deinen **bisherigen Autopicker-Ordner** kopieren; Dateien ersetzen. `.venv` und `native_manifests` dort behalten.
3. `Start.bat` starten. Kein `Setup.bat`, keine Opera-Neueinrichtung und kein Neuladen der Erweiterung nötig; geändert wurde nur die League-Verbindung (`lolpicker/lcu.py`).

## Was 2.2 an der League-Verbindung ändert

- **Kein Flackern mehr zwischen „Verbunden“ und „Getrennt“.** Vorher beendete jede einzelne fehlgeschlagene oder langsame Anfrage (3-Sekunden-Limit, Keep-Alive-Abbruch durch den Client, 401/403, fehlende WebSocket-Pong-Antworten) die komplette Verbindung. Jetzt werden einzelne Anfragen protokolliert und wiederholt; erst nach vier Fehlschlägen in Folge oder wenn der League-WebSocket wirklich schließt, wird neu verbunden.
- **League schließen und neu starten:** Der Autopicker erkennt den neuen Port und das neue Passwort automatisch (Prüfung alle 1,5 Sekunden) und zeigt in der Zwischenzeit „Getrennt“ mit zurückgesetzter Spielphase.
- **Zugangsdaten wie beim ursprünglich funktionierenden Tool:** zuerst aus der Befehlszeile von `LeagueClientUx.exe` (wie `lcu-driver`), danach aus dem `lockfile` neben dem Client und zuletzt aus `C:\Riot Games\League of Legends\lockfile`.
- **Pick und Ban exakt wie in der ursprünglich funktionierenden Datei (2.2.1):** Solange nichts gehovert ist, wird der geplante Champion jede Sekunde als Pick-Intent gesetzt (manuelles Hovern wird nicht überschrieben). Im eigenen Zug: `PATCH championId + completed=true` → 120 ms warten → `POST …/complete`. Schlägt die Bestätigung fehl, wird jede Sekunde erneut versucht, bis der Client die Aktion als abgeschlossen meldet. Die frühere Vorab-Prüfung über `pickable-champion-ids`, die Picks blockieren konnte, ist entfernt. Jeder Schritt steht mit HTTP-Status im Protokoll.
- Unerwartete Fehler bei der Verarbeitung von Client-Daten beenden den Verbindungs-Thread nicht mehr, sondern landen im Protokoll `%LOCALAPPDATA%\LoLAutopicker\autopicker.log`.

## Update von 2.0 — Opera ist schon eingerichtet

1. Autopicker vollständig beenden.
2. ZIP entpacken und **den Inhalt** des enthaltenen Programmordners in deinen **bisherigen Autopicker-Ordner** kopieren; Dateien ersetzen. `.venv` und `native_manifests` dort behalten. Den bisherigen Ordner nicht verschieben oder umbenennen.
3. In Opera `opera://extensions` öffnen und bei der Autopicker-Erweiterung **Neu laden** anklicken (für 2.4 nötig, weil sich `background.js` geändert hat). Version: **2.5.0**. Kein erneutes ID-Kopieren nötig, solange Ordner und Browserprofil unverändert bleiben.
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

## Schwacher PC Modus (2.4)

Standard: **AUS**. Bei **AN** werden **nur Lolalytics-Tabs** geschlossen, sobald das eigentliche Spiel in den Vordergrund kommt, also auch beim erneuten Reintabben. Im Launcher/Client passiert nichts. Das Schließen läuft über die Browser-Erweiterung in allen verbundenen Browsern; andere Tabs, Fenster oder Prozesse werden nie angefasst. Vorher wird die letzte Lolalytics-URL gespeichert.

Alt+Shift+4 löst denselben Ablauf manuell aus. Alt+Shift+3 schließt alle Lolalytics-Tabs im ausgewählten Browser.

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
| Alt+Shift+3 | Alle Lolalytics-Tabs speichern und schließen |
| Alt+Shift+4 | Lolalytics-Tabs in allen verbundenen Browsern schließen |

In Einstellungen Kürzel anklicken und neue Kombination drücken. ESC bricht die Aufnahme ab. Konflikte werden angezeigt, statt nur die Anzeige zu ändern. Physische Zifferntasten bleiben mit Shift Zifferntasten. Windows kann Alt+Shift selbst zum Sprachwechsel verwenden; bei Konflikten andere Kombination wählen.

## Daten und Grenzen

- `%LOCALAPPDATA%\LoLAutopicker`: `settings.json` (inkl. `loadouts`, `opacity_default`, `opacity_ingame`), `urls.json`, `cache\` (Data-Dragon-Daten und -Symbole), rotierendes `autopicker.log`. `bridge-session.json` enthält einen kurzlebigen lokalen Token und darf nicht weitergegeben werden.
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