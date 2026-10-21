# Phase 3 — Cleanup und Produktkatalog

Stand: 16.10.2026, Europe/Zurich. P0 und P1 sind lokal umgesetzt und getestet. Die Root-README bleibt wie gewünscht zurückgestellt. Kein Commit, Push, DB-Reset oder Löschen produktiver Volumes.

## Ergebnis

Eine Anwendung, ein Prefect-Flow, drei Compose-Services. Der normale Einstieg ist `python -m backend.flow` für `init`, `initial`, `daily`, `replay`, `verify`, `catalog` und `serve`. Die bisherigen 18 Scraper- und 20 Pipeline-Tests sind weiter enthalten; sieben Katalogtests ergänzen sie. Alle 45 Tests bestehen.

Der Bestand wuchs von 6 Produkten / 6 Angeboten / 10 Beobachtungen zu Beginn dieser Phase auf **9 Produkte / 9 Angebote / 16 echte Preisbeobachtungen**. Die Phase-2-Zahl von 7 Beobachtungen war ein historischer Stand: Ein nächtlicher Lauf hatte inzwischen drei weitere gespeichert. Dieser Nachtlauf hatte zwei Netzwerkfehler und endete **FAILED**, nicht vollständig erfolgreich. Die neuen Phase-3-Läufe INITIAL, DAILY und REPLAY wurden erfolgreich abgeschlossen.

## Aktive Struktur

```text
backend/
  flow.py                     # CLI und genau ein Flow: Collect → Transform → Load
  database.py                 # Verbindung, bestehende Migrationen, DB-Katalog, Verifikation
  transform.py                # Validierung, Normalisierung, belegte Legacy-Kompatibilität
  ingestion.py                # Produkte/Angebote/Preisbeobachtungen, Transaktionen
  retailers/mediamarkt/
    collector.py              # HTTP, robots, URL-Auswahl, Batch, optionale Discovery
    parser.py                 # Bestehendes JSON-LD-/Technik-Parsing
    scope.json                # Fachlicher GPU-/RAM-/SSD-Scope
  tests/                      # Alle 45 Tests und erhaltene HTML-Fixtures
  Dockerfile
  requirements.lock           # Ein gepinnter Python-Abhängigkeitsstand
data/
  catalog/mediamarkt_initial.json  # Explizite Auswahl: drei URLs pro Kategorie
  catalog/mediamarkt.json          # Bestehende Discovery-/Abrufinformationen
  raw/mediamarkt/                  # Unveränderte Originale und neue echte Beobachtungen
  debug/                          # HTML-Belege; alte Sperrseiten unter legacy/
  initialization.sql
  migrations/002_midterm.sql       # In Phase 3 unverändert
  queries/verification.sql
docs/
  RUN_COMMANDS.md
  ARCHITECTURE.md
  MEDIAMARKT.md
  PHASE2.md, PHASE3.md
  evidence/phase2/, evidence/phase3/
  archive/phase1-code.tar.gz       # Passiver früherer Code, nicht importiert/ausgeführt
frontend/                         # Bestehendes Svelte-Projekt, unverändert optional
```

Sechs Produktions-/Adapter-Python-Dateien statt zuvor neun Dateien im MediaMarkt-/Pipeline-/Orchestrierungsbereich einschliesslich Debug-Helfer, zuzüglich der entfernten Wrapper und des losen Archivcodes. Keine neue Datenbankmigration. Weitere Händler können später als Adapter hinzukommen; deren tatsächliche Datenformate müssen dann ausdrücklich in Validierung/Ingestion aufgenommen werden. Es gibt keine erfundene generische Händlerunterstützung.

## Cleanup und Wiederherstellung

Vor Änderungen: Git-Status, Diff zu HEAD und staged Diff gesichert. `before.tar.gz` im Chat-Arbeitsordner `work/phase3/` wurde dateiweise gegen den Checkout geprüft. Der PostgreSQL-Dump `before.dump` ist mit `pg_restore --list` lesbar; er wurde nicht über die Projektdatenbank zurückgespielt. Originale Daten, Fixtures und SQL-Nachweise bleiben erhalten. Die bereits vorher gestagte Löschung von `dummy_flow.py` stammt nicht aus diesem Cleanup. Vorhandene Änderungen an PyCharm-Konfiguration und Frontend-Lockfile wurden nicht überschrieben.

