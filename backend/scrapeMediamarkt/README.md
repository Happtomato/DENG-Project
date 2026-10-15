# MediaMarkt: Katalogaufbau und tägliche Preisbeobachtungen

Python 3.10+; alle Befehle hier werden im DENG-Projektverzeichnis ausgeführt.
Die Pfade im Code sind unabhängig vom aktuellen Arbeitsverzeichnis.

```powershell
python -m pip install -r backend/scrapeMediamarkt/requirements.txt
```

## 1. Produktlinks entdecken und erste Produkte prüfen

```powershell
python backend/scrapeMediamarkt/pipeline.py discover
```

Pro Lauf werden standardmässig höchstens zwei Kategorieseiten je GPU/RAM/SSD
und zehn Produktseiten je Kategorie abgerufen, insgesamt höchstens 100 Requests.
Zwischen Requests liegen mindestens drei Sekunden; robots.txt kann mehr verlangen.
Die echten ProductList-IDs der Kategorieseite bestimmen die Kandidaten.
Produktempfehlungen oder Navigationslinks werden nicht als Katalogtreffer verwendet.

Die Seitenposition wird nach jeder erfolgreichen Seite gespeichert. Derselbe Befehl
setzt den Aufbau beim nächsten Aufruf fort. Nach dem Ende einer Kategorie beginnt
ein neuer Suchzyklus auf Seite 1, um neue Produkte zu entdecken. Das ist ein laufender
Shopkatalog, kein vollständiges Archiv aller jemals produzierten Modelle.

Nur Links sammeln:

```powershell
python backend/scrapeMediamarkt/pipeline.py discover --links-only --max-pages 5
```

Anschliessend gespeicherte, noch ungeprüfte Kandidaten abarbeiten:

```powershell
python backend/scrapeMediamarkt/pipeline.py collect --max-products 20
```

Der Katalog liegt in `data/catalog/mediamarkt.json`. Schlüssel sind
`mediamarkt:<retailer_sku>`; Varianten und Händler-SKUs werden nicht anhand ähnlich
klingender Namen zusammengelegt. Trackingparameter werden aus Produktlinks entfernt.

## 2. Umfang nach Pitch

`scope.json` enthält anpassbare Grenzen; leere `brands`-Listen bedeuten alle Marken:

- GPU: Consumer-Desktop, GeForce RTX ab Modell 3000 und Radeon RX ab Modell 6000.
- RAM: DDR4/DDR5, Desktop-DIMM, 8–64 GB Gesamtkapazität.
- SSD: interne NVMe, PCIe 3.0/4.0/5.0, 256–4000 GB; 1 TB = 1000 GB.
- Gebraucht/Refurbished, erkennbare Server-/NAS-/Workstation-Produkte,
  SO-DIMM/Notebook-RAM, HDDs und externe/SATA-SSDs werden ausgeschlossen.
- Fehlende Belege und widersprüchliche Angaben erhalten `review`.

Beispiel für einen separaten ASUS-Katalog, RTX 30 und neuer:

```powershell
python backend/scrapeMediamarkt/pipeline.py discover --categories gpu --brand ASUS --gpu-family rtx --catalog data/catalog/mediamarkt_asus.json
python backend/scrapeMediamarkt/pipeline.py collect --categories gpu --brand ASUS --gpu-family rtx --catalog data/catalog/mediamarkt_asus.json
```

Die CLI-Filter gelten nur für den jeweiligen Aufruf. Für dauerhafte Einschränkungen
eine eigene Konfigurationsdatei mit `--config` verwenden und bei Folgeaufrufen
denselben Katalog und dieselbe Konfiguration angeben. Die Prüfung erfolgt auf der
Produktseite; auch nicht passende Kandidaten können dafür einen Abruf benötigen.
ROG ist eine ASUS-Produktfamilie, keine zusätzliche Hersteller-ID.

Bekannte ältere Produktlinks lassen sich ergänzen, auch wenn sie im aktuellen
Kategoriekatalog fehlen:

```powershell
python backend/scrapeMediamarkt/pipeline.py add --categories gpu --url https://www.mediamarkt.ch/de/product/_asus-prime-geforce-rtx-5070-12gb-gddr7-nvidia-grafikkarte-2277751.html
python backend/scrapeMediamarkt/pipeline.py collect --categories gpu
```

