<script lang="ts">
	import type { PageData } from './$types';
	import { tx } from '$lib/i18n';
	import { project } from '$lib/identity';
	import { usePreferences } from '$lib/preferences.svelte';
	import { ArrowUpRight, BarChart3, CircleDot, Database, ShieldCheck } from '@lucide/svelte';
	import { categoryLabel, dateTime, money } from '$lib/format';
	import CapacityChart from '$lib/CapacityChart.svelte';
	import HistoricalContextChart from '$lib/HistoricalContextChart.svelte';
	let { data }: { data: PageData } = $props();
	const prefs = usePreferences();
	const total = $derived(data.db?.stats.products || 0);
	const chartCategories = ['ram', 'ssd', 'gpu'] as const;
	const largestRate = $derived(
		Math.max(1, ...data.historical.frequencies.map((row) => row.changes_per_year || 0))
	);
</script>

<svelte:head><title>{project.name}</title></svelte:head>
<div class="page-heading">
	<div>
		<p class="eyebrow">{tx('ANALYSE / DATENBESTAND', prefs.lang)}</p>
		<h1>{tx('Was die Daten zeigen.', prefs.lang)}</h1>
		<p>
			{tx(
				'Transparente Kennzahlen aus dem aktuellen Datenbestand, ohne künstliche Markttrends.',
				prefs.lang
			)}
		</p>
	</div>
