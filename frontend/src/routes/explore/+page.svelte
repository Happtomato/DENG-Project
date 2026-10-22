<script lang="ts">
	import type { PageData } from './$types';
	import { tx } from '$lib/i18n';
	import { project } from '$lib/identity';
	import { usePreferences } from '$lib/preferences.svelte';
	import { SvelteURLSearchParams } from 'svelte/reactivity';
	import { ArrowLeft, ArrowRight, ArrowUpRight, Search, X } from '@lucide/svelte';
	import { dateTime, money } from '$lib/format';
	let { data }: { data: PageData } = $props();
	const prefs = usePreferences();
	let search = $state('');
	let category = $state('');
	let brand = $state('');
	let retailer = $state('');
	let digitecHistory = $state(false);
	let min = $state('');
	let max = $state('');
	let sort = $state('recent');
	let loading = $state(false);
	function applyFilter(event: Event) {
		(event.currentTarget as HTMLInputElement | HTMLSelectElement).form?.requestSubmit();
	}
	$effect(() => {
		search = data.filters.search;
		category = data.filters.category;
		brand = data.filters.brand;
		retailer = data.filters.retailer;
		digitecHistory = data.filters.digitec_history;
		min = data.filters.min?.toString() ?? '';
		max = data.filters.max?.toString() ?? '';
		sort = data.filters.sort;
		loading = false;
	});
	function pageHref(n: number) {
		const p = new SvelteURLSearchParams();
		if (data.filters.search) p.set('search', data.filters.search);
		if (data.filters.category) p.set('category', data.filters.category);
		if (data.filters.brand) p.set('brand', data.filters.brand);
		if (data.filters.retailer) p.set('retailer', data.filters.retailer);
		if (data.filters.digitec_history) p.set('history', 'digitec');
		if (data.filters.min != null) p.set('min', String(data.filters.min));
		if (data.filters.max != null) p.set('max', String(data.filters.max));
		if (data.filters.sort !== 'recent') p.set('sort', data.filters.sort);
		p.set('page', String(n));
		return '/explore?' + p.toString();
	}
</script>

<svelte:head><title>{project.name}</title></svelte:head>
<div class="page-heading">
	<div>
		<p class="eyebrow">{tx('PRODUKTE / SUCHE', prefs.lang)}</p>
		<h1>{tx('Produkte entdecken.', prefs.lang)}</h1>
		<p>
			{tx(
				'Durchsuche importierte Hardware, Angebote und tatsächliche Preisbeobachtungen.',
				prefs.lang
			)}
		</p>
	</div>
	<span class="result-pill">{data.listing.total} {tx('Produkte', prefs.lang).toUpperCase()}</span>
