import { query, serialize } from './db';

export type ProductRow = {
	product_id: string;
	product_name: string;
	brand: string;
	category: string;
	model: string | null;
	mpn: string | null;
	ean: string | null;
	price: number | null;
	retailer: string | null;
	retailer_product_id: string | null;
	collected_at: string | null;
	observation_count: number;
	digitec_history_count: number;
	price_point_count: number;
	spec: string | null;
};

export type Filters = {
	search: string;
	category: string;
	brand: string;
	retailer: string;
	digitec_history: boolean;
	min: number | null;
	max: number | null;
	sort: string;
	page: number;
	pageSize: number;
	view: 'cards' | 'list';
};

export function parseFilters(url: URL): Filters {
	const p = url.searchParams;
	const number = (key: string) => {
		const raw = p.get(key);
		const n = raw === null || raw.trim() === '' ? NaN : Number(raw);
		return Number.isFinite(n) && n >= 0 ? n : null;
	};
	return {
		search: (p.get('search') || '').trim().slice(0, 100),
		category: ['gpu', 'ram', 'ssd'].includes((p.get('category') || '').toLowerCase())
			? p.get('category')!.toLowerCase()
			: '',
		brand: (p.get('brand') || '').trim().slice(0, 100),
		retailer: (p.get('retailer') || '').trim().slice(0, 100),
		digitec_history: p.get('history') === 'digitec',
		min: number('min'),
		max: number('max'),
		sort: ['recent', 'price_asc', 'price_desc', 'points_desc', 'points_asc', 'name'].includes(
			p.get('sort') || ''
		)
			? p.get('sort')!
			: 'recent',
		page: Math.min(10000, Math.max(1, Math.floor(Number(p.get('page')) || 1))),
		pageSize: [18, 36, 72].includes(Number(p.get('pageSize'))) ? Number(p.get('pageSize')) : 18,
		view: p.get('view') === 'list' ? 'list' : 'cards'
	};
}

const BASE = `FROM product p
 JOIN brand b ON b.brand_id=p.brand_id JOIN category c ON c.category_id=p.category_id
 LEFT JOIN LATERAL (
   SELECT rp.retailer_product_id, r.name AS retailer, ph.price_chf::float8 AS price, ph.collected_at
   FROM retailer_product rp JOIN retailer r ON r.retailer_id=rp.retailer_id
   LEFT JOIN LATERAL (SELECT price_chf,collected_at FROM price_history WHERE retailer_product_id=rp.retailer_product_id ORDER BY collected_at DESC,price_id DESC LIMIT 1) ph ON true
   WHERE rp.product_id=p.product_id ORDER BY ph.collected_at DESC NULLS LAST,rp.retailer_product_id LIMIT 1
 ) latest ON true
 LEFT JOIN gpu_details gpu ON gpu.product_id=p.product_id
 LEFT JOIN ram_details ram ON ram.product_id=p.product_id
 LEFT JOIN ssd_details ssd ON ssd.product_id=p.product_id`;

const SELECT = `SELECT p.product_id::text,p.product_name,b.name AS brand,lower(c.name) AS category,p.model,p.mpn,p.ean,
 latest.price,latest.retailer,latest.retailer_product_id::text,latest.collected_at,
 (SELECT count(*)::int FROM price_history ph JOIN retailer_product rp ON rp.retailer_product_id=ph.retailer_product_id WHERE rp.product_id=p.product_id) AS observation_count,
 (SELECT count(*)::int FROM retailer_price_change rpc JOIN retailer_product rp USING(retailer_product_id) JOIN retailer r USING(retailer_id) WHERE rp.product_id=p.product_id AND r.name='Digitec') AS digitec_history_count,
	(SELECT count(*)::int FROM price_history ph JOIN retailer_product rp ON rp.retailer_product_id=ph.retailer_product_id WHERE rp.product_id=p.product_id)
	+ (SELECT count(*)::int FROM retailer_price_change rpc JOIN retailer_product rp USING(retailer_product_id) WHERE rp.product_id=p.product_id) AS price_point_count,
 CASE lower(c.name) WHEN 'gpu' THEN concat_ws(' · ',gpu.gpu_model, CASE WHEN gpu.vram_gb IS NOT NULL THEN gpu.vram_gb||' GB VRAM' END)
 WHEN 'ram' THEN concat_ws(' · ',ram.total_capacity_gb||' GB',ram.ram_type,ram.speed_mts||' MT/s')
 WHEN 'ssd' THEN concat_ws(' · ',ssd.capacity_gb||' GB',ssd.pcie_generation,ssd.form_factor) END AS spec `;

