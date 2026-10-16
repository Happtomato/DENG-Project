> Historischer Phase-2-Bericht. Nach dem Cleanup gelten die Pfade und Befehle in [RUN_COMMANDS.md](RUN_COMMANDS.md) und [PHASE3.md](PHASE3.md). Die damaligen Nachweise bleiben unverändert.

# Phase 2 — Implementierungsbericht

Stand: 15.10.2026, Europe/Zurich. Dies sind kurze Arbeits- und Prüfanweisungen, keine finale README oder Prüfungsvorbereitung.

## Ergebnis und Daten

Der aktive MVP verwendet ausschliesslich MediaMarkt: Collect → Raw JSON → Transform → Load → PostgreSQL. Genau ein Prefect-Flow hat die Tasks Collect, Transform und Load. LIVE nutzt den vorhandenen Collector; REPLAY verwendet dieselbe Transformation und Ingestion ohne HTTP-Zugriff.

Der geprüfte Bestand umfasst 6 Produkte, 6 Händlerangebote und 7 Preisbeobachtungen: drei GPU-, zwei RAM-Beobachtungen desselben Produkts und zwei SSD-Beobachtungen. Sieben Quelldateien wurden akzeptiert, eine abgelehnt. Es gibt keine ungültigen Preise und keine doppelten Beobachtungsschlüssel. Die beiden RAM-Beobachtungen stammen aus zwei tatsächlichen Abrufen am 15.10.; sie sind keine mehrtägige Preisserie.

- `2155505`: SAMSUNG aus gespeichertem HTML; 1 TB wird zu 1000 GB.
- `2199070`: WESTERN DIGITAL aus gespeichertem HTML; 1 TB wird zu 1000 GB.
- `2277751`: alte GPU-Datei aus passendem gespeicherten HTML neu ausgewertet, Scope bestätigt.
- `133486101`: weiterhin abgelehnt: `Scope excluded: excluded_hardware_or_condition`.
- `160229354`: Verkäufer bleibt ausdrücklich Buchmann; Plattform ist MediaMarkt.
- Unbekannte Verkäufer bleiben NULL, keine automatische Annahme MediaMarkt.

Alle sieben ursprünglichen Raw-Dateien und vorhandenen HTML-Aufzeichnungen bleiben bytegleich. Eine echte zusätzliche RAM-Raw-Datei und ihr HTML-Beleg wurden beim begrenzten LIVE-Test erzeugt. Der separate Testkatalog `data/catalog/midterm-live-check.json` diente nur diesem Abruf; der normale Scheduler nutzt `data/catalog/mediamarkt.json`.

## Geänderte Komponenten

- `backend/pipeline/contracts.py`: kleiner MediaMarkt-Vertrag, GTIN/MPN/CHF/Zeitpunkte/Detailfelder.
- `backend/pipeline/transform.py`: schreibfreie Verarbeitung und belegte Kompatibilität alter Raw-Dateien.
- `backend/pipeline/ingest.py`: Datei/Verzeichnis laden, exakte Zuordnung, Transaktionen, Idempotenz.
- `backend/pipeline/db.py`: bestehender Migrationsrunner; stoppt ausdrücklich bei bereits angewandter grosser Phase-1-Migration.
- `backend/pipeline/cli.py`: `init` und nichtleere `verify`-Abnahme.
- `backend/pipeline/tests/`: 20 gezielte Tests der aktiven Implementierung.
- `backend/orchestrator/flow.py`: genau ein aktiver Flow, LIVE/REPLAY und Schedule.
- `docker-compose.yaml`: drei Services, bestehende Volumes weiterverwendet, keine erzwungene amd64-Emulation.
- `backend/Dockerfile`, `backend/requirements.txt`, `backend/requirements.lock`: ein gepinnter Abhängigkeitsstand für Docker und lokale Installation.
- `.env.example`: lokale DB-Konfiguration und optionaler Cron-Zeitplan, keine Secrets.
- `data/migrations/002_midterm.sql`, `data/queries/verification.sql`: kleine additive Schemaergänzung und SQL-Auswertung.
- `backend/ingestMediamarkt/app.py`: Kompatibilitätseinstieg in denselben Replay-Flow.
- Die Digitec-Einstiegspunkte melden ausdrücklich, dass sie inaktiv sind.
- Architekturdiagramm in `docs/ARCHITECTURE.md`, Nachweise unter `docs/evidence/phase2/`.