Die vollständigen Einzelpfade mit Löschgründen und Verschiebungen stehen in [cleanup.json](../evidence/phase3/cleanup.json).

| Entfernt / zusammengefasst | Begründung / Ersatz |
|---|---|
| `ingestBrack/`, `ingestInterdiscount/`, `seedDatabase/`: jeweils `app.py`, `Dockerfile`, `requirements.txt` | Leere Programme/Dependencies und `top`-Container; keine aktiven Aufrufer |
| `ingestDigitec/`, `scrapeDigitec/`: jeweilige Python-/Docker-/Dependency-Dateien | Inaktive Hinweise statt aktiver Datenquelle; kein autorisierter Digitec-Zugang |
| `ingestMediamarkt/`: drei Dateien | Reine Weiterleitung; `backend.flow replay` ist der direkte Einstieg |
| `scrapeBrack/`, `scrapeInterdiscount/`: Python-/Docker-/Dependency-Dateien | Kopierte Digitec-HTTP-Experimente, keine Händlerimplementierungen; HTML-Belege separat erhalten |
| Alter MediaMarkt-Dockerfile und `requirements.txt` | Gemeinsames Image und einziges Lockfile |
| `scrapeMediamarkt/inspect.py` | Nicht importierter Debug-Ausdruck; Roh-HTML und Parser bleiben erhalten |
| Einzelprodukt-CLI und zusätzliche Abruf-/Schreibfunktionen im alten Parser | Zweiter Ausführungspfad entfällt; ein Collector übernimmt HTTP und Raw-Schreiben; Parsing-Funktionen erhalten |
| `orchestrator/Dockerfile` | Nicht in Compose verwendet; enthielt einen zweiten unvollständigen Build |
| `backend/requirements.txt` | Weiterleitete nur zum Lockfile; Docker nutzt direkt das Lockfile |
| Leere `backend/README.md`, `data/README.md` | Keine Inhalte; aktuelle Anleitung zentral unter `docs/` |
| Lose Dateien unter `backend/legacy/phase1/` | Geprüft in einem passiven Archiv erhalten, nicht mehr im aktiven Python-Baum |
| `pipeline/contracts.py` + `pipeline/transform.py` | Zusammengeführt zu `backend/transform.py` |
| `pipeline/db.py` + Verifikation aus `pipeline/cli.py` | Zusammengeführt zu `backend/database.py`; CLI-Befehle in `backend/flow.py` |
| Leeres `pipeline/__init__.py` und leere alte Ordner | Alte Paketstruktur nicht mehr verwendet |

Verschoben: MediaMarkt `app.py` → `parser.py`, `pipeline.py` → `collector.py`, Scope in den Adapterordner; Scraper-Tests und acht HTML-Fixtures nach `backend/tests/`; Scraper-README nach `docs/MEDIAMARKT.md`; `pipeline/ingest.py` → `backend/ingestion.py`; Flow nach `backend/flow.py`; drei alte Händler-Sperrseiten nach `data/debug/legacy/<alter Ordner>/`. Die übrigen Pipeline-Tests liegen ebenfalls unter `backend/tests/`. Details und erhaltene Inhalte stehen im Cleanup-Nachweis.

Ein zusätzlicher Konfigurationsfehler wurde ohne Datenbankänderung behoben: Laufende Container nutzten `admin`, `.env` enthielt inzwischen `POSTGRES_USER=deng`. Frisch gestartete Testcontainer konnten daher nicht authentifizieren. Nur `.env` wurde wieder auf den vorhandenen Benutzer abgestimmt; keine Rolle und kein Passwort verändert. Die ursprünglichen DB-Testfehler waren damit behoben.

## Dienste und Datenfluss

| Service | Aufgabe | Persistenz / Erreichbarkeit |
|---|---|---|
| `postgres` | Fachliche Datenbank | Bestehendes `postgres_data`, localhost:5432, Healthcheck |
| `prefect_server` | Laufverwaltung und Scheduling | Bestehendes `prefect_data`, localhost:4200, API-Healthcheck |
| `pipeline` | Flow manuell ausführen oder Schedule bedienen | Datenverzeichnis gemountet; gemeinsames Compose-Netzwerk |

Images werden nativ gebaut; Linux/ARM64 ist geprüft, keine erzwungene amd64-Emulation. Python-Pakete bleiben im vorhandenen Lockfile gepinnt, einschliesslich der in Phase 2 getesteten Prefect-/SQLAlchemy-Kombination. SQL-Migrationen und vorhandene Constraints wurden nicht verändert.

