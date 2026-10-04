# LoL Autopicker 2.0 — Windows-Quellcode

Überarbeitung deines hochgeladenen Python-Autopickers. **Keine Handy-App, kein Account, kein Cloud-Zwang.** Alle League-Zugangsdaten bleiben lokal. Die Browser-Erweiterung kommuniziert ausschließlich mit dem lokalen Python-Programm. Lolalytics selbst ist natürlich eine externe Webseite.

## 1. Wichtig vorab

- **Es gibt keine Garantie, dass Defender oder ein anderes Schutzprogramm die Anwendung nie beanstandet.** Die ursprüngliche Erkennung ist unbekannt. Ohne Schutzverlauf/Erkennungsname lässt sich die Löschursache nicht beweisen.
- Dieses Paket enthält **lesbaren Python-Quellcode**, keine neue ungeprüfte EXE. Windows-Schutzeinstellungen werden weder ausgeschaltet noch umgangen. Es werden keine Defender-Ausnahmen eingerichtet.
- **Windows + echter League-Client müssen lokal abschließend getestet werden.** Linux-Tests können Windows-Hotkeys, Registry, Defender und ein echtes Match nicht bestätigen. Siehe `TESTPLAN.md` und den mitgelieferten Testbericht.
- „Alle Browser“ ist technisch nicht garantiert: Native Messaging/WebExtensions müssen vom Browser unterstützt und zugelassen werden. Unterstützte Integrationswege und Grenzen stehen in Abschnitt 3.
- Die League-Client-Schnittstelle (LCU) ist nicht offiziell für Drittanbieter unterstützt und kann sich ändern. Riot-Regeln können Automatisierung einschränken. Vor Nutzung insbesondere im Ranked aktuelle Riot-Nutzungsbedingungen und Drittanbieterregeln prüfen. Keine Anti-Cheat-Umgehung, Speicherzugriffe oder Eingriffe in laufende Matches.

## 2. Installation und Start

1. Alte Anwendung vollständig beenden. In `Win + R` → `shell:startup` den bisherigen `LoLHelper.bat`-Autostart prüfen und bei Bedarf selbst entfernen. **Nicht zwei Versionen parallel betreiben.** Alte Dateien zunächst sichern.
2. ZIP vollständig an einen **dauerhaften benutzereigenen Ort** entpacken, z. B. `C:\Users\DEINNAME\Tools\LoL-Autopicker-2.0`. Nicht direkt aus dem ZIP starten; nach Einrichtung Ordner nicht verschieben. Nicht als Administrator ausführen.
3. Python **3.11 oder neuer**, vorzugsweise 3.12/3.13, von https://www.python.org installieren, einschließlich Tkinter und Python Launcher (`py`).
4. Optional vor dem ersten Start `lolhelper_config.json` und `lol_tool_state.json` aus dem alten Programmordner neben `Autopicker.py` kopieren. Pick-/Ban-Listen, Bad-Matchups, gültige Hotkeys und gespeicherte URLs werden einmalig übernommen. Die Originaldateien werden nicht überschrieben. Fehlerhafte `Alt+Shift+exclam`/`!` werden zu `Alt+Shift+1` migriert. Doppelte/ungültige Kürzel werden deaktiviert und können neu gesetzt werden.
5. `Setup.bat` doppelklicken. Es erstellt `.venv` und installiert `aiohttp` + `psutil` über pip. Internet ist nur für diesen Download nötig. Keine Administratorrechte.
6. `Start.bat` startet ohne Konsolenfenster. Bei Startproblemen `Diagnose.bat` verwenden. Doppelte Starts werden durch eine Single-Instance-Sperre verhindert.
7. Browser-Erweiterung und Native Host wie unten einrichten. League darf vor oder nach dem Autopicker gestartet werden.
8. Autostart **freiwillig** mit `Autostart_aktivieren.bat` aktivieren. Eine normale, sichtbare Verknüpfung wird für deine Windows-Anmeldung erstellt. Mit `Autostart_entfernen.bat` wieder entfernen. Das ist Benutzer-Anmeldung, kein Windows-Systemdienst.

