import { json } from '@sveltejs/kit';
import { getProduct } from '$lib/server/products';

export async function GET({ params }) {
	if (!/^\d+$/.test(params.id)) return json({ error: 'Ungültige Produkt-ID' }, { status: 400 });
	try {
		const product = await getProduct(params.id);
		return product ? json(product) : json({ error: 'Produkt nicht gefunden' }, { status: 404 });
	} catch {
		return json({ error: 'Datenbank momentan nicht erreichbar' }, { status: 503 });
	}
}
