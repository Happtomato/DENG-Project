import { env } from '$env/dynamic/private';
import pg from 'pg';

let pool: pg.Pool | undefined;

function getPool() {
	if (!pool) {
		const connectionString = env.DATABASE_URL;
		if (!connectionString && !(env.POSTGRES_DB && env.POSTGRES_USER && env.POSTGRES_PASSWORD)) {
			throw new Error(
				'Datenbank nicht konfiguriert. DATABASE_URL oder POSTGRES_DB/USER/PASSWORD in frontend/.env.local setzen.'
			);
		}
		pool = new pg.Pool({
			...(connectionString
				? { connectionString }
				: {
						host: env.POSTGRES_HOST || '127.0.0.1',
						port: Number(env.POSTGRES_PORT || 5432),
						database: env.POSTGRES_DB,
						user: env.POSTGRES_USER,
						password: env.POSTGRES_PASSWORD
					}),
			max: 5,
			connectionTimeoutMillis: 2500,
			idleTimeoutMillis: 10000,
			application_name: 'hardware-pulse'
		});
	}
	return pool;
}

export async function query<T extends pg.QueryResultRow>(
	sql: string,
	params: unknown[] = []
): Promise<T[]> {
	const result = await getPool().query<T>(sql, params);
	return result.rows;
}

export function serialize<T>(value: T): T {
	return JSON.parse(JSON.stringify(value));
}
