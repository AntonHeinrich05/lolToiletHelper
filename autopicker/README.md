# Rückmeldung 3 (nach 2.6.0) → umgesetzt in 2.7.0

> Zauber Vorab Setzen: Setze die Beschwörerzauber schon beim Hovern des Champions, nicht erst nach dem Lock-in · Ban-Import Lolalytics: Lass die meistgebannten Gegner-Champions pro Rolle als Vorschlag für deine Ban-Liste holen, und wenn ein mate einen champ picken will kann man den nicht bannen · bad matchup vorschläge für hardcounter … liste der 5 größten hardcounter und man kann weitere laden … gegen die Viego bei all ranks letzte 30 tage die schlechteste winrate hat, mit der winrate danebenstehend · standard einstellung für lol runen soll all ranks und 30 tage sein statt 7 tage · alt shift 4 funktioniert immer noch nicht, es findet keinen lolalytics tab obwohl ich mit alt shift 3 den schließen kann · unterer rand: ohne den Lolalytics-Button ist unten fast kein Rand, links/rechts dreimal so viel

- **Zauber vorab:** Sobald du einen Champion hoverst (Pick-Intent in der Planungsphase oder Hover in deinem Pick), setzt der Autopicker sofort die Beschwörerzauber (eigene Zauber, bei Jungle Flash + Smite bzw. deine Jungle-Zauber; ohne eigene Runen und mit „Lolalytics-Runen ohne eigene Wahl“ AN die Lolalytics-Zauber). Hinweis im Overlay: „Zauber vorab gesetzt: Viego“. Wechselst du den Hover, werden die Zauber des neuen Champions gesetzt. Die Runenseite wird weiterhin erst beim Lock-in angelegt (sie gilt sonst für den falschen Champion); Lolalytics wird pro Champion-Auswahl nur einmal geladen.
- **⤓ Bans (Lolalytics):** Neben „⤓ Runen“ (bisher „⤓ Lolalytics“) steht jetzt „⤓ Bans“. Es lädt die **meistgebannten Champions der gewählten Rolle** (Lolalytics-Tierlist, Rang/Zeitraum aus deinen Lolalytics-Einstellungen – Standard All Ranks, 30 Tage) als Vorschlagsliste unter deinen Bans: Name + Banrate. **Klick übernimmt** den Champion in die Ban-Liste (bereits enthaltene sind ausgegraut mit ✓), „Mehr laden“ zeigt die nächsten 5, ✕ schließt die Liste. Es wird nichts automatisch eingetragen.
- **Mate will den Champion:** Will ein Mitspieler einen Champion aus deiner Ban-Liste (Hover oder Pick-Intent), wird er beim Bannen **übersprungen** (nächster Ban aus der Liste) und in der Liste **grau mit Hinweis „Mate will – übersprungen“** angezeigt.
- **Hardcounter-Vorschläge:** Im Bad-Matchup-Feld (… an der Pick-Zeile) gibt es „⤓ Hardcounter (Lolalytics)“. Es lädt die Gegner **derselben Lane**, gegen die dein Champion (All Ranks, 30 Tage bzw. deine Lolalytics-Einstellungen) die **schlechteste Winrate** hat – zuerst die 5 schlimmsten, „Mehr laden“ jeweils 5 weitere (bis zu 30). Neben jedem Namen steht **deine Winrate gegen ihn** (rot < 47 %, gelb < 49 %), damit du selbst bewerten kannst; Klick übernimmt ihn in die Bad-Matchups (max. 6). Matchups mit sehr wenigen Spielen werden ausgeblendet, solange genug Daten bleiben.
- **All Ranks + 30 Tage als Standard:** Die Lolalytics-Seiten, die Alt+Shift+1/2 und die Buttons öffnen, tragen jetzt `patch=30` (vorher nahm Lolalytics 7 Tage). Gespeicherte Seiten ohne Zeitraum bekommen 30 Tage ergänzt; Einstellungen mit „7 Tage“ aus älteren Versionen werden einmalig auf 30 Tage gesetzt.
- **Alt+Shift+4 repariert:** „Nur Lolalytics-Tabs“ nutzt jetzt **denselben Erweiterungsbefehl wie Alt+Shift+3** (den jede installierte Erweiterungsversion kennt – auch ohne Neu-Laden) in allen verbundenen Browsern. Ursache: Lolalytics-Seiten tragen das Wort „Lolalytics“ nicht im Fenstertitel („Viego Build, Runes & Counters Guide …“), daher fand der Windows-Fallback nichts, sobald die Erweiterung den neuen Befehl nicht kannte. Der Fallback erkennt jetzt auch Titel mit „Build … Runes“, „Counters Guide“ oder deinem Champion-Namen. Die Antwort der Erweiterung steht im Protokoll.
- **Unterer Rand:** Das Overlay hat jetzt immer einen festen unteren Rand (5 px, passend zu den 4 px links/rechts) – mit und ohne Champion-Zeile/Lolalytics-Button.


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

