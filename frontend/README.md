# PC Price Lab

**Swiss PC hardware prices, under the microscope.** Das lokale SvelteKit-Frontend des HSLU-Projekts liest Produkte, Händlerangebote und `price_history` serverseitig aus PostgreSQL. Es löst keine MediaMarkt-Abrufe aus.

Die Gestaltung ist ein ruhiges Hardware-Research-Lab mit warmem Light Mode und graphitfarbenem Dark Mode. Oben rechts stehen **Hell**, **Dunkel** und **System** sowie **DE** und **EN** zur Wahl. Die Auswahl wird lokal im Browser gespeichert; System folgt der Betriebssystem-Einstellung. Produktnamen, Marken und technische Kennungen bleiben in der Originalsprache. Name und Untertitel sind zentral in `src/lib/identity.ts`, UI-Texte in `src/lib/i18n.ts` definiert.

## Mit Docker Compose starten (empfohlen)

Im Projektroot muss eine lokale `.env` mit den PostgreSQL-Werten aus `.env.example` existieren. Danach genügt:

```sh
cd /pfad/zum/DENG-Project
docker compose up -d --build
```

Compose startet PostgreSQL, eine einmalige idempotente Schema-Initialisierung, Prefect Server, Pipeline Runner und PC Price Lab im gemeinsamen Netzwerk. Bestehende Volumes, Raw-Daten und Preisbeobachtungen bleiben erhalten. Das Frontend ist unter [http://localhost:3000](http://localhost:3000) erreichbar; Prefect unter [http://localhost:4200](http://localhost:4200).

```sh
docker compose ps
docker compose logs frontend --tail=50
docker compose down
```

`docker compose down` lässt Datenbank- und Prefect-Volumes bestehen. Der Pipeline Runner startet den bestehenden DAILY-Deployment; ob sein Schedule aktiv ist, zeigt das Dashboard aus Prefect an. Der Frontend-Container löst selbst keine MediaMarkt-Abrufe aus.

## Ohne Frontend-Container entwickeln

Voraussetzungen: Node.js 24, npm, Docker Desktop sowie die bestehende Root-`.env` aus `.env.example`.

```sh
cd /pfad/zum/DENG-Project
docker compose up -d postgres prefect_server
cp .env frontend/.env.local
printf '\nPOSTGRES_HOST=127.0.0.1\n' >> frontend/.env.local
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Danach [http://127.0.0.1:5173](http://127.0.0.1:5173) öffnen. `frontend/.env.local` ist ignoriert und darf nicht eingecheckt werden. Alternativ reicht eine `DATABASE_URL` in dieser Datei. `PREFECT_API_URL` ist optional und standardmässig `http://127.0.0.1:4200/api`. Wenn das Frontend ausserhalb des Repositorys gestartet wird, `CATALOG_PATH` auf die absolute `data/catalog/mediamarkt.json` setzen.

## Seiten und Daten

- **Übersicht:** Produktsuche, Kategorie-Einstiege, ein hervorgehobener echter Preisverlauf, neueste Beobachtungen und kompakte Projektzahlen.
- **Explore:** Suche nach Name/Marke/Modell, Kategorie, Hersteller, Händler, CHF-Preisbereich und Sortierung. Die Liste ist auf 18 Produkte pro Seite begrenzt.
- **Produktdetail:** originale Händler-URL, vorhandene technische Merkmale, Angebots- und Beobachtungsdaten. Das Diagramm verwendet ausschliesslich gespeicherte Beobachtungszeitpunkte. Bei einer Messung steht ein Punkt ohne Verlaufslinie.
- **Analytics:** Abdeckung und Datenqualität ohne geschätzte Trends.
- **Pipeline Lab:** Prefect-Deployments und Runs (Aktualisierung alle 15 Sekunden), Kandidatenkatalog mit Kategorie-/Statuszahlen und read-only Datenbankprüfung.

Read-only JSON-Endpunkte: `GET /api/products`, `GET /api/products/:id`, `GET /api/verify`. Die Datenbankabfragen verwenden Parameterbindung; Credentials bleiben auf dem SvelteKit-Server. Prefect-Status wird ebenfalls nur serverseitig abgerufen.

Der vorhandene Prefect-Deployment `mediamarkt-daily` kann extern aktiviert oder pausiert werden; das Dashboard liest den aktuellen Zustand, verändert ihn aber nicht. Weil kein sicherer manueller Runner für die verschiedenen Modi konfiguriert ist, zeigt es DISCOVER, INITIAL, DAILY und REPLAY bewusst als **nicht verfügbar**. Diese Buttons starten keine versteckten Prozesse. Die dokumentierten [CLI-Befehle](../docs/RUN_COMMANDS.md) bleiben der manuelle Weg.

## Prüfen

```sh
cd frontend
npm run check
npm run build
npm run test:integration   # erwartet laufendes Frontend auf 127.0.0.1:5173
DASHBOARD_TEST_URL=http://127.0.0.1:3000 npm run test:integration  # Docker-Version
```

Die Google-Fonts sind als lokale `@fontsource`-Pakete installiert, sodass das Dashboard ohne externe Font-Anfragen dargestellt wird. Chart.js wird erst im Browser geladen.

Bekannte Einschränkungen: Viele Produkte haben derzeit nur einen Preispunkt; dort wird kein künstlicher Verlauf gezeichnet. Manuelle Prefect-Starts bleiben im Frontend deaktiviert, bis ein sicherer Runner dafür eingerichtet ist. Die DE/EN-Umschaltung betrifft UI-Texte, nicht Rohdaten, Produktnamen oder alle freien Fehlertexte aus PostgreSQL/Prefect.