const sorts: Record<string, string> = {
	recent: 'latest.collected_at DESC NULLS LAST,p.product_id DESC',
	price_asc: 'latest.price ASC NULLS LAST,p.product_id DESC',
	price_desc: 'latest.price DESC NULLS LAST,p.product_id DESC',
	points_desc: 'price_point_count DESC,p.product_id DESC',
	points_asc: 'price_point_count ASC,p.product_id DESC',
	name: 'p.product_name ASC,p.product_id ASC'
};

export async function listProducts(filters: Filters) {
	const listBase = BASE.replace(
		'WHERE rp.product_id=p.product_id ORDER BY',
		"WHERE rp.product_id=p.product_id AND ($7::text='' OR r.name=$7) ORDER BY"
	);
	const where = `WHERE ($1::text='' OR p.product_name ILIKE '%'||$1||'%' OR b.name ILIKE '%'||$1||'%' OR coalesce(p.model,'') ILIKE '%'||$1||'%')
	 AND ($2::text='' OR lower(c.name)=$2) AND ($3::text='' OR b.name=$3)
	 AND ($4::text='' OR EXISTS (SELECT 1 FROM retailer_product rp JOIN retailer r USING(retailer_id) WHERE rp.product_id=p.product_id AND r.name=$4))
	 AND ($5::float8 IS NULL OR latest.price >= $5) AND ($6::float8 IS NULL OR latest.price <= $6)
	 AND (NOT $8::boolean OR EXISTS (SELECT 1 FROM retailer_price_change rpc JOIN retailer_product rp USING(retailer_product_id) JOIN retailer r USING(retailer_id) WHERE rp.product_id=p.product_id AND r.name='Digitec'))`;
	const params = [
		filters.search,
		filters.category,
		filters.brand,
		filters.retailer,
		filters.min,
		filters.max
	];
	const [rows, count] = await Promise.all([
		query<ProductRow>(
			`${SELECT} ${listBase} ${where} ORDER BY ${sorts[filters.sort]} LIMIT $9 OFFSET $10`,
			[
				...params,
				filters.retailer,
				filters.digitec_history,
				filters.pageSize,
				(filters.page - 1) * filters.pageSize
			]
		),
		query<{ total: number }>(`SELECT count(*)::int AS total ${listBase} ${where}`, [
			...params,
			filters.retailer,
			filters.digitec_history
		])
	]);
	return serialize({
		rows,
		total: count[0]?.total ?? 0,
		page: filters.page,
		pageSize: filters.pageSize
	});
}

export async function filterOptions() {
	const [brands, retailers] = await Promise.all([
		query<{ name: string }>(
			'SELECT name FROM brand WHERE EXISTS (SELECT 1 FROM product WHERE product.brand_id=brand.brand_id) ORDER BY name'
		),
		query<{ name: string }>(
			'SELECT name FROM retailer WHERE EXISTS (SELECT 1 FROM retailer_product WHERE retailer_product.retailer_id=retailer.retailer_id) ORDER BY name'
		)
	]);
	return { brands: brands.map((x) => x.name), retailers: retailers.map((x) => x.name) };
}

export async function getProduct(id: string) {
	const products = await query<ProductRow>(`${SELECT} ${BASE} WHERE p.product_id=$1`, [id]);
	if (!products.length) return null;
	const [offers, history, chartHistory, details] = await Promise.all([
		query<{
			retailer_product_id: string;
			retailer: string;
			retailer_sku: string;
			product_url: string;
			price: number | null;
			collected_at: string | null;
			availability: string | null;
			is_active: boolean;
			tracking_reason: string | null;
		}>(
			`SELECT rp.retailer_product_id::text,r.name AS retailer,rp.retailer_sku,rp.product_url,
		latest.price_chf::float8 AS price,latest.collected_at,latest.availability,
		rp.is_active,rp.tracking_reason
		FROM retailer_product rp JOIN retailer r USING(retailer_id)
		LEFT JOIN LATERAL (SELECT price_chf,collected_at,availability FROM price_history WHERE retailer_product_id=rp.retailer_product_id ORDER BY collected_at DESC,price_id DESC LIMIT 1) latest ON true
		WHERE rp.product_id=$1 ORDER BY r.name,rp.retailer_product_id`,
			[id]
		),
		query<{
			retailer_product_id: string;
			retailer: string;
			price: number;
			collected_at: string;
			availability: string | null;
		}>(
			`SELECT ph.retailer_product_id::text,r.name AS retailer,ph.price_chf::float8 AS price,ph.collected_at,ph.availability
		FROM price_history ph JOIN retailer_product rp USING(retailer_product_id) JOIN retailer r USING(retailer_id)
		WHERE rp.product_id=$1 ORDER BY ph.collected_at,ph.price_id`,
			[id]
		),
		query<{
			retailer_product_id: string;
			retailer: string;
			valid_from: string;
			price: number | null;
			point_type: 'price' | 'no_price';
		}>(
			`SELECT rpc.retailer_product_id::text,r.name AS retailer,rpc.valid_from,
			rpc.price_chf::float8 AS price,rpc.point_type
			FROM retailer_price_change rpc
			JOIN retailer_product rp USING(retailer_product_id)
			JOIN retailer r USING(retailer_id)
			WHERE rp.product_id=$1 ORDER BY rpc.valid_from,rpc.retailer_product_id`,
			[id]
		),
		query<Record<string, unknown>>(
			`SELECT to_jsonb(gpu)-'gpu_details_id'-'product_id' AS gpu,to_jsonb(ram)-'ram_details_id'-'product_id' AS ram,
		to_jsonb(ssd)-'ssd_details_id'-'product_id' AS ssd FROM product p
		LEFT JOIN gpu_details gpu USING(product_id) LEFT JOIN ram_details ram USING(product_id) LEFT JOIN ssd_details ssd USING(product_id)
		WHERE p.product_id=$1`,
			[id]
		)
	]);
	const prices = history.map((x) => x.price);
	return serialize({
		product: products[0],
		offers,
		history,
		chartHistory,
		details: details[0] ?? {},
		min: prices.length ? Math.min(...prices) : null,
		max: prices.length ? Math.max(...prices) : null
	});
}

