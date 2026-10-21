import type { Language } from './preferences.svelte';

const en: Record<string, string> = {
	Übersicht: 'Overview',
	Entdecken: 'Explore',
	Analysen: 'Analytics',
	'Pipeline Lab': 'Pipeline Lab',
	Sprache: 'Language',
	Darstellung: 'Appearance',
	Hell: 'Light',
	Dunkel: 'Dark',
	System: 'System',
	'Lokales Projekt': 'Local project',
	'Lokale Datenbank': 'Local database',
	Datenquelle: 'Data source',
	'Zur Pipeline': 'To the pipeline',
	'Echte Daten, klar gekennzeichnet': 'Real data, clearly labelled',
	'Entdecke, wie sich Hardwarepreise verändern.': 'See how hardware prices change.',
	'Wir beobachten Schweizer Hardwarepreise und machen ihre Entwicklung sichtbar.':
		'We track Swiss hardware prices and make their history visible.',
	'Produkt, Marke oder Modell suchen …': 'Search product, brand or model …',
	'Produkte suchen': 'Search products',
	Alle: 'All',
	'Preisverlauf im Fokus': 'Featured price history',
	'Die Preisgeschichte wächst mit jeder echten Beobachtung.':
		'The price history grows with every real observation.',
	'Zuletzt beobachtet': 'Recently observed',
	'Neueste echte Preismessungen aus PostgreSQL.': 'Latest real price observations from PostgreSQL.',
	'Komponenten entdecken': 'Explore components',
	'Vom Grafikchip bis zur schnellen SSD.': 'From graphics cards to fast SSDs.',
	Grafikkarten: 'Graphics cards',
	Arbeitsspeicher: 'Memory',
	SSDs: 'SSDs',
	Produkte: 'Products',
	Beobachtungen: 'Observations',
	Händler: 'Retailer',
	'Alle Produkte ansehen': 'View all products',
	'Pipeline öffnen': 'Open Pipeline Lab',
	'Kein Preisverlauf vorhanden.': 'No price history yet.',
	'Für dieses Produkt liegt erst eine echte Messung vor.':
		'This product has only one real observation so far.',
	'Produkte entdecken.': 'Explore products.',
	'Durchsuche importierte Hardware, Angebote und tatsächliche Preisbeobachtungen.':
		'Browse imported hardware, offers and real price observations.',
	'Die Produktdatenbank ist momentan nicht erreichbar.':
		'The product database is currently unavailable.',
	'Produkt suchen': 'Search products',
	Suche: 'Search',
	Kategorie: 'Category',
	'Alle Kategorien': 'All categories',
	Hersteller: 'Brand',
	'Alle Hersteller': 'All brands',
	'Alle Händler': 'All retailers',
	Sortierung: 'Sort by',
	'Preis aufsteigend': 'Price: low to high',
	'Preis absteigend': 'Price: high to low',
	'Name A–Z': 'Name A–Z',
	'Filter verfeinern': 'Refine filters',
	Zurücksetzen: 'Reset',
	Anwenden: 'Apply',
	'Importierte Produkte': 'Imported products',
	Ergebnisse: 'Results',
	Seite: 'Page',
	von: 'of',
	'Lade Produkte': 'Loading products',
	'Technische Details nicht vorhanden': 'No technical details available',
	'Letzter Preis': 'Latest price',
	'Noch keine Preisbeobachtung': 'No price observation yet',
	'Keine Produkte mit diesen Filtern gefunden. Prüfe Suchbegriff oder Preisbereich.':
		'No products match these filters. Try another search or price range.',
	Vorherige: 'Previous',
	Nächste: 'Next',
	'Zurück zum Explorer': 'Back to explorer',
	'Aktueller Preis': 'Current price',
	'Kein Angebot': 'No offer',
	'Tiefster Preis': 'Lowest price',
	'Beobachtetes Minimum': 'Observed minimum',
	'Höchster Preis': 'Highest price',
	'Beobachtetes Maximum': 'Observed maximum',
	'Alle Händlerangebote': 'All retailer offers',
	'Echte Preismessungen': 'Real price observations',
	Preisverlauf: 'Price history',
	Messpunkt: 'data point',
	Messpunkte: 'data points',
	'Technische Daten': 'Technical details',
	Modell: 'Model',
	Ja: 'Yes',
	Nein: 'No',
	Händlerangebote: 'Retailer offers',
	'Jedes Angebot hat eine eigene Preisreihe.': 'Each offer has its own price series.',
	'Verfügbarkeit unbekannt': 'Availability unknown',
	'Original-Produktseite öffnen': 'Open original product page',
	'Noch kein Händlerangebot vorhanden.': 'No retailer offer yet.',
	'Alle Beobachtungen': 'All observations',
	'Originale Zeitpunkte': 'Original timestamps',
	Zeitpunkt: 'Time',
	Verfügbarkeit: 'Availability',
	'Noch keine Preisbeobachtungen.': 'No price observations yet.',
	'Für diesen Zeitraum gibt es noch keine Beobachtungen.': 'No observations in this period yet.',
	'Bisher eine Beobachtung. Eine Linie erscheint erst mit einem zweiten echten Messpunkt.':
		'One observation so far. A line appears only after a second real measurement.',
	Zeitraum: 'Time range',
	'Preisverlauf aus echten Preisbeobachtungen': 'Price history from real observations',
	'Preisverlauf aus Preisbeobachtungen und historischen Preiswechseln':
		'Price history from observations and historical price changes',
	Messung: 'Observation',
	'historische Preiswechsel': 'historical price changes',
	'kein belegter Preis': 'no recorded price',
	'Digitec-Preiswechsel sind historische Händlerangaben, keine eigenen Tagesmessungen.':
		'Digitec price changes are retailer history, not our daily observations.',
	'Gestrichelte Stellen bedeuten: nicht verfügbar, kein belegter Preis.':
		'Dashed sections mean unavailable; no price was recorded.',
	'MESSUNGEN & HÄNDLERHISTORIE': 'OBSERVATIONS & RETAILER HISTORY',
	Preiswechsel: 'price changes',
	Datenpunkte: 'data points',
	Jahr: 'year',
	'Wie oft wechseln die Preise?': 'How often do prices change?',
	'Tatsächliche Preisänderungen pro Jahr, gemessen vom ersten bis zum letzten gespeicherten Digitec-Preis.':
		'Actual price changes per year, measured from the first to the last saved Digitec price.',
	'tatsächliche Preisänderungen': 'actual price changes',
	'unter 90 Tagen Verlauf': 'less than 90 days of history',
	'Gleiche Preise und Punkte ohne verfügbaren Preis zählen nicht als Änderung. Unter 90 Tagen Verlauf wird keine Jahresrate berechnet.':
		'Unchanged prices and unavailable-price points do not count as changes. No annual rate is calculated for histories under 90 days.',
	'Zoom zurücksetzen': 'Reset zoom',
	'Zum Vergrössern einen Bereich im Diagramm aufziehen.':
		'Drag across the chart to zoom into a section.',
	'Mit Digitec-Preisverlauf': 'With Digitec price history',
	'Digitec-Verlauf': 'Digitec history',
	'Nur historischer Preisverlauf (manuell zugeordnet)':
		'Historical price changes only (manually matched)',
	'Gestrichelte Händlerlinien und farbige Flächen markieren belegte Nichtverfügbarkeit.':
		'Dashed retailer lines and shaded areas mark recorded unavailability.',
	'Drei Produkte im Zeitverlauf': 'Three products over time',
	'Je ein vorhandenes Beispiel für RAM, SSD und GPU. Linien zeigen manuell gespeicherte Digitec-Preiswechsel, nicht tägliche Messungen.':
		'One available example each for RAM, SSD and GPU. Lines show manually saved Digitec price changes, not daily observations.',
	'Chipmangel 2020–2022': 'Chip shortage 2020–2022',
	'KI-Nachfrage ab März 2023': 'AI demand from March 2023',
	'Historische Analyse momentan nicht verfügbar.': 'Historical analysis is currently unavailable.',
	'Noch keine historischen Preiswechsel importiert.': 'No historical price changes imported yet.',
	'Die Flächen sind zeitlicher Marktkontext, kein Beleg für die Ursache eines konkreten Ladenpreises. GPU-Historien beginnen hier erst 2025; für den Chipmangel gibt es in dieser Kategorie keine Messpunkte.':
		'The shaded periods provide market context; they do not prove the cause of any retail price. Our GPU history starts in 2025, with no GPU data for the chip-shortage period.',
	'Für die Chipmangel-Phase liegen zu diesem Beispiel keine Daten vor.':
		'This example has no data from the chip-shortage period.',
	'Alle Zeiträume': 'All time',
	'Abdeckung und Datenqualität.': 'Coverage and data quality.',
	'Keine geschätzten Trends und keine Hochrechnung auf den Gesamtmarkt.':
		'No estimated trends or extrapolation to the whole market.',
	Datenbestand: 'Dataset',
	Abdeckung: 'Coverage',
	Preisbeobachtungen: 'Price observations',
	'Neuester Messzeitpunkt': 'Latest observation',
	Kategorieverteilung: 'Category mix',
	'Anteil an importierten Produkten, nicht an Katalogkandidaten.':
		'Share of imported products, not catalog candidates.',
	'PREIS / KAPAZITÄT': 'PRICE / CAPACITY',
	'Was kostet ein GB?': 'What does one GB cost?',
	'X: Kapazität in GB · Y: durchschnittliche CHF pro GB. Pro Produkt zählt das günstigste zuletzt beobachtete Händlerangebot.':
		'X: capacity in GB · Y: average CHF per GB. Each product uses the lowest latest observed retailer offer.',
	'Nur Produkte mit bestätigter Kapazität und echtem CHF-Preis. Jede Gruppe zeigt ihren Stichprobenumfang; keine repräsentativen Marktpreise. Bei GPUs ist CHF pro GB VRAM kein Mass für die Rechenleistung.':
		'Only products with confirmed capacity and a real CHF price. Each group shows its sample size; these are not representative market prices. For GPUs, CHF per GB of VRAM does not measure processing performance.',
	'Grafikkarten · VRAM': 'Graphics cards · VRAM',
	Kapazität: 'Capacity',
	'CHF pro GB': 'CHF per GB',
	'Preis in CHF': 'Price in CHF',
	Produktpreis: 'Product price',
	'Diagramm-Metrik': 'Chart metric',
	'Durchschnittspreis nach Kapazität': 'Average price by capacity',
	'Werte zum Diagramm': 'Chart values',
	'Produkte in dieser Gruppe': 'products in this group',
	'Produkt in dieser Gruppe': 'product in this group',
	'Noch keine Produkte mit Preis und bestätigter Kapazität.':
		'No products with both a price and confirmed capacity yet.',
	'Kapazitätsanalyse momentan nicht verfügbar.': 'Capacity analysis is currently unavailable.',
	Validierung: 'Validation',
	'Ungültige Preise': 'Invalid prices',
	'Doppelte Beobachtungszeitpunkte': 'Duplicate observation timestamps',
	'Basierend auf CHF- und Eindeutigkeitsprüfungen in PostgreSQL.':
		'Based on CHF and uniqueness checks in PostgreSQL.',
	'Letzte Messungen': 'Recent observations',
	'Aktuelle Stichprobe, keine vollständige Marktübersicht.':
		'Current sample, not a complete market overview.',
	'Explorer öffnen': 'Open explorer',
	'Keine Messungen vorhanden.': 'No observations yet.',
	'Aussagekräftige Preisverläufe entstehen erst durch weitere echte Tagesbeobachtungen.':
		'Meaningful price histories require more real daily observations.',
	'Alles im Fluss.': 'Everything is flowing.',
	'Prefect-Status, Datenqualität und Kandidatenkatalog an einem Ort.':
		'Prefect status, data quality and candidate catalog in one place.',
	'Prefect öffnen': 'Open Prefect',
	Aktualisieren: 'Refresh',
	Erreichbar: 'Reachable',
	'Nicht erreichbar': 'Unavailable',
	Aktiv: 'Active',
	Pausiert: 'Paused',
	Unbekannt: 'Unknown',
	Katalogkandidaten: 'Catalog candidates',
	'Manuelle Schritte': 'Manual steps',
	Aktionen: 'Actions',
	'Nur sichere, tatsächlich unterstützte Aktionen sind ausführbar.':
		'Only supported, safe actions can be run.',
	'PostgreSQL-Bestand und Qualitätsregeln prüfen.': 'Check PostgreSQL data and quality rules.',
	'Prüfe …': 'Checking …',
	'Jetzt prüfen': 'Check now',
	'Nicht verfügbar': 'Unavailable',
	'Katalog-Links sammeln · Live-Abrufe': 'Collect catalog links · live requests',
	'Kandidaten importieren · Live-Abrufe': 'Import candidates · live requests',
	'Bekannte URLs abrufen · Live-Abrufe': 'Fetch known URLs · live requests',
	'Gespeicherte Raw-Dateien erneut verarbeiten': 'Reprocess saved raw files',
	'Verifikation erfolgreich': 'Verification passed',
	'Verifikation fehlgeschlagen': 'Verification failed',
	Angebote: 'Offers',
	'ungültige Preise': 'invalid prices',
	Duplikate: 'duplicates',
	Konfiguration: 'Configuration',
	'Kein Deployment gefunden.': 'No deployment found.',
	'Letzte Flow-Runs': 'Recent flow runs',
	'Alle 15 Sekunden aktualisiert.': 'Updated every 15 seconds.',
	Modus: 'Mode',
	Status: 'Status',
	Start: 'Start',
	Dauer: 'Duration',
	'Run in Prefect öffnen': 'Open run in Prefect',
	'Keine Prefect-Runs verfügbar.': 'No Prefect runs available.',
	Kandidatenkatalog: 'Candidate catalog',
	'MediaMarkt-Kandidaten': 'MediaMarkt candidates',
	'Kandidatenstatus aus mediamarkt.json; importierte Produkte stehen separat in PostgreSQL.':
		'Candidate status from mediamarkt.json; imported products are stored separately in PostgreSQL.',
	'Katalog nicht lesbar:': 'Catalog unavailable:',
	'Titel fehlt': 'Title missing',
	Grund: 'Reason',
	'Letzter Versuch': 'Last attempt',
	'Keine Daten verfügbar': 'No data available',
	'Menü schliessen': 'Close menu',
	'Menü öffnen': 'Open menu',
	Produkt: 'Product',
	'Produkte / Suche': 'Products / Search',
	'Analyse / Datenbestand': 'Analytics / Dataset',
	'Projekt / Pipeline': 'Project / Pipeline',
	'Was die Daten zeigen.': 'What the data shows.',
	'Transparente Kennzahlen aus dem aktuellen Datenbestand, ohne künstliche Markttrends.':
		'Transparent figures from the current dataset, without invented market trends.',
	'Letzte Preismessungen': 'Latest price measurements',
	'Quality gates': 'Quality checks',
	'Prefect server': 'Prefect server',
	'Daily schedule · 03:00': 'Daily schedule · 03:00',
	Deployment: 'Deployment',
	Schedule: 'Schedule',
	Zeitzone: 'Time zone',
	'Flow run': 'Flow run',
	Runs: 'Runs',
	'SKU / Titel': 'SKU / Title',
	'Manuelle Prefect-Starts sind derzeit deaktiviert: Für die Workflow-Modi ist kein sicherer manueller Runner konfiguriert.':
		'Manual Prefect starts are disabled: no safe manual runner is configured for these workflow modes.',
	'CLI-Befehle bleiben in der Projektdokumentation verfügbar; der DAILY-Schedule wird hier nicht verändert.':
		'CLI commands remain available in the project documentation; the DAILY schedule is not changed here.',
	'Technische Merkmale werden angezeigt, sobald sie erfasst sind.':
		'Technical features will appear when available.',
	Angebot: 'Offer',
	Messungen: 'Measurements',
	beobachtet: 'observed',
	'GPU-Modell': 'GPU model',
	Architektur: 'Architecture',
	'Takt (MHz)': 'Clock (MHz)',
	'Boost (MHz)': 'Boost (MHz)',
	Kühlung: 'Cooling',
	'Kapazität (GB)': 'Capacity (GB)',
	Module: 'Modules',
	'Pro Modul (GB)': 'Per module (GB)',
	'Geschwindigkeit (MT/s)': 'Speed (MT/s)',
	'CAS-Latenz': 'CAS latency',
	'Spannung (V)': 'Voltage (V)',
	'PCIe-Generation': 'PCIe generation',
	Formfaktor: 'Form factor',
	'NAND-Typ': 'NAND type',
	'Lesen (MB/s)': 'Read (MB/s)',
	'Schreiben (MB/s)': 'Write (MB/s)',
	'DRAM-Cache': 'DRAM cache',
	'Letzte Läufe': 'Recent runs',
	'Das vorhandene Deployment meldet': 'The current deployment reports',
	Preis: 'Price',
	Rohkatalog: 'Raw catalog',
	Läufe: 'Runs'
};

