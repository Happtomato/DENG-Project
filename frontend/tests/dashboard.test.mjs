import test from 'node:test';
import assert from 'node:assert/strict';
import { filterHistory, priceSeries } from '../src/lib/series.ts';
import { dateTime, money } from '../src/lib/format.ts';
import {
	availabilityLabel,
	catalogReasonLabel,
	catalogStatusLabel,
	stateLabel,
	tx
} from '../src/lib/i18n.ts';
import { project } from '../src/lib/identity.ts';

const origin = process.env.DASHBOARD_TEST_URL || 'http://127.0.0.1:5173';
const get = async (path) => {
	const response = await fetch(origin + path);
	return { response, body: await response.json() };
};

test('single and empty histories never become invented lines', () => {
	assert.deepEqual(priceSeries([]), []);
	const one = {
		retailer_product_id: '1',
		retailer: 'MediaMarkt',
		price: 489.6,
		collected_at: '2026-10-16T09:00:00Z'
	};
	assert.equal(priceSeries([one])[0].showLine, false);
	assert.equal(priceSeries([one])[0].data.length, 1);
	const next = { ...one, collected_at: '2026-10-17T09:00:00Z' };
	assert.equal(priceSeries([one, next])[0].showLine, true);
	assert.equal(priceSeries([one, next])[0].data.length, 2);
	assert.equal(
		priceSeries([one, { ...one, retailer_product_id: '2', retailer: 'Digitec' }]).length,
		2
	);
	assert.deepEqual(filterHistory([], '7D'), []);
	assert.equal(filterHistory([one], '7D', Date.parse('2026-11-01T00:00:00Z')).length, 0);
});

test('CHF formatting uses real values', () => {
	assert.match(money(489.6), /CHF.*489[.,]60|489[.,]60.*CHF/);
	assert.equal(money(null), '—');
});

test('language changes UI labels without changing product identifiers or CHF values', () => {
	assert.equal(project.name, 'PC Price Lab');
	assert.equal(tx('Preisverlauf', 'en'), 'Price history');
	assert.equal(tx('Preisverlauf', 'de'), 'Preisverlauf');
	assert.equal(tx('GPU-Modell', 'en'), 'GPU model');
	assert.equal(stateLabel('Completed', 'de'), 'Abgeschlossen');
	assert.equal(catalogStatusLabel('candidate', 'en'), 'Candidate');
	assert.equal(catalogStatusLabel('excluded', 'de'), 'Ausgeschlossen');
	assert.equal(catalogReasonLabel('brand_filter', 'en'), 'Brand outside scope');
	assert.equal(availabilityLabel('InStock', 'de'), 'Auf Lager');
	assert.match(money(489.6, 'en'), /CHF.*489[.,]60|489[.,]60.*CHF/);
	assert.match(dateTime('2026-10-16T09:00:00Z', 'en'), /Oct/);
});

test('home page uses real featured history and a product-first layout', async () => {
	const response = await fetch(origin);
	assert.equal(response.status, 200);
	const html = await response.text();
	assert.match(html, /PC Price Lab/);
	assert.match(html, /Preisverlauf im Fokus/);
	assert.match(html, /name="search"/);
	assert.match(html, /\/explore\?category=gpu/);
	assert.doesNotMatch(html, /Hardware Pulse/);
});

test('product API paginates and filters real database rows', async () => {
	const all = await get('/api/products');
	assert.equal(all.response.status, 200);
	assert.ok(all.body.total > 0);
	assert.ok(all.body.rows.length <= 18);
	const gpu = await get('/api/products?category=gpu&retailer=MediaMarkt&sort=price_asc');
	assert.equal(gpu.response.status, 200);
	assert.ok(gpu.body.rows.every((row) => row.category === 'gpu' && row.retailer === 'MediaMarkt'));
	assert.deepEqual(
		gpu.body.rows.map((row) => row.price),
		[...gpu.body.rows.map((row) => row.price)].sort((a, b) => a - b)
	);
	const injected = await get('/api/products?search=%27%20OR%201%3D1%20--');
	assert.equal(injected.response.status, 200);
	assert.equal(injected.body.total, 0);
});

test('product detail preserves offer-specific history and handles missing IDs', async () => {
	const listing = await get('/api/products');
	const id = listing.body.rows[0].product_id;
	const detail = await get('/api/products/' + id);
	assert.equal(detail.response.status, 200);
	assert.equal(detail.body.product.product_id, id);
	assert.ok(detail.body.offers.length >= 1);
	assert.ok(
		detail.body.history.every((row) =>
			detail.body.offers.some((offer) => offer.retailer_product_id === row.retailer_product_id)
		)
	);
	assert.equal((await get('/api/products/999999999')).response.status, 404);
	assert.equal((await get('/api/products/invalid')).response.status, 400);
});

test('read-only verification reports valid PostgreSQL observations', async () => {
	const result = await get('/api/verify');
	assert.equal(result.response.status, 200);
	assert.equal(result.body.ok, true);
	assert.equal(result.body.invalid_prices, 0);
	assert.equal(result.body.duplicates, 0);
	assert.ok(result.body.observations > 0);
});

test('pipeline page reports Prefect state and no live start controls', async () => {
	const response = await fetch(origin + '/pipelines');
	assert.equal(response.status, 200);
	const html = await response.text();
	assert.match(html, /mediamarkt-daily/);
	const deployments = await fetch('http://127.0.0.1:4200/api/deployments/filter', {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ limit: 20 })
	}).then((result) => result.json());
	const daily = deployments.find((item) => item.name === 'mediamarkt-daily');
	assert.ok(daily);
	const expected =
		daily.paused || !daily.schedules.some((schedule) => schedule.active) ? 'Pausiert' : 'Aktiv';
	assert.ok(html.includes(expected));
	assert.match(html, /Nicht verfügbar/);
});
