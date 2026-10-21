<script lang="ts">
	import type { PageData } from './$types';
	import { availabilityLabel, tx } from '$lib/i18n';
	import { project } from '$lib/identity';
	import { usePreferences } from '$lib/preferences.svelte';
	import { ArrowLeft, CircleDot, ExternalLink, Hash, Layers3 } from '@lucide/svelte';
	import PriceChart from '$lib/PriceChart.svelte';
	import { dateTime, money } from '$lib/format';
	let { data }: { data: PageData } = $props();
	const prefs = usePreferences();
	let detail = $derived(data.detail);
	const labels: Record<string, string> = {
		gpu_model: 'GPU-Modell',
		gpu_architecture: 'Architektur',
		vram_gb: 'VRAM (GB)',
		vram_type: 'VRAM-Typ',
		clock_mhz: 'Takt (MHz)',
		boost_clock_mhz: 'Boost (MHz)',
		pcie_interface: 'PCIe',
		tdp_watts: 'TDP (W)',
		cooling_variant: 'Kühlung',
		ram_type: 'RAM-Typ',
		total_capacity_gb: 'Kapazität (GB)',
		module_count: 'Module',
		capacity_per_module_gb: 'Pro Modul (GB)',
		speed_mts: 'Geschwindigkeit (MT/s)',
		cas_latency: 'CAS-Latenz',
		voltage: 'Spannung (V)',
		ecc: 'ECC',
		rgb: 'RGB',
		capacity_gb: 'Kapazität (GB)',
		interface: 'Interface',
		pcie_generation: 'PCIe-Generation',
		form_factor: 'Formfaktor',
		nand_type: 'NAND-Typ',
		controller: 'Controller',
		read_speed_mbps: 'Lesen (MB/s)',
		write_speed_mbps: 'Schreiben (MB/s)',
		tbw: 'TBW',
		dram_cache: 'DRAM-Cache'
	};
	let specs = $derived(
		Object.entries(
			(detail.details[detail.product.category] || {}) as Record<string, unknown>
		).filter(([, v]) => v !== null && v !== undefined && v !== '')
	);
</script>

<svelte:head><title>{project.name}</title></svelte:head>
<a class="back-link" href="/explore"
	><ArrowLeft size={14} /> {tx('Zurück zum Explorer', prefs.lang)}</a