Die umfangreiche vorherige Pipeline inklusive ihrer damaligen 23 Tests wurde unter `backend/legacy/phase1/pipeline/` erhalten. Diese Tests beziehen sich auf die alte Architektur und sind keine aktuelle grüne Testsuite. Die Phase-1-Migration und SQL-Abfragen liegen unter den jeweiligen `archive/`-Verzeichnissen. Der Dummy-Flow, weitere Händler und das Frontend wurden nicht gelöscht, werden aber nicht von Compose oder dem Midterm-Flow verwendet. `data/initialization.sql` und die funktionierenden MediaMarkt-Scraper-Dateien wurden in Phase 2 nicht geändert.

Vor Änderungen wurden Arbeitsdateien als `phase2-before.tar.gz` und die Datenbank als `phase2-before.sql` im Chat-Arbeitsordner gesichert. Keine Commits, Pushes, Volume-Löschungen oder destruktiven Git-Befehle. Bestehende Änderungen an Dummy-Flow und Frontend-Lockfile bleiben erhalten.

Die vollständige Dateiliste gegenüber dem gesicherten Beginn von Phase 2 steht in [changed-files.json](evidence/phase2/changed-files.json). Sie unterscheidet diese Änderungen von bereits vorher vorhandenen uncommitted Änderungen.

## Kurze Ausführungshinweise

Voraussetzung: Docker Compose mit Linux-Containern. Aus dem Repository-Verzeichnis starten. Bei neuem Checkout `.env.example` nach `.env` kopieren und lokale DB-Werte setzen. Eine vorhandene `.env` nicht überschreiben. Die Datenbank-Zugangsdaten eines bestehenden Volumes ändern sich nicht durch nachträgliches Ändern der Environment-Datei.

```sh
docker compose build pipeline
docker compose up -d --wait postgres prefect_server
docker compose run --rm pipeline python -m backend.pipeline.cli init
docker compose run --rm pipeline python -m backend.orchestrator.flow --mode replay
docker compose run --rm pipeline python -m backend.pipeline.cli verify
# Derselbe Replay erneut: keine zusätzlichen Preiszeilen
docker compose run --rm pipeline python -m backend.orchestrator.flow --mode replay
# Begrenzter LIVE-Lauf, Standard: höchstens 3 Produktversuche je Kategorie, 20 Requests
docker compose run --rm pipeline python -m backend.orchestrator.flow --mode live
# Dauerhafter Runner für täglich 03:00 Europe/Zurich
docker compose up -d pipeline
# Stoppt die Bedienung des Zeitplans; keine Datenvolumes werden gelöscht
docker compose stop pipeline
```

`init` ist wiederholbar; auch der Load-Task stellt das Schema vor der Ingestion sicher. Die Reihenfolge ist Originalschema → `002_midterm.sql`. Bereits angewandte SQL-Dateien dürfen nicht nachträglich verändert werden. Konflikte mit vorhandenen Daten führen zu einem Fehler/Transaktionsrollback, nicht zu Datenbereinigung. Dieser Lauf startete mit einer nachweislich leeren Projektdatenbank.

Für einen Backfill einen vorhandenen Raw-Unterordner unter `data/` an `--input /workspace/data/<unterordner>` übergeben. REPLAY importiert die tatsächlichen alten Beobachtungszeitpunkte, nicht das heutige Importdatum. Legacy-Raw-Dateien benötigen die dazugehörigen vorhandenen HTML-Aufzeichnungen. Für einen frischen Rechner gehören daher Raw-Dateien und HTML-Belege zum zu versionierenden Abgabestand.

