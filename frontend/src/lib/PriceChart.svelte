<script lang="ts">
	import { onMount } from 'svelte';
	import type { Chart as ChartType, ScriptableLineSegmentContext } from 'chart.js';
	import { dateTime, money, shortDate } from '$lib/format';
	import { tx } from '$lib/i18n';
	import { usePreferences } from '$lib/preferences.svelte';
	import {
		filterHistory,
		filterPriceChanges,
		historicalPriceSeries,
		priceSeries,
		unavailableIntervals,
		type Observation,
		type PriceChange,
		type Range
	} from '$lib/series';
	let {
		history,
		chartHistory = [],
		height = 285
	}: { history: Observation[]; chartHistory?: PriceChange[]; height?: number } = $props();
	const prefs = usePreferences();
	let range = $state<Range>('90D');
	let canvas = $state<HTMLCanvasElement>();
	let chart: ChartType | undefined;
	let zoomWindow = $state<{ min: number; max: number } | null>(null);
	let dragStart: number | null = null;
	let dragEnd: number | null = null;
	let ChartConstructor: typeof import('chart.js/auto').default | undefined = $state(undefined);
	let visible = $derived(filterHistory(history, range));
	let visibleChanges = $derived(filterPriceChanges(chartHistory, range));
	function selectRange(next: Range) {
		range = next;
		zoomWindow = null;
	}
	function pointerDown(event: PointerEvent) {
		if (!chart || !canvas || event.button !== 0) return;
		dragStart = event.offsetX;
		dragEnd = event.offsetX;
		canvas.setPointerCapture(event.pointerId);
	}
	function pointerMove(event: PointerEvent) {
		if (dragStart === null || !chart) return;
		dragEnd = event.offsetX;
		chart.draw();
	}
	function pointerUp(event: PointerEvent) {
		if (dragStart === null || !chart) return;
		const start = dragStart;
		const end = event.offsetX;
		dragStart = dragEnd = null;
		if (Math.abs(end - start) < 12) {
			chart.draw();
			return;
		}
		const min = Number(chart.scales.x.getValueForPixel(Math.min(start, end)));
		const max = Number(chart.scales.x.getValueForPixel(Math.max(start, end)));
		if (Number.isFinite(min) && Number.isFinite(max) && max > min) zoomWindow = { min, max };
	}
	onMount(async () => {
		ChartConstructor = (await import('chart.js/auto')).default;
	});
	$effect(() => {
		const points = visible;
		const changes = visibleChanges;
		const theme = prefs.resolved;
		const lang = prefs.lang;
		const light = theme === 'light';
		const colors = light ? ['#6e58ba', '#187e87', '#a37027'] : ['#ab9afa', '#6bd6d7', '#e6bb7b'];
		if (!ChartConstructor || !canvas || (!points.length && !changes.length)) {
			chart?.destroy();
			chart = undefined;
			return;
		}
		chart?.destroy();
		const offers = priceSeries(points);
		const unavailable = unavailableIntervals(points);
		const historical = historicalPriceSeries(changes, points);
		const times = [
			...points.map((p) => new Date(p.collected_at).getTime()),
			...changes.map((p) => new Date(p.valid_from).getTime())
		];
		const min = Math.min(...times),
			max = Math.max(...times);
		const compactDateTime = new Intl.DateTimeFormat(lang === 'de' ? 'de-CH' : 'en-CH', {
			day: '2-digit',
			month: 'short',
			hour: '2-digit',
			timeZone: 'Europe/Zurich'
		});
		chart = new ChartConstructor(canvas, {
			type: 'line',
			plugins: [
				{
					id: 'unavailableBandsAndSelection',
					beforeDatasetsDraw(instance) {
						const { ctx, chartArea, scales } = instance;
						ctx.save();
						ctx.beginPath();
						ctx.rect(chartArea.left, chartArea.top, chartArea.width, chartArea.height);
						ctx.clip();
						ctx.fillStyle = light ? '#187e8724' : '#6bd6d724';
						for (const offer of historical)
							for (const gap of offer.gaps) {
								const from = scales.x.getPixelForValue(gap[0].x);
								const to = scales.x.getPixelForValue(gap[1].x);
								ctx.fillRect(from, chartArea.top, to - from, chartArea.height);
							}
						for (const interval of unavailable) {
							const index = offers.findIndex((offer) => offer.id === interval.id);
							ctx.fillStyle =
								index === 0
									? light
										? '#6e58ba24'
										: '#ab9afa30'
									: light
										? '#187e8724'
										: '#6bd6d730';
							const from = scales.x.getPixelForValue(interval.start);
							const to = scales.x.getPixelForValue(interval.end);
							ctx.fillRect(from, chartArea.top, Math.max(to - from, 4), chartArea.height);
						}
						if (dragStart !== null && dragEnd !== null) {
							ctx.fillStyle = light ? '#6e58ba30' : '#ab9afa38';
							ctx.fillRect(
								Math.min(dragStart, dragEnd),
								chartArea.top,
								Math.abs(dragEnd - dragStart),
								chartArea.height
							);
						}
						ctx.restore();
					}
				},
				{
					id: 'pulseCrosshair',
					afterDatasetsDraw(instance) {
						const active = instance.getActiveElements();
						if (!active.length) return;
						const x = active[0].element.x;
						const { top, bottom } = instance.chartArea;
						instance.ctx.save();
						instance.ctx.strokeStyle = light ? '#a8a0b3' : '#8e849f';
						instance.ctx.setLineDash([3, 4]);
						instance.ctx.beginPath();
						instance.ctx.moveTo(x, top);
						instance.ctx.lineTo(x, bottom);
						instance.ctx.stroke();
						instance.ctx.restore();
					}
				}
			],
			data: {
				datasets: [
					...offers.map((offer, index) => ({
						label: chartHistory.length
							? `${offer.retailer} · ${tx('Messung', lang)}`
							: offer.retailer,
						data: offer.data,
						borderColor: colors[index % colors.length],
						backgroundColor: colors[index % colors.length],
						borderWidth: 2,
						pointRadius: offer.showLine ? 4 : 6,
						pointHoverRadius: 7,
						pointBorderWidth: 2,
						pointBorderColor: light ? '#fffefa' : '#1d2024',
						tension: 0,
						fill: false,
						showLine: offer.showLine,
						spanGaps: false,
						segment: {
							borderDash: (context: ScriptableLineSegmentContext) =>
								offer.data[context.p0DataIndex]?.availability === 'OutOfStock' ||
								offer.data[context.p1DataIndex]?.availability === 'OutOfStock'
									? [5, 5]
									: undefined
						}
					})),
					...historical.flatMap((offer) => [
						...offer.segments.map((segment) => ({
							label: `${offer.retailer} · ${tx('historische Preiswechsel', lang)}`,
							data: segment,
							borderColor: colors[1],
							backgroundColor: colors[1],
							borderWidth: 2,
							pointRadius: 0,
							pointHoverRadius: 5,
							stepped: 'after' as const,
							fill: false
						})),
						...offer.gaps.map((gap) => ({
							label: `${offer.retailer} · ${tx('Nicht verfügbar', lang)}`,
							data: gap,
							borderColor: colors[1],
							backgroundColor: colors[1],
							borderWidth: 2,
							borderDash: [5, 5],
							pointRadius: 0,
							pointHoverRadius: 0,
							fill: false
						}))
					])
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: {
					duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 350
				},
				interaction: { mode: 'nearest', intersect: false },
				plugins: {
					legend: {
						display:
							offers.length + historical.length > 1 || historical.some((row) => row.gaps.length),
						position: 'bottom',
						labels: {
							color: light ? '#565751' : '#adb3be',
							boxWidth: 8,
							boxHeight: 8,
							usePointStyle: false,
							padding: 18,
							font: { size: 11 },
							filter: (item, data) =>
								data.datasets.findIndex((dataset) => dataset.label === item.text) ===
								item.datasetIndex
						}
					},
					tooltip: {
						backgroundColor: light ? '#fffefa' : '#272a33',
						titleColor: light ? '#242722' : '#dfe2e9',
						bodyColor: light ? '#565751' : '#c7cbd5',
						borderColor: light ? '#d9d5cb' : '#484c58',
						borderWidth: 1,
						padding: 12,
						displayColors: true,
						callbacks: {
							title: (items) => dateTime(new Date(items[0].parsed.x ?? 0).toISOString(), lang),
							label: (item) =>
								item.dataset.label?.includes(tx('Nicht verfügbar', lang))
									? `${item.dataset.label} · ${tx('kein belegter Preis', lang)}`
									: `${item.dataset.label}: ${money(item.parsed.y, lang)}${(item.raw as { availability?: string })?.availability === 'OutOfStock' ? ` · ${tx('Nicht verfügbar', lang)}` : ''}`
						}
					}
				},
				scales: {
					x: {
						type: 'linear',
						min: zoomWindow?.min ?? (min === max ? min - 86400000 : min),
						max: zoomWindow?.max ?? (min === max ? max + 86400000 : max),
						grid: { color: light ? '#e8e4dc' : '#292c34' },
						border: { display: false },
						ticks: {
							color: light ? '#686963' : '#858b96',
							maxTicksLimit: 6,
							font: { size: 10 },
							callback: (value) =>
								max - min < 2 * 86400000
									? compactDateTime.format(new Date(Number(value)))
									: range === 'ALL' && !zoomWindow
										? new Intl.DateTimeFormat(lang === 'de' ? 'de-CH' : 'en-CH', {
												month: 'short',
												year: 'numeric',
												timeZone: 'Europe/Zurich'
											}).format(new Date(Number(value)))
										: shortDate(new Date(Number(value)).toISOString(), lang)
						}
					},
					y: {
						grid: { color: light ? '#e8e4dc' : '#292c34' },
						border: { display: false },
						ticks: {
							color: light ? '#686963' : '#858b96',
							font: { size: 10 },
							callback: (value) =>
								`CHF ${Number(value).toLocaleString(lang === 'de' ? 'de-CH' : 'en-CH')}`
						}
					}
				}
			}
		});
		return () => {
			chart?.destroy();
			chart = undefined;
		};
	});
</script>

<div class="chart-header">
	<span class="section-kicker">{tx('Preisverlauf', prefs.lang).toUpperCase()} · CHF</span>
	<div class="range-tabs" aria-label={tx('Zeitraum', prefs.lang)}>
		{#each ['7D', '30D', '90D', 'ALL'] as option (option)}<button
				class:active={range === option}
				onclick={() => selectRange(option as Range)}
				>{option === 'ALL' ? tx('Alle Zeiträume', prefs.lang) : option}</button
			>{/each}
	</div>
</div>
{#if zoomWindow}<button class="reset-zoom" onclick={() => (zoomWindow = null)}
		>{tx('Zoom zurücksetzen', prefs.lang)}</button
	>{/if}
{#if visible.length || visibleChanges.length}<div class="chart-wrap" style:height="{height}px">
		<canvas
			bind:this={canvas}
			onpointerdown={pointerDown}
			onpointermove={pointerMove}
			onpointerup={pointerUp}
			aria-label={tx(
				'Preisverlauf aus Preisbeobachtungen und historischen Preiswechseln',
				prefs.lang
			)}
		></canvas>
	</div>{:else}<div class="chart-empty">
		{tx('Für diesen Zeitraum gibt es noch keine Beobachtungen.', prefs.lang)}
	</div>{/if}
{#if history.length === 1}<p class="chart-note">
		{tx(
			'Bisher eine Beobachtung. Eine Linie erscheint erst mit einem zweiten echten Messpunkt.',
			prefs.lang
		)}
	</p>{/if}
{#if chartHistory.length}<p class="chart-note">
		{tx(
			'Digitec-Preiswechsel sind historische Händlerangaben, keine eigenen Tagesmessungen.',
			prefs.lang
		)}
		{#if chartHistory.some((point) => point.price === null)}
			{tx('Gestrichelte Stellen bedeuten: nicht verfügbar, kein belegter Preis.', prefs.lang)}
		{/if}
	</p>{/if}
{#if history.some((point) => point.availability === 'OutOfStock')}<p class="chart-note">
		{tx(
			'Gestrichelte Händlerlinien und farbige Flächen markieren belegte Nichtverfügbarkeit.',
			prefs.lang
		)}
	</p>{/if}
{#if visible.length || visibleChanges.length}<p class="chart-note">
		{tx('Zum Vergrössern einen Bereich im Diagramm aufziehen.', prefs.lang)}
	</p>{/if}

<style>
	.chart-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 15px;
		margin: 0 0 17px;
	}
	.range-tabs {
		display: flex;
		gap: 3px;
		background: var(--surface);
		padding: 3px;
		border: 1px solid var(--surface-strong);
		border-radius: 7px;
	}
	.range-tabs button {
		min-height: 32px;
		background: transparent;
		border: 0;
		border-radius: 4px;
		color: var(--muted);
		padding: 5px 10px;
		font:
			11px 'DM Mono',
			monospace;
		transition:
			background 0.2s,
			color 0.2s;
	}
	.range-tabs button.active {
		background: var(--violet);
		color: var(--bg);
	}
	.chart-wrap {
		width: 100%;
		position: relative;
		cursor: crosshair;
		touch-action: none;
	}
	.reset-zoom {
		border: 0;
		background: transparent;
		color: var(--violet);
		font:
			11px 'DM Mono',
			monospace;
		margin: -7px 0 8px;
		padding: 0;
	}
	.chart-empty {
		height: 220px;
		display: grid;
		place-items: center;
		color: var(--muted-high);
		font-size: 12px;
	}
	.chart-note {
		margin: 9px 0 0;
		color: var(--muted);
		font-size: 10px;
	}
	@media (max-width: 480px) {
		.chart-header {
			align-items: flex-start;
			flex-direction: column;
		}
		.range-tabs {
			align-self: flex-end;
		}
	}
</style>
