# Testergebnis — 04.10.2026

## Automatisiert bestanden

- **33 Python-Tests**, einschließlich echter lokaler Socket-/Native-Host-Protokolltests und Tk-Oberflächeninteraktionen unter Xvfb.
- **5 JavaScript-Tests** der produktiven Erweiterungslogik in einer Node-VM mit simulierten WebExtension-APIs.
- Python-Kompilierung und JavaScript-Syntaxprüfung ohne Fehler; Produktionsmodule ohne gemeldete Lintfehler.

Geprüfte Bereiche: Konfigurationsmigration, Speichern/Schreibfehler, Kürzelwechsel/Rollback, eigene Windows-Nachrichtenthread-Zuständigkeit, Shift-Ziffern-Normalisierung, URL-Deduplizierung, Item-/VS-Parameter, Bad-Matchups, Active-Action-Schutz, Ready-Accept-Deduplizierung, LCU-Neuverbindung mit geänderten Zugangsdaten, ARAM-Filter, lokale Bridge-Authentifizierung, Native-Messaging-Framing, Speicherbestätigung vor Schließen, Tab-Eigentum über Service-Worker-Neustarts, sichtbare Status-/Fehlerhinweise.

## Testgrenzen

**SIMULIERT:** Win32-Aufrufe, League-HTTP/WebSocket-Antworten und Browser-API-Antworten wurden für diese Tests durch kontrollierte Testimplementierungen ersetzt. Diese Tests prüfen die Programmlogik, **nicht** die gesamte Integration auf einem echten Windows-PC. Die produktive Anwendung selbst enthält keine vorgetäuschten League-/Browser-Antworten.

**Nicht hier abgenommen:** echte WM_HOTKEY-Zustellung durch Windows, Registry-/Startup-Einrichtung, League-/Riot-Versionskompatibilität, native Messaging-Registrierung in echten Windows-Browsern, Firefox-Dauersignierung, Defender/SmartScreen, Leistungsdaten deines Laptops und tatsächliche Lane-Swaps.

Die manuelle Abnahme steht in `TESTPLAN.md`. Keine Zusage „Defender wird nie löschen“ oder „jeder Browser funktioniert garantiert“.

## Tests erneut ausführen

```bat
.venv\Scripts\python.exe -m pip install ".[test]"
.venv\Scripts\python.exe -m pytest -q
node --test tests\test_extension_background.js
```

Node.js nur für die JavaScript-Tests erforderlich. Bild-/Screenshot-Test kann ohne zusätzlich installiertes Pillow übersprungen werden. Linux-Tk-Tests benötigen einen laufenden X-Server/Xvfb.