**Persistente Daten:** `%LOCALAPPDATA%\LoLAutopicker`

| Datei | Inhalt |
|---|---|
| `settings.json` | Pick/Ban, Bad-Matchups, Hotkeys, Optionen, Browserauswahl |
| `urls.json` | Letzte Lolalytics-Seiten je Champion/Modus/Aufrufart und Matchup |
| `autopicker.log` | Rotierende Diagnosen, max. ca. 1,5 MB insgesamt |
| `bridge-session.json` | Zufälliger lokaler Port + Sitzungs-Token; nicht weitergeben |

Die Anwendung beschränkt den Datenordner per Windows-Dateirechten auf deinen Benutzer und SYSTEM. Der Bridge-Token wird pro Start erneuert; beim sauberen Beenden wird die Sitzungsdatei entfernt. Programme unter demselben Windows-Benutzer sind dadurch nicht gegeneinander isoliert.

## 3. Browser — Installation, Auswahl, Grenzen

### Chrome, Microsoft Edge, Brave, Vivaldi, Opera / Opera GX

1. Browser-Erweiterungsverwaltung öffnen:
   - Chrome/Brave: `chrome://extensions` / `brave://extensions`
   - Edge: `edge://extensions`
   - Vivaldi: `vivaldi://extensions`
   - Opera: `opera://extensions`
2. **Entwicklermodus** der Erweiterungsverwaltung aktivieren. Das ist für eine lokal entpackte Erweiterung nötig und schaltet Windows-Schutz **nicht** ab.
3. **Entpackte Erweiterung laden** → Ordner `extension\chromium` auswählen.
4. Die 32-stellige **Erweiterungs-ID** kopieren.
5. `Browser_Bridge_installieren.bat` starten → `1` → ID einfügen. Für mehrere Browser-/Profil-IDs wiederholen oder durch Kommas trennen. Die registrierten IDs bleiben erhalten.
6. Autopicker starten, Erweiterung in der Verwaltung einmal neu laden. Auf das Erweiterungssymbol klicken. `ON` zeigt die Verbindung; ein weiterer Klick wählt diesen Browser als Ziel (`OK`).

Chrome und Edge haben eigene Registrypfade. Das Skript registriert außerdem Chromium- und gängige Herstellerpfade; kompatible Derivate können auf den Google/Chromium-Pfad zurückgreifen. Ob ein Derivat Native Messaging und entpackte Erweiterungen erlaubt, hängt von seiner Version und eventuellen Unternehmensrichtlinien ab. **Brave, Vivaldi und Opera sind hier nicht mit einer echten Windows-Installation abgenommen.** Eine unbekannte Variante erhält keine scheinbar funktionierende Fenster-/Tastatursimulation als Ersatz.

### Firefox

1. `about:debugging#/runtime/this-firefox` → **Temporäres Add-on laden** → `extension\firefox\manifest.json` auswählen.
2. `Browser_Bridge_installieren.bat` → `2` (Firefox).
3. Autopicker starten, Add-on neu laden und Erweiterungssymbol anklicken.

**Wichtig:** Temporäre Firefox-Add-ons verschwinden beim Browser-Neustart. Für dauerhaft saubere Nutzung muss diese Erweiterung über Mozilla signiert werden (auch eine **nicht gelistete** signierte Verteilung ist möglich). Das hier mitgelieferte Add-on ist **nicht signiert**. Die feste Add-on-ID lautet `lolautopicker@local.invalid`. Keine Anleitung zum Abschalten der Firefox-Signaturprüfung. Hinweise: https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/

### Mehrere Browser / Profile

