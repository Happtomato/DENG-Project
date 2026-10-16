<script lang="ts">
	import type { PageData } from './$types';
	import {
		ArrowRight,
		ArrowUpRight,
		CircuitBoard,
		Cpu,
		FlaskConical,
		HardDrive,
		MemoryStick,
		Search
	} from '@lucide/svelte';
	import PriceChart from '$lib/PriceChart.svelte';
	import { categoryLabel, dateTime, money } from '$lib/format';
	import { project } from '$lib/identity';
	import { tx } from '$lib/i18n';
	import { usePreferences } from '$lib/preferences.svelte';
	let { data }: { data: PageData } = $props();
	const prefs = usePreferences();
	const categories = [
		{ id: 'gpu', icon: CircuitBoard },
		{ id: 'ram', icon: MemoryStick },
		{ id: 'ssd', icon: HardDrive }
	];
</script>

<svelte:head><title>{project.name} · {tx('Übersicht', prefs.lang)}</title></svelte:head>

<section class="lab-hero">
	<div class="hero-copy">
		<p class="eyebrow">{project.credit}</p>
		<h1>{tx('Entdecke, wie sich Hardwarepreise verändern.', prefs.lang)}</h1>
		<p class="hero-intro">
			{tx(
				'Wir beobachten Schweizer Hardwarepreise und machen ihre Entwicklung sichtbar.',
				prefs.lang
			)}
		</p>
		<form class="hero-search" action="/explore" method="GET">
			<Search size={21} strokeWidth={1.9} />
			<input
				name="search"
				aria-label={tx('Produkte suchen', prefs.lang)}
				placeholder={tx('Produkt, Marke oder Modell suchen …', prefs.lang)}
			/>
			<button type="submit" aria-label={tx('Produkte suchen', prefs.lang)}
				><ArrowRight size={18} /></button
			>
		</form>
		<div class="hero-chips" aria-label={tx('Kategorie', prefs.lang)}>
			<a href="/explore">{tx('Alle', prefs.lang)}</a>
			{#each categories as category (category.id)}<a href="/explore?category={category.id}"
					>{category.id.toUpperCase()}</a
				>{/each}
		</div>
	</div>
	<div class="hero-aside" aria-hidden="true">
		<div class="chip-outline"><Cpu size={41} strokeWidth={1.1} /><span>GPU / RAM / SSD</span></div>
		<div class="hero-index">CH—26 <span>◉</span> 03 CATEGORIES</div>
	</div>
</section>

{#if data.dbError}<div class="alert">
		{tx('Die Produktdatenbank ist momentan nicht erreichbar.', prefs.lang)}
		{data.dbError}
	</div>{/if}

<section class="featured-section">
	<div class="section-title">
		<div>
			<p class="section-kicker">01 / {tx('Preisverlauf im Fokus', prefs.lang)}</p>
			<h2>{tx('Preisverlauf im Fokus', prefs.lang)}</h2>
		</div>
		{#if data.featured}<a class="text-link" href="/explore/{data.featured.product.product_id}"
				>{tx('Alle Produkte ansehen', prefs.lang)} <ArrowUpRight size={16} /></a
			>{/if}
	</div>
	<div class="featured-card panel">
		{#if data.featured}
			<div class="featured-copy">
				<span class="category {data.featured.product.category}"
					>{data.featured.product.category.toUpperCase()}</span
				>
				<span class="featured-brand">{data.featured.product.brand}</span>
				<h3>
					<a href="/explore/{data.featured.product.product_id}"
						>{data.featured.product.product_name}</a
					>
				</h3>
				<div class="featured-current">
					<strong>{money(data.featured.product.price, prefs.lang)}</strong><span
						>{data.featured.product.retailer}</span
					>
				</div>
				<p>
					{data.featured.history.length === 1
						? tx('Für dieses Produkt liegt erst eine echte Messung vor.', prefs.lang)
						: tx('Die Preisgeschichte wächst mit jeder echten Beobachtung.', prefs.lang)}
				</p>
			</div>
			<div class="featured-chart"><PriceChart history={data.featured.history} height={275} /></div>
		{:else}
			<div class="empty">
				<FlaskConical size={28} />
				<p>{tx('Kein Preisverlauf vorhanden.', prefs.lang)}</p>
			</div>
		{/if}
	</div>
</section>

<section class="latest-section">
	<div class="section-title">
		<div>
			<p class="section-kicker">02 / LIVE DATA</p>
			<h2>{tx('Zuletzt beobachtet', prefs.lang)}</h2>
			<p>{tx('Neueste echte Preismessungen aus PostgreSQL.', prefs.lang)}</p>
		</div>
		<a class="text-link" href="/explore"
			>{tx('Alle Produkte ansehen', prefs.lang)} <ArrowUpRight size={16} /></a
		>
	</div>
	<div class="latest-grid">
		{#each (data.db?.recent || []).slice(0, 4) as row (row.product_id + row.collected_at + row.retailer)}
			<a class="latest-card panel" href="/explore/{row.product_id}">
				<div class="latest-top">
					<span class="category {row.category}">{row.category.toUpperCase()}</span><ArrowUpRight
						size={16}
					/>
				</div>
				<span class="latest-brand">{row.brand}</span>
				<h3>{row.product_name}</h3>
				<div class="latest-bottom">
					<strong>{money(row.price, prefs.lang)}</strong><span
						>{dateTime(row.collected_at, prefs.lang)}</span
					>
				</div>
			</a>
		{:else}<div class="empty panel">{tx('Keine Messungen vorhanden.', prefs.lang)}</div>{/each}
	</div>
</section>

<section class="categories-section">
	<div class="section-title">
		<div>
			<p class="section-kicker">03 / COMPONENTS</p>
			<h2>{tx('Komponenten entdecken', prefs.lang)}</h2>
			<p>{tx('Vom Grafikchip bis zur schnellen SSD.', prefs.lang)}</p>
		</div>
	</div>
	<div class="category-links">
		{#each categories as category (category.id)}<a
				class="category-link panel"
				href="/explore?category={category.id}"
			>
				<div class="category-link-icon {category.id}">
					<category.icon size={27} strokeWidth={1.5} />
				</div>
				<div>
					<span>{category.id.toUpperCase()}</span><strong
						>{categoryLabel(category.id, prefs.lang)}</strong
					><small
						>{data.db?.categories.find((item) => item.category === category.id)?.count ?? 0}
						{tx('Produkte', prefs.lang)}</small
					>
				</div>
				<ArrowUpRight size={17} />
			</a>{/each}
	</div>
</section>

<section class="lab-footer">
	<div class="lab-stats">
		<div>
			<strong>{data.db?.stats.products ?? '—'}</strong><span>{tx('Produkte', prefs.lang)}</span>
		</div>
		<div>
			<strong>{data.db?.stats.observations ?? '—'}</strong><span
				>{tx('Beobachtungen', prefs.lang)}</span
			>
		</div>
		<div><strong>MediaMarkt</strong><span>{tx('Händler', prefs.lang)}</span></div>
	</div>
	<div class="lab-actions">
		<a class="btn primary" href="/explore"
			>{tx('Alle Produkte ansehen', prefs.lang)} <ArrowRight size={15} /></a
		><a class="btn ghost" href="/pipelines"
			>{tx('Pipeline öffnen', prefs.lang)} <ArrowUpRight size={15} /></a
		>
	</div>
</section>

<style>
	.lab-hero {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 280px;
		gap: 35px;
		align-items: center;
		padding: 30px 0 62px;
	}
	.hero-copy h1 {
		max-width: 750px;
		margin: 0;
		font:
			600 clamp(38px, 5vw, 70px)/1.04 'Space Grotesk',
			sans-serif;
		letter-spacing: -0.067em;
	}
	.hero-intro {
		margin: 20px 0 27px;
		max-width: 590px;
		color: var(--muted);
		font-size: 15px;
		line-height: 1.7;
	}
	.hero-search {
		max-width: 660px;
		height: 58px;
		display: flex;
		align-items: center;
		gap: 15px;
		padding: 6px 7px 6px 19px;
		background: var(--panel);
		border: 1px solid var(--line-strong);
		border-radius: 14px;
		color: var(--violet);
		box-shadow: 0 8px 25px #0000000a;
	}
	.hero-search:focus-within {
		border-color: var(--violet);
		box-shadow: 0 0 0 3px #8d76c42b;
	}
	.hero-search input {
		min-width: 0;
		flex: 1;
		border: 0;
		outline: 0;
		background: none;
		color: var(--text);
		font-size: 14px;
	}
	.hero-search input::placeholder {
		color: var(--muted);
	}
	.hero-search button {
		height: 43px;
		width: 43px;
		flex: none;
		display: grid;
		place-items: center;
		border: 0;
		border-radius: 10px;
		background: var(--violet);
		color: var(--bg);
	}
	.hero-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 15px;
	}
	.hero-chips a {
		padding: 8px 14px;
		border: 1px solid var(--line);
		border-radius: 99px;
		color: var(--muted);
		font:
			11px 'DM Mono',
			monospace;
		transition: 0.2s;
	}
	.hero-chips a:hover {
		color: var(--text);
		border-color: var(--violet);
		transform: translateY(-2px);
	}
	.hero-aside {
		min-height: 265px;
		display: grid;
		place-items: center;
		position: relative;
		color: var(--violet);
	}
	.chip-outline {
		width: 210px;
		height: 210px;
		display: grid;
		place-items: center;
		border: 1px solid var(--line-strong);
		border-radius: 32px;
		transform: rotate(-8deg);
		background: var(--surface);
	}
	.chip-outline::before {
		content: '';
		position: absolute;
		inset: 16px;
		border: 1px dashed var(--line-strong);
		border-radius: 20px;
	}
	.chip-outline :global(svg),
	.chip-outline span {
		transform: rotate(8deg);
	}
	.chip-outline span {
		position: absolute;
		bottom: 45px;
		color: var(--muted);
		font:
			9px 'DM Mono',
			monospace;
		letter-spacing: 0.1em;
	}
	.hero-index {
		position: absolute;
		bottom: 0;
		right: 3px;
		color: var(--muted);
		font:
			10px 'DM Mono',
			monospace;
	}
	.hero-index span {
		color: var(--green);
	}
	.featured-section,
	.latest-section,
	.categories-section {
		margin-bottom: 50px;
	}
	.section-title {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 18px;
		margin-bottom: 17px;
	}
	.section-title h2 {
		font:
			600 clamp(23px, 2.4vw, 32px) 'Space Grotesk',
			sans-serif;
		letter-spacing: -0.045em;
		margin: 8px 0 0;
	}
	.section-title p:last-child:not(.section-kicker) {
		color: var(--muted);
		margin: 6px 0 0;
		font-size: 12px;
	}
	.featured-card {
		display: grid;
		grid-template-columns: minmax(225px, 0.7fr) minmax(0, 1.3fr);
		gap: 20px;
		padding: 27px;
		background: var(--panel);
	}
	.featured-copy {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
	}
	.featured-brand,
	.latest-brand {
		color: var(--violet);
		font:
			10px 'DM Mono',
			monospace;
		letter-spacing: 0.11em;
		text-transform: uppercase;
	}
	.featured-brand {
		margin-top: 25px;
	}
	.featured-copy h3 {
		font:
			600 clamp(19px, 2.4vw, 29px)/1.22 'Space Grotesk',
			sans-serif;
		letter-spacing: -0.045em;
		margin: 9px 0 20px;
	}
	.featured-copy h3 a:hover {
		color: var(--violet);
	}
	.featured-current {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.featured-current strong {
		font:
			600 25px 'Space Grotesk',
			sans-serif;
	}
	.featured-current span,
	.featured-copy p {
		color: var(--muted);
		font-size: 11px;
	}
	.featured-copy p {
		margin-top: auto;
		line-height: 1.6;
	}
	.featured-chart {
		min-width: 0;
		padding: 3px 0;
	}
	.featured-card .empty {
		grid-column: 1 / -1;
		display: grid;
		place-items: center;
		gap: 10px;
	}
	.latest-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 13px;
	}
	.latest-card {
		padding: 19px;
		min-height: 205px;
		display: flex;
		flex-direction: column;
		transition:
			transform 0.2s,
			border-color 0.2s,
			box-shadow 0.2s;
	}
	.latest-card:hover {
		transform: translateY(-3px);
		border-color: var(--violet);
		box-shadow: 0 14px 30px #00000012;
	}
	.latest-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		color: var(--muted);
		margin-bottom: 20px;
	}
	.latest-card h3 {
		margin: 6px 0 20px;
		font:
			600 14px/1.35 'Space Grotesk',
			sans-serif;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.latest-bottom {
		margin-top: auto;
		padding-top: 13px;
		border-top: 1px solid var(--line);
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.latest-bottom strong {
		font:
			600 16px 'Space Grotesk',
			sans-serif;
	}
	.latest-bottom span {
		color: var(--muted);
		font:
			10px 'DM Mono',
			monospace;
	}
	.category-links {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 13px;
	}
	.category-link {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 18px;
		transition:
			transform 0.2s,
			border-color 0.2s;
	}
	.category-link:hover {
		transform: translateY(-2px);
		border-color: var(--violet);
	}
	.category-link-icon {
		width: 52px;
		height: 52px;
		flex: none;
		display: grid;
		place-items: center;
		border-radius: 11px;
		background: var(--surface);
		color: var(--violet);
	}
	.category-link-icon.ram {
		color: var(--cyan);
	}
	.category-link-icon.ssd {
		color: #b28a3e;
	}
	.category-link div:nth-child(2) {
		min-width: 0;
		flex: 1;
	}
	.category-link span,
	.category-link small {
		display: block;
		color: var(--muted);
		font:
			10px 'DM Mono',
			monospace;
	}
	.category-link strong {
		display: block;
		margin: 3px 0;
		font:
			600 15px 'Space Grotesk',
			sans-serif;
	}
	.category-link > :global(svg) {
		color: var(--muted);
	}
	.lab-footer {
		border-top: 1px solid var(--line);
		padding: 22px 0 5px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 20px;
	}
	.lab-stats {
		display: flex;
		gap: 35px;
	}
	.lab-stats strong {
		display: block;
		font:
			600 21px 'Space Grotesk',
			sans-serif;
	}
	.lab-stats span {
		color: var(--muted);
		font:
			10px 'DM Mono',
			monospace;
	}
	.lab-actions {
		display: flex;
		gap: 9px;
		flex-wrap: wrap;
	}
	@media (max-width: 1120px) {
		.latest-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.lab-hero {
			grid-template-columns: minmax(0, 1fr) 190px;
		}
		.chip-outline {
			width: 165px;
			height: 165px;
		}
	}
	@media (max-width: 760px) {
		.lab-hero {
			grid-template-columns: 1fr;
			padding-top: 15px;
		}
		.hero-aside {
			display: none;
		}
		.featured-card {
			grid-template-columns: 1fr;
		}
		.featured-copy p {
			margin-top: 12px;
		}
		.category-links {
			grid-template-columns: 1fr;
		}
		.lab-footer {
			align-items: flex-start;
			flex-direction: column;
		}
	}
	@media (max-width: 520px) {
		.lab-hero {
			padding-bottom: 43px;
		}
		.latest-grid {
			grid-template-columns: 1fr;
		}
		.section-title {
			align-items: flex-start;
			flex-direction: column;
		}
		.lab-stats {
			gap: 22px;
		}
		.featured-card {
			padding: 18px;
		}
	}
</style>