export async function overview() {
	const [stats, categories, recent, quality] = await Promise.all([
		query<{
			products: number;
			offers: number;
			observations: number;
			last_observation: string | null;
		}>(`SELECT (SELECT count(*)::int FROM product) AS products,(SELECT count(*)::int FROM retailer_product) AS offers,
		(SELECT count(*)::int FROM price_history) AS observations,(SELECT max(collected_at) FROM price_history) AS last_observation`),
		query<{ category: string; count: number }>(
			`SELECT lower(c.name) AS category,count(*)::int AS count FROM product p JOIN category c USING(category_id) GROUP BY 1 ORDER BY 1`
		),
		query<{
			product_id: string;
			product_name: string;
			brand: string;
			category: string;
			retailer: string;
			price: number;
			collected_at: string;
		}>(`SELECT p.product_id::text,p.product_name,b.name AS brand,lower(c.name) AS category,r.name AS retailer,ph.price_chf::float8 AS price,ph.collected_at
		FROM price_history ph JOIN retailer_product rp USING(retailer_product_id) JOIN retailer r USING(retailer_id)
		JOIN product p USING(product_id) JOIN brand b USING(brand_id) JOIN category c USING(category_id)
		ORDER BY ph.collected_at DESC,ph.price_id DESC LIMIT 7`),
		query<{
			invalid_prices: number;
			duplicates: number;
		}>(`SELECT (SELECT count(*)::int FROM price_history WHERE price_chf<=0 OR currency<>'CHF') AS invalid_prices,
		(SELECT count(*)::int FROM (SELECT retailer_product_id,collected_at FROM price_history GROUP BY 1,2 HAVING count(*)>1) d) AS duplicates`)
	]);
	return serialize({ stats: stats[0], categories, recent, quality: quality[0] });
}

export type CapacityPoint = {
	category: string;
	capacity_gb: number;
	products: number;
	avg_price_per_gb: number;
	avg_price_chf: number;
};

export async function capacityAnalytics() {
	const rows = await query<CapacityPoint>(`
		WITH latest_offer AS (
			SELECT rp.product_id, latest.price_chf
			FROM retailer_product rp
			JOIN LATERAL (
				SELECT ph.price_chf FROM price_history ph
				WHERE ph.retailer_product_id = rp.retailer_product_id
				ORDER BY ph.collected_at DESC, ph.price_id DESC LIMIT 1
			) latest ON true
			WHERE latest.price_chf > 0
		), product_price AS (
			SELECT product_id, min(price_chf) AS price_chf
			FROM latest_offer GROUP BY product_id
		), measured AS (
			SELECT lower(c.name) AS category,
				CASE lower(c.name)
					WHEN 'gpu' THEN gpu.vram_gb
					WHEN 'ram' THEN ram.total_capacity_gb
					WHEN 'ssd' THEN ssd.capacity_gb
				END AS capacity_gb,
				pp.price_chf
			FROM product p
			JOIN category c USING (category_id)
			JOIN product_price pp USING (product_id)
			LEFT JOIN gpu_details gpu USING (product_id)
			LEFT JOIN ram_details ram USING (product_id)
			LEFT JOIN ssd_details ssd USING (product_id)
		)
		SELECT category, capacity_gb, count(*)::int AS products,
			round(avg(price_chf / capacity_gb), 3)::float8 AS avg_price_per_gb,
			round(avg(price_chf), 2)::float8 AS avg_price_chf
		FROM measured WHERE capacity_gb > 0 AND category IN ('gpu', 'ram', 'ssd')
		GROUP BY category, capacity_gb ORDER BY category, capacity_gb
	`);
	return serialize(rows);
}

