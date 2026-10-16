import { json } from '@sveltejs/kit';
import { verify } from '$lib/server/products';

export async function GET() {
	try {
		return json(await verify());
	} catch {
		return json({ ok: false, error: 'Datenbank momentan nicht erreichbar' }, { status: 503 });
	}
}