## Rückmeldung 2 (nach 2.5.1) → umgesetzt in 2.6.0

> die allgemeinen lolalytics einstellungen … auch noch eingeklappt bei jedem champ neben dem lolalytics button … damit man da auch probieren kann wie es für den champ wär mit highest win rate · liste funktioniert noch nicht richtig, es switcht immer auf alle rollen … es soll immer die die ich gerade ausgewählt hab als meine liste nehmen, außer ich habe eine andere rolle bekommen · alt shift 1 öffnet ahri aus „alle rollen“ statt viego aus der jungle-liste · der alle schließen button funktioniert nicht, außerdem sollte man entscheiden können ob wirklich alle browser und tabs geschlossen werden oder nur lolalytics-tabs (spielt mit schwacher pc modus zusammen) · lolalytics runen ohne eigene wahl soll standardmäßig aus sein

- **Lolalytics pro Champion:** Im Runen-Fenster (✦) steht neben „⤓ Von Lolalytics“ der eingeklappte Punkt „▸ Einstellungen“. Aufgeklappt: Rang, Zeitraum/Patch und Build **nur für diesen Champion** (Standard = deine allgemeinen Einstellungen; eigene Werte sind gold markiert, „Standard“ setzt zurück). „⤓ Von Lolalytics“ importiert Runen, Statusrunen **und Beschwörerzauber** mit genau diesen Werten – so probierst du z. B. „Highest Win“ nur für Viego. Die Werte werden mit SPEICHERN am Champion gespeichert und gelten auch beim automatischen Import nach dem Lock-in (falls deine gespeicherten Runen durch ein Runen-Update ungültig wurden).
- **Liste richtig:** Es gilt immer **die Liste, die du im Dropdown gewählt hast** (z. B. Jungle) – in der Lobby, für Alt+Shift+1 (öffnet jetzt Viego, nicht Ahri) und in der Champion-Auswahl. Nur wenn du eine **andere Rolle mit eigener Liste** zugewiesen bekommst, greift diese Liste; hat die zugewiesene Rolle keine eigene Liste, bleibt deine gewählte Liste. „Alle Rollen“ ist nur noch die letzte Reserve, wenn die gewählte Liste leer ist. Das Dropdown springt in der Champion-Auswahl nicht mehr auf „Alle Rollen“, sondern zeigt die wirklich benutzte Liste und kehrt danach zu deiner Wahl zurück.
- **Alles schließen (Alt+Shift+4 / Schwacher PC Modus):** Neue Einstellung „Schließen betrifft“ – **Nur Lolalytics-Tabs** (Standard) oder **Ganze Browser (alle Tabs)**. „Ganze Browser“ schließt jedes Browserfenster per Windows-API (WM_CLOSE, wie das ursprüngliche Tool) und zusätzlich über die Erweiterung. „Nur Lolalytics-Tabs“ läuft über die Erweiterung in allen verbundenen Browsern; findet sie nichts, werden Browserfenster mit „lolalytics“ im Titel per Windows-API geschlossen. Du bekommst jetzt **immer eine Rückmeldung** im Overlay („Lolalytics-Tabs geschlossen: 2“, „Keine Lolalytics-Tabs gefunden – kein Browser verbunden (Erweiterung?)“, …) – vorher kam bei 0 Treffern gar nichts, was wie „funktioniert nicht“ aussah. Wichtig: Nach dem Update die Erweiterung in `opera://extensions` **neu laden** (Version 2.6.0), sonst kennt sie den Befehl „Ganze Browser“ nicht (der Windows-API-Weg funktioniert trotzdem).
- **„Lolalytics-Runen ohne eigene Wahl“ ist jetzt standardmäßig AUS** – auch bei bestehenden Einstellungen aus 2.5 wird es einmalig auf AUS gesetzt (einfach wieder einschalten, wenn gewünscht).

