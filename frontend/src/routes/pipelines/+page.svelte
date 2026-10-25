<script lang="ts">
	import type { PageData } from './$types';
	import { catalogReasonLabel, catalogStatusLabel, stateLabel, tx } from '$lib/i18n';
	import { project } from '$lib/identity';
	import { usePreferences } from '$lib/preferences.svelte';
	import { onMount } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import {
		ArrowUpRight,
		CheckCircle2,
		Clock3,
		Database,
		ExternalLink,
		Pause,
		Play,
		RefreshCw,
		ShieldCheck,
		Workflow
	} from '@lucide/svelte';
	import { dateTime } from '$lib/format';
	let { data }: { data: PageData } = $props();
	const prefs = usePreferences();
	let verifying = $state(false);
	let verification = $state<Record<string, unknown> | null>(null);
	let verifyError = $state('');
	const deployment = $derived(
		data.prefect.deployments.find((d) => d.name === 'fetch-product-prices-daily')
	);
	onMount(() => {
		const timer = setInterval(() => invalidateAll(), 15000);
		return () => clearInterval(timer);
	});
	async function verifyNow() {
		if (verifying) return;
		verifying = true;
		verifyError = '';
		try {
			const response = await fetch('/api/verify');
			verification = await response.json();
			if (!response.ok)
				verifyError = String(verification?.error || tx('Verifikation fehlgeschlagen', prefs.lang));
		} catch (error) {
			verifyError = String(error);
		} finally {
			verifying = false;
		}
	}
</script>

<svelte:head><title>{project.name}</title></svelte:head>
<div class="page-heading">
	<div>
		<p class="eyebrow">{tx('PROJEKT / PIPELINE', prefs.lang)}</p>
		<h1>Pipeline Lab.</h1>
		<p>{tx('Prefect-Status, Datenqualität und Kandidatenkatalog an einem Ort.', prefs.lang)}</p>
	</div>
	<div class="heading-actions">
		<a class="btn ghost" href={data.prefect.uiUrl} target="_blank" rel="noreferrer"
			>{tx('Prefect öffnen', prefs.lang)} <ExternalLink size={14} /></a
		><button class="btn" onclick={() => invalidateAll()}
			><RefreshCw size={14} /> {tx('Aktualisieren', prefs.lang)}</button
		>
	</div>
</div>
<div class="pipeline-summary">
	<div class="panel summary-card">
		<span class="summary-icon"><Workflow size={18} /></span>
		<div>
			<small>{tx('PREFECT SERVER', prefs.lang)}</small><strong
				>{tx(data.prefect.available ? 'Erreichbar' : 'Nicht erreichbar', prefs.lang)}</strong
			>
		</div>
		<span class:offline={!data.prefect.available} class="status"
			>{data.prefect.available ? 'Online' : 'Offline'}</span
		>
	</div>
	<div class="panel summary-card">
		<span class="summary-icon purple"><Pause size={18} /></span>
		<div>
			<small>{tx('DAILY SCHEDULE · 03:00', prefs.lang)}</small><strong
				>{deployment?.schedules?.[0]?.schedule?.timezone || 'Europe/Zurich'}</strong
			>
		</div>
		<span
			class:paused={deployment?.paused || !deployment?.schedules?.some((s) => s.active)}
			class="status"
			>{tx(
				deployment
					? deployment.paused || !deployment.schedules.some((s) => s.active)
						? 'Pausiert'
						: 'Aktiv'
					: 'Unbekannt',
				prefs.lang
			)}</span
		>
	</div>
	<div class="panel summary-card">
		<span class="summary-icon cyan"><Database size={18} /></span>
		<div>
			<small>{tx('KATALOGKANDIDATEN', prefs.lang)}</small><strong
				>{data.catalog.available ? data.catalog.total : '—'}</strong
			>
		</div>
		<span class="hint">{tx('Rohkatalog', prefs.lang)}</span>
	</div>