</div>
{#if data.error}<div class="alert">
		{tx('Die Produktdatenbank ist momentan nicht erreichbar.', prefs.lang)}
		{data.error}
	</div>{/if}
<form
	id="explore-filters"
	action="/explore"
	method="GET"
	class="filters panel"
	onsubmit={() => (loading = true)}
>
	<div class="search-field">
		<Search size={17} /><input
			name="search"
			aria-label={tx('Produkt suchen', prefs.lang)}
			bind:value={search}
			placeholder={tx('Produkt, Marke oder Modell suchen …', prefs.lang)}
		/><span class="search-hint">{tx('SUCHE', prefs.lang)}</span>
	</div>
	<div class="filter-row">
		<div class="field">
			<label for="category">{tx('Kategorie', prefs.lang)}</label><select
				id="category"
				name="category"
				bind:value={category}
				onchange={applyFilter}
				><option value="">{tx('Alle Kategorien', prefs.lang)}</option><option value="gpu"
					>GPU</option
				><option value="ram">RAM</option><option value="ssd">SSD</option></select
			>
		</div>
		<div class="field">
			<label for="brand">{tx('Hersteller', prefs.lang)}</label><select
				id="brand"
				name="brand"
				bind:value={brand}
				onchange={applyFilter}
				><option value="">{tx('Alle Hersteller', prefs.lang)}</option
				>{#each data.options.brands as b (b)}<option value={b}>{b}</option>{/each}</select
			>
		</div>
		<div class="field">
			<label for="retailer">{tx('Händler', prefs.lang)}</label><select
				id="retailer"
				name="retailer"
				bind:value={retailer}
				onchange={applyFilter}
				><option value="">{tx('Alle Händler', prefs.lang)}</option
				>{#each data.options.retailers as r (r)}<option value={r}>{r}</option>{/each}</select
			>
		</div>
		<div class="field">
			<label for="min">Min. CHF</label><input
				id="min"
				name="min"
				type="number"
				min="0"
				step="0.01"
				bind:value={min}
				onchange={applyFilter}
				placeholder="0"
			/>
		</div>
		<div class="field">
			<label for="max">Max. CHF</label><input
				id="max"
				name="max"
				type="number"
				min="0"
				step="0.01"
				bind:value={max}
				onchange={applyFilter}
				placeholder="∞"
			/>
		</div>
	</div>
	<div class="filter-actions">
		<label class="history-filter"
			><input
				type="checkbox"
				name="history"
				value="digitec"
				bind:checked={digitecHistory}
				onchange={applyFilter}
			/>{tx('Mit Digitec-Preisverlauf', prefs.lang)}</label
		>
		<div>
			<a class="clear" href="/explore"><X size={13} /> {tx('Zurücksetzen', prefs.lang)}</a><button
				class="btn primary"
				type="submit">{tx('Anwenden', prefs.lang)} <ArrowRight size={13} /></button
			>
		</div>
	</div>
</form>
<div class="results-title">
	<div>
		<span class="section-kicker">{tx('IMPORTIERTE PRODUKTE', prefs.lang)}</span>
		<h2>{tx('Ergebnisse', prefs.lang)} <span>({data.listing.total})</span></h2>
	</div>
	<div class="results-controls">
		<label for="sort">{tx('Sortierung', prefs.lang)}</label>
		<select id="sort" name="sort" form="explore-filters" bind:value={sort} onchange={applyFilter}
			><option value="recent">{tx('Zuletzt beobachtet', prefs.lang)}</option><option
				value="price_asc">{tx('Preis aufsteigend', prefs.lang)}</option
			><option value="price_desc">{tx('Preis absteigend', prefs.lang)}</option><option
				value="points_desc">{tx('Meiste Preispunkte', prefs.lang)}</option
			><option value="points_asc">{tx('Wenigste Preispunkte', prefs.lang)}</option><option
				value="name">{tx('Name A–Z', prefs.lang)}</option
			></select
		>
		<span
			>{tx('Seite', prefs.lang)}
			{data.listing.page}
			{tx('von', prefs.lang)}
			{Math.max(1, Math.ceil(data.listing.total / data.listing.pageSize))}</span
		>
	</div>
</div>
{#if loading}<div class="loading-grid" aria-label={tx('Lade Produkte', prefs.lang)}>
		{#each [1, 2, 3, 4, 5, 6] as index (index)}<div class="panel">
				<div class="skeleton" style="height:18px;width:65%"></div>
				<div class="skeleton" style="height:11px;width:40%;margin-top:16px"></div>
				<div class="skeleton" style="height:30px;width:45%;margin-top:28px"></div>
			</div>{/each}
	</div>{:else if data.listing.rows.length}<div class="product-grid">
		{#each data.listing.rows as product (product.product_id)}<a
				class="product-card panel"
				href="/explore/{product.product_id}"
				><div class="card-top">
					<span class="category {product.category}">{product.category.toUpperCase()}</span
					>{#if product.digitec_history_count}<span class="history-tag"
							>{tx('Digitec-Verlauf', prefs.lang)}</span
						>{/if}<ArrowUpRight size={16} />
				</div>
				<div class="card-brand">{product.brand}</div>
				<h3>{product.product_name}</h3>
				<div class="card-spec">
					{product.spec || product.model || tx('Technische Details nicht vorhanden', prefs.lang)}
				</div>
				<div class="card-line"></div>
				<div class="card-bottom">
					<div>
						<span>{tx('LETZTER PREIS', prefs.lang)}</span><strong
							>{money(product.price, prefs.lang)}</strong
						>
					</div>
					<div>
						<span>{tx('HÄNDLER', prefs.lang)}</span><strong>{product.retailer || '—'}</strong>
					</div>
				</div>
				<div class="card-date">
					{product.price_point_count}
					{tx('Preispunkte', prefs.lang)} ·
					{product.collected_at
						? `${tx('Zuletzt beobachtet', prefs.lang)} ${dateTime(product.collected_at, prefs.lang)}`
						: tx('Noch keine Preisbeobachtung', prefs.lang)}
				</div></a
			>{/each}
	</div>{:else}<div class="panel empty">
		{tx(
			'Keine Produkte mit diesen Filtern gefunden. Prüfe Suchbegriff oder Preisbereich.',
			prefs.lang
		)}
	</div>{/if}
{#if data.listing.total > data.listing.pageSize}<div class="pagination">
		{#if data.listing.page > 1}<a class="btn" href={pageHref(data.listing.page - 1)}
				><ArrowLeft size={14} /> {tx('Vorherige', prefs.lang)}</a
			>{/if}<span
			>{data.listing.page} / {Math.ceil(data.listing.total / data.listing.pageSize)}</span
		>{#if data.listing.page * data.listing.pageSize < data.listing.total}<a
				class="btn"
				href={pageHref(data.listing.page + 1)}
				>{tx('Nächste', prefs.lang)} <ArrowRight size={14} /></a
			>{/if}
	</div>{/if}

<style>
	.result-pill {
		border: 1px solid var(--line-strong);
		background: var(--surface);
		color: var(--violet);
		border-radius: 7px;
		padding: 9px 12px;
		font:
			10px 'DM Mono',
			monospace;
		letter-spacing: 0.08em;
	}
	.filters {
		padding: 16px;
		margin-bottom: 30px;
	}
	.search-field {
		display: flex;
		align-items: center;
		gap: 10px;
		background: var(--surface);
		border: 1px solid var(--line-strong);
		border-radius: 8px;
		padding: 0 13px;
		height: 44px;
		color: var(--muted-high);
	}
	.search-field:focus-within {
		border-color: var(--violet);
	}
	.search-field input {
		width: 100%;
		background: none;
		border: 0;
		outline: none;
		color: var(--text);
		font-size: 12px;
	}
	.search-field input::placeholder {
		color: var(--muted);
	}
	.search-hint {
		font:
			9px 'DM Mono',
			monospace;
		color: var(--muted-low);
	}
	.filter-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr) repeat(2, 0.7fr);
		gap: 10px;
		margin: 15px 0;
	}
	.filter-row .field {
		min-width: 0;
	}
	.filter-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 13px;
		border-top: 1px solid var(--line);
	}
	.history-filter {
		display: flex;
		gap: 7px;
		align-items: center;
		color: var(--muted-high);
		font-size: 10px;
		cursor: pointer;
	}
	.history-filter input {
		accent-color: var(--violet);
	}
	.filter-actions > div {
		display: flex;
		align-items: center;
		gap: 16px;
	}
	.clear {
		display: flex;
		align-items: center;
		gap: 4px;
		color: var(--muted);
		font-size: 10px;
	}
	.clear:hover {
		color: var(--soft);
	}
	.results-title {
		display: flex;
		justify-content: space-between;
		align-items: end;
		margin-bottom: 14px;
	}
	.results-title h2 {
		font:
			600 20px 'Space Grotesk',
			sans-serif;
		margin: 7px 0 0;
	}
	.results-title h2 span {
		color: var(--muted);
		font-size: 13px;
	}
	.results-controls {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.results-controls label,
	.results-controls > span {
		color: var(--muted);
		font:
			10px 'DM Mono',
			monospace;
	}
	.results-controls select {
		min-width: 190px;
		border: 1px solid var(--line-strong);
		border-radius: 7px;
		padding: 9px;
		background: var(--surface);
		color: var(--text);
		cursor: pointer;
	}
	.product-grid,
	.loading-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 14px;
	}
	.product-card {
		display: flex;
		flex-direction: column;
		padding: 20px;
		min-height: 246px;
		transition:
			0.2s transform,
			0.2s border-color,
			0.2s background;
	}
	.product-card:hover {
		transform: translateY(-3px);
		border-color: var(--violet);
		background: var(--panel);
	}
	.card-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 21px;
		color: var(--muted);
	}
	.history-tag {
		margin-left: auto;
		margin-right: 10px;
		padding: 5px 7px;
		border: 1px solid var(--surface-strong);
		border-radius: 5px;
		color: var(--teal, #6bd6d7);
		font:
			9px 'DM Mono',
			monospace;
	}
	.product-card:hover .card-top :global(svg) {
		color: var(--violet);
	}
	.card-brand {
		font:
			10px 'DM Mono',
			monospace;
		color: var(--violet);
		text-transform: uppercase;
		letter-spacing: 0.07em;
	}
	.product-card h3 {
		font:
			600 15px/1.35 'Space Grotesk',
			sans-serif;
		letter-spacing: -0.02em;
		margin: 6px 0;
		min-height: 42px;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.card-spec {
		color: var(--muted-high);
		font-size: 10px;
		white-space: nowrap;
		text-overflow: ellipsis;
		overflow: hidden;
	}
	.card-line {
		height: 1px;
		background: var(--surface-strong);
		margin: auto 0 13px;
	}
	.card-bottom {
		display: flex;
		justify-content: space-between;
		gap: 10px;
	}
	.card-bottom > div:last-child {
		text-align: right;
	}
	.card-bottom span {
		display: block;
		color: var(--muted);
		font:
			9px 'DM Mono',
			monospace;
		margin-bottom: 6px;
	}
	.card-bottom strong {
		font:
			600 13px 'Space Grotesk',
			sans-serif;
	}
	.card-date {
		color: var(--muted);
		font-size: 10px;
		margin-top: 13px;
	}
	.loading-grid .panel {
		padding: 22px;
		min-height: 220px;
	}
	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 20px;
		margin: 25px 0;
		color: var(--muted);
		font:
			11px 'DM Mono',
			monospace;
	}
	@media (max-width: 1200px) {
		.filter-row {
			grid-template-columns: repeat(3, 1fr);
		}
		.product-grid,
		.loading-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (max-width: 650px) {
		.results-title,
		.results-controls {
			align-items: flex-start;
			flex-wrap: wrap;
			gap: 10px;
		}
		.filter-row {
			grid-template-columns: repeat(2, 1fr);
		}
		.product-grid,
		.loading-grid {
			grid-template-columns: 1fr;
		}
		.filter-actions {
			gap: 14px;
			flex-wrap: wrap;
		}
	}
</style>