- Jede Erweiterungsinstallation hat eine eigene Kennung. Über ihr Symbol kann sie sich selbst als Zielbrowser auswählen. Alternativ: im Autopicker Einstellungen öffnen und einen verbundenen Browser auswählen. Nach neuer Verbindung Einstellungen erneut öffnen, um die Liste zu aktualisieren.
- „Automatisch“ funktioniert nur, wenn **genau ein** Browserprofil verbunden ist. Mehrdeutige Ziele werden nicht geraten.
- Duplikate werden innerhalb des **ausgewählten Browserprofils** verhindert, nicht browserübergreifend. Derselbe Link kann bewusst in zwei unterschiedlichen Browsern existieren.
- Einen geschlossenen Browser zuerst normal öffnen. Die Erweiterung verbindet sich dann erneut; die Anwendung startet nicht ungefragt andere Browser oder neue Fenster.
- Im Inkognito-/Privatmodus wird die Integration nicht als unterstützter Standardbetrieb vorgesehen. Separate Profile, Richtlinien und Berechtigungen können abweichen.

### Nicht unterstützt

Safari unter Windows (keine aktuelle unterstützte Version), mobile Browser, Browser ohne WebExtensions/Native Messaging und durch Unternehmensrichtlinien gesperrte Erweiterungen. **„Jeder Browser garantiert“ wäre eine falsche Zusage.** Die gemeinsame Browser-API ersetzt jedoch die bisher sprach- und browserspezifische Adressleisten-Erkennung vollständig.

### Berechtigungen / Datenschutz

Die Erweiterung nutzt `nativeMessaging`, `storage`, `webNavigation`, `alarms` und Host-Berechtigungen ausschließlich für Lolalytics. Sie benötigt keine allgemeinen `tabs`-/Verlaufsrechte, liest keine Passwörter, nutzt keine Zwischenablage und injiziert keine Skripte in Lolalytics. `webNavigation` ist eine weitreichende Browserberechtigung; die Handler filtern ausdrücklich auf Lolalytics und Hauptframes. An Python werden nur passende Champion-URLs und die lokale Browserkennung übertragen.

## 4. Bedienung

### Auto-Pick & Ban

- Champions über das Suchfeld oder die Vorschlagsliste hinzufügen. Mit Pfeilen Priorität ändern, mit × entfernen.
- Der erste verfügbare Pick ohne einen deiner Bad-Matchup-Konflikte wird bevorzugt. Falls alle konfliktbehaftet sind, wird der erste verfügbare Pick genommen.
- Einen Pick markieren → **Bad Matchups für ausgewählten Pick** → bis zu 6 Gegner markieren → speichern. Filtern behält die Auswahl bei.
- Auto-Ban nimmt den ersten verfügbaren Ban, schützt dabei auch die von Teammitgliedern gehoverten Champions.
- Die Anwendung prüft die LCU-Listen der tatsächlich pick-/bannbaren Champions. Schlagen diese Abfragen fehl, wird **nicht blind gelockt**.
- PATCH setzt `completed: false`; `/complete` erfolgt erst nach erneuter Prüfung einer **eigenen aktiven** Aktion. Die alte Vorwahl hat bereits `completed: True` außerhalb des eigenen Zuges gesetzt; dieses unsichere Verhalten wurde entfernt. Es wird jetzt nur im eigenen aktiven Zug gewählt.

### Auto-Ready und Wiederverbindung

- LCU-WebSocket-Ereignisse lösen Ready-Accept direkt nach Empfang aus. Kein mehrsekündiger Poll-Takt im Hauptweg. Bereits beantwortete Anfragen und doppelte Ereignisse werden abgefangen.
- Fallback-Abgleich: 0,5 Sekunden in ReadyCheck/ChampSelect, sonst 5 Sekunden. Verbindungsaufbau sucht den Client mit moderatem Backoff. **Null Millisekunden / garantierte Sofortreaktion** kann niemand zusagen: Windows, Client und Netzwerkzugriffe brauchen Zeit.
- Nach Verbindungsende wird das Lockfile samt Port und Zugang erneut eingelesen, statt endlos eine tote Verbindung zu verwenden. Bei ungewöhnlicher Installation vollständigen Lockfile-Pfad in Einstellungen angeben.
- Startet League mit anderen Benutzer-/Administratorrechten, kann die Erkennung scheitern. Normalerweise beide im selben Benutzerkontext ohne Administratorrechte starten.

