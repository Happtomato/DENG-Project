> Historischer ursprünglicher Projektplan (v0.1). Für den aktuellen Midterm-Stand gilt [README.md](../../README.md). Links und Bestandszahlen unten können veraltet sein.

# Swiss Consumer Electronics Price Dataset

**Data Engineering Project – HS26**

## Project Overview

This project builds an end-to-end batch data pipeline for collecting,
processing and analysing historical prices of consumer electronics in the
Swiss market.

The dataset focuses on three product categories:

- GPUs: NVIDIA RTX 30 series and newer, AMD RX 6000 series and newer
- RAM: DDR4 and DDR5
- SSDs: NVMe SSDs using PCIe 3.0–5.0

The initial target is approximately 100 products per category.

The project focuses on Swiss retailers such as Digitec, Interdiscount,
Brack and MediaMarkt.

Excluded products:

- Used or refurbished products
- Enterprise/server hardware
- DDR3 and older RAM
- HDDs
- External SSDs


## Problem & Use Case

Historical pricing information for Swiss computer components is fragmented
across different retailers and is difficult to analyse consistently over time.

The goal of this project is to create a curated historical price dataset that
makes Swiss component pricing more transparent.

The dataset should enable questions such as:

- How have product prices evolved over time?
- How do prices differ between retailers?
- How do different product generations compare?
- How do product releases and market events affect prices?
- What is the price per unit, such as CHF/GB, for comparable products?


### Intended Users

The primary users are consumers and researchers interested in historical
Swiss consumer-electronics pricing and market behaviour.


### Expected Data Product

The main data product will be a curated analytical dataset stored in BigQuery,
containing standardized products, specifications, retailers and historical
price observations.

The curated data will support:

- Historical price analysis
- Retailer comparisons
- Price-per-unit metrics
- Volatility analysis
- Release and market-event analysis
- Dashboards and visualisations

Price forecasting may be implemented as an additional analytical extension
if sufficient historical data is available.


## Data Sources

The pipeline will collect product and pricing information from Swiss
electronics retailers.

Initial target retailers:

- Digitec
- Interdiscount
- Brack
- MediaMarkt

Data will be obtained from available retailer APIs and/or website data.

Expected source formats include:

- JSON
- XML
- HTML

Product information will be matched across sources primarily using EAN and
MPN identifiers.

The planned ingestion frequency is one batch per day.


### Data Characteristics

The main entities are:

- Products
- Brands
- Retailers
- Product specifications
- Price history

Each price observation will be associated with a canonical product and
retailer.

Relevant source-data risks include:

- Missing or inconsistent EAN/MPN identifiers
- Duplicate product listings
- Missing specifications
- Temporary product unavailability
- Unexpected price jumps
- Changes to retailer websites or source formats
- Incomplete historical data


## Ingestion Strategy

The project uses batch ingestion.


### Initial Full Load

The initial load establishes the available products, specifications and
available price history.


### Incremental Daily Load

After the initial load, the pipeline will run daily and append new price
observations while preserving listings from multiple retailers.

Retailer-specific ingestion logic will be implemented as modular Python
components so individual sources can be changed without redesigning the
entire pipeline.

The pipeline will include validation, logging and failure handling.

The planned workflow orchestration layer will coordinate dependencies and
support retries and reruns/backfills where appropriate.


## Data Quality

Automated data-quality checks will be applied before data is published to the
analytical layer.

Planned checks include:

- Price > 0
- Valid product and retailer identifiers
- Duplicate detection
- EAN/MPN validation
- Price-jump detection
- Availability checks
- Missing specification detection


## Architecture v0.1

The planned high-level pipeline is:

    Retailer APIs / Websites
              |
              v
      Python Batch Ingestion
              |
              v
    Validation & Product Matching
              |
       +------+------+
       |             |
       v             v
    PostgreSQL    Google Cloud Storage
    (local)          (data lake)
                         |
                         v
                   Transformations
                         |
                         v
                      BigQuery
                         |
                         v
                Analytics / Dashboard
                         |
                         v
                Forecasting (optional)


