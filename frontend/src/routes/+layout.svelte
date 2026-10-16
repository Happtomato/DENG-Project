<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import {
		ArrowUpRight,
		BarChart3,
		Cpu,
		FlaskConical,
		Menu,
		Moon,
		Search,
		Sun,
		X
	} from '@lucide/svelte';
	import { project } from '$lib/identity';
	import { tx } from '$lib/i18n';
	import { providePreferences, type ThemeMode } from '$lib/preferences.svelte';
	import './layout.css';
	let { children } = $props();
	const prefs = providePreferences();
	let menuOpen = $state(false);
	let path = $derived(page.url.pathname);
	const nav = [
		{ href: '/', label: 'Übersicht', icon: FlaskConical },
		{ href: '/explore', label: 'Entdecken', icon: Search },
		{ href: '/analytics', label: 'Analysen', icon: BarChart3 },
		{ href: '/pipelines', label: 'Pipeline Lab', icon: Cpu }
	];
	onMount(() => prefs.init());
</script>

<svelte:head>
	<meta name="description" content="{project.name} — {project.tagline}" />
	<meta name="theme-color" content={prefs.resolved === 'light' ? '#f7f5ef' : '#17191d'} />
</svelte:head>

<div class="shell">
	<aside class:open={menuOpen} class="sidebar">
		<a
			href="/"
			class="brand"
			onclick={() => (menuOpen = false)}
			aria-label="{project.name} Startseite"
		>
			<span class="brand-mark"><FlaskConical size={20} strokeWidth={2.1} /></span>
			<span class="brand-copy">{project.name}<small>{project.credit}</small></span>
		</a>
		<div class="side-label">{tx('Entdecken', prefs.lang).toUpperCase()} <span>01 / 04</span></div>
		<nav aria-label={tx('Übersicht', prefs.lang)}>
			{#each nav as item (item.href)}
				<a
					href={item.href}
					class:active={item.href === '/' ? path === '/' : path.startsWith(item.href)}
					onclick={() => (menuOpen = false)}
				>
					<item.icon size={18} strokeWidth={1.8} /><span>{tx(item.label, prefs.lang)}</span>
				</a>
			{/each}
		</nav>
		<div class="side-bottom">
			<div class="lab-note">
				<span class="lab-note-icon"><Cpu size={16} /></span>
				<div><strong>GPU · RAM · SSD</strong><small>{project.tagline}</small></div>
			</div>
			<a class="sidebar-link" href="/pipelines"
				>{tx('Zur Pipeline', prefs.lang)} <ArrowUpRight size={14} /></a
			>
		</div>
	</aside>
	{#if menuOpen}<button
			class="scrim"
			aria-label={tx('Menü schliessen', prefs.lang)}
			onclick={() => (menuOpen = false)}
		></button>{/if}
	<div class="main-area">
		<header class="topbar">
			<div class="topbar-left">
				<button
					class="mobile-menu"
					aria-label={tx('Menü öffnen', prefs.lang)}
					onclick={() => (menuOpen = !menuOpen)}
					>{#if menuOpen}<X size={20} />{:else}<Menu size={20} />{/if}</button
				>
				<span class="breadcrumb-root">{project.name}</span><span class="breadcrumb-slash">/</span>
				<span class="breadcrumb-current"
					>{tx(
						nav.find((n) => (n.href === '/' ? path === '/' : path.startsWith(n.href)))?.label ||
							'Entdecken',
						prefs.lang
					)}</span
				>
			</div>
			<div class="topbar-right">
				<div class="preference-group" aria-label={tx('Darstellung', prefs.lang)}>
					{#each ['light', 'dark', 'system'] as mode (mode)}<button
							aria-label={tx(
								mode === 'light' ? 'Hell' : mode === 'dark' ? 'Dunkel' : 'System',
								prefs.lang
							)}
							title={tx(
								mode === 'light' ? 'Hell' : mode === 'dark' ? 'Dunkel' : 'System',
								prefs.lang
							)}
							class:chosen={prefs.theme === mode}
							onclick={() => prefs.setTheme(mode as ThemeMode)}
							>{#if mode === 'light'}<Sun size={14} />{:else if mode === 'dark'}<Moon
									size={14}
								/>{:else}<span class="system-glyph">◐</span>{/if}<span class="choice-word"
								>{tx(
									mode === 'light' ? 'Hell' : mode === 'dark' ? 'Dunkel' : 'System',
									prefs.lang
								)}</span
							></button
						>{/each}
				</div>
				<div class="preference-group language-switch" aria-label={tx('Sprache', prefs.lang)}>
					<button
						class:chosen={prefs.lang === 'de'}
						aria-label="Deutsch"
						onclick={() => prefs.setLanguage('de')}>DE</button
					>
					<button
						class:chosen={prefs.lang === 'en'}
						aria-label="English"
						onclick={() => prefs.setLanguage('en')}>EN</button
					>
				</div>
			</div>
		</header>
		<main id="content">{@render children()}</main>
		<footer class="footer">
			<span>{project.name} <span class="footer-muted">/</span> {project.credit}</span><span
				>{tx('Nur echte Messungen', prefs.lang)} <FlaskConical size={13} /></span
			>
		</footer>
	</div>
</div>