>
<div class="detail-heading">
	<div>
		<p class="eyebrow">{tx('Produkt', prefs.lang).toUpperCase()} / #{detail.product.product_id}</p>
		<div class="title-line">
			<span class="category {detail.product.category}">{detail.product.category.toUpperCase()}</span
			><span class="brand-name">{detail.product.brand}</span>{#if detail.chartHistory.length}<span
					class="history-tag">{tx('Digitec-Verlauf', prefs.lang)}</span
				>{/if}
		</div>
		<h1>{detail.product.product_name}</h1>
		<p>
			{detail.product.spec ||
				tx('Technische Merkmale werden angezeigt, sobald sie erfasst sind.', prefs.lang)}
		</p>
	</div>
</div>
<div class="detail-metrics">
	<div class="panel">
		<span>{tx('AKTUELLER PREIS', prefs.lang)}</span><strong
			>{money(detail.product.price, prefs.lang)}</strong
		><small>{detail.product.retailer || tx('Kein Angebot', prefs.lang)}</small>
	</div>
	<div class="panel">
		<span>{tx('TIEFSTER PREIS', prefs.lang)}</span><strong>{money(detail.min, prefs.lang)}</strong
		><small>{tx('Beobachtetes Minimum', prefs.lang)}</small>
	</div>
	<div class="panel">
		<span>{tx('HÖCHSTER PREIS', prefs.lang)}</span><strong>{money(detail.max, prefs.lang)}</strong
		><small>{tx('Beobachtetes Maximum', prefs.lang)}</small>
	</div>
	<div class="panel">
		<span>{tx('BEOBACHTUNGEN', prefs.lang)}</span><strong>{detail.history.length}</strong><small
			>{tx('Alle Händlerangebote', prefs.lang)}</small
		>
	</div>
</div>
<div class="detail-grid">
	<section class="panel chart-panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">
					{tx(
						detail.chartHistory.length ? 'MESSUNGEN & HÄNDLERHISTORIE' : 'ECHTE PREISMESSUNGEN',
						prefs.lang
					)}
				</p>
				<h2>{tx('Preisverlauf', prefs.lang)}</h2>
			</div>
			<span class="chart-count"
				><CircleDot size={13} />
				{detail.history.length}
				{tx(
					detail.history.length === 1 ? 'Messpunkt' : 'Messpunkte',
					prefs.lang
				).toUpperCase()}{#if detail.chartHistory.length}
					· {detail.chartHistory.length} {tx('Preiswechsel', prefs.lang).toUpperCase()}{/if}</span
			>
		</div>
		<div class="chart-inner">
			<PriceChart history={detail.history} chartHistory={detail.chartHistory} />
		</div>
	</section>
	<section class="panel spec-panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">{tx('TECHNISCHE DATEN', prefs.lang)}</p>
				<h2>{tx('Technische Daten', prefs.lang)}</h2>
			</div>
			<Layers3 size={17} color="#a594dd" />
		</div>
		<div class="spec-list">
			<div><span>{tx('Hersteller', prefs.lang)}</span><strong>{detail.product.brand}</strong></div>
			{#if detail.product.model}<div>
					<span>{tx('Modell', prefs.lang)}</span><strong>{detail.product.model}</strong>
				</div>{/if}{#if detail.product.mpn}<div>
					<span>MPN</span><strong class="mono">{detail.product.mpn}</strong>
				</div>{/if}{#if detail.product.ean}<div>
					<span>EAN</span><strong class="mono">{detail.product.ean}</strong>
				</div>{/if}{#each specs as [key, value] (key)}<div>
					<span>{tx(labels[key] || key.replaceAll('_', ' '), prefs.lang)}</span><strong
						>{typeof value === 'boolean'
							? tx(value ? 'Ja' : 'Nein', prefs.lang)
							: String(value)}</strong
					>
				</div>{/each}
		</div>
	</section>
</div>
<section class="panel offers-panel">
	<div class="panel-head">
		<div>
			<p class="section-kicker">{tx('HÄNDLERANGEBOTE', prefs.lang)}</p>
			<h2>{tx('Händlerangebote', prefs.lang)}</h2>
			<p>{tx('Jedes Angebot hat eine eigene Preisreihe.', prefs.lang)}</p>
		</div>
		<span class="section-kicker"
			>{detail.offers.length}
			{tx(detail.offers.length === 1 ? 'Angebot' : 'Angebote', prefs.lang).toUpperCase()}</span
		>
	</div>
	<div class="offer-list">
		{#each detail.offers as offer (offer.retailer_product_id)}<div class="offer-row">
				<div class="offer-icon"><Hash size={18} /></div>
				<div class="offer-main">
					<strong>{offer.retailer}</strong><small
						>SKU {offer.retailer_sku} · {offer.price === null &&
						offer.retailer === 'Digitec' &&
						detail.chartHistory.length
							? tx('Nur historischer Preisverlauf (manuell zugeordnet)', prefs.lang)
							: offer.availability
								? availabilityLabel(offer.availability, prefs.lang)
								: tx('Verfügbarkeit unbekannt', prefs.lang)}</small
					>
				</div>
				<div class="offer-price">
					<strong>{money(offer.price, prefs.lang)}</strong><small
						>{dateTime(offer.collected_at, prefs.lang)}</small
					>
				</div>
				{#if offer.product_url}<a
						class="offer-link"
						href={offer.product_url}
						target="_blank"
						rel="noreferrer"
						aria-label={tx('Original-Produktseite öffnen', prefs.lang)}
						><ExternalLink size={16} /></a
					>{/if}
			</div>{:else}<div class="empty">
				{tx('Noch kein Händlerangebot vorhanden.', prefs.lang)}
			</div>{/each}
	</div>
</section>
<section class="panel observations-panel">
	<div class="panel-head">
		<div>
			<p class="section-kicker">{tx('ALLE BEOBACHTUNGEN', prefs.lang)}</p>
			<h2>{tx('Beobachtungen', prefs.lang)}</h2>
		</div>
		<span class="hint">{tx('Originale Zeitpunkte', prefs.lang)} · Europe/Zurich</span>
	</div>
	<div class="table-wrap">
		<table class="data-table">
			<thead
				><tr
					><th>{tx('ZEITPUNKT', prefs.lang)}</th><th>{tx('HÄNDLER', prefs.lang)}</th><th
						>{tx('VERFÜGBARKEIT', prefs.lang)}</th
					><th>CHF</th></tr
				></thead
			><tbody
				>{#each [...detail.history].reverse() as row (row.retailer_product_id + row.collected_at)}<tr
						><td class="mono">{dateTime(row.collected_at, prefs.lang)}</td><td>{row.retailer}</td
						><td class="muted"
							>{row.availability ? availabilityLabel(row.availability, prefs.lang) : '—'}</td
						><td class="price">{money(row.price, prefs.lang)}</td></tr
					>{:else}<tr
						><td colspan="4" class="empty">{tx('Noch keine Preisbeobachtungen.', prefs.lang)}</td
						></tr
					>{/each}</tbody
			>
		</table>
	</div>
</section>

<style>
	.back-link {
		display: inline-flex;
		gap: 8px;
		align-items: center;
		color: var(--muted-high);
		font-size: 11px;
		margin-bottom: 26px;
	}
	.back-link:hover {
		color: var(--violet);
	}
	.detail-heading {
		margin-bottom: 30px;
	}
	.title-line {
		display: flex;
		align-items: center;
		gap: 10px;
		margin: 13px 0;
	}
	.brand-name {
		font:
			11px 'DM Mono',
			monospace;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--violet);
	}
	.history-tag {
		padding: 5px 7px;
		border: 1px solid var(--surface-strong);
		border-radius: 5px;
		color: var(--teal, #6bd6d7);
		font:
			9px 'DM Mono',
			monospace;
	}
	.detail-heading h1 {
		font:
			600 clamp(27px, 3.2vw, 44px)/1.14 'Space Grotesk',
			sans-serif;
		letter-spacing: -0.045em;
		margin: 0 0 10px;
		max-width: 950px;
	}
	.detail-heading p:last-child {
		color: var(--muted);
		font-size: 12px;
	}
	.detail-metrics {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 13px;
		margin: 0 0 15px;
	}
	.detail-metrics .panel {
		padding: 19px;
	}
	.detail-metrics span {
		display: block;
		font:
			9px 'DM Mono',
			monospace;
		color: var(--muted-high);
		letter-spacing: 0.06em;
	}
	.detail-metrics strong {
		display: block;
		font:
			600 25px 'Space Grotesk',
			sans-serif;
		margin: 14px 0 5px;
		letter-spacing: -0.03em;
	}
	.detail-metrics small {
		color: var(--muted);
		font-size: 10px;
	}
	.detail-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.65fr) minmax(260px, 1fr);
		gap: 15px;
		margin-bottom: 15px;
	}
	.chart-panel,
	.spec-panel {
		min-height: 399px;
	}
	.chart-inner {
		padding: 4px 23px 20px;
	}
	.chart-count {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--muted);
		font:
			9px 'DM Mono',
			monospace;
	}
	.spec-list {
		padding: 0 23px 19px;
	}
	.spec-list > div {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		border-top: 1px solid var(--surface-strong);
		padding: 10px 0;
		font-size: 11px;
	}
	.spec-list span {
		color: var(--muted);
	}
	.spec-list strong {
		text-align: right;
		font-weight: 600;
		word-break: break-word;
	}
	.offers-panel {
		margin-bottom: 15px;
	}
	.offer-list {
		padding: 0 23px 9px;
	}
	.offer-row {
		display: flex;
		align-items: center;
		gap: 13px;
		border-top: 1px solid var(--surface-strong);
		padding: 15px 0;
	}
	.offer-icon {
		background: var(--surface-strong);
		border-radius: 8px;
		color: var(--violet);
		padding: 9px;
		display: grid;
		place-items: center;
	}
	.offer-main {
		flex: 1;
		min-width: 0;
	}
	.offer-main strong,
	.offer-price strong {
		display: block;
		font-size: 12px;
	}
	.offer-main small,
	.offer-price small {
		display: block;
		color: var(--muted);
		font-size: 10px;
		margin-top: 4px;
	}
	.offer-price {
		text-align: right;
	}
	.offer-price strong {
		font-family: 'DM Mono', monospace;
	}
	.offer-link {
		color: var(--violet);
		margin-left: 7px;
	}
	.observations-panel {
		margin-bottom: 12px;
	}
	@media (max-width: 1050px) {
		.detail-grid {
			grid-template-columns: 1fr;
		}
		.detail-metrics {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (max-width: 590px) {
		.detail-metrics {
			gap: 8px;
		}
		.detail-metrics .panel {
			padding: 14px;
		}
		.detail-metrics strong {
			font-size: 19px;
		}
		.offer-row {
			flex-wrap: wrap;
		}
		.offer-price {
			margin-left: auto;
		}
	}
</style>
