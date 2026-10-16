import type { PageServerLoad } from './$types';
import { prefectStatus } from '$lib/server/prefect';
import { catalogSummary } from '$lib/server/catalog';

export const load: PageServerLoad = async () => {
	const [prefect, catalog] = await Promise.all([prefectStatus(), catalogSummary()]);
	return { prefect, catalog };
};
