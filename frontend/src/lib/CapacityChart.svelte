<script lang="ts">
	import { onMount } from 'svelte';
	import type { Chart as ChartType } from 'chart.js';
	import { money } from '$lib/format';
	import { tx } from '$lib/i18n';
	import { usePreferences } from '$lib/preferences.svelte';

	type Point = {
		capacity_gb: number;
		products: number;
		avg_price_per_gb: number;
		avg_price_chf: number;
	};
	let { category, points }: { category: 'gpu' | 'ram' | 'ssd'; points: Point[] } = $props();
	const prefs = usePreferences();
	let metric = $state<'per_gb' | 'total'>('per_gb');
	let canvas = $state<HTMLCanvasElement>();
	let ChartConstructor: typeof import('chart.js/auto').default | undefined = $state(undefined);
	let chart: ChartType | undefined;
	const names = { gpu: 'Grafikkarten · VRAM', ram: 'Arbeitsspeicher', ssd: 'SSDs' };
	const accents = { gpu: '#aa96f2', ram: '#6bcfd0', ssd: '#dfbd78' };
	let productCount = $derived(points.reduce((total, point) => total + point.products, 0));
	const unitPrice = (value: number) =>
		new Intl.NumberFormat(prefs.lang === 'de' ? 'de-CH' : 'en-CH', {
			style: 'currency',
			currency: 'CHF',
			minimumFractionDigits: 2,
			maximumFractionDigits: 3
		}).format(value);

	onMount(async () => {
		ChartConstructor = (await import('chart.js/auto')).default;
	});

	$effect(() => {
		const rows = points;
		const selected = metric;
		const light = prefs.resolved === 'light';
		const lang = prefs.lang;
		if (!ChartConstructor || !canvas || !rows.length) return;
		chart?.destroy();
		const instance = new ChartConstructor(canvas, {
			type: 'bar',
			data: {
				labels: rows.map((row) => `${row.capacity_gb} GB`),
				datasets: [
					{
						label: selected === 'per_gb' ? tx('CHF pro GB', lang) : tx('Preis in CHF', lang),
						data: rows.map((row) =>
							selected === 'per_gb' ? row.avg_price_per_gb : row.avg_price_chf
						),
						backgroundColor: accents[category],
						hoverBackgroundColor: light ? '#6552a8' : '#d1c5ff',
						borderRadius: 6,
						maxBarThickness: 52
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: {
					duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 280
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: light ? '#fffefa' : '#272a33',
						titleColor: light ? '#242722' : '#dfe2e9',
						bodyColor: light ? '#565751' : '#c7cbd5',
						borderColor: light ? '#d9d5cb' : '#484c58',
						borderWidth: 1,
						padding: 11,
						callbacks: {
							label: (item) =>
								`${item.dataset.label}: ${selected === 'per_gb' ? unitPrice(Number(item.parsed.y)) : money(item.parsed.y, lang)}`,
							afterLabel: (item) =>
								`${rows[item.dataIndex].products} ${tx(rows[item.dataIndex].products === 1 ? 'Produkt in dieser Gruppe' : 'Produkte in dieser Gruppe', lang)}`
						}
					}
				},
				scales: {
					x: {
						grid: { display: false },
						border: { display: false },
						ticks: { color: light ? '#686963' : '#a0a6af', font: { size: 11 } }
					},
					y: {
						beginAtZero: true,
						grid: { color: light ? '#e8e4dc' : '#30333a' },
						border: { display: false },
						ticks: {
							color: light ? '#686963' : '#a0a6af',
							font: { size: 10 },
							callback: (value) =>
								`CHF ${Number(value).toLocaleString(lang === 'de' ? 'de-CH' : 'en-CH')}`
						}
					}
				}
			}
		});
		chart = instance;
		return () => {
			instance.destroy();
			if (chart === instance) chart = undefined;
		};
	});
</script>

<section class="panel capacity-panel {category}">
	<div class="capacity-head">
		<div>
			<p class="section-kicker">
				{category.toUpperCase()} · {productCount}
				{tx(productCount === 1 ? 'Produkt' : 'Produkte', prefs.lang)}
			</p>
			<h2>{tx(names[category], prefs.lang)}</h2>
		</div>
		<span class="metric-badge"
			>{category === 'gpu' ? 'VRAM' : tx('Kapazität', prefs.lang)} · GB</span
		>
	</div>
	{#if points.length}
		<div class="metric-switch" aria-label={tx('Diagramm-Metrik', prefs.lang)}>
			<button class:active={metric === 'per_gb'} onclick={() => (metric = 'per_gb')}
				>{tx('CHF pro GB', prefs.lang)}</button
			>
			<button class:active={metric === 'total'} onclick={() => (metric = 'total')}
				>{tx('Produktpreis', prefs.lang)}</button
			>
		</div>
		<div class="canvas-wrap">
			<canvas
				bind:this={canvas}
				aria-label="{tx(names[category], prefs.lang)}: {tx(
					'Durchschnittspreis nach Kapazität',
					prefs.lang
				)}"
			></canvas>
		</div>
		<div class="capacity-rows" aria-label={tx('Werte zum Diagramm', prefs.lang)}>
			{#each points as point (point.capacity_gb)}
				<div class="capacity-row">
					<strong>{point.capacity_gb} GB</strong>
					<span
						>{point.products} {tx(point.products === 1 ? 'Produkt' : 'Produkte', prefs.lang)}</span
					>
					<b
						>{metric === 'per_gb'
							? unitPrice(point.avg_price_per_gb)
							: money(point.avg_price_chf, prefs.lang)}</b
					>
				</div>
			{/each}
		</div>
	{:else}
		<p class="capacity-empty">
			{tx('Noch keine Produkte mit Preis und bestätigter Kapazität.', prefs.lang)}
		</p>
	{/if}
</section>

<style>
	.capacity-panel {
		min-width: 0;
		overflow: hidden;
	}
	.capacity-head {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		align-items: flex-start;
		padding: 22px 23px 12px;
	}
	.capacity-head h2 {
		margin: 7px 0 0;
		font:
			600 18px 'Space Grotesk',
			sans-serif;
	}
	.capacity-head .section-kicker {
		margin: 0;
	}
	.metric-badge {
		flex: none;
		color: var(--muted);
		border: 1px solid var(--line);
		border-radius: 6px;
		padding: 6px 8px;
		font:
			10px 'DM Mono',
			monospace;
	}
	.metric-switch {
		display: inline-flex;
		gap: 3px;
		margin: 5px 23px 15px;
		padding: 3px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: 8px;
	}
	.metric-switch button {
		border: 0;
		border-radius: 5px;
		background: transparent;
		color: var(--muted);
		padding: 7px 10px;
		font:
			11px 'DM Mono',
			monospace;
	}
	.metric-switch button.active {
		background: var(--surface-strong);
		color: var(--text);
	}
	.metric-switch button:focus-visible {
		outline: 2px solid var(--violet);
		outline-offset: 2px;
	}
	.canvas-wrap {
		height: 245px;
		margin: 0 17px 16px 8px;
	}
	.capacity-rows {
		border-top: 1px solid var(--line);
		padding: 5px 23px 15px;
		max-height: 235px;
		overflow-y: auto;
	}
	.capacity-row {
		display: grid;
		grid-template-columns: 68px 1fr auto;
		gap: 10px;
		align-items: center;
		padding: 10px 0;
		border-bottom: 1px solid var(--surface-strong);
		font-size: 11px;
	}
	.capacity-row:last-child {
		border: 0;
	}
	.capacity-row strong,
	.capacity-row b {
		font:
			500 11px 'DM Mono',
			monospace;
	}
	.capacity-row span {
		color: var(--muted);
	}
	.capacity-row b {
		text-align: right;
	}
	.capacity-empty {
		min-height: 290px;
		display: grid;
		place-items: center;
		margin: 0;
		padding: 25px;
		color: var(--muted);
		text-align: center;
		font-size: 12px;
		line-height: 1.6;
	}
	@media (max-width: 600px) {
		.capacity-head {
			padding: 18px 18px 12px;
		}
		.metric-switch {
			margin-left: 18px;
		}
		.capacity-rows {
			padding-left: 18px;
			padding-right: 18px;
		}
	}
</style>