In der Prefect-UI `http://localhost:4200` sind Flow-Runs und die drei Tasks sichtbar. Der Zeitplan ist über `PIPELINE_CRON` konfigurierbar, immer Europe/Zurich. Der Runner muss laufen; Rechner-Schlafmodus ist kein zuverlässiger Scheduler-Betrieb. LIVE kann wegen vorhandener Tagesbeobachtungen ohne neuen HTTP-Abruf enden; das steht im Collector-Bericht unter `skipped_today` und `requests`.

Für SQL `docker compose exec postgres sh` öffnen und im Container `psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"` starten. Dort beispielsweise:

```sql
SELECT product_name, category, platform, seller_name, price_chf, observed_at
FROM hardware_prices ORDER BY observed_at;
SELECT status, reason, count(*) FROM raw_import GROUP BY 1,2;
```

Weitere Abfragen: `data/queries/verification.sql`. `verify` gibt technisch gültig und tatsächlich Daten geladen getrennt aus. Eine leere DB liefert `ok: false` und Exit-Code 1. Ablehnungen werden nicht verschwiegen; ein erfolgreicher Batch darf einzelne abgelehnte Dateien enthalten, muss aber mindestens eine akzeptierte Datei und einen nichtleeren gültigen DB-Bestand haben.

## Abhängigkeiten und Fehlerbehandlung

`requirements.lock` pinnt direkte und transitive Python-Pakete. Docker installiert diese Datei und führt `pip check` aus; `requirements.txt` verweist auf denselben Stand. Kein neues Paketverwaltungssystem. Änderungen am Lockfile erfordern Build und Tests. Python-/PostgreSQL-Basisimages verwenden Versionstags, keine unveränderlichen Image-Digests; bitidentische Builds sind daher nicht zugesichert.

Beim realen Scheduling-Test zeigte Prefect 3.8.8 mit SQLAlchemy 2.1.4 einen Fehler beim Anlegen geplanter Flow-Runs. SQLAlchemy wurde deshalb auf 2.0.43 gepinnt und der Scheduler erneut geprüft. Ein Healthcheck allein war kein ausreichender Nachweis.

Ein zweiter gefundener Fehler betraf RAM-Spannung `1.4` gegenüber PostgreSQL `1.40`: jetzt numerischer Decimal-Vergleich statt Textvergleich. Transaktionen gelten pro Datei; ein abgelehnter Datensatz erzeugt keine halben Produkte oder Preiszeilen. Gleichzeitige kleine Imports werden über einen DB-Lock serialisiert. Keine automatischen HTTP-Retries bei Sperren. Unbekannte/konfliktbehaftete Daten bleiben als abgelehnte Originaldateien nachvollziehbar.

## Tests und Nachweise

```sh
docker compose run --rm pipeline python -m unittest discover -s backend/scrapeMediamarkt/tests -v
docker compose run --rm pipeline python -m unittest discover -s backend/pipeline/tests -v
```

Die Datenbanktests erzeugen ausschliesslich eigene `midterm_test_<uuid>`-Schemas und entfernen diese wieder. Mutierte Testbeobachtungen bleiben dort; sie werden nie als echte Produktionspreise ausgegeben.

- 18 Scraper-Tests: bestanden, auch im nativen ARM64-Container.
- 20 aktuelle Pipeline-Tests: bestanden; Schema, echte Raw-Dateien, Normalisierung, SQL, Reruns, Zeitpunkte, Widersprüche, Fehlerisolation, paralleler Replay und Orchestrierungslogik.
- LIVE: zwei HTTP-Requests (robots + eine RAM-Seite), echter Prefect-Lauf, eine Beobachtung geladen.
- Backfill: danach sechs alte Beobachtungen vom Vormittag geladen, ursprüngliche Zeiten erhalten. Keine erfundene mehrjährige Historie.
- Rerun: 0 neue, 7 bereits vorhandene Beobachtungen, 1 weiterhin begründet abgelehnte Datei.
- Leere Datenbank: Prüfung scheitert wie vorgesehen mit Exit-Code 1.
- SQL: 6 Produkte, 6 Angebote, 7 Beobachtungen; keine ungültigen Preise oder doppelten Schlüssel.

## Phase 3 und Grenzen

