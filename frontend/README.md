# PC Price Lab — frontend

The SvelteKit frontend reads products, offers, price observations, and Prefect status on the server. It does not scrape or write prices. See the [root README](../README.md) for Compose startup and the [runbook](../docs/RUN_COMMANDS.md) for pipeline commands.

The UI has a product-focused home page, search and filters, product details, analytics, and Pipeline Lab. Light/dark/system themes and German/English UI preferences are stored in the browser. Source product names and technical identifiers are preserved. Charts use Chart.js in the browser.

The analytics page compares RAM capacity, SSD capacity, and GPU VRAM against average CHF per GB, with a switch to average product price. For each product, the calculation takes the latest price per offer and then the cheapest offer, so repeated daily observations do not count as separate products. Products without confirmed capacity or price are omitted. Each capacity group shows its sample size. These are descriptive figures for our small database, not market-wide estimates.

Three concrete RAM, SSD, and GPU examples also show **manually saved Digitec retailer price changes**. Shaded periods mark the 2020–2022 chip shortage and stronger AI demand from 2023, with sources shown in the UI. This is temporal context, not proof that a particular event caused an individual shop price. Our GPU sample has no chip-shortage-period data. Dashed sections and shaded areas on product charts mark evidenced unavailability only. The price-change comparison counts changes between two recorded CHF prices and annualizes them over the first-to-last recorded price interval (365.2425 days per year). Equal prices, the first point, and points without a price do not count; histories shorter than 90 days receive no annual rate. Historical retailer changes remain separate from our own daily observations.

## Local development

Requires Node.js 24, npm, running PostgreSQL, and optionally Prefect. `frontend/.env.local` is ignored by Git.

```sh
cp .env frontend/.env.local
printf '\nPOSTGRES_HOST=127.0.0.1\n' >> frontend/.env.local
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open [127.0.0.1:5173](http://127.0.0.1:5173). `DATABASE_URL` can replace individual PostgreSQL variables. `PREFECT_API_URL` is optional and defaults to `http://127.0.0.1:4200/api`. If the frontend runs outside the repository, set `CATALOG_PATH` to the absolute `data/catalog/mediamarkt.json` path. Database credentials are not sent to the browser.

## API and checks

Read-only endpoints: `GET /api/products`, `GET /api/products/:id`, and `GET /api/verify`. Search and filters use parameterized SQL. Pipeline Lab displays Prefect runs and catalog status; DISCOVER/INITIAL/DAILY/REPLAY actions remain disabled there until a safe manual runner exists.

```sh
npm run check
npm run lint
npm run build
DASHBOARD_TEST_URL=http://127.0.0.1:3000 npm run test:integration
```

The integration test requires the running Compose frontend, populated PostgreSQL, and Prefect on localhost:4200. Many products have only a few actual observations; a single observation is drawn as one point. Free-text product/source fields and nonstandard error messages are not all translated. No historical prices are invented.
