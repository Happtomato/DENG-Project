import type { PageServerLoad } from './$types';
import { featuredProduct, overview } from '$lib/server/products';
import { catalogSummary } from '$lib/server/catalog';
import { prefectStatus } from '$lib/server/prefect';

export const load: PageServerLoad = async () => {
	const [db, catalog, prefect, featured] = await Promise.allSettled([
		overview(),
		catalogSummary(),
		prefectStatus(),
		featuredProduct()
	]);
	return {
		db: db.status === 'fulfilled' ? db.value : null,
		dbError: db.status === 'rejected' ? String(db.reason) : null,
		catalog: catalog.status === 'fulfilled' ? catalog.value : null,
		prefect: prefect.status === 'fulfilled' ? prefect.value : null,
		featured: featured.status === 'fulfilled' ? featured.value : null
	};
};
