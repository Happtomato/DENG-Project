import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getProduct } from '$lib/server/products';

export const load: PageServerLoad = async ({ params }) => {
	if (!/^\d+$/.test(params.id)) error(404, 'Produkt nicht gefunden');
	try {
		const detail = await getProduct(params.id);
		if (!detail) error(404, 'Produkt nicht gefunden');
		return { detail };
	} catch (cause) {
		if (cause && typeof cause === 'object' && 'status' in cause) throw cause;
		error(503, 'Datenbank momentan nicht erreichbar');
	}
};
