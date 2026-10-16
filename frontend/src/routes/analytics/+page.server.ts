import type { PageServerLoad } from './$types';
import { overview } from '$lib/server/products';

export const load: PageServerLoad = async () => {
	try {
		return { db: await overview(), error: null };
	} catch (error) {
		return { db: null, error: String(error) };
	}
};