</div>
{#if data.prefect.error}<div class="alert">Prefect API: {data.prefect.error}</div>{/if}
<div class="operations-grid">
	<section class="panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">{tx('MANUELLE SCHRITTE', prefs.lang)}</p>
				<h2>{tx('Aktionen', prefs.lang)}</h2>
				<p>{tx('Nur sichere, tatsächlich unterstützte Aktionen sind ausführbar.', prefs.lang)}</p>
			</div>
			<ShieldCheck size={18} color="#a999f1" />
		</div>
		<div class="actions-list">
			<div class="action-row">
				<span class="action-symbol"><CheckCircle2 size={17} /></span>
				<div>
					<strong>VERIFY</strong><small
						>{tx('PostgreSQL-Bestand und Qualitätsregeln prüfen.', prefs.lang)}</small
					>
				</div>
				<button class="btn primary" disabled={verifying} onclick={verifyNow}
					>{tx(verifying ? 'Prüfe …' : 'Jetzt prüfen', prefs.lang)}</button
				>
			</div>
			{#each [{ name: 'DISCOVER', info: 'Katalog-Links sammeln · Live-Abrufe' }, { name: 'INITIAL FROM CATALOG', info: 'Kandidaten importieren · Live-Abrufe' }, { name: 'DAILY', info: 'Bekannte URLs abrufen · Live-Abrufe' }, { name: 'REPLAY', info: 'Gespeicherte Raw-Dateien erneut verarbeiten' }] as action (action.name)}<div
					class="action-row unavailable"
				>
					<span class="action-symbol muted-icon"><Play size={16} /></span>
					<div><strong>{action.name}</strong><small>{tx(action.info, prefs.lang)}</small></div>
					<span class="unavailable-label">{tx('Nicht verfügbar', prefs.lang)}</span>
				</div>{/each}
		</div>
		{#if verification}<div class:failure={verification.ok === false} class="verify-result">
				<strong
					>{verification.ok
						? '✓ ' + tx('Verifikation erfolgreich', prefs.lang)
						: tx('Verifikation fehlgeschlagen', prefs.lang)}</strong
				><span
					>{verification.products}
					{tx('Produkte', prefs.lang)} · {verification.offers}
					{tx('Angebote', prefs.lang)} · {verification.observations}
					{tx('Beobachtungen', prefs.lang)} · {verification.invalid_prices}
					{tx('ungültige Preise', prefs.lang)} · {verification.duplicates}
					{tx('Duplikate', prefs.lang)}</span
				>
			</div>{/if}{#if verifyError}<div class="alert">{verifyError}</div>{/if}
		<p class="control-note">
			{tx(
				'Manuelle Prefect-Starts sind derzeit deaktiviert: Für die Workflow-Modi ist kein sicherer manueller Runner konfiguriert.',
				prefs.lang
			)}
			{tx('Das vorhandene Deployment meldet', prefs.lang)}
			<span class="mono">{deployment?.status || '—'}</span>. {tx(
				'CLI-Befehle bleiben in der Projektdokumentation verfügbar; der DAILY-Schedule wird hier nicht verändert.',
				prefs.lang
			)}
		</p>
	</section>
	<section class="panel">
		<div class="panel-head">
			<div>
				<p class="section-kicker">{tx('DEPLOYMENT', prefs.lang)}</p>
				<h2>{tx('Konfiguration', prefs.lang)}</h2>
			</div>
			<Clock3 size={18} color="#79d6d6" />
		</div>
		{#if deployment}<div class="deployment-info">
				<div><span>Name</span><strong>{deployment.name}</strong></div>
				<div><span>{tx('Status', prefs.lang)}</span><strong>{deployment.status}</strong></div>
				<div>
					<span>{tx('Schedule', prefs.lang)}</span><strong
						>{deployment.schedules?.[0]?.schedule?.cron || '—'}</strong
					>
				</div>
				<div>
					<span>{tx('Zeitzone', prefs.lang)}</span><strong
						>{deployment.schedules?.[0]?.schedule?.timezone || '—'}</strong
					>
				</div>
				<div>
					<span>{tx('Aktiv', prefs.lang)}</span><strong
						>{deployment.paused || !deployment.schedules.some((s) => s.active)
							? tx('Nein', prefs.lang)
							: tx('Ja', prefs.lang)}</strong
					>
				</div>
			</div>{:else}<div class="empty">{tx('Kein Deployment gefunden.', prefs.lang)}</div>{/if}
	</section>
</div>
<section class="panel runs-panel">
	<div class="panel-head">
		<div>
			<p class="section-kicker">{tx('Letzte Läufe', prefs.lang).toUpperCase()}</p>
			<h2>{tx('Letzte Flow-Runs', prefs.lang)}</h2>
			<p>{tx('Alle 15 Sekunden aktualisiert.', prefs.lang)}</p>
		</div>
		<span class="section-kicker"
			>{data.prefect.runs.length} {tx('Läufe', prefs.lang).toUpperCase()}</span
		>
	</div>
	<div class="table-wrap">
		<table class="data-table">
			<thead
				><tr
					><th>{tx('FLOW RUN', prefs.lang)}</th><th>{tx('MODUS', prefs.lang)}</th><th
						>{tx('STATUS', prefs.lang)}</th
					><th>{tx('START', prefs.lang)}</th><th>{tx('DAUER', prefs.lang)}</th><th></th></tr
				></thead
			><tbody
				>{#each data.prefect.runs as run (run.id)}<tr
						><td
							><strong>{run.name}</strong><small class="mono">{run.id.slice(0, 8)}</small
							>{#if run.state_type === 'FAILED' && run.state?.message}<small class="run-error"
									>{run.state.message}</small
								>{/if}</td
						><td class="mono">{String(run.parameters?.mode || '—').toUpperCase()}</td><td
							><span
								class:failed={run.state_type === 'FAILED'}
								class:neutral={run.state_type !== 'FAILED' && run.state_type !== 'COMPLETED'}
								class="status">{stateLabel(run.state_name, prefs.lang)}</span
							></td
						><td class="mono muted">{dateTime(run.start_time, prefs.lang)}</td><td class="mono"
							>{run.total_run_time != null ? `${Math.round(run.total_run_time)}s` : '—'}</td
						><td
							><a
								href={data.prefect.uiUrl + '/runs/flow-run/' + run.id}
								target="_blank"
								rel="noreferrer"
								aria-label={tx('Run in Prefect öffnen', prefs.lang)}><ArrowUpRight size={15} /></a
							></td
						></tr
					>{:else}<tr
						><td colspan="6" class="empty">{tx('Keine Prefect-Runs verfügbar.', prefs.lang)}</td
						></tr
					>{/each}</tbody
			>
		</table>
	</div>
</section>
<section class="panel catalog-panel">
	<div class="panel-head">
		<div>
			<p class="section-kicker">{tx('KANDIDATENKATALOG', prefs.lang)}</p>
			<h2>{tx('MediaMarkt-Kandidaten', prefs.lang)}</h2>
			<p>
				{tx(
					'Kandidatenstatus aus mediamarkt.json; importierte Produkte stehen separat in PostgreSQL.',
					prefs.lang
				)}
			</p>
		</div>
		<span class="section-kicker">{data.catalog.total} URLS</span>
	</div>
	{#if !data.catalog.available}<div class="alert">
			{tx('Katalog nicht lesbar:', prefs.lang)}
			{data.catalog.error}
		</div>{:else}<div class="catalog-counts">
			{#each Object.entries(data.catalog.categories) as [category, count] (category)}<span
					><strong>{count}</strong> {category.toUpperCase()}</span
				>{/each}
			{#each Object.entries(data.catalog.counts) as [status, count] (status)}<span
					><strong>{count}</strong> {catalogStatusLabel(status, prefs.lang)}</span
				>{/each}
		</div>
		<div class="table-wrap">
			<table class="data-table">
				<thead
					><tr
						><th>{tx('SKU / TITEL', prefs.lang)}</th><th>{tx('KATEGORIE', prefs.lang)}</th><th
							>{tx('STATUS', prefs.lang)}</th
						><th>{tx('GRUND', prefs.lang)}</th><th>{tx('LETZTER VERSUCH', prefs.lang)}</th></tr
					></thead
				><tbody
					>{#each data.catalog.items as item (item.retailer_sku)}<tr
							><td
								><strong>{item.title || tx('Titel fehlt', prefs.lang)}</strong><small class="mono"
									>{item.retailer_sku}</small
								></td
							><td
								><span class="category {item.category || ''}"
									>{(item.category || '—').toUpperCase()}</span
								></td
							><td
								><span class="status neutral"
									>{catalogStatusLabel(item.status || 'unknown', prefs.lang)}</span
								></td
							><td class="muted"
								>{item.reason ? catalogReasonLabel(item.reason, prefs.lang) : '—'}</td
							><td class="mono muted">{dateTime(item.last_attempt_at, prefs.lang)}</td></tr
						>{/each}</tbody
				>
			</table>
		</div>{/if}
</section>

<style>
	.pipeline-summary {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 14px;
		margin-bottom: 15px;
	}
	.summary-card {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 18px;
		min-width: 0;
	}
	.summary-card > div {
		min-width: 0;
	}
	.summary-icon {
		color: var(--green);
		background: var(--surface-strong);
		padding: 9px;
		border-radius: 8px;
		display: grid;
		place-items: center;
	}
	.summary-icon.purple {
		background: var(--surface-strong);
		color: var(--violet);
	}
	.summary-icon.cyan {
		background: var(--surface-strong);
		color: var(--cyan);
	}
	.summary-card small {
		display: block;
		color: var(--muted);
		font:
			9px 'DM Mono',
			monospace;
		margin-bottom: 6px;
	}
	.summary-card strong {
		font:
			600 13px 'Space Grotesk',
			sans-serif;
	}
	.summary-card .status,
	.summary-card .hint {
		margin-left: auto;
	}
	.operations-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.7fr) minmax(260px, 1fr);
		gap: 15px;
		margin-bottom: 15px;
	}
	.actions-list {
		padding: 0 23px;
	}
	.action-row {
		display: flex;
		align-items: center;
		gap: 12px;
		border-top: 1px solid var(--surface-strong);
		padding: 13px 0;
	}
	.action-row > div {
		flex: 1;
	}
	.action-row strong {
		font-size: 11px;
	}
	.action-row small {
		display: block;
		color: var(--muted);
		font-size: 10px;
		margin-top: 3px;
	}
	.action-symbol {
		background: var(--surface-strong);
		color: var(--green);
		border-radius: 7px;
		padding: 8px;
		display: grid;
		place-items: center;
	}
	.action-symbol.muted-icon {
		background: var(--surface-strong);
		color: var(--muted);
	}
	.unavailable-label {
		font:
			9px 'DM Mono',
			monospace;
		color: var(--muted);
		border: 1px solid var(--line-strong);
		border-radius: 5px;
		padding: 6px;
	}
	.verify-result {
		margin: 6px 23px 0;
		padding: 12px;
		background: var(--surface-strong);
		border: 1px solid #3c5a49;
		border-radius: 7px;
		font-size: 11px;
	}
	.verify-result.failure {
		background: var(--surface-strong);
		border-color: #65444b;
	}
	.verify-result strong,
	.verify-result span {
		display: block;
	}
	.verify-result span {
		color: var(--muted-high);
		margin-top: 4px;
	}
	.control-note {
		color: var(--muted);
		font-size: 10px;
		line-height: 1.6;
		padding: 0 23px 10px;
	}
	.deployment-info {
		padding: 0 23px 23px;
	}
	.deployment-info > div {
		display: flex;
		justify-content: space-between;
		gap: 15px;
		border-top: 1px solid var(--surface-strong);
		padding: 13px 0;
		font-size: 11px;
	}
	.deployment-info span {
		color: var(--muted);
	}
	.deployment-info strong {
		text-align: right;
	}
	.runs-panel {
		margin-bottom: 15px;
	}
	.catalog-counts {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		padding: 0 23px 20px;
	}
	.catalog-counts span {
		border: 1px solid var(--line-strong);
		background: var(--surface);
		padding: 7px 10px;
		border-radius: 6px;
		color: var(--muted-high);
		font-size: 10px;
	}
	.catalog-counts strong {
		color: var(--text);
	}
	.catalog-panel .table-wrap {
		max-height: 490px;
		overflow: auto;
	}
	@media (max-width: 1100px) {
		.pipeline-summary {
			grid-template-columns: 1fr 1fr;
		}
		.pipeline-summary > .panel:last-child {
			grid-column: span 2;
		}
		.operations-grid {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 650px) {
		.pipeline-summary {
			grid-template-columns: 1fr;
		}
		.pipeline-summary > .panel:last-child {
			grid-column: auto;
		}
		.summary-card {
			padding: 14px;
		}
		.unavailable-label {
			font-size: 8px;
			white-space: nowrap;
		}
		.action-row {
			flex-wrap: wrap;
		}
		.action-row > div {
			min-width: 150px;
		}
		.actions-list {
			padding: 0 16px;
		}
		.control-note {
			padding: 0 16px 10px;
		}
	}
</style>