`add` legt nur einen Kandidaten an. Es validiert noch keine technischen Daten.
Eine heute gefundene RTX-30-Karte liefert heutige Beobachtungen, keine Preisreihe
seit deren Markteinführung. Historische Daten benötigen eine eigene Quelle.

## 3. Täglicher Lauf mit gespeicherten Links

```powershell
python backend/scrapeMediamarkt/pipeline.py daily --max-products 100 --max-requests 350
```

Dieser Befehl ruft nur Produkte mit Status `accepted` auf, ohne Kategoriesuche.
Die Produktseite wird weiterhin auf Identität, Zustand und Datenqualität geprüft.
Bereits erfolgreich beobachtete Produkte werden am selben Kalendertag in
`Europe/Zurich` übersprungen. Zeitstempel werden in UTC gespeichert.
Ein zweiter Aufruf am selben Tag erzeugt keine zweite Batch-Beobachtung.
Auch ein Abbruch zwischen dem Schreiben der Tagesdatei und dem Katalog-Update
kann anhand der vorhandenen Tagesdatei ohne erneuten Abruf wiederaufgenommen werden.

Der Befehl ist für einen späteren täglichen Scheduler-Aufruf vorbereitet.
Es wurde noch kein Scheduler installiert oder aktiviert. Request- und Produktlimits
müssen zum Katalogumfang passen; `remaining_due` und `stopped_reason` im Laufbericht
zeigen nicht erledigte Arbeit. Fehler führen zu Exitcode 1. Bei Bedarf denselben
Befehl erneut starten; bereits erfolgreiche Tagesbeobachtungen werden ausgelassen.

```powershell
python backend/scrapeMediamarkt/pipeline.py status
python backend/scrapeMediamarkt/pipeline.py collect --recheck
```

`--recheck` prüft zusätzlich `review` und `excluded` gegen die aktuelle Konfiguration.
Am selben Tag nutzt es vorhandene Rohdaten. Der Status im Katalog ist die aktuelle
Entscheidung; die Rohdatei behält die beim ursprünglichen Abruf gespeicherte Entscheidung.

## 4. Dateien, Fehler und Wiederaufnahme

- `data/catalog/mediamarkt.json`: Linkkatalog mit Status, EAN/MPN, letzter Beobachtung
  und Fehlerzähler. Status: `candidate`, `accepted`, `excluded`, `review`.
- `data/catalog/runs/*.json`: Parameter, Anzahl Requests, Ergebnisse und Fehler je Lauf.
- `data/raw/mediamarkt/<sku>_<YYYY-MM-DD>.json`: Tagesdateien des Batch-Scrapers.
- `data/debug/mediamarkt/*.html`: Originalantworten je Produkt/Kategorieseite und Abruf.
- `raw_payload`: unverändertes geparstes Product-JSON-LD.
- `technical_payload`: zu dieser SKU gehörende technische Features als Prüfbelege.

Der bestehende Einzelproduktaufruf bleibt möglich und schreibt weiterhin Dateien
mit Zeitstempel. Er führt keinen Linkkatalog und keine Tages-Deduplizierung:

```powershell
python backend/scrapeMediamarkt/app.py --html data/debug/mediamarkt_product.html
```

Der Batch läuft sequenziell, prüft robots.txt auch vor Redirect-Zielen und akzeptiert
nur öffentliche deutsche MediaMarkt-HTML-Seiten. Bei 401/403/429/503 wird der gesamte
Lauf gestoppt; keine Proxywechsel oder sofortigen Wiederholungen. 404 und andere
einzelne Fehler werden protokolliert; der Link bleibt für spätere Läufe erhalten.
`OutOfStock` ist eine gültige Beobachtung und deaktiviert keinen Link.
Fehlende/ungültige Preise werden nicht erfunden. Der Laufbericht zählt sie separat.

Katalog und Tagesdateien werden über temporäre Dateien atomar ersetzt.
Eine `.lock`-Datei verhindert parallele Schreiber auf denselben Katalog. Nach einem
harten Prozessabbruch die Lock-Datei nur entfernen, wenn der Prozess sicher beendet ist.

## 5. PostgreSQL und mehrere Händler

Eine zusätzliche Linkspalte pro Händler ist nicht erforderlich. Das vorhandene
Schema bildet genau diese Beziehung ab:

| Tabelle | Bedeutung |
| --- | --- |
| `product` | Händlerübergreifendes physisches Produkt |
| `retailer` | Händler |
| `retailer_product` | Angebot/Listing mit `product_id`, `retailer_id`, `retailer_sku`, `product_url` |
| `price_history` | Beobachtungen pro `retailer_product_id` |

Ein identisches Produkt kann mehrere `retailer_product`-Zeilen haben: eine für
MediaMarkt, eine für Digitec usw. `UNIQUE (retailer_id, retailer_sku)` existiert bereits.
EAN beziehungsweise Hersteller+MPN sind Belege für das spätere Matching. Varianten
mit anderer Kapazität, Kühlung oder OC-Ausführung nicht anhand des GPU-Chips vereinigen.

Nach einem gesonderten Ingest-Schritt sind die Händlerlinks z.B. so verfügbar:

```sql
SELECT rp.retailer_product_id, rp.retailer_sku, rp.product_url
FROM retailer_product AS rp
JOIN retailer AS r ON r.retailer_id = rp.retailer_id
WHERE r.name = 'MediaMarkt' AND rp.product_url IS NOT NULL;
```

Diese Änderung implementiert den Scraper und seinen lokalen Linkkatalog. Sie öffnet
keine PostgreSQL-Verbindung, schreibt keine DB-Zeilen und ändert das Schema nicht.
Beim späteren Ingest:

1. Nur bestätigte, zum Scope passende Rohdaten übernehmen; `review`/`excluded` bleiben Auditdaten.
2. Brand/Category/Retailer auflösen, Produkt über geprüfte Identifikatoren zuordnen.
   `metadata.category_code` liefert `gpu`/`ram`/`ssd` zur einheitlichen Kategoriezuordnung.
3. `retailer_product` nach `(retailer_id, retailer_sku)` upserten und Link aktualisieren.
4. Nur positive CHF-Preise mit zugehöriger Listing-ID in `price_history` schreiben.
   Leere Detailobjekte erzeugen keine RAM-/SSD-Zeile für eine GPU.
5. IDENTITY-IDs und DB-Zeitstempel weglassen bzw. DB-seitig erzeugen, nicht explizit NULL einfügen.
6. Für tägliche DB-Idempotenz `(Listing, Beobachtungstag Europe/Zurich)` verwenden.
   Das bestehende UNIQUE auf dem exakten `collected_at` verhindert keine zwei Abrufe
   mit unterschiedlichen Zeitstempeln am selben Tag.

MediaMarkt kann Marketplace-Angebote enthalten. `source=mediamarkt` bezeichnet die
Plattform, nicht zwingend den tatsächlichen Verkäufer. Für reine Händlervergleiche
ist eine zusätzliche verifizierte Verkäuferzuordnung im Ingest erforderlich.

## 6. Tests und bekannte Grenzen

```powershell
python -m unittest discover -s backend/scrapeMediamarkt/tests -v
```

Die Fixtures sind auf relevante JSON-LD-, Apollo- und Linkdaten reduzierte reale
HTML-Antworten vom 15.10.2026. GPU: gespeicherte ASUS-5070-Seite; RAM: Corsair
2230728; SSD: Samsung 2155505 und Kingston 145381326. Die Tests nutzen kein Netzwerk.
HTTP-Fehler, Budgetgrenzen und Wiederaufnahme werden isoliert simuliert.

Geprüft werden u.a. Produktvarianten, TB→GB, deutsche Tausendertrennzeichen,
RAM-Kitgrösse, Scope-Prüfung, Schemafelder, unverändertes JSON-LD, Duplikate,
Locks, Fehlerfortsetzung, Redirect-Prüfung und Pagination.

Die technischen Angaben des Händlers können lückenhaft oder widersprüchlich sein;
unbekannte Werte bleiben NULL. Die RTX-5070-Seite nennt 2512 MHz als Standard-Boost
und 2542 MHz als OC-Modus: `boost_clock_mhz` verwendet den expliziten Standard-Boost.
Ein allgemeines Feld „Grafik-Taktfrequenz“ wird nicht pauschal als Basis- oder
Boost-Takt interpretiert. Die OC-Angabe bleibt in den Originalfeatures erhalten.

Weitere Händler, Hersteller-Enrichment, historische Backfills, Datenbank-Ingest
und Cloud-Orchestrierung sind separate Module entsprechend dem Pitch.