export async function historicalAnalytics() {
	const examples = await query<{
		product_id: string;
		product_name: string;
		category: string;
		brand: string;
		retailer_product_id: string;
		first_point: string;
		point_count: number;
	}>(`WITH candidates AS (
		SELECT p.product_id::text,p.product_name,lower(c.name) AS category,b.name AS brand,
			rp.retailer_product_id::text,min(rpc.valid_from) AS first_point,
			count(*)::int AS point_count,
			row_number() OVER (PARTITION BY lower(c.name) ORDER BY min(rpc.valid_from),count(*) DESC,p.product_id) AS rank
		FROM retailer_price_change rpc JOIN retailer_product rp USING(retailer_product_id)
		JOIN retailer r USING(retailer_id) JOIN product p USING(product_id)
		JOIN category c USING(category_id) JOIN brand b USING(brand_id)
		WHERE r.name='Digitec' AND lower(c.name) IN ('gpu','ram','ssd')
		GROUP BY p.product_id,c.name,b.name,rp.retailer_product_id
	) SELECT product_id,product_name,category,brand,retailer_product_id,first_point,point_count
	FROM candidates WHERE rank=1 ORDER BY CASE category WHEN 'ram' THEN 1 WHEN 'ssd' THEN 2 ELSE 3 END`);
	const ids = examples.map((row) => row.retailer_product_id);
	const [points, frequencies] = await Promise.all([
		ids.length
			? query<{
					retailer_product_id: string;
					valid_from: string;
					price: number | null;
					point_type: string;
				}>(
					`SELECT retailer_product_id::text,valid_from,price_chf::float8 AS price,point_type
			FROM retailer_price_change WHERE retailer_product_id::text=ANY($1) ORDER BY valid_from`,
					[ids]
				)
			: [],
		query<{
			product_id: string;
			product_name: string;
			category: string;
			brand: string;
			first_point: string;
			last_point: string;
			min_price: number;
			max_price: number;
			price_changes: number;
			changes_per_year: number | null;
		}>(
			`WITH priced AS (
				SELECT retailer_product_id,valid_from,price_chf,
				lag(price_chf) OVER (PARTITION BY retailer_product_id ORDER BY valid_from) AS previous_price
				FROM retailer_price_change WHERE point_type='price'
			), history AS (
				SELECT p.product_id::text,p.product_name,lower(c.name) AS category,b.name AS brand,
				min(priced.valid_from) AS first_point,max(priced.valid_from) AS last_point,
				min(priced.price_chf)::float8 AS min_price,max(priced.price_chf)::float8 AS max_price,
				count(*) FILTER (WHERE priced.previous_price IS NOT NULL
					AND priced.price_chf<>priced.previous_price)::int AS price_changes
				FROM priced JOIN retailer_product rp USING(retailer_product_id)
				JOIN retailer r USING(retailer_id) JOIN product p USING(product_id)
				JOIN category c USING(category_id) JOIN brand b USING(brand_id)
				WHERE r.name='Digitec' GROUP BY p.product_id,c.name,b.name
			) SELECT *, CASE WHEN last_point-first_point >= interval '90 days'
			THEN round(price_changes * 365.2425 /
				nullif(extract(epoch FROM (last_point-first_point))/86400,0),1)::float8
			ELSE NULL END AS changes_per_year
			FROM history ORDER BY changes_per_year DESC NULLS LAST,product_id`
		)
	]);
	return serialize({
		examples: examples.map((row) => ({
			...row,
			points: points.filter((point) => point.retailer_product_id === row.retailer_product_id)
		})),
		frequencies
	});
}

export async function featuredProduct() {
	const rows = await query<{ product_id: string }>(
		`SELECT rp.product_id::text FROM price_history ph
		JOIN retailer_product rp USING(retailer_product_id)
		GROUP BY rp.product_id
		ORDER BY count(*) DESC, max(ph.collected_at) DESC LIMIT 1`
	);
	return rows[0] ? getProduct(rows[0].product_id) : null;
}

export async function verify() {
	const data = await overview();
	return {
		...data.stats,
		...data.quality,
		ok:
			data.stats.products > 0 &&
			data.stats.offers > 0 &&
			data.stats.observations > 0 &&
			data.quality.invalid_prices === 0 &&
			data.quality.duplicates === 0
	};
}
