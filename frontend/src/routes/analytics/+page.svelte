<script lang="ts">
	import type { PageData } from './$types';
	import { tx } from '$lib/i18n';
	import { project } from '$lib/identity';
	import { usePreferences } from '$lib/preferences.svelte';
	import { ArrowUpRight, BarChart3, CircleDot, Database, ShieldCheck } from '@lucide/svelte';
	import { categoryLabel, dateTime, money } from '$lib/format';
	let { data }: { data: PageData } = $props();
	const prefs = usePreferences();
	const total = $derived(data.db?.stats.products || 0);
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
		.analytics-grid {
			grid-template-columns: 1fr 1fr;
		}
		.analytics-grid > .panel:last-child {
			grid-column: span 2;
		}
	}
	@media (max-width: 650px) {
		.analytics-grid {
			grid-template-columns: 1fr;
		}
		.analytics-grid > .panel:last-child {
			grid-column: auto;
		}
	}
</style>
