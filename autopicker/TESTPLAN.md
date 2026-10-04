# Abnahme auf deinem Windows-PC

Diese Liste trennt implementierte Logik von lokal noch ausstehender Integration. Automatisierte Tests verwenden isolierte Testdaten und simulierte Windows-/Browser-/League-Antworten, keine echte Spielsitzung.

## Priorität 0 — vor produktiver Nutzung

- [ ] `Setup.bat` in Pfad mit Leerzeichen ausführen; `Diagnose.bat` zeigt bei Problemen Fehler.
- [ ] Einmal starten, zweimal Start drücken → nur eine Instanz; beenden → sofort neu startbar.
- [ ] Autopicker vor League starten → verbindet sich nach League-Start.
- [ ] League 5-mal schließen/neu starten, auch während ChampSelect → neuer Port/Zugang erkannt, kein alter Gegner/Ready-Zustand.
- [ ] ReadyCheck mit Auto-Ready AN angenommen, AUS nicht angenommen; wiederholte Ereignisse lösen keine POST-Flut aus.
- [ ] Eigenen Pick und Ban testen; fremde oder bereits fertige Aktionen werden nicht verändert; Team-Hover nicht bannen.
- [ ] Priorität, nicht verfügbare Champions und Bad-Matchup-Fallback in einem zulässigen Testspiel kontrollieren.
- [ ] Alt+Shift+1 mit deutschem Layout bleibt `1`, nicht `!`.
- [ ] Kürzel ändern → nur neues Kürzel aktiv; altes in anderem Programm verwendbar; Neustart behält Änderung.
- [ ] Reserviertes/belegtes/doppeltes Kürzel → sichtbare Ablehnung, keine falsche Aktiv-Anzeige.
- [ ] Je Browser: Erweiterung laden, Native Host registrieren, `ON` abwarten. Chrome, Edge, Firefox separat prüfen; weitere Derivate nur nach erfolgreichem Test als abgenommen markieren.
- [ ] 30-mal schnell dieselbe URL öffnen → ein Tab; andere Itemfilter/Matchups dürfen eigenen Tab erhalten.
- [ ] Item `1_6692` auswählen → Autopicker-Schließen → wieder öffnen → Itemfilter vorhanden.
- [ ] Aatrox → Aatrox-vs-Caitlyn mit `vslane=bottom` → speichern/schließen → vollständig wieder öffnen.
- [ ] Live-Tracking AN: SPA-/History-Änderung wird gespeichert, anderer Champion überschreibt Aatrox nicht.
- [ ] Live-Tracking AUS: Änderungen vor dem Autopicker-Schließen gespeichert; bei nicht schreibbarem Datenordner bleibt Tab offen.
- [ ] Fremde Tabs und Downloads bleiben bei „alle verwalteten Tabs schließen“ unangetastet. Auch nach Navigation eines verwalteten Tabs zu fremder Domain/Champion.
- [ ] Draft-Reihenfolge ungleich Rollenreihenfolge: keine Index-Zuordnung; nach Spielstart VS gemäß eindeutigen Live-Daten angepasst, vorhandene VS-Tabs ohne Fokuswechsel korrigiert.

## Priorität 1 — Neustarts / Belastung

- [ ] Browser-Neustart bei laufendem Autopicker; Autopicker-Neustart bei offenem Browser. Warten bis Verbindung wiederhergestellt, dann öffnen/schließen.
- [ ] Firefox: temporäres Add-on nach Browser-Neustart erneut laden; für dauerhafte Installation Signierung erforderlich.
- [ ] Mehrere Profile: Ziel per Erweiterungssymbol auswählen; keine fremden Profile aktivieren.
- [ ] Autostart aktivieren → Windows neu anmelden → startet; entfernen → startet nicht mehr automatisch.
- [ ] 30 Minuten Task-Manager beobachten: CPU im Leerlauf, RAM im Match, keine steigende Threadzahl, keine wachsenden Logdateien.
- [ ] Netzwerk/Live-Client nicht verfügbar → Hinweis/unbekannte Rolle statt erfundenem Gegner.
- [ ] 1366×768 und Windows-Anzeigeskalierung 125/150 %: Bedienung/Dialogs sichtbar; bei Bedarf Fenstergröße anpassen.
- [ ] Icon in Fenster/Verknüpfung auf heller und dunkler Fläche ohne weißen Außenrand.

## Offen, nicht durch Code garantierbar

- Defender-/SmartScreen-Ergebnis und Ursache der alten Löschung (Erkennungsname fehlt).
- Anti-Cheat-/Riot-Regelkonformität und Verhalten zukünftiger Client-Versionen.
- Echte Lane-Swaps ohne entsprechende Positionsdaten, neue Champions außerhalb der mitgelieferten Namenliste.
- Dauerhafte Firefox-Installation ohne Mozilla-Signierung; unbekannte Browser/Unternehmensrichtlinien.