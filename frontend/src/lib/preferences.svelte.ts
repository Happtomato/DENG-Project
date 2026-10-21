import { getContext, setContext } from 'svelte';

export type Language = 'de' | 'en';
export type ThemeMode = 'light' | 'dark' | 'system';
const key = Symbol('preferences');

export class Preferences {
	lang = $state<Language>('de');
	theme = $state<ThemeMode>('system');
	resolved = $state<'light' | 'dark'>('dark');
	private media: MediaQueryList | null = null;

	init() {
		this.media = window.matchMedia('(prefers-color-scheme: dark)');
		this.lang = localStorage.getItem('pc-price-lab-language') === 'en' ? 'en' : 'de';
		const saved = localStorage.getItem('pc-price-lab-theme');
		this.theme = saved === 'light' || saved === 'dark' ? saved : 'system';
		this.apply();
		this.media.addEventListener('change', this.apply);
		return () => this.media?.removeEventListener('change', this.apply);
	}

	private apply = () => {
		this.resolved = this.theme === 'system' ? (this.media?.matches ? 'dark' : 'light') : this.theme;
		document.documentElement.dataset.theme = this.resolved;
		document.documentElement.lang = this.lang === 'de' ? 'de-CH' : 'en-CH';
	};

	setTheme(theme: ThemeMode) {
		this.theme = theme;
		localStorage.setItem('pc-price-lab-theme', theme);
		this.apply();
	}

	setLanguage(lang: Language) {
		this.lang = lang;
		localStorage.setItem('pc-price-lab-language', lang);
		this.apply();
	}
}

export function providePreferences() {
	const preferences = new Preferences();
	setContext(key, preferences);
	return preferences;
}

export function usePreferences() {
	return getContext<Preferences>(key);
}
