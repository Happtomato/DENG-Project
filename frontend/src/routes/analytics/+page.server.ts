import type { PageServerLoad } from './$types';
import { capacityAnalytics, historicalAnalytics, overview } from '$lib/server/products';

export const load: PageServerLoad = async () => {
	const [db, capacity, historical] = await Promise.allSettled([
		overview(),
		capacityAnalytics(),
		historicalAnalytics()
	]);
	return {
		db: db.status === 'fulfilled' ? db.value : null,
		capacity: capacity.status === 'fulfilled' ? capacity.value : [],
		historical:
			historical.status === 'fulfilled' ? historical.value : { examples: [], frequencies: [] },
		error: db.status === 'rejected' ? String(db.reason) : null,
		capacityError: capacity.status === 'rejected' ? String(capacity.reason) : null,
		historicalError: historical.status === 'rejected' ? String(historical.reason) : null
	};
};
