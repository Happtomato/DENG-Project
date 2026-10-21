import { env } from '$env/dynamic/private';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

type Candidate = {
	retailer_sku: string;
	title: string | null;
	category: string | null;
	status: string | null;
	reason: string | null;
	last_attempt_at: string | null;
};

export async function catalogSummary() {
	try {
		const path = env.CATALOG_PATH || resolve(process.cwd(), '../data/catalog/mediamarkt.json');
		const data = JSON.parse(await readFile(path, 'utf8')) as {
			products: Record<string, Partial<Candidate>>;
		};
		const items: Candidate[] = Object.values(data.products || {}).map((item) => ({
			retailer_sku: String(item.retailer_sku || ''),
			title: item.title || null,
			category: item.category || null,
			status: item.status || null,
			reason: item.reason || null,
			last_attempt_at: item.last_attempt_at || null
		}));
		const counts: Record<string, number> = {};
		const categories: Record<string, number> = {};
		for (const item of items) {
			counts[item.status || 'unknown'] = (counts[item.status || 'unknown'] || 0) + 1;
			categories[item.category || 'unknown'] = (categories[item.category || 'unknown'] || 0) + 1;
		}
		return {
			available: true,
			total: items.length,
			counts,
			categories,
			items: items.slice(0, 100),
			error: null
		};
	} catch (error) {
		return {
			available: false,
			total: 0,
			counts: {} as Record<string, number>,
			categories: {} as Record<string, number>,
			items: [] as Candidate[],
			error: error instanceof Error ? error.message : 'Katalog nicht erreichbar'
		};
	}
}