export function tx(text: string, lang: Language) {
	if (lang !== 'en') return text;
	const result =
		en[text] ??
		Object.entries(en).find(
			([key]) => key.toLocaleLowerCase('de-CH') === text.toLocaleLowerCase('de-CH')
		)?.[1];
	return result ? (text === text.toUpperCase() ? result.toUpperCase() : result) : text;
}

export function stateLabel(state: string, lang: Language) {
	if (lang === 'en') return state;
	return (
		(
			{
				Completed: 'Abgeschlossen',
				Running: 'Läuft',
				Failed: 'Fehlgeschlagen',
				Scheduled: 'Geplant',
				Pending: 'Ausstehend',
				Cancelled: 'Abgebrochen',
				Crashed: 'Abgestürzt',
				Ready: 'Bereit'
			} as Record<string, string>
		)[state] ?? state
	);
}

export function catalogStatusLabel(status: string, lang: Language) {
	const labels: Record<string, [string, string]> = {
		candidate: ['Kandidat', 'Candidate'],
		accepted: ['Akzeptiert', 'Accepted'],
		excluded: ['Ausgeschlossen', 'Excluded'],
		rejected: ['Abgelehnt', 'Rejected'],
		review: ['Prüfen', 'Review'],
		unknown: ['Unbekannt', 'Unknown']
	};
	return labels[status.toLowerCase()]?.[lang === 'de' ? 0 : 1] ?? status;
}

