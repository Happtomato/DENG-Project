import type { Language } from './preferences.svelte';

export const money = (value: number | string | null | undefined, lang: Language = 'de') =>
	value == null
		? '—'
		: new Intl.NumberFormat(lang === 'de' ? 'de-CH' : 'en-CH', {
				style: 'currency',
				currency: 'CHF'
			}).format(Number(value));

export const dateTime = (value: string | null | undefined, lang: Language = 'de') =>
	value
		? new Intl.DateTimeFormat(lang === 'de' ? 'de-CH' : 'en-CH', {
				dateStyle: 'medium',
				timeStyle: 'short',
				timeZone: 'Europe/Zurich'
			}).format(new Date(value))
		: '—';

export const shortDate = (value: string | null | undefined, lang: Language = 'de') =>
	value
		? new Intl.DateTimeFormat(lang === 'de' ? 'de-CH' : 'en-CH', {
				day: '2-digit',
				month: 'short',
				timeZone: 'Europe/Zurich'
			}).format(new Date(value))
		: '—';

export const categoryLabel = (value: string, lang: Language = 'de') =>
	(lang === 'de'
		? { gpu: 'Grafikkarten', ram: 'Arbeitsspeicher', ssd: 'SSDs' }
		: { gpu: 'Graphics cards', ram: 'Memory', ssd: 'SSDs' })[
		value.toLowerCase() as 'gpu' | 'ram' | 'ssd'
	] ?? value;