### Tastenkürzel

| Standard | Aktion |
|---|---|
| Alt + Q | Overlay ein-/ausblenden |
| Alt + Shift + 1 | Lolalytics öffnen / passenden bestehenden Tab aktivieren |
| Alt + Shift + 2 | VS-Matchup öffnen |
| Alt + Shift + 3 | Verwalteten Tab speichern, dann schließen |
| Alt + Shift + 4 | Alle verwalteten Lolalytics-Tabs in verbundenen Profilen speichern und schließen |

Einstellungen → Kürzel anklicken → Kombination drücken. Erfassung verwendet Windows-**Virtual-Key-Codes**, deshalb bleibt Shift+1 die physische Ziffer 1. Neue Kürzel werden direkt mit `RegisterHotKey` registriert. Konflikte werden angezeigt; die Oberfläche behauptet nicht stillschweigend eine erfolgreiche Änderung. Kein `pynput`-Hook, keine künstlichen Tastendrücke. ESC bricht ab. F12 ist unter Windows reserviert. Bei deutschem Layout kann Windows selbst Alt+Shift zum Sprachwechsel nutzen; bei Konflikten eine andere Kombination wählen. Globale Kürzel können im exklusiven Vollbild oder durch andere Anwendungen eingeschränkt sein.

### Lolalytics: Duplikate und Speichern

- Identische normalisierte URL → vorhandenen Tab aktivieren. Abweichende Item-/Runenparameter, Gegner oder Pfade → eigener Tab zulässig. Parameterreihenfolge und abschließender Slash allein erzeugen keinen zweiten Tab.
- Öffnen wird serialisiert; wiederholte Anfragen werden bis zur Bestätigung zusammengefasst. Kein `--new-window`, kein Fenster-Titel-Raten, keine Clipboard-Manipulation.
- **Live-Tracking an:** URL-Änderungen passender Champion-Seiten, einschließlich History/SPA-Navigation, werden ereignisbasiert gespeichert. Der Wechsel von `aatrox/build/?item=1_6692` zu `aatrox/vs/caitlyn/build/?vslane=bottom` bleibt erhalten. Ein anderer eigener Champion überschreibt Aatrox nicht. Aktive, gleiche Champion-Seiten in manuell geöffneten Tabs können ebenfalls gespeichert werden; sie werden dadurch nicht zu verwalteten Tabs.
- **Live-Tracking aus:** Der Autopicker-Schließen-Befehl liest die aktuelle Tab-URL, wartet auf erfolgreiches Schreiben auf die Festplatte und schließt **erst danach**. Bei Speicher-/Verbindungsfehler bleibt der Tab offen.
- Nativer Browser-Schließknopf/Ctrl+W: Die letzte vom Browser gemeldete URL kann noch gespeichert werden. Bei sofortigem Browserabsturz, Stromausfall oder gleichzeitigem Navigieren/Schließen ist die letzte Änderung **nicht garantiert**. Für garantierten Bestätigungsablauf den Autopicker-Hotkey verwenden.
- Der Basis-Button setzt die letzte Seite desselben Champions/Modus fort, auch eine manuell gewählte VS-Seite. Der VS-Button wählt dagegen den ermittelten Gegner und übernimmt nur passende gespeicherte Matchup-Daten.
- „Alle Browser schließen“ wurde bewusst in **„Alle verwalteten Tabs schließen“** geändert. Keine fremden Fenster, Downloads oder privaten Tabs werden zwangsweise beendet. Der Sparmodus verwendet denselben sicheren Ablauf **einmal bei Spielstart**, nicht bei jedem Alt-Tab. Der Browserprozess bleibt ggf. mit anderen Tabs/Erweiterungen aktiv; eine feste RAM-Ersparnis wird nicht behauptet.

