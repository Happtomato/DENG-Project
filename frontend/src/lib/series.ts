export type Observation = {
	retailer_product_id: string;
	retailer: string;
	price: number;
	collected_at: string;
	availability?: string | null;
};
export type Range = '7D' | '30D' | '90D' | 'ALL';
export type PriceChange = {
	retailer_product_id: string;
	retailer: string;
	valid_from: string;
	price: number | null;
	point_type: 'price' | 'no_price';
};

export function rangeStart(range: Range, now = Date.now()): number | null {
	if (range === 'ALL') return null;
	const days = range === '7D' ? 7 : range === '30D' ? 30 : 90;
	return now - days * 86400000;
}

export function filterHistory(
	history: Observation[],
	range: Range,
	now = Date.now()
): Observation[] {
	if (range === 'ALL') return history;
	if (!history.length) return [];
	const latest = Math.max(now, ...history.map((row) => Date.parse(row.collected_at)));
	return history.filter((row) => Date.parse(row.collected_at) >= rangeStart(range, latest)!);
}

// Include the last change before the window: its price remains effective at the left edge.
// A null change marks an unavailable interval and must never become a price.
export function filterPriceChanges(history: PriceChange[], range: Range, now = Date.now()) {
	const start = rangeStart(range, now);
	if (start === null) return history;
	const byOffer = new Map<string, PriceChange[]>();
	for (const row of history) {
		const rows = byOffer.get(row.retailer_product_id) ?? [];
		rows.push(row);
		byOffer.set(row.retailer_product_id, rows);
	}
	return [...byOffer.values()].flatMap((rows) => {
		const sorted = [...rows].sort((a, b) => Date.parse(a.valid_from) - Date.parse(b.valid_from));
		const before = sorted.filter((row) => Date.parse(row.valid_from) < start).at(-1);
		const visible = sorted.filter((row) => Date.parse(row.valid_from) >= start);
		return before
			? [{ ...before, valid_from: new Date(start).toISOString() }, ...visible]
			: visible;
	});
}

export function historicalPriceSeries(history: PriceChange[], observations: Observation[] = []) {
	const byOffer = new Map<string, PriceChange[]>();
	for (const row of history) {
		const rows = byOffer.get(row.retailer_product_id) ?? [];
		rows.push(row);
		byOffer.set(row.retailer_product_id, rows);
	}
	return [...byOffer].map(([id, rows]) => {
		const sorted = rows.sort((a, b) => Date.parse(a.valid_from) - Date.parse(b.valid_from));
		const segments: { x: number; y: number }[][] = [];
		const gaps: { x: number; y: number }[][] = [];
		let segment: { x: number; y: number }[] = [];
		let unavailableAt: number | null = null;
		let previousPrice: number | null = null;
		for (const row of sorted) {
			const x = Date.parse(row.valid_from);
			if (row.price === null) {
				if (previousPrice !== null) segment.push({ x, y: previousPrice });
				if (segment.length) segments.push(segment);
				segment = [];
				unavailableAt = x;
			} else {
				if (unavailableAt !== null && previousPrice !== null) {
					gaps.push([
						{ x: unavailableAt, y: previousPrice },
						{ x, y: row.price }
					]);
				}
				segment.push({ x, y: row.price });
				unavailableAt = null;
				previousPrice = row.price;
			}
		}
		if (segment.length) segments.push(segment);
		const lastChange = sorted.at(-1);
		const latestObservation = observations
			.filter(
				(row) =>
					row.retailer_product_id === id &&
					Date.parse(row.collected_at) > Date.parse(lastChange?.valid_from ?? '')
			)
			.sort((a, b) => Date.parse(b.collected_at) - Date.parse(a.collected_at))[0];
		// A matching real observation confirms the price at its own timestamp.
		// Extend the change-history line to that point without creating daily rows.
		if (
			lastChange?.price !== null &&
			lastChange?.price !== undefined &&
			latestObservation?.price === lastChange.price &&
			segments.length
		) {
			segments.at(-1)!.push({ x: Date.parse(latestObservation.collected_at), y: lastChange.price });
		}
		return { id, retailer: sorted[0]?.retailer ?? '', segments, gaps };
	});
}

export function priceSeries(history: Observation[]) {
	const offers = [
		...new Map(history.map((row) => [row.retailer_product_id, row.retailer])).entries()
	];
	return offers.map(([id, retailer]) => {
		const data = history
			.filter((row) => row.retailer_product_id === id)
			.map((row) => ({
				x: Date.parse(row.collected_at),
				y: row.price,
				availability: row.availability
			}))
			.sort((a, b) => a.x - b.x);
		return { id, retailer, data, showLine: data.length > 1 };
	});
}

export function unavailableIntervals(history: Observation[]) {
	const byOffer = new Map<string, Observation[]>();
	for (const row of history) {
		const rows = byOffer.get(row.retailer_product_id) ?? [];
		rows.push(row);
		byOffer.set(row.retailer_product_id, rows);
	}
	return [...byOffer].flatMap(([id, rows]) => {
		const sorted = rows.sort((a, b) => Date.parse(a.collected_at) - Date.parse(b.collected_at));
		const intervals: { id: string; retailer: string; start: number; end: number }[] = [];
		let start: number | null = null;
		let lastUnavailable: number | null = null;
		for (const row of sorted) {
			const time = Date.parse(row.collected_at);
			if (row.availability === 'OutOfStock') {
				start ??= time;
				lastUnavailable = time;
			} else if (start !== null) {
				intervals.push({ id, retailer: row.retailer, start, end: time });
				start = lastUnavailable = null;
			}
		}
		if (start !== null)
			intervals.push({ id, retailer: sorted[0].retailer, start, end: lastUnavailable ?? start });
		return intervals;
	});
}