### Supporting Components

- PostgreSQL for local development and testing
- Docker / Docker Compose for reproducible local environments
- Workflow orchestration for scheduling, dependencies, retries and backfills
- Google Cloud Storage for cloud data-lake storage
- BigQuery for curated analytical data
- Terraform for reproducible Google Cloud infrastructure
- GitHub for source control and project documentation

This represents Architecture v0.1 and may evolve as implementation experience
reveals new requirements or constraints.


## Risks & Challenges

### Data Availability

Historical data may not be available for every product and retailer.

**Mitigation:** Start with available data and clearly document coverage and
gaps.


### Website Changes

Retailer websites and source structures may change.

**Mitigation:** Use modular retailer connectors and monitoring.


### Product Matching

The same product may appear under different names at different retailers.

**Mitigation:** Prefer EAN/MPN identifiers and review unmatched or ambiguous
records.


### Scope Creep

Supporting too many product categories and retailers could make the project
unmanageable.

**Mitigation:** Maintain strict category and retailer boundaries.


### Pipeline Reliability

Individual sources or processing steps may fail.

**Mitigation:** Implement tests, logging, validation, retries and reproducible
deployments.


## Responsibilities

Both team members are expected to understand the complete architecture and
end-to-end pipeline. Primary ownership is divided as follows:


### Dominik

- Develop the Digitec web scraper
- Set up and configure the local PostgreSQL database


### Diego

- Contact and evaluate additional retailers as potential data sources
- Develop the Python ingestion pipeline for Digitec


### Shared

- Architecture decisions
- Data-quality strategy
- Documentation
- Testing and code review
- Integration of individual components
- Understanding of the complete end-to-end pipeline


## Initial Project Plan / Backlog

### Phase 1 – Foundation

- [ ] Develop the initial Digitec web scraper
- [ ] Implement the Digitec Python ingestion pipeline
- [ ] Set up the PostgreSQL database
- [ ] Define the PostgreSQL schema
- [ ] Load the initial dataset
- [ ] Create a reproducible local environment


### Phase 2 – Expand & Validate

- [ ] Contact and evaluate additional retailers
- [ ] Add additional retailer connectors
- [ ] Implement EAN/MPN product matching
- [ ] Implement data-quality checks
- [ ] Add validation and logging
- [ ] Introduce workflow orchestration
- [ ] Support retries and reruns/backfills


### Phase 3 – Cloud Pipeline

- [ ] Provision Google Cloud resources with Terraform
- [ ] Configure Google Cloud Storage
- [ ] Implement cloud ingestion
- [ ] Build the transformation pipeline
- [ ] Create curated BigQuery tables


### Phase 4 – Analytics

- [ ] Define analytical KPIs
- [ ] Implement retailer comparisons
- [ ] Implement historical price analysis
- [ ] Implement price-per-unit metrics
- [ ] Build dashboard / visualisations
- [ ] Evaluate the feasibility of forecasting models


## Current local implementation

The midterm implementation uses the existing MediaMarkt collector, one Prefect
flow and PostgreSQL. It supports manual discovery, initial collection from the
catalogue, daily collection from stored product URLs and offline replay. The
local [PC Price Lab frontend](../../frontend/README.md) reads this database
without running a second pipeline. For exact pipeline commands see
[docs/RUN_COMMANDS.md](../RUN_COMMANDS.md). The earlier architecture and
project plan above record the original proposal; cloud components remain
future work.

Start the local stack, including the dashboard on [localhost:3000](http://localhost:3000),
with `docker compose up -d --build` after setting the root `.env`.

### TODO: controlled catalogue expansion

Once MediaMarkt's terms and permitted request volume are clarified, reuse the
existing discovery with bounded category pagination, save candidates in the
catalogue, apply the existing hardware/manufacturer scope, and import
validated candidates through INITIAL. The long-term goal is 200–300 distinct,
fully validated products; do not add arbitrary products to reach a number.
DAILY should then continue to use only stored PostgreSQL product URLs. No
large crawl or access-control bypass is part of the frontend phase.