export function catalogReasonLabel(reason: string, lang: Language) {
	const labels: Record<string, [string, string]> = {
		in_scope: ['Im Projektscope', 'In project scope'],
		excluded_hardware_or_condition: [
			'Hardware oder Zustand ausserhalb Scope',
			'Hardware or condition outside scope'
		],
		brand_filter: ['Marke ausserhalb Scope', 'Brand outside scope'],
		capacity_out_of_range: ['Kapazität ausserhalb Scope', 'Capacity outside scope'],
		ram_type: ['RAM-Typ ausserhalb Scope', 'RAM type outside scope'],
		non_nvme_ssd: ['Keine NVMe-SSD', 'Not an NVMe SSD'],
		category_not_confirmed: ['Kategorie unklar', 'Category not confirmed'],
		nvme_not_confirmed: ['NVMe nicht bestätigt', 'NVMe not confirmed']
	};
	return labels[reason]?.[lang === 'de' ? 0 : 1] ?? reason;
}

export function availabilityLabel(value: string, lang: Language) {
	const labels: Record<string, [string, string]> = {
		InStock: ['Auf Lager', 'In stock'],
		OutOfStock: ['Nicht verfügbar', 'Out of stock'],
		PreOrder: ['Vorbestellbar', 'Preorder']
	};
	return labels[value]?.[lang === 'de' ? 0 : 1] ?? value;
}
