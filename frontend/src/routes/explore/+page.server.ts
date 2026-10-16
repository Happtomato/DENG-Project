import type { PageServerLoad } from './$types';
import { filterOptions, listProducts, parseFilters } from '$lib/server/products';

export const load: PageServerLoad = async ({ url }) => {
	const filters = parseFilters(url);
	try {
		const [listing, options] = await Promise.all([listProducts(filters), filterOptions()]);
		return { filters, listing, options, error: null };
	} catch (error) {
		return {
			filters,
			listing: { rows: [], total: 0, page: 1, pageSize: 18 },
			options: { brands: [], retailers: [] },
			error: String(error)
		};
	}
};