Priorität für Phase 3: frischer Checkout auf dem zweiten Rechner (insbesondere Windows/amd64), Neuaufbau mit eigenem leeren Volume ohne bestehende Volumes zu löschen, die dokumentierten Befehle unabhängig ausführen, Container-Neustart und Persistenz prüfen, tatsächlichen täglichen 03:00-Lauf beobachten, LIVE-Abrufe für GPU und SSD sowie mehrtägige Beobachtungen prüfen. Umfangreicher Batch und langfristiger stabiler Website-Zugriff sind noch nicht belegt. 403-/429-Verhalten ist offline getestet; keine Sperre wurde absichtlich provoziert.

Digitec-Zugang bleibt extern blockiert. BRACK, Interdiscount, Händlervergleich, Cloud und Frontend sind nicht Teil des aktiven MVP. Produktattribute werden nicht automatisch korrigiert; widersprechende spätere Angaben werden abgelehnt. Ein hash-identischer bereits akzeptierter Raw-Datensatz wird nicht bei jedem Parserwechsel neu in PostgreSQL überschrieben; Datenkorrekturen benötigen eine bewusste Änderung. Nur das erste JSON-LD-Angebot wird betrachtet. Der aktuelle Bestand ist klein und vom 15.10.2026, keine repräsentative Markt- oder Langzeitstudie.

Finale Setup-/Verifikations-README und mündliche Vorbereitung folgen in Phase 4. Der getestete Arbeitsstand ist noch nicht committed; ein frischer Clone vom derzeitigen HEAD enthält die neuen Dateien noch nicht.

## Scheduling-Nachweis

Mit demselben Flow wurde vorübergehend ein REPLAY-Schedule `* * * * *` registriert. Prefect erzeugte und vollendete den Lauf `ultraviolet-sponge` automatisch (`auto_scheduled: true`, Starttermin 15.10.2026 17:58 UTC / 19:58 Europe/Zurich). Collect, Transform und Load sind jeweils Completed. Danach wurde der Testrunner gestoppt und das einzige Deployment `mediamarkt-daily` auf LIVE, `0 3 * * *`, Europe/Zurich gesetzt. Nächster geplanter Lauf: 16.10.2026 03:00 Europe/Zurich. Der normale Compose-Runner bleibt gestartet. Dies belegt die Scheduler-Funktion, noch keinen über Nacht beobachteten LIVE-Lauf.

Nachweise: [Prefect-API-Snapshot](evidence/phase2/prefect.json), [automatischer Lauf](evidence/phase2/scheduled-replay.txt), [SQL-Ergebnisse](evidence/phase2/sql.txt), [aktuelle Verifikation](evidence/phase2/verification.txt), [Pipeline-Tests](evidence/phase2/pipeline-tests.txt), [Scraper-Tests](evidence/phase2/scraper-tests.txt). Zeitangaben der Containerlogs sind UTC. [Originaldatei-Prüfung](evidence/phase2/original-files.json): 21 vorhandene Dateien überprüft, 0 verändert/fehlend.

## Vollständige Notion-Abnahme nach Phase 2

Alle Punkte sind P0 für die Abgabe; die technische DONE-Bewertung gilt für den hier ausgeführten lokalen Umfang. Menschliche Aufgaben bleiben ausdrücklich offen. Ein zweiter Rechner und die finale Dokumentation sind nicht durch diesen Lauf abgenommen.

