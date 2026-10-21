import test from 'node:test';
import assert from 'node:assert/strict';
import {
	filterHistory,
	filterPriceChanges,
	historicalPriceSeries,
	priceSeries,
	unavailableIntervals
} from '../src/lib/series.ts';
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

test('historical price gaps stay unavailable, and the 90-day window keeps the effective price', () => {
	const make = (valid_from, price) => ({
		retailer_product_id: '2',
		retailer: 'Digitec',
		valid_from,
		price,
		point_type: price === null ? 'no_price' : 'price'
	});
	const rows = [
		make('2026-06-01T00:00:00Z', 190),
		make('2026-07-05T00:00:00Z', null),
		make('2026-07-18T00:00:00Z', 170),
		make('2026-10-09T00:00:00Z', 269)
	];
	const series = historicalPriceSeries(rows)[0];
	assert.equal(series.segments.length, 2);
	assert.equal(series.gaps.length, 1);
	assert.deepEqual(
		series.gaps[0].map((point) => point.x),
		[Date.parse('2026-07-05T00:00:00Z'), Date.parse('2026-07-18T00:00:00Z')]
	);
	assert.equal(rows[1].price, null);
	const confirmed = historicalPriceSeries(rows, [
		{
			retailer_product_id: '2',
			retailer: 'Digitec',
			price: 269,
			collected_at: '2026-10-20T08:28:53Z'
		}
	])[0];
	assert.equal(confirmed.segments.at(-1).at(-1).x, Date.parse('2026-10-20T08:28:53Z'));
	assert.equal(confirmed.segments.at(-1).at(-1).y, 269);
	const ninetyDays = filterPriceChanges(rows, '90D', Date.parse('2026-10-20T00:00:00Z'));
	assert.equal(ninetyDays[0].price, 170);
	assert.equal(ninetyDays[0].valid_from, '2026-07-22T00:00:00.000Z');
	assert.equal(ninetyDays.length, 2);
	assert.equal(filterPriceChanges(rows, 'ALL').length, 4);
});

test('MediaMarkt out-of-stock intervals use only recorded availability', () => {
	const make = (day, availability) => ({
		retailer_product_id: '1',
		retailer: 'MediaMarkt',
		price: 259.95,
		collected_at: `2026-10-${day}T12:00:00Z`,
		availability
	});
	const rows = [
		make('15', 'InStock'),
		make('16', 'OutOfStock'),
		make('17', 'OutOfStock'),
		make('19', 'InStock')
	];
	assert.deepEqual(
		unavailableIntervals(rows).map(({ start, end }) => [start, end]),
		[[Date.parse('2026-10-16T12:00:00Z'), Date.parse('2026-10-19T12:00:00Z')]]
	);
	assert.equal(priceSeries(rows)[0].data[1].availability, 'OutOfStock');
	assert.deepEqual(
		unavailableIntervals([make('16', 'OutOfStock')]).map(({ start, end }) => [start, end]),
		[[Date.parse('2026-10-16T12:00:00Z'), Date.parse('2026-10-16T12:00:00Z')]]
	);
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

test('Digitec price changes are returned separately from daily observations', async () => {
	const listing = await get('/api/products?search=SN850P');
	const product = listing.body.rows.find((row) => row.ean?.replace(/^0+/, '') === '619659198053');
	assert.ok(product);
	const detail = await get('/api/products/' + product.product_id);
	assert.equal(detail.response.status, 200);
	assert.equal(detail.body.chartHistory.length, 292);
	assert.equal(detail.body.chartHistory.filter((point) => point.price === null).length, 1);
	assert.ok(detail.body.chartHistory.every((point) => point.retailer === 'Digitec'));
	assert.ok(detail.body.history.length < detail.body.chartHistory.length);
	const page = await fetch(origin + '/explore/' + product.product_id).then((response) =>
		response.text()
	);
	assert.match(page, /historische Händlerangaben/);
	assert.match(page, /Gestrichelte Stellen/);
});

test('manually mapped Digitec histories are discoverable without false daily prices', async () => {
	const selected = await get('/api/products?history=digitec');
	assert.equal(selected.response.status, 200);
	assert.equal(selected.body.total, 8);
	assert.ok(selected.body.rows.every((row) => row.digitec_history_count > 0));
	const corsair = selected.body.rows.find((row) => row.mpn === 'CMK64GX5M2B6000Z30');
	assert.ok(corsair);
	const detail = await get('/api/products/' + corsair.product_id);
	assert.equal(detail.body.chartHistory.length, 558);
	assert.equal(detail.body.offers.find((offer) => offer.retailer === 'Digitec').price, null);
	assert.ok(detail.body.history.every((observation) => observation.retailer === 'MediaMarkt'));
	const homepage = await fetch(origin).then((response) => response.text());
	assert.match(homepage, /historische Händlerangaben/);
});

test('read-only verification reports valid PostgreSQL observations', async () => {
	const result = await get('/api/verify');
	assert.equal(result.response.status, 200);
	assert.equal(result.body.ok, true);
	assert.equal(result.body.invalid_prices, 0);
	assert.equal(result.body.duplicates, 0);
	assert.ok(result.body.observations > 0);
});

test('capacity charts use PostgreSQL prices and hardware capacities', async () => {
	const response = await fetch(origin + '/analytics');
	assert.equal(response.status, 200);
	const html = await response.text();
	assert.match(html, /Was kostet ein GB\?/);
	assert.match(html, /Grafikkarten · VRAM/);
	assert.match(html, /CHF pro GB/);
	assert.doesNotMatch(html, /Kapazitätsanalyse momentan nicht verfügbar/);
	assert.doesNotMatch(html, /Noch keine Produkte mit Preis und bestätigter Kapazität/);
});

test('historical analytics show sourced examples and annualized price-change rates', async () => {
	const response = await fetch(origin + '/analytics');
	assert.equal(response.status, 200);
	const html = await response.text();
	assert.match(html, /Drei Produkte im Zeitverlauf/);
	assert.match(html, /Chipmangel 2020–2022/);
	assert.match(html, /KI-Nachfrage ab März 2023/);
	assert.match(html, /RAM historische Preiswechsel/);
	assert.match(html, /SSD historische Preiswechsel/);
	assert.match(html, /GPU historische Preiswechsel/);
	assert.match(html, /Wie oft wechseln die Preise\?/);
	assert.match(html, /Tatsächliche Preisänderungen pro Jahr/);
	assert.match(html, /\d+(?:[,.]\d+)? \/ Jahr/);
	assert.match(html, /Gleiche Preise und Punkte ohne verfügbaren Preis zählen nicht als Änderung/);
	const listing = await get('/api/products?history=digitec');
	const gskill = listing.body.rows.find((row) => row.brand === 'G.SKILL');
	assert.ok(gskill);
	const detail = await get('/api/products/' + gskill.product_id);
	const priced = detail.body.chartHistory.filter((point) => point.price !== null);
	const actualChanges = priced
		.slice(1)
		.filter((point, index) => point.price !== priced[index].price).length;
	const elapsedDays =
		(Date.parse(priced.at(-1).valid_from) - Date.parse(priced[0].valid_from)) / 86_400_000;
	const annualRate = ((actualChanges * 365.2425) / elapsedDays).toFixed(1);
	assert.ok(html.includes(`${annualRate} / Jahr`));
	assert.match(html, /kein Beleg für die Ursache/);
	assert.equal((html.match(/class="frequency-row\b/g) || []).length, 8);
	assert.doesNotMatch(html, /Historische Analyse momentan nicht verfügbar/);
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
