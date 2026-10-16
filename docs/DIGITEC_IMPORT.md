> Phase 3: Früherer Adaptercode ist passiv in [phase1-code.tar.gz](archive/phase1-code.tar.gz) erhalten. Kein aktiver Digitec-Import.

> Inaktiver Phase-1-Entwurf: kein aktiver Midterm-Import. Umsetzung erst anhand echter autorisierter Daten neu prüfen. Aktueller Ablauf: [PHASE2.md](PHASE2.md).

# Digitec: Vorbereitung ohne Umgehung des Zugriffsschutzes

Derzeit fehlen Digitec-Quelldaten und eine Antwort auf die Anfrage des Teams. `scrape_digitec` ist daher ein Importjob ohne Netzwerkzugriff. Eine leere Inbox meldet `awaiting_source_data` und ist kein erfundener erfolgreicher Scrape.

Nach Erhalt eines erlaubten Exports muss dessen echtes Format geprüft werden. Der vorhandene Adapter unterstützt folgenden ausdrücklich projektinternen Austauschvertrag, nicht ein behauptetes offizielles Digitec-API-Format. Ein Dokument darf ein Objekt oder eine Liste solcher Objekte enthalten. Pro Objekt entsteht eine Raw-Datei; das vollständige Eingabedokument bleibt als Herkunftsnachweis erhalten.

Erforderliche Felder:

- `source_product_id`: Digitec-ID als String.
- `source_url`: HTTPS-Produktadresse auf digitec.ch.
- `collected_at`: dokumentierter Empfang/Abruf der Quelle als ISO-8601 mit Zeitzone; nicht beim Rerun neu erzeugen.
- `category_code`: `gpu`, `ram` oder `ssd`; `scope_status: accepted` erst nach tatsächlicher Scope-Prüfung.
- `brand` und `product.product_name`; mindestens eine geprüfte `product.ean` oder `product.mpn`.
- `product`: optionale Felder `release_date`, `model`, `series`, `generation`, `msrp_chf`, `manufacturer_url`.
- Passendes Detailobjekt mit den Feldnamen aus `data/initialization.sql`. Nicht belegte Werte sind NULL. Keine Spezifikationen aus Modellfamilien ergänzen.
- `observation_type`: `master_data`, `daily_scrape` oder `historical_import`.

`master_data` darf keinen undatierten Preis enthalten. Für einen aktuell beobachteten Preis muss `price_history.price_chf` positiv und `price_history.currency` ausdrücklich `CHF` sein. Der Beobachtungszeitpunkt gehört in `price_history.observed_at`; wenn die Quelle tatsächlich beim Abruf beobachtet wurde, kann er dem `collected_at` entsprechen. `price_basis` lautet `observed_offer`. Optional: `original_price_chf`, `original_price_type`, `availability`.

Historische Importe benötigen zusätzlich `source_series_id`, `source_observation_id` (beide stabil bei erneuten Exporten), `provider`, `price_history.price_date` und eine bekannte `price_basis`: `observed_offer`, `daily_min`, `daily_max`, `daily_close` oder `change_point`. `observed_at` bleibt NULL, wenn nur ein Datum belegt ist. Tagesminimum und einzelne Tagesbeobachtung werden nicht in der Vergleichsansicht vermischt. Keine Lücken durch erfundene tägliche Punkte auffüllen.

Die Händlervergleichsansicht benötigt einen ausdrücklich belegten Verkäufer. Falls vorhanden enthält `seller` die Felder `source_id`, `name`, `verified: true` und `is_retailer: true/false`. Fehlende Verkäuferinformationen werden nicht automatisch mit Digitec ersetzt.

Die ursprünglichen JSON-Felder im Export werden als `raw_payload` unverändert erhalten. `DIGITEC_PERMISSION_REFERENCE` verweist auf eine echte Vereinbarung, E-Mail oder Nutzungsgrundlage. Dieser String ist ein Auditnachweis und kein technischer Beweis einer Lizenz; die Bedingungen müssen vom Team tatsächlich geprüft werden.

Ablauf nach Erlaubnis:

1. Dokumente unter `data/import/digitec/` ablegen. Originale behalten; Mapper-Anpassung bei anderem Format prüfen.
2. In `.env` die echte `DIGITEC_PERMISSION_REFERENCE` setzen.
3. `docker compose run --rm scrape_digitec`
4. `docker compose run --rm ingest_digitec`
5. `docker compose run --rm verify`

Der Import kann beliebig wiederholt werden. Ein anderer Preis unter derselben historischen Ereigniskennung verlangt eine bewusste Korrekturprüfung; er überschreibt nicht stillschweigend die Historie.

Kein Preisbeispiel aus dem Auftrag und keine Testbeobachtung wird in die echte Datenbank geladen. Integrations-Testdaten existieren ausschliesslich in temporären Dateien und eigens erzeugten Testschemas.