| Requirement | Status | Evidenz | Fehlende Arbeit / nächste Prüfung | Priorität |
|---|---|---|---|---|
| PostgreSQL | DONE | Laufende DB, `verify`, SQL-Ergebnisse | Unabhängiger Rechner in Phase 3 | P0 |
| Local Schema | DONE | `init`, wiederholte Migration in DB-Tests, echte Ingestion | Migration eines abweichenden befüllten Altbestands nicht zugesichert | P0 |
| Data loaded | DONE | SQL: 6 Produkte, 6 Angebote, 7 echte Beobachtungen | Datenbestand später erweitern | P0 |
| Queryable Data | DONE | Nichtleere `hardware_prices`-Abfrage in `sql.txt` | Unabhängige Wiederholung | P0 |
| Docker | DONE | Native Linux/ARM64-Images, Build und `pip check` erfolgreich | Windows/amd64 noch NOT TESTED | P0 |
| Docker Compose | DONE | Drei Services laufen über Compose; DB/Prefect healthy | Frischer Checkout mit eigenem Volume | P0 |
| Common Network | DONE | Runner erreicht Prefect und PostgreSQL in echten Flow-Runs | Keine lokale Lücke | P0 |
| Modular Batch Ingestion | DONE | Replay verarbeitet 8 Raw-Dateien, Ergebnis pro Datei | Grössere Batches optional | P0 |
| Source → Storage | DONE | Echter LIVE-Lauf + Raw-Datei + DB-Zeile; `live.txt` | Live GPU/SSD in Phase 3 | P0 |
| Transformation | DONE | SSD-Hersteller und 1000 GB in SQL; Decimal/GTIN- und RAM-Tests | Erklärung in finale README übernehmen | P0 |
| Justification | DONE | Architektur begründet Einheiten, Identifikatoren, CHF/GB | Finale README in Phase 4 | P0 |
| Orchestrator | DONE | Prefect 3.8.8 führt echte und geplante Runs aus | Keine lokale Lücke | P0 |
| Pipeline Workflow | DONE | LIVE, Backfill, Rerun und Schedule Completed; drei echte Tasks | Zweiter Rechner | P0 |
| Scheduling | DONE | Automatisch geplanter Replay Completed; aktiver täglicher Zurich-Cron in API | Tatsächlichen 03:00-LIVE-Lauf beobachten | P0 |
| Reruns | DONE | Zweiter Replay: 0 neu, 7 Duplikate erkannt; weiterhin 7 DB-Zeilen | Langzeitbetrieb Phase 3 | P0 |
| Backfills | DONE | Alte Vormittagsdaten nach frischem Abend-Abruf geladen, Originalzeiten erhalten | Keine mehrjährige Historie vorhanden/erforderlich | P0 |
| Architecture v0.2 | DONE | Aktuelles Diagramm in `ARCHITECTURE.md` | Nach Phase 3 nur bei Änderungen aktualisieren | P0 |
| Architecture Changes | DONE | v0.1 und grosser Phase-1-Entwurf gegenüber MVP begründet | Keine lokale Lücke | P0 |
| Setup Instructions | IN PROGRESS | Kurze getestete Arbeitsbefehle in diesem Bericht | Frischer Checkout/zweiter Rechner; finale README Phase 4 | P0 |
| Execution Instructions | DONE | Befehle für init, LIVE, REPLAY, Scheduling und Tests dokumentiert und ausgeführt | In finale README übernehmen | P0 |
| Verification Instructions | IN PROGRESS | SQL-Datei, `verify`, erwartete Zahlen und Belege vorhanden | Unabhängige Abnahme und finale Anleitung | P0 |
| Beide verstehen Architektur | NOT TESTED | Nicht durch Code-Ausführung belegbar | MANUAL ACTION: beide erklären den gesamten Datenfluss | P0 |
| Reliability erklären | IN PROGRESS | Transaktions-, Konflikt-, Rerun- und Fehlerisolationstests; Grenzen dokumentiert | MANUAL ACTION: beide erklären Fehlerverhalten, Phase 4 | P0 |
| Limitations erklären | IN PROGRESS | Kleine Datenbasis, Verkäufer, Altdatei-Beleg und Zugriffsgrenzen dokumentiert | MANUAL ACTION: gemeinsam erklären, Phase 4 | P0 |
| Commit Hash / Release Tag | IN PROGRESS | Arbeitsstand geprüft, aber uncommitted | MANUAL ACTION: Freigabe für Commit/Abgabestand; kein Commit/Push ausgeführt | P0 |
| Repository Link einreichen | NOT STARTED | Kein Einreichungsnachweis | MANUAL ACTION: ILIAS | P0 |
| Deadline einhalten | NOT STARTED | 22.10.2026, 15:30 Europe/Zurich | MANUAL ACTION: rechtzeitig einreichen | P0 |
