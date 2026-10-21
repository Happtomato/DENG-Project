<script lang="ts">
	import { onMount } from 'svelte';
	import type { Chart as ChartType } from 'chart.js';
	import { dateTime, money } from '$lib/format';
	import { tx } from '$lib/i18n';
	import { usePreferences } from '$lib/preferences.svelte';
	import { historicalPriceSeries, type PriceChange } from '$lib/series';

	type Example = {
		product_id: string;
		product_name: string;
		category: string;
		brand: string;
		point_count: number;
		points: {
			retailer_product_id: string;
			valid_from: string;
			price: number | null;
			point_type: string;
		}[];
	};
	let { example }: { example: Example } = $props();
	const prefs = usePreferences();
	let canvas = $state<HTMLCanvasElement>();
	let ChartConstructor: typeof import('chart.js/auto').default | undefined = $state(undefined);
	let chart: ChartType | undefined;
	const shortageStart = Date.parse('2020-01-01T00:00:00Z');
	const shortageEnd = Date.parse('2022-12-31T23:59:59Z');
	const aiStart = Date.parse('2023-03-21T00:00:00Z');
	let hasShortageData = $derived(
		example.points.some((point) => Date.parse(point.valid_from) <= shortageEnd)
	);
	onMount(async () => {
		ChartConstructor = (await import('chart.js/auto')).default;
	});
	$effect(() => {
		const theme = prefs.resolved;
		const lang = prefs.lang;
		const light = theme === 'light';
		const points = example.points;
		if (!ChartConstructor || !canvas || !points.length) return;
		chart?.destroy();
		const color =
			example.category === 'ram'
				? light
					? '#6e58ba'
					: '#ab9afa'
				: example.category === 'gpu'
					? light
						? '#a37027'
						: '#e6bb7b'
					: light
						? '#187e87'
						: '#6bd6d7';
		const series = historicalPriceSeries(
			points.map((point): PriceChange => ({
				...point,
				point_type: point.point_type as PriceChange['point_type'],
				retailer: 'Digitec'
			}))
		)[0];
		const from = Date.parse(points[0].valid_from);
		const to = Date.parse(points.at(-1)!.valid_from);
		chart = new ChartConstructor(canvas, {
			type: 'line',
			plugins: [
				{
					id: 'marketContextBands',
					beforeDatasetsDraw(instance) {
						const { ctx, chartArea, scales } = instance;
						ctx.save();
						ctx.beginPath();
						ctx.rect(chartArea.left, chartArea.top, chartArea.width, chartArea.height);
						ctx.clip();
						const band = (start: number, end: number, fill: string) => {
							if (end < from || start > to) return;
							ctx.fillStyle = fill;
							const left = scales.x.getPixelForValue(Math.max(start, from));
							const right = scales.x.getPixelForValue(Math.min(end, to));
							ctx.fillRect(left, chartArea.top, right - left, chartArea.height);
						};
						band(shortageStart, shortageEnd, light ? '#d8894725' : '#d8894720');
						band(aiStart, to, light ? '#7d76cf16' : '#7d76cf1a');
						for (const gap of series.gaps)
							band(gap[0].x, gap[1].x, light ? '#187e8725' : '#6bd6d729');
						ctx.restore();
					}
				}
			],
			data: {
				datasets: [
					...series.segments.map((segment) => ({
						label: 'Digitec',
						data: segment,
						borderColor: color,
						backgroundColor: color,
						borderWidth: 2,
						pointRadius: 0,
						pointHoverRadius: 4,
						stepped: 'after' as const,
						fill: false
					})),
					...series.gaps.map((gap) => ({
						label: tx('Nicht verfügbar', lang),
						data: gap,
						borderColor: color,
						backgroundColor: color,
						borderWidth: 2,
						borderDash: [5, 5],
						pointRadius: 0,
						fill: false
					}))
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				interaction: { mode: 'nearest', intersect: false },
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							title: (items) => dateTime(new Date(items[0].parsed.x ?? 0).toISOString(), lang),
							label: (item) =>
								item.dataset.label === tx('Nicht verfügbar', lang)
									? tx('Nicht verfügbar', lang)
									: money(item.parsed.y, lang)
						}
					}
				},
				scales: {
					x: {
						type: 'linear',
						min: from,
						max: to,
						grid: { color: light ? '#e8e4dc' : '#292c34' },
						border: { display: false },
						ticks: {
							color: light ? '#686963' : '#858b96',
							maxTicksLimit: 5,
							font: { size: 10 },
							callback: (value) =>
								new Intl.DateTimeFormat(lang === 'de' ? 'de-CH' : 'en-CH', {
									year: 'numeric',
									month: 'short',
									timeZone: 'Europe/Zurich'
								}).format(new Date(Number(value)))
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

<article class="context-card panel">
	<div class="context-info">
		<span class="category {example.category}">{example.category.toUpperCase()}</span>
		<h3><a href="/explore/{example.product_id}">{example.product_name}</a></h3>
		<p>{example.brand} · {example.point_count} {tx('Datenpunkte', prefs.lang)}</p>
		{#if !hasShortageData}<small
				>{tx(
					'Für die Chipmangel-Phase liegen zu diesem Beispiel keine Daten vor.',
					prefs.lang
				)}</small
			>{/if}
	</div>
	<div class="context-plot">
		<canvas
			bind:this={canvas}
			aria-label={`${example.category.toUpperCase()} ${tx('historische Preiswechsel', prefs.lang)}`}
		></canvas>
	</div>
</article>

<style>
	.context-card {
		display: grid;
		grid-template-columns: minmax(190px, 0.9fr) minmax(0, 2.1fr);
		gap: 18px;
		padding: 20px;
		margin-bottom: 12px;
		align-items: center;
	}
	.context-info h3 {
		font:
			600 16px/1.35 'Space Grotesk',
			sans-serif;
		margin: 12px 0 7px;
	}
	.context-info h3 a:hover {
		color: var(--violet);
	}
	.context-info p,
	.context-info small {
		font-size: 10px;
		color: var(--muted);
		line-height: 1.6;
	}
	.context-info small {
		display: block;
		margin-top: 12px;
	}
	.context-plot {
		height: 205px;
		min-width: 0;
		position: relative;
	}
	@media (max-width: 700px) {
		.context-card {
			grid-template-columns: 1fr;
		}
		.context-plot {
			height: 200px;
		}
	}
</style>
