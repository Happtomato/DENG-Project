# Startbefehle — Midterm

Stand: 16.10.2026 (Phase 5). Alle Befehle im Projektroot ausführen. Ein Pipeline-Einstieg: `python -m backend.flow`. Die Container enthalten Python und alle Pakete; keine lokale Python-Installation nötig. Docker Desktop muss mit Linux-Containern laufen. Getestet: Mac/ARM64. Windows/amd64 ist noch unabhängig zu prüfen.

## First-time setup

1. Docker Desktop starten. Nur wenn noch keine `.env` existiert, `.env.example` im Editor nach `.env` kopieren und DB-Name, Benutzer und Passwort setzen. Bei einem bestehenden Volume müssen die Werte zur vorhandenen Datenbank passen; Environment-Änderungen legen keine neuen DB-Benutzer an.
2. Die folgenden Befehle ausführen:

```sh
docker compose up -d --build
docker compose ps
docker compose run --rm pipeline python -m backend.flow verify
```

`db_init` wendet die vorhandenen Migrationen beim ersten Compose-Start automatisch an und beendet sich danach. Der Befehl `up` startet PostgreSQL, Prefect Server, Pipeline Runner und das SvelteKit-Frontend über das gemeinsame Netzwerk. Dashboard: [localhost:3000](http://localhost:3000), Prefect: [localhost:4200](http://localhost:4200). Bestehende Daten und Volumes bleiben erhalten. Ein manueller erneuter Schema-Check ist mit `docker compose run --rm pipeline python -m backend.flow init` möglich.

Für einen späteren erlaubten Live-Start stehen acht ausgewählte URLs in `data/catalog/mediamarkt_initial.json`: zwei GPU, drei RAM, drei SSD. Ein protokollierter kleiner INITIAL-Lauf vom 16.10. hat die beiden GPU-URLs und eine G.Skill-RAM-URL erfolgreich validiert und importiert. Vier früher importierte Produkte ausserhalb des neuen Marken-Scopes bleiben als historische Daten erhalten; neue DAILY-Läufe wählen sie nicht mehr aus. Der aktuelle Scope steht in `backend/retailers/mediamarkt/scope.json`.

**Zugriffsgrenze:** Vor weiteren automatisierten Abrufen die zulässige Nutzung und das Volumen mit MediaMarkt klären. Die [Nutzungsbedingungen](https://www.mediamarkt.ch/de/legal/nutzungsbedingungen/mediamarkt) geben keine ausdrückliche Freigabe für systematische Sammlung. Bis dahin für Midterm-Verifikation den vorhandenen echten Raw-Bestand mit REPLAY verwenden. Die folgenden INITIAL-/DAILY-Befehle sind betriebsbereit, aber kein Auftrag für einen Massenabruf.

```sh
docker compose run --rm pipeline python -m backend.flow initial --max-products 3 --max-requests 10 --delay 3
docker compose run --rm pipeline python -m backend.flow verify
```

INITIAL erfasst hier nur die manuell ausgewählten URLs, speichert Raw-Dateien, transformiert und lädt sie. `--max-products` gilt pro Kategorie; `--max-requests` für den gesamten Abruf inklusive robots.txt und Redirects. Bei begrenztem Budget bleiben weitere URLs für einen späteren Lauf. Unzulässige oder widersprüchliche Produkte werden mit Begründung abgelehnt.

## Discovery und INITIAL aus dem Katalog

**Catalog** (`data/catalog/mediamarkt.json`) enthält persistente URL-Kandidaten, Kategorien, Discovery-Cursor und Abrufzustände. **Selection** (`data/catalog/mediamarkt_initial.json`) ist eine optionale, manuell gepflegte URL-Auswahl für INITIAL. **PostgreSQL** enthält erst nach erfolgreichem Laden Produkte, Händlerangebote und Preisbeobachtungen. `last_success_at` im Catalog bedeutet, dass eine Produktseite geparst wurde; es beweist keinen Datenbankimport.

Die folgenden Befehle sind für einen späteren **kleinen, geklärten** Live-Test vorgesehen. Sie wurden in Phase 4B nur mit gespeicherten HTML-Seiten und Mock-Requests getestet. Listing-Seiten werden ausschliesslich durch den manuellen Befehl `discover` abgerufen; DAILY benötigt sie nicht.

```sh
# Eine RAM-Kategorieseite, höchstens drei HTTP-Anfragen einschliesslich robots.txt/Redirects
docker compose run --rm pipeline python -m backend.flow discover --categories ram --max-pages 1 --max-requests 3 --delay 3
# Alternativ alle drei Kategorien, je höchstens eine Seite
docker compose run --rm pipeline python -m backend.flow discover --max-pages 1 --max-requests 5 --delay 3
# Bekannte, versuchte, geparste und akzeptierte SKUs je Kategorie; dazu DB-Angebote
docker compose run --rm pipeline python -m backend.flow catalog
# Bis zu ein noch nicht importierter RAM-Kandidat; keine zweite Selection-Datei nötig
docker compose run --rm pipeline python -m backend.flow initial --from-catalog --categories ram --max-products 1 --max-requests 3 --delay 3
# Bewusste manuelle Auswahl bleibt weiterhin möglich
docker compose run --rm pipeline python -m backend.flow initial --selection /workspace/data/catalog/mediamarkt_initial.json --max-products 3 --max-requests 10 --delay 3
docker compose run --rm pipeline python -m backend.flow verify
```

`discover` verwendet den bestehenden MediaMarkt-Adapter, speichert nur Links und einen Run-Bericht unter `data/catalog/runs/`; es führt weder Produktdetailabrufe noch Transform/Load aus. `--max-pages` gilt je Kategorie und startet beim gespeicherten Cursor. `initial --from-catalog` wählt `candidate`/`accepted`-Einträge ohne importiertes MediaMarkt-Angebot; eindeutig fremde Marken werden vor dem Detailabruf übersprungen. Fehlgeschlagene DB-Importe können aus vorhandenen Raw-Dateien nachgeholt werden. Der Ergebnisblock `outcome` zeigt neue URLs, HTTP-Anfragen, Auswahl, DB-Neuimporte und Null-Ergebnisse getrennt von alten Raw-Duplikaten.

Bei einer bereits vorhandenen Datenbank kann `--from-catalog` mit null neuen Kandidaten enden. Das ist ein ehrliches Leerergebnis. Der manuelle `--selection`-Weg bleibt für eine gezielte Stichprobe erhalten; die beiden JSON-Dateien sind nicht austauschbar.

Ohne Live-Zugriff kann stattdessen zuerst der vorhandene echte Raw-Bestand importiert werden:

```sh
docker compose run --rm pipeline python -m backend.flow replay
docker compose run --rm pipeline python -m backend.flow verify
```

Die alten Raw-Dateien benötigen die mitgelieferten HTML-Belege unter `data/debug/`. Stand der Phase-3.5-Prüfung am 16.10.: 12 Produkte, 12 Angebote, 19 Beobachtungen; davon 8 Angebote im neuen Scope. Eine leere DB liefert bei `verify` Exit-Code 1, auch wenn keine ungültigen Preise vorliegen.

## Daily operation

Der Prefect-Zeitplan ist `0 3 * * *`/`Europe/Zurich`. Sein Aktivierungszustand kann sich durch manuelle Änderungen ändern; vor einem Compose-Start und vor Live-Abrufen den tatsächlichen Zustand in Prefect prüfen. Der `pipeline`-Dienst startet mit `docker compose up -d --build` und betreibt das DAILY-Deployment. Die folgenden Live-Befehle nur im geklärten Nutzungsumfang ausführen.

```sh
# Persistierte Angebote und letzter erfolgreicher Beobachtungszeitpunkt
docker compose run --rm pipeline python -m backend.flow catalog
# Tagesabruf mit denselben DB-Produkt-URLs
docker compose run --rm pipeline python -m backend.flow daily
# Ergebnisse und Importstatus
docker compose run --rm pipeline python -m backend.flow verify
# Nach Klärung des zulässigen Abrufumfangs: Zeitplan bedienen
docker compose up -d pipeline
docker compose logs --tail 50 pipeline
docker compose ps
```

DAILY liest importierte MediaMarkt-Angebote mit Preisbeobachtung, unterstützter Kategorie und URL aus PostgreSQL und filtert sie nach dem aktuellen Marken-/GPU-Scope. Historische ausserhalb des Scopes liegende Angebote bleiben gespeichert. Neue Produkte kommen über die manuelle Auswahl oder `initial --from-catalog` hinzu. Nicht mehr erreichbare URLs werden protokolliert und bleiben im Katalog. Ein fehlgeschlagener Abruf erzeugt keinen Ersatzpreis und löscht keine Vergangenheit.

Die konservativen Standardlimits sind **3 Produktversuche pro Kategorie und 20 HTTP-Requests insgesamt**, einschliesslich robots.txt und Redirects, mit mindestens 3 Sekunden Abstand. `catalog` zeigt bekannte, versuchte und erfolgreich geparste SKUs je Kategorie; der letzte Collector-Report enthält `remaining_due`, Fehler und Requestzahl. Nur nach geklärtem Nutzungsumfang können `--max-products`, `--max-requests` und `--delay` für einen manuellen Lauf oder `PIPELINE_MAX_PRODUCTS`, `PIPELINE_MAX_REQUESTS` und `PIPELINE_DELAY_SECONDS` in `.env` für den Prefect-Schedule angepasst werden. Ein grösseres Tagesziel ist mit den Standardlimits nicht vollständig abgedeckt.

Bereits heute erfolgreich beobachtete Angebote werden ohne HTTP-Aufruf übersprungen. Ein neuer Tag erlaubt eine neue Preisbeobachtung, auch bei gleichem Preis. Abgelehnte/ungeklärte oder bei HTTP 404 verschwundene Produkte werden nicht künstlich als günstig, kostenlos oder verkauft gespeichert. `OutOfStock` mit einem belegten Preis kann als Beobachtung mit dieser Verfügbarkeit gespeichert werden.

Prefect-UI: [localhost:4200](http://localhost:4200). Flow: `DENG MediaMarkt Batch`, Deployment: `mediamarkt-daily`. Bei INITIAL/DAILY/REPLAY müssen Collect, Transform und Load sowie der Gesamtstatus geprüft werden; reine Discovery endet nach Collect. Der Ergebnisblock `outcome` trennt neue Beobachtungen von wiederverarbeiteten Raw-Dateien. Ein fehlgeschlagener Abruf lässt den Gesamtflow scheitern, obwohl vorhandene gültige Raw-Dateien noch geladen werden können.

Den Schedule ohne Änderung seines Zustands prüfen:

```sh
docker compose exec -T prefect_server env PREFECT_API_URL=http://localhost:4200/api prefect deployment inspect 'DENG MediaMarkt Batch/mediamarkt-daily' --output json
```

Im Ergebnis müssen `mode: daily`, `0 3 * * *` und `Europe/Zurich` stehen. `paused` und `active` zeigen den tatsächlichen aktuellen Zustand; diese Anleitung setzt keinen festen Wert voraus. `serve` akzeptiert absichtlich nur DAILY.

`PIPELINE_CRON` in `.env` ändert den Zeitplan; danach `docker compose up -d pipeline` ausführen. Der Runner und Rechner müssen laufen. Während Schlafmodus/Stillstand ist eine pünktliche Ausführung nicht garantiert. Der frühere Modus `--mode live` bleibt als Alias für DAILY unterstützt; im normalen Betrieb die obigen Befehle nutzen.

Falls der Zeitplan nach einem Neustart weiterhin pausiert ist, kann er nach der Zugriffsklärung mit `docker compose exec -T pipeline prefect deployment schedule resume --deployment_name 'DENG MediaMarkt Batch/mediamarkt-daily' --schedule_id <ID>` aktiviert werden. Die ID zuerst mit `docker compose exec -T pipeline prefect deployment inspect 'DENG MediaMarkt Batch/mediamarkt-daily' --output json` ablesen. Für reine Replay-Verifikation ist keine Aktivierung nötig.

## SQL-Verifikation

```sh
docker compose exec postgres sh
```

Im Container:

```sh
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

In psql:

```sql
SELECT category, count(DISTINCT product_id) AS products, count(*) AS observations
FROM hardware_prices GROUP BY category ORDER BY category;
SELECT product_name, platform, seller_name, price_chf, observed_at, raw_path
FROM hardware_prices ORDER BY observed_at DESC;
SELECT status, reason, count(*) FROM raw_import GROUP BY 1,2;
SELECT retailer_product_id, collected_at, count(*)
FROM price_history GROUP BY 1,2 HAVING count(*) > 1;
```

Die letzte Abfrage muss leer bleiben. `\q` beendet psql, `exit` die Container-Shell. Weitere SQL-Abfragen: [verification.sql](../data/queries/verification.sql).

Der vollständige schreibgeschützte Katalogbericht (Kategorien, Marken, Verkäufer, Preisverlauf und Qualitätsprüfungen) läuft direkt aus dem Projektroot:

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < data/queries/catalog_stats.sql
```

## Replay und Backfill

```sh
docker compose run --rm pipeline python -m backend.flow replay
docker compose run --rm pipeline python -m backend.flow replay --input /workspace/data/raw/mediamarkt/live-check
```

Der zweite Befehl zeigt einen gezielten Backfill/Replay mit vorhandenen echten Rohdaten. Für andere Bestände `--input` auf einen tatsächlichen Unterordner in `data/` setzen. Bereits bekannte Beobachtungen werden erkannt; der Originalzeitpunkt wird niemals durch das Importdatum ersetzt. Der Ordner `live-check` enthält den echten früheren RAM-Abruf, keine Demo-Daten.

## Tests

```sh
docker compose run --rm pipeline python -m unittest discover -s backend/tests -v
```

HTTP-Tests verwenden Fixtures/Mocks. DB-Tests arbeiten nur in eigenen temporären Schemas. Die echten Daten im Standardschema werden nicht gelöscht. Phase 4B: 58 Tests erfolgreich, einschliesslich Discovery, Catalog-INITIAL und Raw-Wiederaufnahme. Nachweise und Einschränkungen: [PHASE3_5.md](PHASE3_5.md).

## Shutdown ohne Datenverlust

```sh
docker compose stop
```

Volumen und Daten bleiben erhalten. Wiederstart: `docker compose up -d --wait`. Der Pipeline-Service bedient dann wieder den täglichen Schedule. Kein `down -v` verwenden, um Daten zu behalten.