## Prüfung und Ergänzungen in 2.5.1 (Stand 06.10.2026)

Was die vorherige Sitzung in 2.5 gebaut hat, wurde komplett nachgeprüft: Alle 55 Tests liefen grün, der Lolalytics-Abruf wurde **live** gegen die echte Seite getestet (Ahri Mid, Lee Sin Jungle, Aatrox ohne Lane → Top, Caitlyn Bot, Ahri Support; Rang `emerald_plus`; Zeitraum 30 Tage und konkrete Patches 16.19/16.18; Most Common und Highest Win) – Runen, Statusrunen und Zauber kommen korrekt an. Rollen-Dropdown, Rollen-Listen, Runen-Fenster mit eingeklappten Jungle-Zaubern, Einstellungen (Flash auf D/F, Lolalytics-Runen ohne eigene Wahl, Rang, Zeitraum/Patch, Build) sind vorhanden und funktionieren in der simulierten Umgebung. Offen bleibt wie immer der echte Windows-/League-Test durch dich.

Ergänzt in 2.5.1:

- **Beschwörerzauber – weiterer Fix:** Der `PATCH …/my-selection` sendet jetzt zusätzlich die aktuelle `selectedSkinId` (vorher per `GET …/my-selection` gelesen), so wie es das LCU-Schema `ChampSelectMySelection` erwartet. Manche Client-Versionen ignorieren den Zauber-PATCH ohne dieses Feld still – das ist die wahrscheinlichste Ursache für „Zauber werden nicht gesetzt“ in 2.4. Die Verifikation (bis zu 4 Versuche, Abgleich mit der Session) bleibt. Falls es weiterhin nicht klappt: `%LOCALAPPDATA%\LoLAutopicker\autopicker.log` schicken – dort steht pro Versuch HTTP-Status und was der Client anzeigt.
- **Runen-Update → Lolalytics statt Fehlermeldung:** Passen deine gespeicherten Runen nach einem Runen-Update nicht mehr zum aktuellen Baum und „Lolalytics-Runen ohne eigene Wahl“ ist AN, holt der Autopicker die aktuelle Lolalytics-Seite für die zugewiesene Lane (Hinweis „Runen veraltet – Lolalytics-Runen genommen“); deine eigenen Zauber bleiben. Nur bei AUS kommt weiterhin „Runen veraltet – bitte neu wählen“.
- **Overlay folgt der zugewiesenen Rolle:** Bekommst du in der Champion-Auswahl eine andere Rolle als die im Dropdown gewählte, springt das Dropdown automatisch auf die Liste, die wirklich benutzt wird (Rolle mit eigener Liste, sonst „Alle Rollen“) – mit Hinweis im Overlay. So siehst du Rahmenfarben und Reihenfolge der tatsächlich aktiven Liste. Nach der Champion-Auswahl (Lobby/Client) springt es auf deine manuelle Wahl zurück.

# LoL Autopicker 2.6.0 — Rollen-Listen, Lolalytics-Import, Zauber-Fix (2.4: Runen & Zauber, Deckkraft, Lolalytics-Tabs)

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
3. In Opera `opera://extensions` öffnen und bei der Autopicker-Erweiterung **Neu laden** anklicken (für 2.4 nötig, weil sich `background.js` geändert hat). Version: **2.6.0** (für 2.6 **Neu laden nötig**, weil `background.js` den Befehl „Ganze Browser schließen“ bekommen hat). Kein erneutes ID-Kopieren nötig, solange Ordner und Browserprofil unverändert bleiben.
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