### Gegner nach Pick/Ban

- In der Auswahlphase nur bei einer eindeutigen zugewiesenen gleichen Rolle: Anzeige **vorläufig**. Keine Annahme aus Pick-Reihenfolge, Teamindex oder `cellId`.
- Nach Spielstart/Loading werden lokale Live-Client-Daten abgefragt. Aktiver Spieler wird über Riot-ID/Summoner-Identität bestimmt, Gegner über gegnerisches Team und gleiche verfügbare Position.
- Bei eindeutiger Zuordnung wird VS aktualisiert. Bereits über den **VS-Button** verwaltete Tabs werden ohne Fokuswechsel angepasst; Itemfilter bleiben erhalten. Eine bewusst manuell gewählte VS-Seite eines Basis-Tabs wird nicht ungefragt ersetzt.
- Bei fehlenden Rollen, mehreren Treffern, ARAM oder Arena wird kein Gegner erfunden. Auch Live-Client-Positionen garantieren keine **tatsächlichen Lane-Swaps** im Spiel.
- Die optionale statistische Pickraten-Vorhersage wurde wie von dir erlaubt **weggelassen**: keine erfundenen Wahrscheinlichkeiten und kein fragiles Scraping als vermeintlich verlässliche Schnittstelle.

## 5. Windows-Warnung / verschwundene EXE

### Was verbessert wurde

- Quellcode-Start mit regulärem Python statt gepackter unbekannter Onefile-EXE.
- Keine globalen Keyboard-Hooks, keine simulierten Eingaben, kein aggressives `AttachThreadInput`, keine COM-Adressleisten-Abfragen, keine Browser-Prozessbeendigung.
- Autostart nur nach bewusster Einrichtung, sichtbar und rückgängig machbar.
- Klar getrennte Module, nachvollziehbare Abhängigkeiten, kleiner lokaler Bridge-Dienst ohne Internet-Listener.

Das **kann** einige Auslöser für Fehlalarme reduzieren, ist aber **kein Beweis für die ursprüngliche Ursache und keine Erkennungsgarantie**. Defender-Signaturen, Heuristiken, Software-Reputation und Unternehmensrichtlinien liegen außerhalb dieser Anwendung.

### Wenn wieder etwas verschwindet

1. **Windows-Sicherheit → Viren- & Bedrohungsschutz → Schutzverlauf** ansehen.
2. Erkennungsname, betroffene Datei, Zeitpunkt und die Aktion notieren; bei anderen Schutzprogrammen deren Quarantäne-/Ereignisverlauf prüfen.
3. Nicht blind wiederherstellen, nicht Schutz deaktivieren, keine pauschale Ordnerausnahme setzen. Zuerst Herkunft und Befund prüfen.
4. Bei nachvollziehbarem Fehlalarm eine Prüfung beim Hersteller beantragen. Microsoft: https://www.microsoft.com/en-us/wdsi/filesubmission
5. SmartScreen („unbekannter Herausgeber“) und Malware-Quarantäne sind verschiedene Dinge. Ohne genaue Meldung lässt sich die passende Maßnahme nicht sicher auswählen.

Falls später wieder eine EXE gewünscht ist: separat auf Windows sauber bauen, nachvollziehbare Versionen und Herausgeberinformationen verwenden, nicht obfuskieren/packen, idealerweise mit vertrauenswürdigem Code-Signing signieren. Auch Signieren garantiert keine Warnungsfreiheit. **Dieses Paket enthält keine als geprüft ausgegebene Windows-EXE.**