Collect speichert tatsächliche Raw-Beobachtungen. Transform prüft Quelle, Scope, Hersteller, GTIN/MPN, CHF-Preis und Zeit sowie technische Felder. Fehlende Werte alter Dateien werden nur aus passenden HTML-Belegen ergänzt. Load verarbeitet je Datei eine Transaktion und speichert Produkt, Händlerangebot und Preis. Unklare Verkäufer bleiben unbekannt, Buchmann bleibt Buchmann. Keine Namens-Fuzzy-Suche, keine erfundenen Daten.

**INITIAL:** Neun ausgewählte URLs aus `mediamarkt_initial.json`. Keine automatische Ausweitung auf alle Discovery-Kandidaten. Der nachgewiesene Lauf benötigte sieben HTTP-Anfragen (robots + sechs Produktseiten), übersprang drei bereits heute erfasste Produkte und lud sechs neue Beobachtungen. Drei bisher nicht importierte Produkte kamen hinzu. Scope und Ingestion-Validierung blieben aktiv.

**DAILY:** Mitgliedschaft und URLs stammen aus PostgreSQL (`active_products()`), einschliesslich des zuvor nur über Legacy-Raw importierten sechsten Produkts. Aktiv bedeutet aktuell: importiertes MediaMarkt-Angebot mit Preisbeobachtung, URL und unterstützter Kategorie. Keine neue Aktivierungstabelle. Der JSON-Katalog hält Abrufzustände, bestimmt aber nicht die DAILY-Mitgliedschaft. Der geprüfte Lauf wählte neun DB-Produkte und übersprang alle neun nach dem bereits erfolgreichen Tagesabruf: 0 HTTP-Anfragen, keine Duplikate. Abruf an einem neuen Tag und Wiederholung am selben Tag sind gezielt getestet; der bestehende echte Bestand enthält bereits Beobachtungen vom 15. und 16.10.

**REPLAY:** Kein HTTP; derselbe Transform-/Load-Pfad für vorhandene Raw-Dateien. Ursprünglicher Zeitpunkt bleibt erhalten. Bei Wiederholung: 16 vorhandene Beobachtungen erkannt, 0 neu, 1 weiterhin ausgeschlossener Raw-Datensatz. Backfill wurde im isolierten DB-Test mit zwei echten gespeicherten RAM-Beobachtungen in umgekehrter Reihenfolge überprüft.

## Katalog und tatsächliche Abdeckung

Quelle: [catalogue.json](../evidence/phase3/catalogue.json). Zahlen sind unterschiedliche Produkte/SKUs, ausser der letzten Spalte.

| Kategorie | Bekannte URLs | In gespeicherten Kategorieseiten automatisch entdeckt | Erfolgreich abgerufene Produkte mit Raw-Beleg | Streng validiert | In PostgreSQL | Preisbeobachtungen |
|---|---:|---:|---:|---:|---:|---:|
| GPU | 25 | 24 | 3 | 3 | 3 | 6 |
| RAM | 25 | 24 | 4 | 3 | 3 | 5 |
| SSD | 24 | 24 | 3 | 3 | 3 | 5 |

Der vierte RAM-Abruf ist der ausgeschlossene Synology-Artikel. Bekannte URLs sind keine erfolgreich verarbeiteten Produkte. Wie viele weitere URLs aktuell erreichbar und importierbar sind, ist **NOT TESTED**. Die historische Pagination und die Erkennung aller drei Kategorien funktionieren in den vorhandenen Fixtures; Phase 3 hat kein umfassendes neues Kategorie-Crawling durchgeführt. Zehn bis zwanzig Produkte pro Kategorie bleiben ein Wunschziel, nicht ein versprochener Datenbestand. Details zum Scraper: [MEDIAMARKT.md](../MEDIAMARKT.md).

## Tatsächliche Prüfungen

