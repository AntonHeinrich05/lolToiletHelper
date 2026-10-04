# Testergebnis — Version 2.3.1

**45 Python-Tests und 7 Browserlogik-Tests bestanden.**

Neu in 2.2 geprüft (simulierter League-Client mit echtem HTTPS- und WebSocket-Server auf Loopback): Verbindung bleibt stabil, obwohl der Server keine WebSocket-Pongs sendet und beim Start mit HTTP 500 antwortet; Trennung und automatische Neuverbindung nach League-Neustart mit neuem Port und neuem Passwort; Auto-Accept über WebSocket-Ereignis genau einmal; Pick-Intent in der Planungsphase, Auto-Ban im eigenen Zug, Auto-Pick mit Bad-Matchup-Ausweichen und Lock-in; fehlgeschlagene Bestätigung wird bis zum Erfolg wiederholt. Zugangsdaten-Suche über `LeagueClientUx.exe`-Befehlszeile, Lockfile-Fallback und veraltete Lockfiles.

# Testergebnis — Version 2.1

**36 Python-Tests und 7 Browserlogik-Tests bestanden.**

Neu geprüft: Original-Tk-Oberfläche und Einstellungen, fünf Suchvorschläge, Enter-Auswahl, Drag-and-drop-Speicherung, Bad-Matchup-Feld, Hotkey-Rollback, Schwacher-PC-Auslösung sowie neue persistente Browser-Brücke.

NativeRelay wurde als echter lokaler Unterprozess mit echten Loopback-Sockets getestet: Browser-Handshake vor Desktopstart, anschließender Bridge-Start, neue Sitzung mit anderem Token/Port, Wiederverbindung im selben Hostprozess. Im letzten lokalen Lauf: **0,252 Sekunden beim Erststart, 0,251 Sekunden bei der Wiederverbindung**. Der Regressionstest verlangt unter 4 Sekunden beim verzögerten Erststart und unter 2,5 Sekunden beim Bridge-Neustart; das ist keine Leistungsgarantie für jeden Windows-PC.

Die produktive Erweiterungslogik lief in Node mit simulierten Browser-APIs. Win32-Hotkeys, Fenster-Schließaktionen und League-API-Antworten wurden dort, wo die Linux-Testumgebung sie nicht bereitstellt, ebenfalls simuliert. Die produktive Anwendung verwendet reale Schnittstellen.

Nicht auf echter Hardware abgenommen: Windows-Transparenz/Skalierung, native Tastenkürzel, echtes Browserfensterschließen und Riot-/League-Verhalten. Opera-Erweiterung funktioniert laut Rückmeldung des Nutzers bereits in Version 2.0. Die neue Fassung benötigt noch dessen Windows-Praxistest.

Python-Kompilierung, JavaScript-Syntax und Lintprüfungen ohne gemeldete Produktionsfehler. Hinweise für die Windows-Abnahme stehen in `TESTPLAN.md`.