</div>
{#if data.error}<div class="alert">{data.error}</div>{/if}
<div class="analytics-grid">
	<section class="panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">{tx('DATENBESTAND', prefs.lang)}</p>
				<h2>{tx('Abdeckung', prefs.lang)}</h2>
			</div>
			<Database size={18} color="#a999f1" />
		</div>
		<div class="coverage">
			<div>
				<span>{tx('Produkte', prefs.lang)}</span><strong>{data.db?.stats.products ?? '—'}</strong>
			</div>
			<div>
				<span>{tx('Händlerangebote', prefs.lang)}</span><strong
					>{data.db?.stats.offers ?? '—'}</strong
				>
			</div>
			<div>
				<span>{tx('Preisbeobachtungen', prefs.lang)}</span><strong
					>{data.db?.stats.observations ?? '—'}</strong
				>
			</div>
			<div>
				<span>{tx('Neuester Messzeitpunkt', prefs.lang)}</span><strong class="date"
					>{dateTime(data.db?.stats.last_observation, prefs.lang)}</strong
				>
			</div>
		</div>
	</section>
	<section class="panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">PRODUCT MIX</p>
				<h2>{tx('Kategorieverteilung', prefs.lang)}</h2>
			</div>
			<BarChart3 size={18} color="#72d6d7" />
		</div>
		<div class="mix">
			{#each ['gpu', 'ram', 'ssd'] as category (category)}{@const count =
					data.db?.categories.find((x) => x.category === category)?.count || 0}
				<div class="mix-row">
					<span class="category {category}">{category.toUpperCase()}</span><span
						>{categoryLabel(category, prefs.lang)}</span
					><strong>{count}</strong><small>{total ? Math.round((count / total) * 100) : 0}%</small>
				</div>{/each}
		</div>
		<p class="mini-note">
			{tx('Anteil an importierten Produkten, nicht an Katalogkandidaten.', prefs.lang)}
		</p>
	</section>
	<section class="panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">{tx('QUALITY GATES', prefs.lang)}</p>
				<h2>{tx('Validierung', prefs.lang)}</h2>
			</div>
			<ShieldCheck size={18} color="#79d8aa" />
		</div>
		<div class="quality-row">
			<span>{tx('Ungültige Preise', prefs.lang)}</span><strong
				>{data.db?.quality.invalid_prices ?? '—'}</strong
			>
		</div>
		<div class="quality-row">
			<span>{tx('Doppelte Beobachtungszeitpunkte', prefs.lang)}</span><strong
				>{data.db?.quality.duplicates ?? '—'}</strong
			>
		</div>
		<p class="mini-note">
			{tx('Basierend auf CHF- und Eindeutigkeitsprüfungen in PostgreSQL.', prefs.lang)}
		</p>
	</section>
</div>
<div class="capacity-heading">
	<div>
		<p class="section-kicker">{tx('PREIS / KAPAZITÄT', prefs.lang)}</p>
		<h2>{tx('Was kostet ein GB?', prefs.lang)}</h2>
	</div>
	<p>
		{tx(
			'X: Kapazität in GB · Y: durchschnittliche CHF pro GB. Pro Produkt zählt das günstigste zuletzt beobachtete Händlerangebot.',
			prefs.lang
		)}
	</p>
</div>
{#if data.capacityError}
	<div class="alert">{tx('Kapazitätsanalyse momentan nicht verfügbar.', prefs.lang)}</div>
{:else}
	<div class="capacity-grid">
		{#each chartCategories as category (category)}
			<CapacityChart {category} points={data.capacity.filter((row) => row.category === category)} />
		{/each}
	</div>
{/if}
<p class="capacity-footnote">
	{tx(
		'Nur Produkte mit bestätigter Kapazität und echtem CHF-Preis. Jede Gruppe zeigt ihren Stichprobenumfang; keine repräsentativen Marktpreise. Bei GPUs ist CHF pro GB VRAM kein Mass für die Rechenleistung.',
		prefs.lang
	)}
</p>
<section class="history-section">
	<div class="capacity-heading">
		<div>
			<p class="section-kicker">DIGITEC / ZEITKONTEXT</p>
			<h2>{tx('Drei Produkte im Zeitverlauf', prefs.lang)}</h2>
		</div>
		<p>
			{tx(
				'Je ein vorhandenes Beispiel für RAM, SSD und GPU. Linien zeigen manuell gespeicherte Digitec-Preiswechsel, nicht tägliche Messungen.',
				prefs.lang
			)}
		</p>
	</div>
	<div class="era-legend">
		<span><i class="shortage"></i>{tx('Chipmangel 2020–2022', prefs.lang)}</span><span
			><i class="ai"></i>{tx('KI-Nachfrage ab März 2023', prefs.lang)}</span
		>
	</div>
	{#if data.historicalError}<div class="alert">
			{tx('Historische Analyse momentan nicht verfügbar.', prefs.lang)}
		</div>
	{:else if data.historical.examples.length}
		{#each data.historical.examples as example (example.product_id)}<HistoricalContextChart
				{example}
			/>{/each}
	{:else}<div class="panel empty">
			{tx('Noch keine historischen Preiswechsel importiert.', prefs.lang)}
		</div>{/if}
	<p class="context-note">
		{tx(
			'Die Flächen sind zeitlicher Marktkontext, kein Beleg für die Ursache eines konkreten Ladenpreises. GPU-Historien beginnen hier erst 2025; für den Chipmangel gibt es in dieser Kategorie keine Messpunkte.',
			prefs.lang
		)}
		<a
			href="https://www.semiconductors.org/wp-content/uploads/2022/11/SIA_State-of-Industry-Report_2022.pdf"
			target="_blank"
			rel="noreferrer">SIA 2022</a
		>
		·
		<a
			href="https://investor.nvidia.com/news/press-release-details/2023/NVIDIA-Hopper-GPUs-Expand-Reach-as-Demand-for-AI-Grows/default.aspx"
			target="_blank"
			rel="noreferrer">NVIDIA 2023</a
		>
	</p>
</section>
{#if data.historical.frequencies.length}<section class="panel frequency-panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">DIGITEC / VERGLEICH</p>
				<h2>{tx('Wie oft wechseln die Preise?', prefs.lang)}</h2>
				<p>
					{tx(
						'Tatsächliche Preisänderungen pro Jahr, gemessen vom ersten bis zum letzten gespeicherten Digitec-Preis.',
						prefs.lang
					)}
				</p>
			</div>
			<BarChart3 size={18} color="#72d6d7" />
		</div>
		<div class="frequency-list">
			{#each data.historical.frequencies as row (row.product_id)}<a
					href="/explore/{row.product_id}"
					class="frequency-row"
				>
					<div class="frequency-label">
						<span class="category {row.category}">{row.category.toUpperCase()}</span><strong
							title={row.product_name}>{row.product_name}</strong
						><span
							>{row.changes_per_year === null
								? '—'
								: `${Number(row.changes_per_year).toLocaleString(prefs.lang === 'de' ? 'de-CH' : 'en-CH')} / ${tx('Jahr', prefs.lang)}`}</span
						>
					</div>
					<div class="frequency-track">
						<div
							class="frequency-fill {row.category}"
							style:width={`${row.changes_per_year === null ? 0 : (row.changes_per_year / largestRate) * 100}%`}
						></div>
					</div>
					<small
						>{money(row.min_price, prefs.lang)} – {money(row.max_price, prefs.lang)} · {row.price_changes}
						{tx('tatsächliche Preisänderungen', prefs.lang)}{#if row.changes_per_year === null}
							· {tx('unter 90 Tagen Verlauf', prefs.lang)}{/if}</small
					>
				</a>{/each}
		</div>
		<p class="mini-note">
			{tx(
				'Gleiche Preise und Punkte ohne verfügbaren Preis zählen nicht als Änderung. Unter 90 Tagen Verlauf wird keine Jahresrate berechnet.',
				prefs.lang
			)}
		</p>
	</section>{/if}
<section class="panel">
	<div class="panel-head">
		<div>
			<p class="section-kicker">{tx('LETZTE PREISMESSUNGEN', prefs.lang)}</p>
			<h2>{tx('Letzte Messungen', prefs.lang)}</h2>
			<p>{tx('Aktuelle Stichprobe, keine vollständige Marktübersicht.', prefs.lang)}</p>
		</div>
		<a class="text-link" href="/explore"
			>{tx('Explorer öffnen', prefs.lang)} <ArrowUpRight size={14} /></a
		>
	</div>
	<div class="table-wrap">
		<table class="data-table">
			<thead
				><tr
					><th>{tx('PRODUKT', prefs.lang)}</th><th>{tx('KATEGORIE', prefs.lang)}</th><th
						>{tx('HÄNDLER', prefs.lang)}</th
					><th>{tx('ZEITPUNKT', prefs.lang)}</th><th>PREIS</th></tr
				></thead
			><tbody
				>{#each data.db?.recent || [] as row (row.product_id + row.collected_at + row.retailer)}<tr
						><td
							><a href="/explore/{row.product_id}"
								><strong>{row.product_name}</strong><small>{row.brand}</small></a
							></td
						><td><span class="category {row.category}">{row.category.toUpperCase()}</span></td><td
							>{row.retailer}</td
						><td class="mono muted">{dateTime(row.collected_at, prefs.lang)}</td><td class="price"
							>{money(row.price, prefs.lang)}</td
						></tr
					>{:else}<tr
						><td colspan="5" class="empty">{tx('Keine Messungen vorhanden.', prefs.lang)}</td></tr
					>{/each}</tbody
			>
		</table>
	</div>
</section>
<div class="analytics-note">
	<CircleDot size={14} />
	{tx(
		'Aussagekräftige Preisverläufe entstehen erst durch weitere echte Tagesbeobachtungen.',
		prefs.lang
	)}
</div>

<style>
	.history-section {
		margin: 25px 0 28px;
	}
	.era-legend {
		display: flex;
		gap: 18px;
		flex-wrap: wrap;
		margin: 0 0 13px;
		color: var(--muted-high);
		font-size: 10px;
	}
	.era-legend span {
		display: flex;
		align-items: center;
		gap: 7px;
	}
	.era-legend i {
		display: inline-block;
		width: 13px;
		height: 13px;
		border-radius: 3px;
	}
	.era-legend .shortage {
		background: #d8894755;
	}
	.era-legend .ai {
		background: #7d76cf55;
	}
	.context-note {
		font-size: 10px;
		color: var(--muted);
		line-height: 1.6;
		margin: 11px 0 0;
	}
	.context-note a {
		color: var(--violet);
		text-decoration: underline;
	}
	.frequency-panel {
		margin: 0 0 24px;
	}
	.frequency-list {
		padding: 0 23px 14px;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px 24px;
	}
	.frequency-row {
		display: block;
		border-top: 1px solid var(--surface-strong);
		padding-top: 10px;
		min-width: 0;
	}
	.frequency-row:hover strong {
		color: var(--violet);
	}
	.frequency-label {
		display: flex;
		align-items: center;
		gap: 9px;
		font-size: 10px;
	}
	.frequency-label strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
		flex: 1;
	}
	.frequency-label > span:last-child {
		font:
			11px 'DM Mono',
			monospace;
		color: var(--soft);
	}
	.frequency-track {
		height: 7px;
		border-radius: 9px;
		background: var(--surface-strong);
		margin: 10px 0 6px;
		overflow: hidden;
	}
	.frequency-fill {
		height: 100%;
		border-radius: 9px;
		background: var(--violet);
	}
	.frequency-fill.ssd {
		background: var(--teal, #6bd6d7);
	}
	.frequency-fill.gpu {
		background: #e6bb7b;
	}
	.frequency-row small {
		color: var(--muted);
		font-size: 9px;
	}
	.capacity-heading {
		display: flex;
		justify-content: space-between;
		align-items: end;
		gap: 25px;
		margin: 28px 0 14px;
	}
	.capacity-heading h2 {
		margin: 7px 0 0;
		font:
			600 23px 'Space Grotesk',
			sans-serif;
		letter-spacing: -0.03em;
	}
	.capacity-heading .section-kicker {
		margin: 0;
	}
	.capacity-heading > p {
		max-width: 460px;
		margin: 0;
		color: var(--muted);
		font-size: 11px;
		line-height: 1.6;
	}
	.capacity-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 15px;
	}
	.capacity-footnote {
		margin: 10px 0 26px;
		color: var(--muted);
		font-size: 10px;
		line-height: 1.6;
	}
	.analytics-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 15px;
		margin-bottom: 15px;
	}
	.analytics-grid > .panel {
		min-height: 275px;
	}
	.coverage {
		padding: 0 23px 20px;
	}
	.coverage > div,
	.quality-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		padding: 12px 0;
		border-top: 1px solid var(--surface-strong);
		font-size: 11px;
	}
	.coverage span,
	.quality-row span {
		color: var(--muted-high);
	}
	.coverage strong,
	.quality-row strong {
		font:
			500 15px 'DM Mono',
			monospace;
	}
	.coverage strong.date {
		font-size: 10px;
		text-align: right;
	}
	.mix {
		padding: 0 23px;
	}
	.mix-row {
		display: flex;
		gap: 9px;
		align-items: center;
		padding: 11px 0;
		border-top: 1px solid var(--surface-strong);
		font-size: 11px;
	}
	.mix-row strong {
		margin-left: auto;
		font-family: 'DM Mono', monospace;
	}
	.mix-row small {
		width: 31px;
		text-align: right;
		color: var(--muted);
		font-family: 'DM Mono', monospace;
	}
	.quality-row {
		margin: 0 23px;
	}
	.quality-row strong {
		color: var(--green);
	}
	.mini-note {
		margin: 11px 23px;
		color: var(--muted);
		font-size: 10px;
		line-height: 1.5;
	}
	.analytics-note {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--muted);
		font-size: 11px;
		margin-top: 17px;
	}
	@media (max-width: 1100px) {
		.capacity-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.analytics-grid {
			grid-template-columns: 1fr 1fr;
		}
		.analytics-grid > .panel:last-child {
			grid-column: span 2;
		}
	}
	@media (max-width: 650px) {
		.frequency-list {
			grid-template-columns: 1fr;
		}
		.capacity-heading {
			display: block;
		}
		.capacity-heading > p {
			margin-top: 9px;
		}
		.capacity-grid {
			grid-template-columns: 1fr;
		}
		.analytics-grid {
			grid-template-columns: 1fr;
		}
		.analytics-grid > .panel:last-child {
			grid-column: auto;
		}
	}
</style>