- Vor Refactoring: 18 Scraper-Tests bestanden; 20 Pipeline-Tests nach Korrektur des `.env`-Benutzers bestanden.
- Nach Refactoring: **45/45 Tests bestanden**, inklusive aller bisherigen Tests. Neue Prüfungen für ausgewählte Initial-URLs, DB-Mitgliedschaft, leeren Katalog, unzulässige URLs, DB-Abfrage im DAILY-Task und neuer Tag mit gleichem Preis.
- INITIAL, DAILY und REPLAY über echte Prefect-Runs erfolgreich. Jeweils Collect, Transform, Load.
- Automatisches Scheduling des refaktorierten Flows mit vorübergehendem Minutentakt im REPLAY-Modus erfolgreich; anschliessend wieder DAILY um 03:00 Europe/Zurich.
- Leere DB weiterhin kein positiver Verifikationsnachweis. Reruns, widersprüchliche Identifikatoren, Transaktionsrollback und paralleler Import getestet.
- Backfill mit echten gespeicherten alten/neuen RAM-Beobachtungen in einem isolierten Testschema; keine erfundenen Preise im Projektbestand.
- Originaldateien: 42 bestehende Daten-/Nachweisdateien unverändert; elf verschobene HTML-/Fixture-Dateien hashgleich.

Belege unter [evidence/phase3/](../evidence/phase3/): Tests, Flow-Logs, SQL/Verifikation, Katalogzahlen, Originaldatei-Prüfung und Cleanup-Liste. Die Arbeitsbefehle stehen vollständig in [RUN_COMMANDS.md](../RUN_COMMANDS.md); ein kompakter Einstieg ist:

```sh
docker compose build pipeline
docker compose up -d --wait postgres prefect_server
docker compose run --rm pipeline python -m backend.flow init
docker compose run --rm pipeline python -m backend.flow initial --max-products 3 --max-requests 10
docker compose run --rm pipeline python -m backend.flow daily
docker compose run --rm pipeline python -m backend.flow replay
docker compose run --rm pipeline python -m backend.flow verify
docker compose up -d pipeline
docker compose run --rm pipeline python -m unittest discover -s backend/tests -v
docker compose stop
```

## Grenzen und bis zum Midterm offen

P2 (Frontend/API) wurde zurückgestellt: Die unabhängige Reproduktion auf dem zweiten Rechner und die vollständige Midterm-Abnahme stehen noch aus. Das bestehende Svelte-Projekt bleibt unverändert. Keine neuen Container, Endpunkte oder Screenshots eines vermeintlich fertigen Frontends.

Noch offen: frischer Checkout auf Windows/amd64, weitere reale DAILY-Abrufe nach diesem Umbau, längerer stabiler Betrieb ohne Rechner-Schlafmodus, finale Root-README/Abnahmedokumentation und gemeinsame mündliche Vorbereitung. Der ursprüngliche Nachtlauf startete verspätet und scheiterte teilweise an Netzwerkzugriffen; die Ursache der Verzögerung ist nicht gesichert. Scheduling allein garantiert keine Händler-Erreichbarkeit. 404/Timeouts bleiben sichtbar; gesperrte Requests werden nicht umgangen.

Nur erstes JSON-LD-Angebot, kleiner Datenbestand, keine repräsentative Langzeitserie. Aktuell maximal drei Produktversuche je Kategorie und 20 Requests im Standardlauf; bei einem später wesentlich grösseren Katalog müssen Budget und `remaining_due` bewusst geprüft werden. Eine am selben Tag vorhandene, aber abgelehnte Raw-Datei wird nicht stillschweigend überschrieben. Schema-Migration eines fremden befüllten Altstands ist weiterhin nicht zugesichert. Digitec-Zugang extern BLOCKED; BRACK, Interdiscount, Cloud und komplexes Matching sind nicht implementiert.

Abgabe: **22.10.2026, 15:30 Europe/Zurich**. Keine eigenständigen Commits/Pushes. Der uncommitted Arbeitsstand muss vor der Abgabe nach Freigabe vollständig versioniert werden.


## Daten- und Infrastrukturabschluss

Stop und Wiederstart aller drei Services wurden mit den vorhandenen Volumes ausgeführt. Danach weiterhin 9 Produkte, 9 Angebote und 16 Beobachtungen. Alle sechs ursprünglichen Produktzeilen und zehn ursprünglichen Preiszeilen sind feldweise unverändert vorhanden; die Identität der sechs ursprünglichen Angebote ist erhalten, ihre letzten Beobachtungszeiten wurden regulär fortgeschrieben. Nachweis: [database-preservation.json](../evidence/phase3/database-preservation.json). Die 42 vorhandenen Daten-/Nachweisdateien blieben bytegleich, zusätzlich elf verschobene HTML-/Fixture-Dateien: [file-preservation.json](../evidence/phase3/file-preservation.json).