## 6. Performance und Grenzen

- Netzwerk und Browserbefehle laufen nicht im Tk-Hauptthread.
- Begrenzte UI-/Befehlsqueues, nur ein Browserbefehls-Worker, keine neue Thread-Flut pro Tastendruck.
- WebSocket statt schnellem Dauerscannen des kompletten Clients; Live-Client-Polling nur während GameStart/InProgress/Reconnect, nach Erkennung alle 10 Sekunden.
- Browser-URL-Tracking ereignisbasiert, keine dauernde DOM-/Adressleisten-/Prozesssuche. Host wartet blockierend auf Nachrichten. Verbindungsversuche bei beendetem Autopicker werden bis auf 30 Sekunden ausgedünnt; Browser-Alarm maximal einmal pro Minute als Neustarthilfe.
- Atomare Schreibvorgänge, keine wiederholten Festplattenwrites für unveränderte URLs. Logrotation begrenzt Plattenverbrauch.
- Mehrere Browserprofile bedeuten mehrere kleine Python-Native-Host-Prozesse. Für schwache Laptops nur das genutzte Profil verbinden.
- Keine belastbare CPU-/RAM-/Akkugarantie ohne Messung auf deinem Laptop. Testszenario in `TESTPLAN.md`.
- Champion-Namenliste aus deiner Datei übernommen (172 Namen). Neue Champions bei Bedarf in `assets/champions.json` ergänzen. Keine unbemerkten Hintergrunddownloads.

## 7. Aufbau und Wartung

```text
Autopicker.py                Startpunkt
lolpicker/
  lcu.py                    Discovery, WebSocket, Ready/Pick/Ban
  selection.py              Reine Auswahl- und Gegnerlogik
  live.py                   Live-Client-Abgleich
  hotkeys.py                Native Windows-Kürzel
  bridge.py, protocol.py    Lokale authentifizierte Browser-Verbindung
  urls.py, storage.py       URL-Regeln, atomare Einstellungen
  controller.py             Koordination und begrenzte Worker-Queue
  ui.py, settings_ui.py     Tk-Oberfläche
  platform_win.py           Einzelinstanz, Dateirechte
native_host.py/.bat          Native-Messaging-Adapter
install_browser.py          Explizite HKCU-Registrierung / Entfernung
autostart.py                Sichtbare Startup-Verknüpfung
extension/chromium/         Chromium MV3
extension/firefox/          Firefox MV2 (Signatur für Dauerbetrieb nötig)
extension/shared/           Gemeinsame Browserlogik
assets/                     Transparentes PNG, ICO, Champion-Namen
tests/                      Automatisierte Regressionstests
```

Entwicklungstests: `.venv\Scripts\python.exe -m pip install ".[test]"` und `.venv\Scripts\python.exe -m pytest -q`. JavaScript-Tests benötigen optional Node.js; sie sind kein Bestandteil des normalen Starts. Gemeinsames `background.js` nach Änderungen in beide Browserordner kopieren und Erweiterungen neu laden.

Deinstallation: Autopicker beenden → Autostart entfernen → Browser-Bridge entfernen → Erweiterungen in den Browsern löschen → Programmordner löschen. Den Datenordner nur löschen, wenn Einstellungen/URLs ebenfalls weg sollen.

## 8. Quellen

- Riot Live Client API: https://developer.riotgames.com/docs/lol#game-client-api
- LCU-WebSocket: https://hextechdocs.dev/getting-started-with-the-lcu-websocket/
- Chrome Native Messaging: https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- Firefox Native Messaging: https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Native_messaging
- Windows RegisterHotKey: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey
- Microsoft Fehlalarm-Prüfung: https://www.microsoft.com/en-us/wdsi/filesubmission

League of Legends und Lolalytics gehören ihren jeweiligen Rechteinhabern; dieses Tool ist keine offizielle Riot-Anwendung.