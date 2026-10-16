# MediaMarkt-Adapter

Aktive Dateien: `backend/retailers/mediamarkt/parser.py`, `collector.py` und `scope.json`. Der normale Einstieg bleibt [backend.flow](../backend/flow.py); Befehle stehen in [RUN_COMMANDS.md](RUN_COMMANDS.md).

## Produktseiten und Parsing

Der Adapter liest öffentliche deutsche Produktseiten auf `https://www.mediamarkt.ch/de/product/...-<SKU>.html`. `Client.get_html()` prüft Domain, SKU, robots.txt, Redirects und HTML-Content-Type. Pro Request gibt es einen Timeout und mindestens drei Sekunden Abstand; 401/403/429/503 beenden den Batch ohne aggressive Wiederholung.

`parser.parse_html()` sucht exakt das Product-JSON-LD zur URL-SKU, einschliesslich verschachtelter Product-Objekte. Empfehlungen mit anderer SKU werden nicht als Zielprodukt verwendet. Preis, CHF-Währung und Verkäufer stammen aus dem ersten JSON-LD-Angebot. Technische Angaben werden aus dem zum selben Produkt gehörenden eingebetteten Apollo-Zustand gelesen, ohne JavaScript auszuführen oder interne APIs aufzurufen.

Kategorie und Details müssen durch Produktdaten/technische Felder bestätigt werden. Die Produktnamen allein reichen nicht für unsichere Varianten-Zusammenführungen. `scope_decision()` prüft zusätzlich:

- GPU: Board-Marke AMD oder MSI oder ASUS mit bestätigter ROG-Serie; bestätigte GeForce-RTX-/Radeon-RX-Familie, mindestens RTX 3000 beziehungsweise RX 6000. „AMD“ als Chip-Hersteller einer Sapphire- oder ASUS-Karte genügt nicht. ASUS Prime/Dual/TUF gehört nicht zum gewählten ROG-Scope.
- RAM: G.Skill, Kingston oder Corsair; DDR4/DDR5, Desktop-DIMM bestätigt, 8–64 GB; keine SO-DIMMs, Server-/ECC-Speicher.
- SSD: Samsung, Western Digital oder Kingston; intern, NVMe, bestätigte PCIe-Generation 3.0/4.0/5.0, 256–4000 GB.
- Zustand: neu; fehlende/konfliktbehaftete Belege bleiben review, unpassende Hardware excluded.

Die anschliessende Transformation prüft Hersteller, gültige Kennungen, Preise, Zeitpunkte und Detailfelder. Ein vom Collector akzeptiertes Produkt ist deshalb nicht automatisch erfolgreich in PostgreSQL geladen. Verkäufer und Plattform bleiben getrennt; ohne Verkäuferbeleg bleibt der Verkäufer unbekannt.

## URLs, Discovery und Pagination

Der Parser ist nicht auf eine einzelne feste URL beschränkt. Die feste GPU-URL im Parser dient weiterhin den bestehenden Tests. Im normalen Betrieb bestimmt INITIAL die URLs über `data/catalog/mediamarkt_initial.json`; DAILY verwendet PostgreSQL-Angebote.

Automatische Entdeckung existiert weiterhin als kleine optionale Adapterfunktion: `discover()` liest Kategorie-Links und Produkt-IDs aus gespeicherten/abgerufenen Kategorieseiten, `listing()` prüft die Vollständigkeit und liest die letzte Seitennummer. Pagination verwendet `?page=N`, einen gespeicherten Cursor und Seitensignaturen zur Erkennung wiederholter Seiten. Es wurde in Phase 3 kein neues umfangreiches Kategorie-Crawling durchgeführt.

Die vorhandenen sechs Aufzeichnungen von zwei Seiten je Kategorie belegen je 24 unterschiedliche automatisch entdeckte URLs. Die damaligen Seitennummern 20 (GPU), 25 (RAM), 4 (SSD) sind historische Quellangaben vom 15.10., keine aktuelle Zusage über den gesamten verfügbaren Katalog und keine Anzahl erfolgreich importierbarer Produkte.

## INITIAL und DAILY

`select_initial()` registriert nur die ausdrücklich ausgewählten URLs; nicht ausgewählte Kandidaten werden nicht nebenbei abgerufen. Die Auswahl umfasst zwei GPU-, drei RAM- und drei SSD-URLs. Die beiden GPU-URLs wurden in einem begrenzten Lauf am 16.10. validiert und importiert. Listing-Titel dienen nur als konservativer Vorfilter, die Produktseite entscheidet über den Scope.

`select_daily()` übernimmt Mitgliedschaft, URLs und letzten erfolgreichen Beobachtungszeitpunkt aus PostgreSQL und lässt frühere, heute ausserhalb des Scopes liegende Produkte aus. Die JSON-Katalogdatei behält Discovery-Kandidaten und Abruffehler, ist für DAILY aber nicht mehr die Quelle der Produktmenge. HTTP-Fehler löschen weder Angebote noch Preise. Bisheriger Tagesabruf und Wiederholung verwenden dieselbe Raw-Datei; ein neuer Tag bekommt einen neuen Originalzeitpunkt. REPLAY interpretiert alte Raw-Dateien unter dem damaligen Scope, damit historische Beobachtungen erhalten bleiben.

Aktuelle, getrennt ausgewiesene Zahlen für bekannte, gefetchte, validierte und importierte Produkte stehen in [PHASE3_5.md](PHASE3_5.md). Raw-Dateien, alte HTML-Aufzeichnungen und Test-Fixtures sind erhalten. Der frühere Einzelprodukt-CLI und `inspect.py` wurden entfernt; ihre zweite Abruf-/Schreiblogik ist nicht mehr nötig.