Das einzige Deployment `mediamarkt-daily` verweist auf `backend/flow.py:mediamarkt_pipeline`, ist aktiv und verwendet DAILY mit `0 3 * * *`, Europe/Zurich. Automatisch erzeugte erfolgreiche REPLAY-Runs und die drei Tasks sind in [prefect.json](../evidence/phase3/prefect.json) nachgewiesen. Ein frischer DAILY-Abruf an einem künftigen Tag mit diesem DB-Katalog muss noch im laufenden Betrieb beobachtet werden; der gleichzeitige Preis-/Zeitpunktmechanismus ist getestet.

## Midterm-Checkliste

| Requirement | Status | Nachweis / offen | Priorität |
|---|---|---|---|
| PostgreSQL | DONE | DB-Verifikation vor und nach Neustart | P0 |
| Local Schema | DONE | Bestehende Migrationen unverändert, `init` und DB-Tests bestanden | P0 |
| Data loaded | DONE | 9 Produkte, 9 Angebote, 16 echte Beobachtungen | P0 |
| Queryable Data | DONE | `hardware_prices`, SQL-Ergebnisse in `evidence/phase3/sql.txt` | P0 |
| Docker | DONE | Native ARM64-Builds; Windows/amd64 noch NOT TESTED | P0 |
| Docker Compose | DONE | Drei Services erfolgreich gestoppt und mit Volumes wieder gestartet | P0 |
| Common Network | DONE | Runner erreicht PostgreSQL und Prefect in echten Läufen | P0 |
| Modular Batch Ingestion | DONE | INITIAL, DAILY, REPLAY; Adapter und gemeinsame Verarbeitung getrennt | P0 |
| Source → Storage | DONE | INITIAL: sechs neue echte Beobachtungen aus sieben HTTP-Requests | P0 |
| Transformation | DONE | Hersteller/GTIN/CHF/Einheiten geprüft, SSD-Kapazitäten und Preise per SQL | P0 |
| Justification | DONE | Preisvergleich, Einheiten und Varianten in ARCHITECTURE/MEDIAMARKT erklärt | P0 |
| Orchestrator | DONE | Ein aktiver Prefect-Flow, echte abgeschlossene Runs | P0 |
| Pipeline Workflow | DONE | Collect, Transform, Load jeweils ausgeführt | P0 |
| Scheduling | DONE | Automatischer REPLAY-Test; DAILY-Cron aktiv. Händler-Erreichbarkeit separat begrenzt | P0 |
| Reruns | DONE | REPLAY und DAILY ohne doppelte Preiszeilen; paralleler Import getestet | P0 |
| Backfills | DONE | Echte gespeicherte Beobachtungen rückwärts geladen im isolierten DB-Test; gezielter Replay ausgeführt | P0 |
| Architecture v0.2 | DONE | Aktuelles Diagramm mit INITIAL-Auswahl und DAILY-DB-Katalog | P0 |
| Architecture Changes | DONE | Änderungen im Bericht und Architekturtext begründet | P0 |
| Setup Instructions | IN PROGRESS | RUN_COMMANDS vorhanden und lokal geprüft; frischer zweiter Rechner fehlt | P0 |
| Execution Instructions | DONE | Einheitlicher Einstieg und konkrete getestete Befehle in RUN_COMMANDS | P0 |
| Verification Instructions | DONE | SQL, `verify`, erwartete Zahlen, Ablehnungen, Testbefehl dokumentiert und lokal geprüft | P0 |
| Beide verstehen Architektur | NOT TESTED | MANUAL ACTION: beide erklären den gesamten Ablauf | P0 |
| Reliability erklären | IN PROGRESS | Fehler-/Rerun-Tests und echter fehlgeschlagener Nachtlauf dokumentiert; MANUAL ACTION mündlich | P0 |
| Limitations erklären | IN PROGRESS | Grenzen dokumentiert; MANUAL ACTION gemeinsam erklären | P0 |
| Commit Hash / Release Tag | IN PROGRESS | MANUAL ACTION: Abgabestand nach Freigabe committen/taggen; hier nichts committed | P0 |
| Repository Link einreichen | NOT STARTED | MANUAL ACTION: GitHub-Link/Angaben in ILIAS | P0 |
| Deadline einhalten | NOT STARTED | MANUAL ACTION: 22.10.2026, 15:30 Europe/Zurich | P0 |
