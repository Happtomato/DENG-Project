import { json } from '@sveltejs/kit';
import { listProducts, parseFilters } from '$lib/server/products';

export async function GET({ url }) {
	try {
		return json(await listProducts(parseFilters(url)));
	} catch {
		return json({ error: 'Datenbank momentan nicht erreichbar' }, { status: 503 });
	}
}
